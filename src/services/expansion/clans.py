"""Diplomacia bilateral y depósito de clan con permisos observados bajo WATCH."""

import json
import time
from operator import itemgetter
from typing import TYPE_CHECKING, Any, cast

from src.models.items_catalog import get_item
from src.services.expansion.pages import bounded_pages
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.models.clan import Clan

DEPOT_CAPACITY = 60
PAGE_SIZE = 8
PROPOSAL_SECONDS = 600
MAX_HISTORY = 100
LEADER_RANK = 4
WITHDRAW_RANK = 2
MAX_QUANTITY = 32767


def relation_key(first: int, second: int) -> str:
    """Deriva una sola identidad para ambos sentidos de una relación.

    Returns:
        Clave canónica ordenada por ID de clan.
    """
    return f"clan:relation:{min(first, second)}:{max(first, second)}"


def member_permission(snapshot: Snapshot, user: int, clan_id: int, minimum_rank: int) -> bool:
    """Revalida pertenencia, existencia y rango en el commit.

    Returns:
        Si el miembro conserva los permisos requeridos.
    """
    members = cast("dict[str, str]", snapshot[f"clan:{clan_id}:members"])
    member = json.loads(members.get(str(user), "{}"))
    clan = json.loads(str(snapshot[f"clan:{clan_id}"] or "{}"))
    return (
        str(snapshot[f"user:{user}:clan"]) == str(clan_id)
        and bool(clan)
        and int(member.get("rank", 0)) >= minimum_rank
    )


class ClanExpansion:
    """Ningún rango o clan proporcionado por la UI concede autorización."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte el repositorio de clanes y el plan de inventarios existente."""
        self.deps = deps

    async def snapshot(self, user: int, topic: str, params: dict[str, Any]) -> dict[str, Any]:
        """Consulta relaciones o una página del depósito propio.

        Returns:
            Estado acotado y permisos del miembro autenticado.
        """
        clan = await self.deps.clan_repo.get_user_clan(user)
        if clan is None:
            return {
                "clan": 0,
                "rows": [],
                "pages": 1,
                "page": 0,
                "message": "Primero debes pertenecer a un clan.",
            }
        rank = int(clan.members[user].rank)
        redis = self.deps.redis_client.redis
        if topic == "diplomacy":
            rows: list[dict[str, Any]] = []
            async for key in redis.scan_iter(match="clan:relation:*", count=100):
                parts = str(key).split(":")
                pair = (int(parts[-2]), int(parts[-1]))
                if clan.clan_id not in pair:
                    continue
                value = await redis.hgetall(key)
                other_id = pair[1] if pair[0] == clan.clan_id else pair[0]
                other = await self.deps.clan_repo.get_clan(other_id)
                if other is None:
                    continue
                if (
                    value.get("state") == "proposed"
                    and float(value.get("expires", 0)) <= time.time()
                ):
                    value = {**value, "state": "expired"}
                rows.append(
                    {
                        "clan": other_id,
                        "name": other.name,
                        "state": value.get("state", "none"),
                        "proposer": int(value.get("proposer", 0)),
                        "revision": int(value.get("revision", 0)),
                        "expires": int(float(value.get("expires", 0))),
                    }
                )
            rows.sort(key=itemgetter("clan"))
            pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(max(0, int(params.get("page", 0))), pages - 1)
            return {
                "clan": clan.clan_id,
                "name": clan.name,
                "leader": rank == LEADER_RANK,
                "rows": rows[page * PAGE_SIZE : (page + 1) * PAGE_SIZE],
                "page": page,
                "pages": pages,
            }
        return await self._depot_snapshot(user, clan, params, rank)

    async def _depot_snapshot(
        self, user: int, clan: Clan, params: dict[str, Any], rank: int
    ) -> dict[str, Any]:
        redis = self.deps.redis_client.redis
        raw = cast("dict[str, str]", await redis.hgetall(f"clan:depot:{clan.clan_id}"))
        bag = SlotPlan(raw, DEPOT_CAPACITY, 10000)
        inventory = cast("dict[str, str]", await redis.hgetall(RedisKeys.player_inventory(user)))
        own = SlotPlan(inventory, 30, self.deps.inventory_repo.stacking.max_stack)

        def inventory_rows(plan: SlotPlan) -> list[dict[str, Any]]:
            result = []
            for slot, stack in sorted(plan.slots.items()):
                item = get_item(stack.item_id)
                result.append(
                    {
                        "slot": slot,
                        "item": stack.item_id,
                        "quantity": stack.quantity,
                        "name": item.name[:80] if item else str(stack.item_id),
                    }
                )
            return result

        depot_rows = inventory_rows(bag)
        own_rows = inventory_rows(own)
        depot_chunks = bounded_pages(depot_rows, PAGE_SIZE, 900)
        own_chunks = bounded_pages(own_rows, PAGE_SIZE, 900)
        pages = max(len(depot_chunks), len(own_chunks))
        page = min(max(0, int(params.get("page", 0))), pages - 1)
        history = []
        for event in sorted(
            await redis.smembers(f"clan:depot:history:{clan.clan_id}"), reverse=True
        )[:5]:
            data = cast("dict[str, str]", await redis.hgetall(f"clan:depot:audit:{event!s}"))
            if data:
                item = get_item(int(data["item"]))
                history.append({**data, "item_name": item.name[:80] if item else "Objeto"})
        return {
            "clan": clan.clan_id,
            "name": clan.name,
            "deposit": rank >= 1,
            "withdraw": rank >= WITHDRAW_RANK,
            "capacity": DEPOT_CAPACITY,
            "rows": depot_chunks[page] if page < len(depot_chunks) else [],
            "inventory": own_chunks[page] if page < len(own_chunks) else [],
            "page": page,
            "pages": pages,
            "history": bounded_pages(history, 5, 900)[0],
        }

    async def relationship(
        self, user: int, action: str, params: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        """Transiciona propuesta/alianza/guerra en ambos metadatos de clan a la vez.

        Returns:
            Resultado con revisión bilateral estable.
        """
        own = await self.deps.clan_repo.get_user_clan(user)
        selected = str(params.get("clan", "")).strip()
        other = (
            await self.deps.clan_repo.get_clan(int(selected))
            if selected.isdecimal()
            else await self.deps.clan_repo.get_clan_by_name(selected)
        )
        target = other.clan_id if other else 0
        if own is None or target < 1 or target == own.clan_id:
            return {"applied": False, "message": "Debes elegir otro clan válido."}
        first, second = own.clan_id, target
        pair_key = relation_key(first, second)
        own_key, other_key = f"clan:{first}", f"clan:{second}"
        resources = (
            Resource(own_key, "string"),
            Resource(other_key, "string"),
            Resource(f"clan:{first}:members", "hash"),
            Resource(f"clan:{second}:members", "hash"),
            Resource(f"user:{user}:clan", "string"),
            Resource(pair_key, "hash"),
            Resource("clans:all", "hash"),
        )

        def decide(snapshot: Snapshot) -> Decision:
            if not member_permission(snapshot, user, first, 4):
                return Decision(
                    {
                        "applied": False,
                        "message": "Sólo el líder vigente puede cambiar relaciones.",
                    },
                    {},
                )
            other = json.loads(str(snapshot[other_key] or "{}"))
            current = json.loads(str(snapshot[own_key] or "{}"))
            if not other:
                return Decision({"applied": False, "message": "El otro clan ya no existe."}, {})
            relation = cast("dict[str, str]", snapshot[pair_key])
            state = relation.get("state", "none")
            proposer = int(relation.get("proposer", 0))
            live = state == "proposed" and float(relation.get("expires", 0)) > time.time()
            if action == "propose" and state not in {"alliance", "war"} and not live:
                next_state, proposer, expires = "proposed", first, time.time() + PROPOSAL_SECONDS
            elif action == "accept" and live and proposer == second:
                next_state, expires = "alliance", 0.0
            elif self._may_cancel(action, state, live, proposer, first, second):
                next_state, expires = "none", 0.0
            elif action == "declare_war" and state != "alliance":
                next_state, expires = "war", 0.0
            elif action == "end_war" and state == "war":
                next_state, expires = "none", 0.0
            else:
                return Decision(
                    {
                        "applied": False,
                        "message": "La relación cambió, venció o la transición no está permitida.",
                    },
                    {},
                )
            for metadata, other_id in ((current, second), (other, first)):
                for field, enabled in (
                    ("alliances", next_state == "alliance"),
                    ("wars", next_state == "war"),
                ):
                    ids = set(metadata.get(field, []))
                    ids.discard(other_id)
                    if enabled:
                        ids.add(other_id)
                    metadata[field] = sorted(ids)
            revision = int(relation.get("revision", 0)) + 1
            return Decision(
                {
                    "applied": True,
                    "message": "Relación entre clanes actualizada.",
                    "revision": revision,
                },
                {
                    own_key: json.dumps(current),
                    other_key: json.dumps(other),
                    "clans:all": {str(first): json.dumps(current), str(second): json.dumps(other)},
                    pair_key: {
                        "state": next_state,
                        "proposer": str(proposer),
                        "expires": str(expires),
                        "revision": str(revision),
                    },
                },
            )

        return await transact(
            self.deps.redis_client.redis,
            resources,
            identity,
            {"diplomacy": action, "clans": [first, second], "user": user},
            decide,
        )

    @staticmethod
    def _may_cancel(
        action: str, state: str, live: bool, proposer: int, first: int, second: int
    ) -> bool:
        rejected = action == "reject" and live and proposer == second
        cancelable = state == "alliance" or (live and proposer == first)
        return rejected or (action == "cancel" and cancelable)

    async def transfer(
        self, user: int, action: str, params: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        """Mueve todos los objetos o ninguno y registra el actor del movimiento.

        Returns:
            Resultado persistido; una revocación de rango invalida el commit.
        """
        clan = await self.deps.clan_repo.get_user_clan(user)
        slot, item_id, quantity = (int(params.get(key, 0)) for key in ("slot", "item", "quantity"))
        if (
            clan is None
            or action not in {"deposit", "withdraw"}
            or not 1 <= quantity <= MAX_QUANTITY
        ):
            return {"applied": False, "message": "Movimiento o clan inválido."}
        clan_id = clan.clan_id
        bag_key, gear_key, depot_key = (
            RedisKeys.player_inventory(user),
            RedisKeys.player_equipment(user),
            f"clan:depot:{clan_id}",
        )
        history_key, audit_key = f"clan:depot:history:{clan_id}", f"clan:depot:audit:{identity}"
        resources = (
            Resource(f"clan:{clan_id}", "string"),
            Resource(f"clan:{clan_id}:members", "hash"),
            Resource(f"user:{user}:clan", "string"),
            Resource(bag_key, "hash"),
            Resource(gear_key, "hash"),
            Resource(depot_key, "hash"),
            Resource(history_key, "set"),
            Resource(audit_key, "hash", ttl_seconds=604800),
        )

        def decide(snapshot: Snapshot) -> Decision:
            if not member_permission(snapshot, user, clan_id, 2 if action == "withdraw" else 1):
                return Decision(
                    {"applied": False, "message": "Ya no tienes permiso para este movimiento."}, {}
                )
            own = SlotPlan(
                cast("dict[str, str]", snapshot[bag_key]),
                30,
                self.deps.inventory_repo.stacking.max_stack,
            )
            depot = SlotPlan(cast("dict[str, str]", snapshot[depot_key]), DEPOT_CAPACITY, 10000)
            equipment = cast("dict[str, str]", snapshot[gear_key])
            if action == "deposit" and str(slot) in equipment.values():
                return Decision(
                    {"applied": False, "message": "Desequipa el objeto antes de depositarlo."}, {}
                )
            source, destination = (own, depot) if action == "deposit" else (depot, own)
            try:
                source.take(slot, item_id, quantity)
                destination.give(item_id, quantity)
            except ValueError as error:
                return Decision({"applied": False, "message": str(error)}, {})
            history = cast("set[str]", snapshot[history_key]) | {identity}
            history = set(sorted(history)[-MAX_HISTORY:])
            return Decision(
                {"applied": True, "message": "Movimiento de depósito confirmado."},
                {
                    bag_key: own.fields(),
                    depot_key: depot.fields(),
                    history_key: history,
                    audit_key: {
                        "clan": str(clan_id),
                        "actor": str(user),
                        "name": self.deps.map_manager.get_player_username(user) or str(user),
                        "action": action,
                        "item": str(item_id),
                        "quantity": str(quantity),
                        "result": "confirmed",
                    },
                },
            )

        return await transact(
            self.deps.redis_client.redis,
            resources,
            identity,
            {"depot": action, "params": params, "user": user, "clan": clan_id},
            decide,
        )
