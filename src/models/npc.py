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
    is_merchant: bool = False  # ¿Es un mercader? (abre ventana de comercio)
    is_banker: bool = False  # ¿Es un banquero? (abre ventana de banco)
    movement_type: str = "static"  # "static", "patrol", "random"
    respawn_time: int = 0  # Tiempo mínimo de respawn en segundos
    respawn_time_max: int = 0  # Tiempo máximo de respawn en segundos (aleatorio entre min y max)

    # Loot
    gold_min: int = 0
    gold_max: int = 0

    # Combat
    last_attack_time: float = 0.0  # Timestamp del último ataque
    attack_damage: int = 10  # Daño base del NPC
    attack_cooldown: float = 3.0  # Segundos entre ataques
    aggro_range: int = 8  # Rango de detección/agresión en tiles

    # Efectos visuales
    fx: int = 0  # FX ID al morir (one-shot)
    fx_loop: int = 0  # FX ID continuo (aura, loop infinito)

    # Estados/efectos
    paralyzed_until: float = 0.0  # Timestamp hasta cuando está paralizado (0 = no paralizado)
    poisoned_until: float = 0.0  # Timestamp hasta cuando está envenenado (0 = no envenenado)
    poisoned_by_user_id: int = 0  # ID del jugador que envenenó al NPC (0 = sistema/desconocido)
