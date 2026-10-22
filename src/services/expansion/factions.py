"""Afiliación neutral explícita y prestigio derivados sólo de eventos del servidor."""

import time
from typing import TYPE_CHECKING, Any, cast

from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

NOBLE_RANGE = 4

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.models.npc import NPC
    from src.services.expansion.catalog import ExpansionCatalog

MAX_PRESTIGE = 1000000


class FactionService:
    """Requisitos y cambios se comprueban sobre el mismo snapshot que se guarda."""

    def __init__(self, deps: DependencyContainer, catalog: ExpansionCatalog) -> None:
        """Conserva el catálogo validado y los repositorios del mundo."""
        self.deps, self.catalog = deps, catalog

    async def initialize_user(self, user: int) -> None:
        """Migración aditiva idempotente: una afiliación existente nunca se reemplaza."""
        await self.deps.redis_client.redis.hsetnx(
            RedisKeys.player_user_stats(user), "faction_id", "neutral"
        )

    def prestige(self, stats: dict[str, str], event: str) -> dict[str, str]:
        """Calcula prestigio y rango sin conceder privilegios ajenos a la facción.

        Returns:
            Cambios para incluir en el commit del evento que produjo el avance.
        """
        row = self.catalog.factions.get(stats.get("faction_id", "neutral"))
        if row is None:
            return {}
        award = (
            row.kill_prestige
            if event == "npc_kill"
            else row.quest_prestige
            if event == "quest_claim"
            else 0
        )
        amount = min(MAX_PRESTIGE, max(0, int(stats.get("faction_prestige", 0)) + award))
        rank = max(index for index, threshold in enumerate(row.thresholds) if amount >= threshold)
        return {"faction_prestige": str(amount), "faction_rank": str(rank)}

    async def snapshot(self, user: int) -> dict[str, Any]:
        """Publica afiliación y requisitos públicos, sin aceptar prestigio del cliente.

        Returns:
            Afiliación actual, rango, próximo umbral y opciones de ingreso.
        """
        await self.initialize_user(user)
        stats = cast(
            "dict[str, str]",
            await self.deps.redis_client.redis.hgetall(RedisKeys.player_user_stats(user)),
        )
        current = stats.get("faction_id", "neutral")
        faction = self.catalog.factions.get(current)
        prestige = int(stats.get("faction_prestige", 0))
        rank = (
            min(len(faction.ranks) - 1, max(0, int(stats.get("faction_rank", 0)))) if faction else 0
        )
        return {
            "faction": current,
            "name": faction.name if faction else "Neutral",
            "prestige": prestige,
            "rank": faction.ranks[rank] if faction else "Sin rango",
            "next": next(
                (threshold for threshold in faction.thresholds if threshold > prestige), None
            )
            if faction
            else None,
            "change_after": int(float(stats.get("faction_change_after", 0))),
            "options": [
                {"id": row.id, "name": row.name, "min_level": row.min_level}
                for row in self.catalog.factions.values()
            ],
        }

    async def command(
        self,
        user: int,
        action: str,
        params: dict[str, Any],
        identity: str,
        *,
        noble: NPC | None = None,
    ) -> dict[str, Any]:
        """Ingresa o abandona una facción con exclusión mutua y cooldown.

        Returns:
            Resultado del commit y mensaje que puede mostrar la interfaz.
        """
        key, now = RedisKeys.player_user_stats(user), time.time()
        selected = str(params.get("faction", "neutral"))
        position_key, selection_key = RedisKeys.player_position(user), f"chat:target:{user}"
        npc_key = RedisKeys.npc_instance(noble.instance_id) if noble else ""

        def decide(snapshot: Snapshot) -> Decision:
            stats = cast("dict[str, str]", snapshot[key])
            if noble:
                position = cast("dict[str, str]", snapshot[position_key])
                npc = cast("dict[str, str]", snapshot[npc_key])
                selection = cast("dict[str, str]", snapshot[selection_key])
                valid_identity = (
                    selection.get("npc") == noble.instance_id
                    and npc.get("instance_id") == noble.instance_id
                    and int(npc.get("npc_id", 0)) == noble.npc_id
                )
                npc_alive = not (int(npc.get("max_hp", 0)) > 0 and int(npc.get("hp", 0)) <= 0)
                if (
                    not valid_identity
                    or int(position.get("map", 0)) != int(npc.get("map_id", -1))
                    or max(
                        abs(int(position.get("x", 0)) - int(npc.get("x", -100))),
                        abs(int(position.get("y", 0)) - int(npc.get("y", -100))),
                    )
                    > NOBLE_RANGE
                    or not npc_alive
                ):
                    return Decision(
                        {
                            "applied": False,
                            "message": "El noble seleccionado cambió o está fuera de alcance.",
                        },
                        {},
                    )
            current = stats.get("faction_id", "neutral")
            row = self.catalog.factions.get(selected)
            if action == "join" and (
                row is None
                or current != "neutral"
                or int(stats.get("level", 0)) < row.min_level
                or stats.get(f"faction_banned_{selected}") == "1"
            ):
                return Decision(
                    {
                        "applied": False,
                        "message": "No cumples los requisitos o ya perteneces a una facción.",
                    },
                    {},
                )
            if int(stats.get("min_hp", 0)) <= 0 or (
                action == "join" and float(stats.get("faction_change_after", 0)) > now
            ):
                return Decision(
                    {
                        "applied": False,
                        "message": "Debes estar vivo y esperar el plazo de cambio de facción.",
                    },
                    {},
                )
            if action == "leave" and current == "neutral":
                return Decision({"applied": True, "message": "Ya eres neutral."}, {})
            if action not in {"join", "leave"}:
                return Decision({"applied": False, "message": "Acción desconocida."}, {})
            policy = row if action == "join" else self.catalog.factions.get(current)
            cooldown = policy.change_cooldown_seconds if policy else 86400
            return Decision(
                {"applied": True, "message": "Afiliación actualizada."},
                {
                    key: {
                        "faction_id": selected if action == "join" else "neutral",
                        "faction_prestige": "0",
                        "faction_rank": "0",
                        "faction_council": "0",
                        "faction_change_after": str(now + cooldown),
                        "faction_kill_baseline": stats.get(
                            "criminal_kills" if selected == "royal" else "citizen_kills", "0"
                        )
                        if action == "join"
                        else stats.get("faction_kill_baseline", "0"),
                    }
                },
            )

        return await transact(
            self.deps.redis_client.redis,
            (
                Resource(key, "hash"),
                *(
                    (
                        Resource(position_key, "hash"),
                        Resource(selection_key, "hash"),
                        Resource(npc_key, "hash"),
                    )
                    if noble
                    else ()
                ),
            ),
            identity,
            {"faction": action, "params": params, "user": user},
            decide,
        )
