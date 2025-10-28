"""Servicio de balance del juego.

Carga y gestiona los datos de balance de clases y razas
desde los archivos TOML extraídos del cliente.
"""

import logging
from pathlib import Path
from tomllib import load as tomllib_load
from typing import Any

logger = logging.getLogger(__name__)


class BalanceService:
    """Servicio centralizado para manejar el balance del juego."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el servicio de balance.

        Args:
            data_dir: Directorio donde se encuentran los datos de balance.
                     Si es None, usa "data" por defecto.
        """
        self.data_dir = data_dir or Path("data")
        self.racial_modifiers: dict[str, dict[str, int]] = {}
        self.class_modifiers: dict[str, dict[str, float]] = {}
        self.balance_data: dict[str, Any] = {}
        self._load_balance_data()

    def _load_balance_data(self) -> None:
        """Carga los datos de balance desde archivos TOML."""
        try:
            balance_file = self.data_dir / "classes_balance.toml"

            if not balance_file.exists():
                logger.warning("No se encontró archivo de balance: %s", balance_file)
                return

            with balance_file.open("rb") as f:
                self.balance_data = tomllib_load(f)

            self._parse_racial_modifiers()
            self._parse_class_modifiers()

            logger.info(
                "Balance cargado: %d razas, %d clases",
                len(self.racial_modifiers),
                len(self.class_modifiers),
            )

        except Exception:
            logger.exception("Error cargando datos de balance")

    def _parse_racial_modifiers(self) -> None:
        """Parsea los modificadores de raza."""
        if "racial_modifiers" not in self.balance_data:
            return

        races_data = self.balance_data["racial_modifiers"].get("races", [])

        for race_info in races_data:
            race_name = race_info.get("name", "")
            if race_name:
                self.racial_modifiers[race_name] = {
                    "strength": race_info.get("strength", 0),
                    "agility": race_info.get("agility", 0),
                    "intelligence": race_info.get("intelligence", 0),
                    "charisma": race_info.get("charisma", 0),
                    "constitution": race_info.get("constitution", 0),
                }

    def _parse_class_modifiers(self) -> None:
        """Parsea los modificadores de clase."""
        if "class_modifiers" not in self.balance_data:
            return

        classes_data = self.balance_data["class_modifiers"].get("classes", [])

        for class_info in classes_data:
            class_name = class_info.get("name", "")
            if class_name:
                self.class_modifiers[class_name] = {
                    "evasion": class_info.get("evasion", 1.0),
                    "ataquearmas": class_info.get("ataquearmas", 1.0),
                    "ataqueproyectiles": class_info.get("ataqueproyectiles", 1.0),
                    "ataquewrestling": class_info.get("ataquewrestling", 1.0),
                    "danoarmas": class_info.get("danoarmas", 1.0),
                    "danoproyectiles": class_info.get("danoproyectiles", 1.0),
                    "danowrestling": class_info.get("danowrestling", 1.0),
                    "escudo": class_info.get("escudo", 1.0),
                    "vida": class_info.get("vida", 1.0),
                }

    def get_racial_modifier(self, race: str, stat: str) -> int:
        """Obtiene el modificador racial para un estadística específica.

        Args:
            race: Nombre de la raza (ej: "Humano", "Elfo")
            stat: Estadística ("strength", "agility", "intelligence", "charisma", "constitution")

        Returns:
            Modificador numérico (positivo, negativo o cero)
        """
        return self.racial_modifiers.get(race, {}).get(stat, 0)

    def get_class_modifier(self, character_class: str, modifier_type: str) -> float:
        """Obtiene el modificador de clase para un tipo específico.

        Args:
            character_class: Nombre de la clase (ej: "Guerrero", "Mago")
            modifier_type: Tipo de modificador ("evasion", "ataquearmas", "danoarmas", etc.)

        Returns:
            Modificador multiplicador (ej: 1.1 para +10%, 0.9 para -10%)
        """
        return self.class_modifiers.get(character_class, {}).get(modifier_type, 1.0)

    def apply_racial_modifiers(self, base_stats: dict[str, int], race: str) -> dict[str, int]:
        """Aplica modificadores raciales a estadísticas base.

        Args:
            base_stats: Estadísticas base sin modificar
            race: Raza del personaje

        Returns:
            Estadísticas modificadas según la raza
        """
        modified_stats = base_stats.copy()

        if race in self.racial_modifiers:
            for stat, modifier in self.racial_modifiers[race].items():
                if stat in modified_stats:
                    modified_stats[stat] += modifier

        return modified_stats

    def calculate_damage(
        self, base_damage: int, character_class: str, damage_type: str = "danoarmas"
    ) -> int:
        """Calcula el daño aplicando modificadores de clase.

        Args:
            base_damage: Daño base antes de modificadores
            character_class: Clase del personaje
            damage_type: Tipo de daño ("danoarmas", "danoproyectiles", etc.)

        Returns:
            Daño final con modificadores aplicados
        """
        modifier = self.get_class_modifier(character_class, damage_type)
        return int(base_damage * modifier)

    def calculate_evasion(self, base_evasion: int, character_class: str) -> int:
        """Calcula la evasión aplicando modificadores de clase.

        Args:
            base_evasion: Evasión base
            character_class: Clase del personaje

        Returns:
            Evasión final con modificadores
        """
        modifier = self.get_class_modifier(character_class, "evasion")
        return int(base_evasion * modifier)

    def calculate_max_health(self, base_health: int, character_class: str) -> int:
        """Calcula la salud máxima aplicando modificadores de clase.

        Args:
            base_health: Salud base
            character_class: Clase del personaje

        Returns:
            Salud máxima final
        """
        modifier = self.get_class_modifier(character_class, "vida")
        return int(base_health * modifier)

    def get_available_races(self) -> list[str]:
        """Retorna la lista de razas disponibles.

        Returns:
            Lista de nombres de razas disponibles.
        """
        return list(self.racial_modifiers.keys())

    def get_available_classes(self) -> list[str]:
        """Retorna la lista de clases disponibles.

        Returns:
            Lista de nombres de clases disponibles.
        """
        return list(self.class_modifiers.keys())

    def validate_race(self, race: str) -> bool:
        """Verifica si una raza existe.

        Args:
            race: Nombre de la raza a verificar.

        Returns:
            True si la raza existe, False en caso contrario.
        """
        return race in self.racial_modifiers

    def validate_class(self, character_class: str) -> bool:
        """Verifica si una clase existe.

        Args:
            character_class: Nombre de la clase a verificar.

        Returns:
            True si la clase existe, False en caso contrario.
        """
        return character_class in self.class_modifiers


# Instancia global del servicio
_balance_service: BalanceService | None = None


def get_balance_service() -> BalanceService:
    """Retorna la instancia global del servicio de balance.

    Returns:
        Instancia del servicio de balance.
    """
    return BalanceService()
