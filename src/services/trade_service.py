"""Intercambio versionado, ligado a conexiones y con arbitraje durable de cancelación."""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4

from src.config.config_manager import ConfigManager
from src.network.capabilities import Capability
from src.services.inventory_notifications import notify_inventory
from src.services.trade_settlement import (
    OfferedItem,
    ParticipantOffer,
    cancel_settlement,
    settle_trade,
)
from src.utils.gold_atomic import operation_id

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)
MAX_TRADE_RANGE = 2
MAX_SNAPSHOT_BYTES = 3072


class TradeAction(StrEnum):
    """Nombres de estados públicos; los códigos del protocolo se definen en TRADE_ACTIONS."""

    ACCEPT = "accept"
    ITEM = "item"
    GOLD = "gold"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    REJECT = "reject"


TRADE_ACTIONS = tuple(TradeAction)


class TradeState(StrEnum):
    """Posibles estados de una sesión de comercio."""

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTING = "committing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TradeOfferItem:
    """Item ofrecido en la sesión."""

    slot: int
    item_id: int
    quantity: int


@dataclass
class TradeOffer:
    """Oferta actual de un jugador."""

    items: dict[int, TradeOfferItem] = field(default_factory=dict)
    gold: int = 0


@dataclass
class TradeSession:
    """Representa una sesión de comercio entre dos jugadores."""

    initiator_id: int
    initiator_username: str
    target_id: int
    target_username: str
    state: TradeState
    created_at: float
    last_update: float
    initiator_confirmed: bool = False
    target_confirmed: bool = False
    initiator_offer: TradeOffer = field(default_factory=TradeOffer)
    target_offer: TradeOffer = field(default_factory=TradeOffer)
    # Guarda síncrona contra doble ejecución de _perform_trade. Se fija en
    # True exactamente una vez, antes de cualquier await, dentro de
    # confirm_trade. Al ser asyncio de un solo hilo, no hay race entre el
    # check y el set, ya que no hay punto de cesión entre ellos.
    trade_executing: bool = False
    settlement_uncertain: bool = False
    settlement_id: str | None = None
    session_id: str = field(default_factory=lambda: uuid4().hex)
    revision: int = 0
    sequence: int = 0
    versioned: bool = False
    senders: dict[int, MessageSender] = field(default_factory=dict)
    frozen_offers: tuple[ParticipantOffer, ParticipantOffer] | None = None


class TradeService:
    """Una sesión por jugador; cada revisión invalida ambas confirmaciones."""

    GOLD_SLOT = 0
    INVITATION_SECONDS = 30.0
    INACTIVITY_SECONDS = 300.0

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_manager: MapManager,
        *,
        clock: Callable[[], float] = monotonic,
        monitor: bool = True,
    ) -> None:
        """Inyecta recursos y reloj; el monitor sólo existe mientras haya sesiones."""
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.clock = clock
        self.monitor = monitor
        self.metadata_publisher: Callable[[int], Awaitable[None]] | None = None
        self._sessions_by_user: dict[int, TradeSession] = {}
        self._monitor_task: asyncio.Task[None] | None = None

    def get_session(self, user_id: int) -> TradeSession | None:
        """Devuelve la sesión actual.

        Returns:
            Sesión reservada o None.
        """
        return self._sessions_by_user.get(user_id)

    def is_user_in_trade(self, user_id: int) -> bool:
        """Consulta la reserva del jugador.

        Returns:
            Si existe una sesión asociada.
        """
        return user_id in self._sessions_by_user

    def clear_session(self, user_id: int) -> None:
        """Libera índices sólo si todavía apuntan a la misma sesión."""
        session = self.get_session(user_id)
        if session:
            for participant in session.senders:
                if self.get_session(participant) is session:
                    del self._sessions_by_user[participant]

    def _get_sender(self, user_id: int) -> MessageSender | None:
        return self.map_manager.get_player_message_sender(user_id)

    def _sender(self, session: TradeSession, user_id: int) -> MessageSender | None:
        sender = session.senders.get(user_id)
        return sender if sender is self._get_sender(user_id) else None

    @staticmethod
    def _versioned(sender: MessageSender) -> bool:
        connection = getattr(sender, "connection", None)
        return bool(connection and connection.capabilities.enabled & Capability.TRADE_STATE)

    @staticmethod
    def _offer(session: TradeSession, user_id: int) -> TradeOffer:
        return session.initiator_offer if user_id == session.initiator_id else session.target_offer

    async def _eligible(self, session: TradeSession) -> str:
        if any(self._sender(session, user_id) is None for user_id in session.senders):
            return "Un participante se desconectó."
        positions = [await self.player_repo.get_position(user_id) for user_id in session.senders]
        stats = [await self.player_repo.get_stats(user_id) for user_id in session.senders]
        if any(not position for position in positions):
            return "Un participante salió del mundo."
        first, second = positions
        if first is None or second is None:
            return "Un participante salió del mundo."
        if (
            first["map"] != second["map"]
            or max(abs(first["x"] - second["x"]), abs(first["y"] - second["y"])) > MAX_TRADE_RANGE
        ):
            return "Los participantes salieron del rango de intercambio."
        if any(int((stat or {}).get("min_hp", 0)) <= 0 for stat in stats):
            return "Un participante murió."
        return ""

    async def request_trade(self, initiator_id: int, target_username: str) -> tuple[bool, str]:
        """Reserva ambos participantes y publica la invitación o el flujo clásico.

        Returns:
            Aceptación y motivo, sin mover recursos.
        """
        target_id = self.map_manager.find_player_by_username(target_username)
        if target_id is None or target_id == initiator_id:
            return False, "El destinatario no está disponible."
        senders = {user: self._get_sender(user) for user in (initiator_id, target_id)}
        if any(sender is None for sender in senders.values()):
            return False, "El destinatario no está conectado."
        concrete = {user: sender for user, sender in senders.items() if sender is not None}
        versions = {self._versioned(sender) for sender in concrete.values()}
        if len(versions) != 1:
            return False, "Ambos participantes deben usar la misma versión de intercambio."
        session = TradeSession(
            initiator_id,
            self.map_manager.get_player_username(initiator_id) or "Jugador",
            target_id,
            self.map_manager.get_player_username(target_id) or "Jugador",
            TradeState.PENDING if True in versions else TradeState.ACTIVE,
            self.clock(),
            self.clock(),
            versioned=True in versions,
            senders=concrete,
        )
        reason = await self._eligible(session)
        if reason:
            return False, reason
        if any(self.is_user_in_trade(user) for user in concrete):
            return False, "Un participante ya tiene una sesión abierta."
        for user in concrete:
            self._sessions_by_user[user] = session
        if self.monitor and (self._monitor_task is None or self._monitor_task.done()):
            self._monitor_task = asyncio.create_task(self._watch_sessions(), name="trade-lifecycle")
        if not session.versioned:
            for user, sender in concrete.items():
                await sender.send_user_commerce_init(
                    session.target_username if user == initiator_id else session.initiator_username
                )
        await self._publish(session)
        return True, f"Solicitud de comercio enviada a {session.target_username}."

    async def _publish(self, session: TradeSession, reason: str = "") -> None:
        # Arrays compactos: cada ítem es [slot, id, cantidad]; 60 ítems caben en 3072 bytes.
        if not session.versioned:
            return
        players = [
            [
                user,
                name,
                offer.gold,
                confirmed,
                [
                    [item.slot, item.item_id, item.quantity]
                    for item in sorted(offer.items.values(), key=lambda item: item.slot)
                ],
            ]
            for user, name, offer, confirmed in (
                (
                    session.initiator_id,
                    session.initiator_username,
                    session.initiator_offer,
                    session.initiator_confirmed,
                ),
                (
                    session.target_id,
                    session.target_username,
                    session.target_offer,
                    session.target_confirmed,
                ),
            )
        ]
        session.sequence += 1
        packets: dict[int, bytes] = {}
        for user in session.senders:
            data = json.dumps(
                {
                    "id": session.session_id,
                    "revision": session.revision,
                    "sequence": session.sequence,
                    "state": session.state,
                    "viewer": user,
                    "players": players,
                    "reason": reason[:160],
                },
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("ascii")
            if len(data) > MAX_SNAPSHOT_BYTES:
                message = "Snapshot de intercambio demasiado grande"
                raise ValueError(message)
            packets[user] = struct.pack("<BBH", 252, 1, len(data)) + data
        # Se congela el estado antes del primer await, incluso la secuencia de publicación.
        for user, packet in packets.items():
            sender = self._sender(session, user)
            if sender:
                await sender.connection.send(packet)
                if self.metadata_publisher:
                    await self.metadata_publisher(user)

    async def apply_action(
        self, user_id: int, session_id: str, revision: int, action: int, slot: int, quantity: int
    ) -> tuple[bool, str]:
        """Valida identidad y revisión antes de interpretar una acción optativa.

        Returns:
            Resultado; una revisión obsoleta recibe el snapshot vigente.
        """
        session = self.get_session(user_id)
        if not session or not session.versioned or session.session_id != session_id:
            return False, "La sesión de intercambio ya no existe."
        if not self._sender(session, user_id):
            return False, "La conexión de intercambio cambió."
        if not 0 <= action < len(TRADE_ACTIONS):
            return False, "Acción de intercambio inválida."
        intent = TRADE_ACTIONS[action]
        if intent in {TradeAction.CANCEL, TradeAction.REJECT}:
            return await self.cancel_trade(user_id, "Intercambio cancelado.")
        if revision != session.revision:
            await self._publish(session, "La oferta cambió; revisá la revisión actual.")
            return False, "Revisión obsoleta."
        if (
            intent == TradeAction.ACCEPT
            and session.state == TradeState.PENDING
            and user_id == session.target_id
        ):
            session.state = TradeState.ACTIVE
            session.revision += 1
            session.last_update = self.clock()
            await self._publish(session)
            return True, "Invitación aceptada."
        if intent == TradeAction.ITEM:
            return await self.update_offer(user_id, slot, quantity, revision=revision)
        if intent == TradeAction.GOLD:
            return await self.update_offer(user_id, 0, quantity, revision=revision)
        if intent == TradeAction.CONFIRM:
            return await self.confirm_trade(user_id, revision=revision)
        return False, "Acción inválida para el estado actual."

    async def update_offer(
        self, user_id: int, slot: int, quantity: int, *, revision: int | None = None
    ) -> tuple[bool, str]:
        """Edita sólo la revisión vigente y borra ambas confirmaciones.

        Returns:
            Resultado sin reservar ni modificar el inventario real.
        """
        session = self.get_session(user_id)
        if not session or session.state != TradeState.ACTIVE or session.settlement_uncertain:
            return False, "La oferta no se puede editar ahora."
        if session.versioned and revision != session.revision:
            return False, "Revisión obsoleta."
        if not 0 <= slot <= ConfigManager.as_int(self.inventory_repo.MAX_SLOTS) or quantity < 0:
            return False, "Slot o cantidad inválidos."
        observed = session.revision
        if slot == 0:
            if quantity > await self.player_repo.get_gold(user_id):
                return False, "No tienes tanto oro."
            item = None
        else:
            item = await self.inventory_repo.get_slot(user_id, slot)
            if quantity and (not item or quantity > item[1]):
                return False, "El slot no tiene esa cantidad."
        if (
            self.get_session(user_id) is not session
            or session.state != TradeState.ACTIVE
            or session.revision != observed
        ):
            return False, "La oferta o la sesión cambió."
        offer = self._offer(session, user_id)
        if slot == 0:
            offer.gold = quantity
        elif quantity == 0:
            offer.items.pop(slot, None)
        else:
            if item is None:
                return False, "El slot quedó vacío."
            offer.items[slot] = TradeOfferItem(slot, item[0], quantity)
        session.initiator_confirmed = session.target_confirmed = False
        session.revision += 1
        session.last_update = self.clock()
        await self._publish(session)
        return True, "Oferta actualizada."

    def _freeze(self, session: TradeSession) -> tuple[ParticipantOffer, ParticipantOffer]:
        offers = [
            ParticipantOffer(
                user,
                offer.gold,
                tuple(
                    OfferedItem(item.slot, item.item_id, item.quantity)
                    for item in sorted(offer.items.values(), key=lambda item: item.slot)
                ),
            )
            for user, offer in (
                (session.initiator_id, session.initiator_offer),
                (session.target_id, session.target_offer),
            )
        ]
        return offers[0], offers[1]

    async def confirm_trade(self, user_id: int, *, revision: int | None = None) -> tuple[bool, str]:
        """Confirma una revisión y reclama el commit antes del primer await.

        Returns:
            Resultado durable, o confirmación parcial de la misma revisión.
        """
        session = self.get_session(user_id)
        if not session or session.state not in {TradeState.ACTIVE, TradeState.COMMITTING}:
            return False, "No tienes una sesión activa."
        if session.versioned and revision != session.revision:
            return False, "Revisión obsoleta."
        observed = session.revision
        reason = await self._eligible(session)
        if reason:
            return await self.cancel_trade(user_id, reason)
        if self.get_session(user_id) is not session or observed != session.revision:
            return False, "La oferta o la sesión cambió."
        if user_id == session.initiator_id:
            session.initiator_confirmed = True
        else:
            session.target_confirmed = True
        session.last_update = self.clock()
        if session.trade_executing:
            return True, "Confirmación en curso."
        if not (session.initiator_confirmed and session.target_confirmed):
            await self._publish(session)
            return True, "Confirmación registrada."
        session.trade_executing = True
        session.settlement_uncertain = True
        session.state = TradeState.COMMITTING
        if session.settlement_id is None:
            session.settlement_id = operation_id()
            session.frozen_offers = self._freeze(session)
        try:
            await self._publish(session)
            result = await self._perform_trade(session)
        finally:
            session.trade_executing = False
        session.settlement_uncertain = False
        success, message = result
        if self.get_session(user_id) is not session:
            return success, message
        if success:
            await self._finish(session, TradeState.COMPLETED, message)
        else:
            session.state = TradeState.ACTIVE
            session.initiator_confirmed = session.target_confirmed = False
            session.settlement_id = None
            session.frozen_offers = None
            session.revision += 1
            await self._publish(session, message)
        return result

    async def _perform_trade(self, session: TradeSession) -> tuple[bool, str]:
        if session.settlement_id is None or session.frozen_offers is None:
            return False, "No hay una oferta congelada."
        result = await settle_trade(
            self.player_repo.redis.redis,
            session.settlement_id,
            session.frozen_offers,
            ConfigManager.as_int(self.inventory_repo.MAX_SLOTS),
            self.inventory_repo.stacking.max_stack,
        )
        if result["applied"]:
            await self._sync_inventory(session)
        return bool(result["applied"]), str(result["message"])

    async def _sync_inventory(self, session: TradeSession) -> None:
        for user in session.senders:
            sender = self._sender(session, user)
            if sender:
                await notify_inventory(sender, self.inventory_repo, user)
                await sender.send_update_gold(await self.player_repo.get_gold(user))

    async def cancel_trade(self, user_id: int, reason: str | None = None) -> tuple[bool, str]:
        """Cancela una vez; un commit ganador se informa como completado.

        Returns:
            Estado final real, sin devoluciones compensatorias.
        """
        session = self.get_session(user_id)
        if not session:
            return False, "No tienes una sesión activa."
        message = reason or "La sesión de comercio fue cancelada."
        if session.settlement_id is not None:
            if session.frozen_offers is None:
                return False, "No hay una oferta congelada."
            result = await cancel_settlement(
                self.player_repo.redis.redis,
                session.settlement_id,
                session.frozen_offers,
                ConfigManager.as_int(self.inventory_repo.MAX_SLOTS),
                self.inventory_repo.stacking.max_stack,
                message,
            )
            if result["applied"]:
                await self._sync_inventory(session)
            state = TradeState.COMPLETED if result["applied"] else TradeState.CANCELLED
            message = str(result["message"])
        else:
            state = TradeState.CANCELLED
        await self._finish(session, state, message)
        return True, message

    async def _finish(self, session: TradeSession, state: TradeState, message: str) -> None:
        if self.get_session(session.initiator_id) is not session:
            return
        session.state = state
        self.clear_session(session.initiator_id)
        await self._publish(session, message)
        if not session.versioned:
            for user in session.senders:
                sender = self._sender(session, user)
                if sender:
                    await sender.send_user_commerce_end()
                    await sender.send_console_msg(
                        message, font_color=7 if state == TradeState.COMPLETED else 1
                    )

    async def ready_trade(self, user_id: int) -> tuple[bool, str]:
        """Compatibilidad con USER_COMMERCE_OK.

        Returns:
            Resultado de la confirmación clásica.
        """
        return await self.confirm_trade(user_id)

    async def reject_trade(self, user_id: int) -> tuple[bool, str]:
        """Compatibilidad con el rechazo clásico.

        Returns:
            Resultado de la cancelación.
        """
        return await self.cancel_trade(user_id, "Comercio rechazado.")

    async def sweep(self) -> None:
        """Evalúa reloj, conexiones, vida y rango sin depender de tráfico del jugador."""
        sessions = {id(session): session for session in self._sessions_by_user.values()}
        for session in sessions.values():
            reason = await self._eligible(session)
            limit = (
                self.INVITATION_SECONDS
                if session.state == TradeState.PENDING
                else self.INACTIVITY_SECONDS
            )
            if self.clock() - session.last_update >= limit:
                reason = "La sesión de intercambio venció."
            if reason and self.get_session(session.initiator_id) is session:
                await self.cancel_trade(session.initiator_id, reason)

    async def _watch_sessions(self) -> None:
        while self._sessions_by_user:
            await asyncio.sleep(0.5)
            try:
                await self.sweep()
            except Exception:
                logger.exception(
                    "No se pudo resolver una sesión; se reintentará sin compensar recursos"
                )

    async def close(self) -> None:
        """Detiene el monitor y resuelve sesiones antes de cerrar Redis."""
        if self._monitor_task:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
        for user in list(self._sessions_by_user):
            await self.cancel_trade(user, "El servidor se está cerrando.")

    async def resend_state(self, user_id: int, reason: str = "") -> None:
        """Libera la espera de la UI también cuando una acción fue rechazada."""
        session = self.get_session(user_id)
        if session:
            await self._publish(session, reason)
