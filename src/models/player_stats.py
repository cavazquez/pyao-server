"""Modelo de estadísticas de jugador."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerStats:
    """Estadísticas del jugador (inmutable).

    Attributes:
        max_hp: HP máximo.
        min_hp: HP actual.
        max_mana: Mana máximo.
        min_mana: Mana actual.
        max_sta: Stamina máxima.
        min_sta: Stamina actual.
        gold: Oro del jugador.
        level: Nivel del jugador.
        elu: Experiencia para subir de nivel.
        experience: Experiencia total acumulada.
    """

    max_hp: int = 100
    min_hp: int = 100
    max_mana: int = 100
    min_mana: int = 100
    max_sta: int = 100
    min_sta: int = 100
    gold: int = 0
    level: int = 1
    elu: int = 300
    experience: int = 0

    @property
    def is_alive(self) -> bool:
        """Verifica si el jugador está vivo."""
        return self.min_hp > 0

    @property
    def hp_percent(self) -> float:
        """Porcentaje de HP actual."""
        if self.max_hp == 0:
            return 0.0
        return self.min_hp / self.max_hp

    @property
    def mana_percent(self) -> float:
        """Porcentaje de mana actual."""
        if self.max_mana == 0:
            return 0.0
        return self.min_mana / self.max_mana

    @property
    def stamina_percent(self) -> float:
        """Porcentaje de stamina actual."""
        if self.max_sta == 0:
            return 0.0
        return self.min_sta / self.max_sta

    def to_dict(self) -> dict[str, int]:
        """Convierte a diccionario para compatibilidad.

        Returns:
            Diccionario con todas las estadísticas.
        """
        return {
            "max_hp": self.max_hp,
            "min_hp": self.min_hp,
            "max_mana": self.max_mana,
            "min_mana": self.min_mana,
            "max_sta": self.max_sta,
            "min_sta": self.min_sta,
            "gold": self.gold,
            "level": self.level,
            "elu": self.elu,
            "experience": self.experience,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, int | str]) -> PlayerStats:
        """Crea instancia desde diccionario Redis.

        Args:
            data: Diccionario con valores de Redis.

        Returns:
            Nueva instancia de PlayerStats.
        """
        return cls(
            max_hp=int(data.get("max_hp", 100)),
            min_hp=int(data.get("hp", data.get("min_hp", 100))),
            max_mana=int(data.get("max_mana", 100)),
            min_mana=int(data.get("min_mana", 100)),
            max_sta=int(data.get("max_sta", 100)),
            min_sta=int(data.get("min_sta", 100)),
            gold=int(data.get("gold", 0)),
            level=int(data.get("level", 1)),
            elu=int(data.get("elu", 300)),
            experience=int(data.get("experience", 0)),
        )


@dataclass(frozen=True, slots=True)
class PlayerAttributes:
    """Atributos del jugador (inmutable).

    Attributes:
        strength: Fuerza.
        agility: Agilidad.
        intelligence: Inteligencia.
        charisma: Carisma.
        constitution: Constitución.
    """

    strength: int = 10
    agility: int = 10
    intelligence: int = 10
    charisma: int = 10
    constitution: int = 10

    def to_dict(self) -> dict[str, int]:
        """Convierte a diccionario para compatibilidad.

        Returns:
            Diccionario con todos los atributos.
        """
        return {
            "strength": self.strength,
            "agility": self.agility,
            "intelligence": self.intelligence,
            "charisma": self.charisma,
            "constitution": self.constitution,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, int | str]) -> PlayerAttributes:
        """Crea instancia desde diccionario Redis.

        Args:
            data: Diccionario con valores de Redis.

        Returns:
            Nueva instancia de PlayerAttributes.
        """
        return cls(
            strength=int(data.get("strength", 10)),
            agility=int(data.get("agility", 10)),
            intelligence=int(data.get("intelligence", 10)),
            charisma=int(data.get("charisma", 10)),
            constitution=int(data.get("constitution", 10)),
        )
