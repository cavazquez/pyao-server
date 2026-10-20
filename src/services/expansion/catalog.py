"""Catálogos finitos de misiones y facciones con referencias comprobadas."""

import json
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.item_catalog import ItemCatalog
from src.models.npc_catalog import NPCCatalog
from src.runtime_paths import data_dir
from src.services.expansion.pages import QUEST_ROW_BUDGET

MAX_PRESTIGE = 1000000
MAX_CLASS = 12


class ItemAmount(BaseModel):
    """Cantidad positiva de un objeto real del catálogo."""

    model_config = ConfigDict(extra="forbid", strict=True)
    item_id: int = Field(ge=1, le=32767)
    quantity: int = Field(ge=1, le=10000)


class Objective(BaseModel):
    """Objetivo limitado a bajas o entrega de objetos."""

    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["kill", "deliver"]
    target: int = Field(ge=1, le=32767)
    quantity: int = Field(ge=1, le=1000)


class Quest(BaseModel):
    """Identidad estable, requisitos y premios que nunca vienen del cliente."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(max_length=300)
    start_npc: int = Field(ge=1)
    finish_npc: int = Field(ge=1)
    min_level: int = Field(default=1, ge=1, le=100)
    classes: list[int] = Field(default_factory=list, max_length=12)
    faction: str = ""
    prerequisites: list[str] = Field(default_factory=list, max_length=8)
    objectives: list[Objective] = Field(min_length=1, max_length=8)
    gold: int = Field(default=0, ge=0, le=100000000)
    experience: int = Field(default=0, ge=0, le=100000000)
    rewards: list[ItemAmount] = Field(default_factory=list, max_length=8)


class Faction(BaseModel):
    """Rangos sin privilegios de moderación ni cambios implícitos de PvP."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: Literal["royal", "chaos"]
    name: str = Field(min_length=1, max_length=60)
    min_level: int = Field(default=12, ge=1, le=100)
    change_cooldown_seconds: int = Field(default=86400, ge=1, le=2592000)
    thresholds: list[int] = Field(min_length=1, max_length=10)
    ranks: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(
        min_length=1, max_length=10
    )
    kill_prestige: int = Field(default=1, ge=0, le=100)
    quest_prestige: int = Field(default=5, ge=0, le=100)


class ExpansionCatalog:
    """Carga antes de aceptar acciones y rechaza errores con archivo/identidad."""

    def __init__(self, root: Path | None = None) -> None:
        """Valida el esquema, referencias cruzadas y ciclos de prerrequisitos.

        Raises:
            ValueError: Por una referencia, ID, requisito o ciclo inválido.
        """
        root = root or data_dir()
        items = ItemCatalog(str(root / "items.toml"))
        npcs = NPCCatalog(str(root / "npcs/hostiles.toml"), str(root / "npcs/friendly.toml"))
        self.quests: dict[str, Quest] = {}
        self.factions: dict[str, Faction] = {}
        faction_path = root / "world/factions.toml"
        quest_path = root / "world/quests.toml"
        self.enabled = True
        for row in tomllib.loads(faction_path.read_text()).get("faction", []):
            faction = Faction.model_validate(row)
            if (
                faction.id in self.factions
                or faction.thresholds[0] != 0
                or faction.thresholds != sorted(set(faction.thresholds))
                or len(faction.thresholds) != len(faction.ranks)
                or any(value < 0 or value > MAX_PRESTIGE for value in faction.thresholds)
            ):
                message = f"{faction_path}: facción/rangos inválidos: {faction.id}"
                raise ValueError(message)
            self.factions[faction.id] = faction
        raw = tomllib.loads(quest_path.read_text())
        self.enabled = bool(raw.get("enabled", True))
        for row in raw.get("quest", []):
            quest = Quest.model_validate(row)
            if (
                len(json.dumps(quest.model_dump(), ensure_ascii=True, separators=(",", ":"))) + 512
                > QUEST_ROW_BUDGET
            ):
                message = f"{quest_path}: la misión {quest.id} excede el presupuesto del protocolo"
                raise ValueError(message)
            valid = (
                quest.id not in self.quests
                and npcs.npc_exists(quest.start_npc)
                and npcs.npc_exists(quest.finish_npc)
                and all(1 <= value <= MAX_CLASS for value in quest.classes)
                and (not quest.faction or quest.faction in self.factions)
            )
            valid = (
                valid
                and all(
                    (
                        npcs.npc_exists(obj.target)
                        if obj.kind == "kill"
                        else items.item_exists(obj.target)
                    )
                    for obj in quest.objectives
                )
                and all(items.item_exists(reward.item_id) for reward in quest.rewards)
            )
            if not valid:
                message = f"{quest_path}: referencia o ID inválido en {quest.id}"
                raise ValueError(message)
            self.quests[quest.id] = quest
        visited: set[str] = set()

        def visit(key: str, path: frozenset[str]) -> None:
            if key not in self.quests or key in path:
                message = f"{quest_path}: prerrequisito inexistente o cíclico: {key}"
                raise ValueError(message)
            if key in visited:
                return
            for dependency in self.quests[key].prerequisites:
                visit(dependency, path | {key})
            visited.add(key)

        for key in self.quests:
            visit(key, frozenset())
