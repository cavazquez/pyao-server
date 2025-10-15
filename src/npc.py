"""Modelo de datos para NPCs (Non-Player Characters)."""

from dataclasses import dataclass


@dataclass
class NPC:
    """Representa un NPC (Non-Player Character) en el mundo.

    Los NPCs son entidades controladas por el servidor que aparecen en el mapa
    junto con los jugadores. Usan el mismo protocolo de red (CHARACTER_CREATE)
    pero tienen CharIndex >= 10001.
    """

    # Identificación
    npc_id: int  # ID del tipo de NPC (del catálogo npcs.toml)
    char_index: int  # CharIndex único en el mapa (10001+)
    instance_id: str  # ID único de la instancia del NPC (UUID)

    # Posición
    map_id: int
    x: int
    y: int
    heading: int  # 1=Norte, 2=Este, 3=Sur, 4=Oeste

    # Datos del catálogo
    name: str
    description: str
    body_id: int  # ID del sprite del cuerpo
    head_id: int  # ID del sprite de la cabeza (0 si no tiene)

    # Stats
    hp: int
    max_hp: int
    level: int

    # Comportamiento
    is_hostile: bool  # ¿Ataca a jugadores?
    is_attackable: bool  # ¿Puede ser atacado?
    movement_type: str  # "static", "patrol", "random"
    respawn_time: int  # Segundos para respawn después de morir

    # Loot
    gold_min: int
    gold_max: int
