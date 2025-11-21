"""Modelos para el sistema de clases de personaje."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CharacterClass:
    """Representa una clase de personaje.

    Define atributos base y skills iniciales.

    NOTA: allowed_weapon_types y allowed_armor_types están definidos pero NO se validan.
    Siguiendo comportamiento VB6 original: cualquier clase puede equipar cualquier item.
    Los modificadores de clase en classes_balance.toml ya balancean el uso inadecuado.
    """

    class_id: int
    name: str
    base_strength: int
    base_agility: int
    base_intelligence: int
    base_charisma: int
    base_constitution: int
    allowed_weapon_types: list[str]  # Definido pero no usado (compatibilidad VB6)
    allowed_armor_types: list[str]  # Definido pero no usado (compatibilidad VB6)
    initial_skills: dict[str, int]
    description: str = ""

    @property
    def base_attributes(self) -> dict[str, int]:
        """Retorna los atributos base como diccionario.

        Returns:
            Diccionario con atributos base.
        """
        return {
            "strength": self.base_strength,
            "agility": self.base_agility,
            "intelligence": self.base_intelligence,
            "charisma": self.base_charisma,
            "constitution": self.base_constitution,
        }

    def can_equip_weapon(self, weapon_type: str) -> bool:
        """Verifica si la clase puede equipar un tipo de arma.

        NOTA: Este método existe pero NO se usa. Siguiendo comportamiento VB6 original,
        cualquier clase puede equipar cualquier item. Los modificadores de clase ya
        balancean el uso inadecuado.

        Args:
            weapon_type: Tipo de arma a verificar.

        Returns:
            True si puede equipar, False en caso contrario.
        """
        return weapon_type in self.allowed_weapon_types

    def can_equip_armor(self, armor_type: str) -> bool:
        """Verifica si la clase puede equipar un tipo de armadura.

        NOTA: Este método existe pero NO se usa. Siguiendo comportamiento VB6 original,
        cualquier clase puede equipar cualquier item. Los modificadores de clase ya
        balancean el uso inadecuado.

        Args:
            armor_type: Tipo de armadura a verificar.

        Returns:
            True si puede equipar, False en caso contrario.
        """
        return armor_type in self.allowed_armor_types


class ClassCatalog:
    """Catálogo de todas las clases disponibles."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el catálogo de clases.

        Args:
            data_dir: Directorio donde se encuentran los datos.
                     Si es None, usa "data" por defecto.
        """
        self.data_dir = data_dir or Path("data")
        self._classes: dict[int, CharacterClass] = {}
        self._classes_by_name: dict[str, CharacterClass] = {}
        self._load_classes()

    def _load_classes(self) -> None:
        """Carga las clases desde el archivo TOML."""
        logger = logging.getLogger(__name__)

        try:
            classes_file = self.data_dir / "classes.toml"

            if not classes_file.exists():
                logger.warning("No se encontró archivo de clases: %s", classes_file)
                return

            with classes_file.open("rb") as f:
                data = tomllib.load(f)

            classes_data = data.get("classes", {}).get("character_class", [])

            for class_data in classes_data:
                class_id = class_data.get("id")
                if not class_id:
                    continue

                character_class = CharacterClass(
                    class_id=class_id,
                    name=class_data.get("name", ""),
                    base_strength=class_data.get("base_strength", 10),
                    base_agility=class_data.get("base_agility", 10),
                    base_intelligence=class_data.get("base_intelligence", 10),
                    base_charisma=class_data.get("base_charisma", 10),
                    base_constitution=class_data.get("base_constitution", 10),
                    allowed_weapon_types=class_data.get("allowed_weapon_types", []),
                    allowed_armor_types=class_data.get("allowed_armor_types", []),
                    initial_skills=class_data.get("initial_skills", {}),
                    description=class_data.get("description", ""),
                )

                self._classes[class_id] = character_class
                self._classes_by_name[character_class.name] = character_class

            logger.info("Cargadas %d clases desde %s", len(self._classes), classes_file)

        except Exception:
            logger.exception("Error cargando clases desde TOML")

    def get_class(self, class_id: int) -> CharacterClass | None:
        """Obtiene una clase por ID.

        Args:
            class_id: ID de la clase.

        Returns:
            CharacterClass o None si no existe.
        """
        return self._classes.get(class_id)

    def get_class_by_name(self, name: str) -> CharacterClass | None:
        """Obtiene una clase por nombre.

        Args:
            name: Nombre de la clase.

        Returns:
            CharacterClass o None si no existe.
        """
        return self._classes_by_name.get(name)

    def get_all_classes(self) -> list[CharacterClass]:
        """Retorna todas las clases disponibles.

        Returns:
            Lista de todas las clases.
        """
        return list(self._classes.values())

    def has_class(self, class_id: int) -> bool:
        """Verifica si existe una clase con el ID dado.

        Args:
            class_id: ID de la clase a verificar.

        Returns:
            True si existe, False en caso contrario.
        """
        return class_id in self._classes
