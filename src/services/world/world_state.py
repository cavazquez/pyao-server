"""Canal optativo de interfaz: revisiones, permisos y resultados autoritativos."""

import asyncio
import contextlib
import json
import logging
import time
from hashlib import sha256
from typing import TYPE_CHECKING, Any, cast

from redis.exceptions import RedisError

from src.economy.tax_service import tax_status
from src.network.capabilities import Capability
from src.network.msg_player_stats import (
    build_update_bank_gold_response,
    build_update_gold_response,
)
from src.network.state_channel import send_state
from src.services.classic_chat.maintenance import ClassicMaintenance
from src.services.expansion.service import EXPANSION_TOPICS, ExpansionService
from src.services.lottery.service import LotteryService
from src.services.world.actions import TOPICS, clan_action, party_action
from src.services.world.commands import command_snapshot
from src.services.world.pets import PetOrders
from src.services.world.serialization import GroupLock, bind_groups
from src.services.world.social import clan_snapshot, party_snapshot
from src.services.world.trade_metadata import trade_metadata
from src.services.world.weather import WeatherState
from src.utils.durability import require_durable
from src.utils.gold_atomic import (
    MAX_CLOCK_SKEW_SECONDS,
    RECEIPT_TTL_SECONDS,
    RETRY_WINDOW_SECONDS,
    validate_operation_id,
)

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)
PUBLISH_SECONDS = 1
VOLATILE_FIELDS = frozenset({"hp", "max_hp", "map", "server_time"})


def _digest(data: dict[str, Any], *, volatile: bool = True) -> str:
    def stable(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: stable(content)
                for key, content in value.items()
                if volatile or key not in VOLATILE_FIELDS
            }
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value

    return sha256(
        json.dumps(stable(data), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:32]


class WorldStateService:
    """Ninguna acción de UI concede autoridad distinta de la sesión autenticada."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte fachadas, reservas y mundo sin caches de propiedad del cliente."""
        self.deps = deps
        self.lock = GroupLock()
        bind_groups(deps.party_service, deps.clan_service, self.lock)
        self.pets = PetOrders(deps.npc_service)
        self.weather = WeatherState(deps)
        self.classic_maintenance = ClassicMaintenance(deps)
        self.expansion = ExpansionService(deps)
        self.lottery = LotteryService(deps)
        self.cache: dict[tuple[str, str], str] = {}
        self.legacy_revisions: dict[str, int] = {}
        self.legacy_receipts: dict[str, str] = {}
        self.task: asyncio.Task[None] | None = None
        deps.trade_service.metadata_publisher = self.publish_trade

    def start(self) -> None:
        """Inicia una sola tarea de publicaciones propiedad del servidor."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run(), name="world-state")

    async def close(self) -> None:
        """Drena la tarea antes de cerrar conexiones y Redis."""
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        self.cache.clear()
        self.legacy_revisions.clear()
        self.legacy_receipts.clear()
        self.expansion.queries.clear()

    async def _run(self) -> None:
        while True:
            try:
                await self.lottery.repo.advance()
                async with self.lock:
                    await self.classic_maintenance.tick()
            except RedisError, ValueError, RuntimeError, ConnectionError:
                logger.exception("Mantenimiento de comandos clásicos pendiente")
            epochs = set()
            for user in self.deps.map_manager.get_all_connected_user_ids():
                sender = self.deps.map_manager.get_player_message_sender(user)
                if sender is None or not sender.connection.is_authenticated:
                    continue
                epochs.add(sender.connection.state_epoch)
                if not sender.connection.capabilities.enabled & Capability.WORLD_STATE:
                    try:
                        await self.publish_legacy_tax(user, sender)
                    except RedisError, ValueError, RuntimeError, ConnectionError:
                        logger.exception("Resumen de devaluación pendiente user_id=%d", user)
                    continue
                for topic in sorted(sender.connection.state_topics & TOPICS):
                    try:
                        await self.publish(user, topic)
                    except RedisError, ValueError, RuntimeError, ConnectionError:
                        logger.exception(
                            "Estado de interfaz pendiente user_id=%d topic=%s", user, topic
                        )
                await asyncio.sleep(0)
            self.cache = {key: value for key, value in self.cache.items() if key[0] in epochs}
            self.legacy_revisions = {
                key: value for key, value in self.legacy_revisions.items() if key in epochs
            }
            self.legacy_receipts = {
                key: value for key, value in self.legacy_receipts.items() if key in epochs
            }
            await asyncio.sleep(PUBLISH_SECONDS)

    async def publish_legacy_tax(self, user: int, sender: MessageSender) -> None:
        """Actualiza ambos saldos y avisa una vez por recibo en el protocolo nativo."""
        data = cast("dict[str, Any]", await tax_status(self.deps.redis_client.redis, user))
        epoch = sender.connection.state_epoch
        revision = int(data["money_revision"])
        if self.legacy_revisions.get(epoch) != revision:
            await sender.connection.send(build_update_gold_response(int(data["wallet"])))
            await sender.connection.send(build_update_bank_gold_response(int(data["bank"])))
            self.legacy_revisions[epoch] = revision
        receipt = str(data["receipt"])
        if receipt and self.legacy_receipts.get(epoch) != receipt:
            if int(data["last_charge"]) > 0:
                await sender.send_console_msg(
                    f"Devaluación diaria: desaparecieron {data['last_charge']} oro "
                    "de tu bolsillo y banco, incluso desconectado."
                )
            self.legacy_receipts[epoch] = receipt

    async def initial(self, user: int, sender: MessageSender) -> None:
        """Publica información inicial sólo después de negociar la capacidad."""
        await self.expansion.factions.initialize_user(user)
        for key in [key for key in self.expansion.queries if key[0] == user]:
            del self.expansion.queries[key]
        if not sender.connection.capabilities.enabled & Capability.WORLD_STATE:
            return
        sender.connection.state_topics.update({"tax", "weather", "lottery"})
        for topic in ("tax", "weather", "commands", "lottery"):
            await self.publish(user, topic, force=True)

    async def snapshot(self, user: int, topic: str, page: int = 0) -> dict[str, Any]:
        """Consulta exclusivamente el estado autorizado del actor.

        Returns:
            Estado del tópico solicitado, sin callbacks ejecutables ni datos de autenticación.

        Raises:
            ValueError: Si el tópico no existe.
        """
        if topic == "tax":
            return await tax_status(self.deps.redis_client.redis, user)
        if topic == "lottery":
            return await self.lottery.snapshot(user)
        if topic in EXPANSION_TOPICS:
            return await self.expansion.snapshot(user, topic)
        if topic == "party":
            return await party_snapshot(self.deps, user)
        if topic == "clan":
            return await clan_snapshot(self.deps, user, page)
        if topic == "pets":
            return self.pets.snapshot(user)
        if topic == "weather":
            return await self.weather.snapshot(user)
        if topic == "commands":
            return await command_snapshot(self.deps, user)
        message = "Tópico de interfaz desconocido"
        raise ValueError(message)

    async def publish(
        self, user: int, topic: str, *, force: bool = False, identity: str = ""
    ) -> None:
        """Emite sólo cambios; cada frame conserva revisión y generación de conexión."""
        sender = self.deps.map_manager.get_player_message_sender(user)
        if sender is None or not sender.connection.capabilities.enabled & Capability.WORLD_STATE:
            return
        if (
            topic in EXPANSION_TOPICS
            and not sender.connection.capabilities.enabled & Capability.EXPANSION
        ):
            return
        async with self.lock:
            data = await self.snapshot(user, topic, sender.connection.state_pages.get(topic, 0))
            if topic == "clan":
                sender.connection.state_pages[topic] = int(data["page"])
            digest = _digest(data)
            key = sender.connection.state_epoch, topic
            if not force and self.cache.get(key) == digest:
                return
            await send_state(
                sender, topic, data, identity=identity, revision=_digest(data, volatile=False)
            )
            self.cache[key] = digest

    async def publish_trade(self, user: int) -> None:
        """Pagina el catálogo de la revisión actual sin ampliar TRADE_STATE legacy."""
        session = self.deps.trade_service.get_session(user)
        sender = self.deps.map_manager.get_player_message_sender(user)
        if (
            session is None
            or sender is None
            or not sender.connection.capabilities.enabled & Capability.WORLD_STATE
        ):
            return
        first = trade_metadata(self.deps, user, session.session_id, session.revision, 0)
        pages = [first] + [
            trade_metadata(self.deps, user, session.session_id, session.revision, page)
            for page in range(1, first["pages"])
        ]
        for data in pages:
            await send_state(sender, "trade", data, revision=str(data["trade_revision"]))

    async def execute(self, user: int, sender: MessageSender, request: dict[str, Any]) -> None:
        """Valida generación, revisión e identidad antes de despachar cualquier mutación."""
        action, params, identity = request["action"], request["params"], request["id"]
        topic = action.split(".")[0]
        if request["epoch"] != sender.connection.state_epoch and not (
            not request["epoch"] and action.endswith(".read")
        ):
            await send_state(
                sender,
                "result",
                {"applied": False, "message": "La conexión cambió; actualizá el estado."},
                identity=identity,
            )
            return
        async with self.lock:
            if action == "subscribe":
                topic = params["topic"]
                if topic not in TOPICS:
                    return
                if params["enabled"]:
                    sender.connection.state_topics.add(topic)
                    await self.publish(user, topic, force=True, identity=identity)
                else:
                    sender.connection.state_topics.discard(topic)
                return
            if action == "trade.read":
                data = trade_metadata(
                    self.deps, user, params["session"], params["revision"], params["page"]
                )
                await send_state(
                    sender, "trade", data, identity=identity, revision=str(params["revision"])
                )
                return
            if action.endswith(".read"):
                if topic in EXPANSION_TOPICS:
                    self.expansion.queries[user, topic] = params.copy()
                if topic == "clan":
                    sender.connection.state_pages[topic] = params["page"]
                await self.publish(user, topic, force=True, identity=identity)
                return
            data = await self.snapshot(user, topic, sender.connection.state_pages.get(topic, 0))
            result = await self._mutate(user, request, _digest(data, volatile=False))
            await send_state(sender, "result", {"action": action, **result}, identity=identity)
            await self.publish(user, topic, force=True)

    async def _mutate(self, user: int, request: dict[str, Any], revision: str) -> dict[str, Any]:
        action, params, identity = request["action"], request["params"], request["id"]
        # El recibo económico resuelve reintentos aun después de cerrar la ronda.
        # No usar la reserva efímera genérica ui-action para operaciones monetarias.
        if action == "lottery.bet":
            try:
                return await self.lottery.bet(user, request)
            except RedisError, RuntimeError:
                logger.exception("Confirmación de apuesta pendiente user_id=%d", user)
                return {
                    "applied": False,
                    "uncertain": True,
                    "message": (
                        "Apuesta pendiente: reintentá la misma operación "
                        "para recuperar el comprobante."
                    ),
                }
        redis = self.deps.redis_client.redis
        key = f"ui-action:{user}:{identity}"
        fingerprint = _digest(request)
        saved = await redis.get(key)
        if saved:
            receipt = json.loads(saved)
            if receipt.get("request") != fingerprint:
                return {"applied": False, "message": "Identificador reutilizado para otra acción."}
            return cast(
                "dict[str, Any]",
                receipt.get(
                    "result",
                    {
                        "applied": False,
                        "uncertain": True,
                        "message": "Operación pendiente; consultá el estado antes de iniciar otra.",
                    },
                ),
            )
        age = time.time() - validate_operation_id(identity)
        if (
            request["revision"] != revision
            or not -MAX_CLOCK_SKEW_SECONDS <= age <= RETRY_WINDOW_SECONDS
        ):
            return {
                "applied": False,
                "message": "El estado cambió o la operación venció; se actualizó la ventana.",
            }
        pending = json.dumps({"request": fingerprint})
        if not await redis.set(key, pending, nx=True, ex=RECEIPT_TTL_SECONDS):
            return {
                "applied": False,
                "uncertain": True,
                "message": "La operación ya está en curso.",
            }
        try:
            await require_durable(redis)
            if action.split(".")[0] in EXPANSION_TOPICS:
                result = await self.expansion.command(user, action, params, identity)
            elif action.startswith("party."):
                result = await party_action(self.deps, user, action.split(".")[1], params)
            elif action.startswith("clan."):
                result = await clan_action(self.deps, user, action.split(".")[1], params)
            elif action in {"pets.order", "pets.release"}:
                result = await self.pets.command(
                    user,
                    params["instance"],
                    "release" if action == "pets.release" else params["order"],
                    identity,
                )
            else:
                result = await self.weather.set(user, params, identity)
            await redis.set(
                key, json.dumps({"request": fingerprint, "result": result}), ex=RECEIPT_TTL_SECONDS
            )
            await require_durable(redis)
        except RedisError, RuntimeError:
            logger.exception("Resultado de acción de UI incierto user_id=%d", user)
            return {
                "applied": False,
                "uncertain": True,
                "message": "No se confirmó el resultado; consultá el estado.",
            }
        return result
