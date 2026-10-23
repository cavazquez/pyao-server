"""Reordenamiento de bóveda con acceso físico, revisión y recibo atómicos."""

import json
from hashlib import sha256
from typing import TYPE_CHECKING, Any, cast

from src.utils.durability import ensure_aof, require_durable
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender

BANK_RANGE = 3
MAX_STACK = 32767


class BankState:
    """El cliente sólo indica dos posiciones, nunca objetos o cantidades."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte el banco, mundo y Redis del servidor."""
        self.deps = deps

    def data(self, raw: dict[str, str], banker: str, access: bool) -> dict[str, Any]:
        """Construye el estado compacto que se revisa antes del intercambio.

        Returns:
            Capacidad, acceso y stacks confirmados de la bóveda propia.
        """
        capacity = int(self.deps.bank_repo.MAX_SLOTS)
        slots = SlotPlan(raw, capacity, MAX_STACK).slots if access else {}
        return {
            "capacity": capacity,
            "banker": banker,
            "access": access,
            "slots": [[slot, item.item_id, item.quantity] for slot, item in sorted(slots.items())],
        }

    async def snapshot(self, user: int) -> dict[str, Any]:
        """Consulta la bóveda sólo con una apertura vigente junto al banquero.

        Returns:
            Estado propio o acceso denegado sin revelar objetos.
        """
        sender = self.deps.map_manager.get_player_message_sender(user)
        banker = str(getattr(sender.connection, "bank_npc", "")) if sender else ""
        redis = self.deps.redis_client.redis
        position = cast("dict[str, str]", await redis.hgetall(RedisKeys.player_position(user)))
        stats = cast("dict[str, str]", await redis.hgetall(RedisKeys.player_user_stats(user)))
        npc = (
            cast("dict[str, str]", await redis.hgetall(RedisKeys.npc_instance(banker)))
            if banker
            else {}
        )
        access = self.allowed(user, sender, banker, position, stats, npc)
        raw = cast("dict[str, str]", await redis.hgetall(RedisKeys.bank(user))) if access else {}
        return self.data(raw, banker, access)

    def allowed(
        self,
        user: int,
        sender: MessageSender | None,
        banker: str,
        position: dict[str, str],
        stats: dict[str, str],
        npc: dict[str, str],
    ) -> bool:
        """Revalida la sesión viva, la apertura, el NPC y la distancia.

        Returns:
            Si el personaje vivo sigue atendido por ese banquero.
        """
        permanent = (
            npc.get("max_hp") == "0"
            and npc.get("is_attackable", "True").lower() == "false"
            and npc.get("is_hostile", "True").lower() == "false"
        )
        return bool(
            sender
            and self.deps.map_manager.get_player_message_sender(user) is sender
            and banker
            and getattr(sender.connection, "bank_npc", "") == banker
            and npc.get("is_banker", "").lower() == "true"
            and (int(npc.get("hp", 0)) > 0 or permanent)
            and int(stats.get("min_hp", 0)) > 0
            and position.get("map") == npc.get("map_id")
            and max(
                abs(int(position.get("x", -100)) - int(npc.get("x", 0))),
                abs(int(position.get("y", -100)) - int(npc.get("y", 0))),
            )
            <= BANK_RANGE
        )

    async def move(
        self, user: int, sender: MessageSender, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Intercambia ambos slots en el mismo EXEC que su recibo recuperable.

        Returns:
            Resultado original en duplicados, o rechazo sin cambiar ningún objeto.
        """
        params = request["params"]
        source, destination, banker = params["source"], params["destination"], params["banker"]
        capacity = int(self.deps.bank_repo.MAX_SLOTS)
        if not 1 <= source <= capacity or not 1 <= destination <= capacity or not banker:
            return {"applied": False, "message": "Posiciones de bóveda inválidas."}
        bank = RedisKeys.bank(user)
        position, stats = RedisKeys.player_position(user), RedisKeys.player_user_stats(user)
        npc = RedisKeys.npc_instance(banker)

        def decide(snapshot: Snapshot) -> Decision:
            raw = cast("dict[str, str]", snapshot[bank])
            allowed = self.allowed(
                user,
                sender,
                banker,
                cast("dict[str, str]", snapshot[position]),
                cast("dict[str, str]", snapshot[stats]),
                cast("dict[str, str]", snapshot[npc]),
            )
            data = self.data(raw, banker, allowed)
            revision = sha256(
                json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:32]
            if not allowed or revision != request["revision"]:
                return Decision(
                    {
                        "applied": False,
                        "message": "El banco cambió o ya no estás junto al banquero.",
                    },
                    {},
                )
            first, second = f"slot_{source}", f"slot_{destination}"
            if source == destination or not raw.get(first):
                return Decision(
                    {
                        "applied": False,
                        "message": "Seleccioná un objeto y otro lugar de la bóveda.",
                    },
                    {},
                )
            return Decision(
                {"applied": True, "message": "Bóveda reordenada."},
                {bank: {first: raw.get(second, ""), second: raw[first]}},
            )

        redis = self.deps.redis_client.redis
        await ensure_aof(redis)
        result = await transact(
            redis,
            (
                Resource(bank, "hash"),
                Resource(position, "hash"),
                Resource(stats, "hash"),
                Resource(npc, "hash"),
            ),
            request["id"],
            {"bank_move": user, "params": params, "revision": request["revision"]},
            decide,
        )
        await require_durable(redis)
        return result
