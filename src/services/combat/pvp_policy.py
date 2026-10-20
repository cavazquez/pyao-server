"""Política única de daño entre jugadores, evaluable sobre el snapshot del commit."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.config.config_manager import config_manager

if TYPE_CHECKING:
    from src.repositories.player_repository import PlayerRepository

DEFAULT_SAFE_MAPS = (1, 34, 59, 62, 151, 196, 286)
HOSTILE_FLAGS = (
    "poisons",
    "paralyzes",
    "immobilizes",
    "blinds",
    "dumbs",
    "decreases_agility",
    "decreases_strength",
)


def is_hostile(spell: Mapping[str, Any]) -> bool:
    """Distingue daño/debuff de curación, resurrección, invocación y buffs.

    Returns:
        True si el efecto requiere consentimiento y zona habilitada para PvP.
    """
    return bool(
        spell.get("dispels_magic")
        or spell.get("periodic", {}).get("mode") == "damage"
        or (
            not spell.get("heals_hp")
            and not spell.get("invokes")
            and (spell.get("min_damage", 0) > 0 or spell.get("max_damage", 0) > 0)
        )
        or any(spell.get(flag) for flag in HOSTILE_FLAGS)
        or spell.get("id") in {12, 13}
    )


@dataclass(frozen=True)
class PvpPolicy:
    """Consentimiento bilateral: ambos seguros apagados, vivos y fuera de ciudades."""

    enabled: bool = True
    safe_maps: tuple[int, ...] = DEFAULT_SAFE_MAPS

    @classmethod
    def configured(cls) -> PvpPolicy:
        """Lee la configuración ya validada del servidor.

        Returns:
            Política común para daño físico y mágico.
        """
        maps = config_manager.get("game.combat.safe_maps", list(DEFAULT_SAFE_MAPS))
        return cls(
            bool(config_manager.get("game.combat.pvp_enabled", True)),
            tuple(maps) if isinstance(maps, list) else DEFAULT_SAFE_MAPS,
        )

    def rejection(
        self,
        attacker: int,
        target: int,
        source_position: Mapping[str, str | int],
        target_position: Mapping[str, str | int],
        source_stats: Mapping[str, str | int],
        target_stats: Mapping[str, str | int],
        relationship: str = "neutral",
    ) -> str | None:
        """Valida sin I/O y permite revalidar exactamente los recursos observados por WATCH.

        Returns:
            Motivo del rechazo o None cuando ambas partes pueden combatir.
        """
        if not self.enabled:
            return "El combate entre jugadores está deshabilitado."
        if attacker == target:
            return "No puedes atacarte a ti mismo."
        source_map, target_map = (
            int(source_position.get("map", 0)),
            int(target_position.get("map", 0)),
        )
        if not source_map or source_map != target_map:
            return "El objetivo está en otro mapa."
        if source_map in self.safe_maps:
            return "No puedes atacar en una zona segura."
        if relationship == "changed":
            return "La pertenencia al clan cambió; vuelve a seleccionar el objetivo."
        if relationship in {"same", "alliance"}:
            return "No puedes atacar a un miembro de tu clan ni de un clan aliado."
        if any(
            int(stats.get("min_hp", stats.get("hp", 0))) <= 0
            for stats in (source_stats, target_stats)
        ):
            return "No puedes atacar a un muerto ni estando muerto."
        if relationship != "war" and any(
            str(stats.get("safe_mode", "1")) != "0" for stats in (source_stats, target_stats)
        ):
            return "Ambos jugadores deben desactivar el modo seguro para combatir."
        return None

    async def authorize(
        self, repository: PlayerRepository, attacker: int, target: int
    ) -> str | None:
        """Prevalida; el plan de combate debe repetir rejection dentro del commit.

        Returns:
            Motivo de rechazo antes de cualquier cobro o efecto.
        """
        source_pos, target_pos = (
            await repository.get_position(attacker),
            await repository.get_position(target),
        )
        source, victim = (
            await repository.get_player_stats(attacker),
            await repository.get_player_stats(target),
        )
        if source is None or victim is None or source_pos is None or target_pos is None:
            return "Objetivo inválido."
        source_stats, target_stats = source.to_dict(), victim.to_dict()
        source_stats["safe_mode"] = int(await repository.get_safe_mode(attacker))
        target_stats["safe_mode"] = int(await repository.get_safe_mode(target))
        return self.rejection(attacker, target, source_pos, target_pos, source_stats, target_stats)
