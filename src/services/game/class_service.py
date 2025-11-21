"""Servicio para gestionar clases de personaje."""

import logging
from pathlib import Path

from src.models.character_class import CharacterClass, ClassCatalog

logger = logging.getLogger(__name__)


class ClassService:
    """Servicio centralizado para manejar clases de personaje."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el servicio de clases.

        Args:
            data_dir: Directorio donde se encuentran los datos.
                     Si es None, usa "data" por defecto.
        """
        self.catalog = ClassCatalog(data_dir)
        logger.info("ClassService inicializado con %d clases", len(self.catalog.get_all_classes()))

    def get_class(self, class_id: int) -> CharacterClass | None:
        """Obtiene una clase por ID.

        Args:
            class_id: ID de la clase.

        Returns:
            CharacterClass o None si no existe.
        """
        return self.catalog.get_class(class_id)

    def get_class_by_name(self, name: str) -> CharacterClass | None:
        """Obtiene una clase por nombre.

        Args:
            name: Nombre de la clase.

        Returns:
            CharacterClass o None si no existe.
        """
        return self.catalog.get_class_by_name(name)

    def get_all_classes(self) -> list[CharacterClass]:
        """Retorna todas las clases disponibles.

        Returns:
            Lista de todas las clases.
        """
        return self.catalog.get_all_classes()

    def get_base_attributes(self, class_id: int) -> dict[str, int]:
        """Obtiene los atributos base de una clase.

        Args:
            class_id: ID de la clase.

        Returns:
            Diccionario con atributos base, o valores por defecto si la clase no existe.
        """
        character_class = self.get_class(class_id)
        if character_class:
            return character_class.base_attributes

        # Valores por defecto si la clase no existe
        logger.warning("Clase %d no encontrada, usando valores por defecto", class_id)
        return {
            "strength": 10,
            "agility": 10,
            "intelligence": 10,
            "charisma": 10,
            "constitution": 10,
        }

    def apply_class_base_attributes(
        self, dice_attributes: dict[str, int], class_id: int
    ) -> dict[str, int]:
        """Aplica los atributos base de la clase a los atributos de dados.

        Args:
            dice_attributes: Atributos obtenidos de los dados.
            class_id: ID de la clase.

        Returns:
            Atributos finales (dados + base de clase).
        """
        base_attributes = self.get_base_attributes(class_id)

        final_attributes = {}
        for stat in ["strength", "agility", "intelligence", "charisma", "constitution"]:
            dice_value = dice_attributes.get(stat, 10)
            base_value = base_attributes.get(stat, 10)
            final_attributes[stat] = dice_value + base_value

        return final_attributes

    def can_equip_weapon(self, class_id: int, weapon_type: str) -> bool:
        """Verifica si una clase puede equipar un tipo de arma.

        NOTA: Este método existe pero NO se usa. Siguiendo comportamiento VB6 original,
        cualquier clase puede equipar cualquier item. Los modificadores de clase en
        classes_balance.toml ya balancean el uso inadecuado.

        Args:
            class_id: ID de la clase.
            weapon_type: Tipo de arma.

        Returns:
            True si puede equipar, False en caso contrario.
        """
        character_class = self.get_class(class_id)
        if not character_class:
            return False

        return character_class.can_equip_weapon(weapon_type)

    def can_equip_armor(self, class_id: int, armor_type: str) -> bool:
        """Verifica si una clase puede equipar un tipo de armadura.

        NOTA: Este método existe pero NO se usa. Siguiendo comportamiento VB6 original,
        cualquier clase puede equipar cualquier item. Los modificadores de clase en
        classes_balance.toml ya balancean el uso inadecuado.

        Args:
            class_id: ID de la clase.
            armor_type: Tipo de armadura.

        Returns:
            True si puede equipar, False en caso contrario.
        """
        character_class = self.get_class(class_id)
        if not character_class:
            return False

        return character_class.can_equip_armor(armor_type)

    def get_initial_skills(self, class_id: int) -> dict[str, int]:
        """Obtiene las skills iniciales de una clase.

        Args:
            class_id: ID de la clase.

        Returns:
            Diccionario con skills iniciales, o vacío si la clase no existe.
        """
        character_class = self.get_class(class_id)
        if character_class:
            return character_class.initial_skills.copy()

        logger.warning("Clase %d no encontrada, sin skills iniciales", class_id)
        return {}

    def validate_class(self, class_id: int) -> bool:
        """Verifica si una clase existe.

        Args:
            class_id: ID de la clase a verificar.

        Returns:
            True si existe, False en caso contrario.
        """
        return self.catalog.has_class(class_id)


# Instancia global del servicio
_class_service: ClassService | None = None


def get_class_service(data_dir: Path | None = None) -> ClassService:
    """Retorna la instancia global del servicio de clases.

    Args:
        data_dir: Directorio de datos (solo usado en primera llamada).

    Returns:
        Instancia del servicio de clases.
    """
    global _class_service  # noqa: PLW0603
    if _class_service is None:
        _class_service = ClassService(data_dir)
    return _class_service
