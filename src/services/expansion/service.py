"""Fachada de extensiones sobre el canal autenticado y negociado del mundo."""

from typing import TYPE_CHECKING, Any

from src.services.expansion.catalog import ExpansionCatalog
from src.services.expansion.clans import ClanExpansion
from src.services.expansion.factions import FactionService
from src.services.expansion.party_finder import PartyFinder
from src.services.expansion.quests import QuestService
from src.services.inventory_notifications import notify_inventory
from src.services.player_progression import publish_progress
from src.utils.durability import require_durable

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

EXPANSION_TOPICS = frozenset({"finder", "diplomacy", "depot", "faction", "quests"})
EXPANSION_FIELDS: dict[str, dict[str, type]] = {
    "finder.read": {"min_level": int, "max_level": int, "activity": str, "map": int, "page": int},
    "finder.publish": {
        "min_level": int,
        "max_level": int,
        "activity": str,
        "text": str,
        "seconds": int,
    },
    "finder.close": {},
    "finder.request": {"party": int},
    "finder.invite": {"party": int, "user": int},
    "diplomacy.read": {"page": int},
    "diplomacy.propose": {"clan": str},
    "diplomacy.accept": {"clan": str},
    "diplomacy.reject": {"clan": str},
    "diplomacy.cancel": {"clan": str},
    "diplomacy.declare_war": {"clan": str},
    "diplomacy.end_war": {"clan": str},
    "depot.read": {"page": int},
    "depot.deposit": {"slot": int, "item": int, "quantity": int},
    "depot.withdraw": {"slot": int, "item": int, "quantity": int},
    "faction.read": {},
    "faction.join": {"faction": str},
    "faction.leave": {},
    "quests.read": {"page": int, "npc": int},
    "quests.accept": {"quest": str, "npc": int},
    "quests.deliver": {"quest": str, "npc": int},
    "quests.claim": {"quest": str, "npc": int},
    "quests.abandon": {"quest": str, "npc": int},
}


class ExpansionService:
    """Las preferencias de consulta son efímeras; todo el progreso vive en Redis."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Valida catálogos y conecta eventos de muerte con misiones y facciones."""
        self.deps = deps
        self.catalog = ExpansionCatalog()
        self.factions = FactionService(deps, self.catalog)
        self.quests = QuestService(deps, self.catalog, self.factions)
        self.clans = ClanExpansion(deps)
        self.finder = PartyFinder(deps)
        self.queries: dict[tuple[int, str], dict[str, Any]] = {}
        deps.npc_death_service.quest_service = self.quests

    async def snapshot(self, user: int, topic: str) -> dict[str, Any]:
        """Resuelve sólo la página y datos autorizados para este personaje.

        Returns:
            Estado público acotado de una extensión habilitada.
        """
        if not self.catalog.enabled:
            return {"enabled": False, "message": "Las extensiones de mundo están deshabilitadas."}
        query = self.queries.get((user, topic), {})
        if topic == "faction":
            return await self.factions.snapshot(user)
        if topic == "quests":
            return await self.quests.snapshot(user, query)
        if topic == "finder":
            return await self.finder.snapshot(user, query)
        return await self.clans.snapshot(user, topic, query)

    async def command(
        self, user: int, action: str, params: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        """Comparte confirmación durable y actualización de inventario/progreso.

        Returns:
            Resultado confirmado de la acción autorizada.
        """
        if not self.catalog.enabled:
            return {"applied": False, "message": "Las extensiones de mundo están deshabilitadas."}
        topic, command = action.split(".", 1)
        if topic == "faction":
            result = await self.factions.command(user, command, params, identity)
        elif topic == "quests":
            result = await self.quests.command(user, command, params, identity)
        elif topic == "finder":
            result = await self.finder.command(user, command, params, identity)
        elif topic == "diplomacy":
            result = await self.clans.relationship(user, command, params, identity)
        else:
            result = await self.clans.transfer(user, command, params, identity)
        if result.get("applied") and topic in {"quests", "depot"}:
            await require_durable(self.deps.redis_client.redis)
            sender = self.deps.map_manager.get_player_message_sender(user)
            if sender:
                await notify_inventory(sender, self.deps.inventory_repo, user)
                await publish_progress(self.deps.player_repo, user, sender)
        return result
