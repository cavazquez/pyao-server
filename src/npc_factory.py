"""Factory para crear NPCs con configuraciones predefinidas."""

import uuid

from src.npc import NPC


class NPCFactory:
    """Factory para crear instancias de NPCs con configuraciones predefinidas.

    Centraliza la creación de NPCs para evitar duplicación de código
    y facilitar el mantenimiento de stats y configuraciones.
    """

    @staticmethod
    def _create_hostile_base(
        npc_id: int,
        name: str,
        body_id: int,
        hp: int,
        level: int,
        x: int,
        y: int,
        map_id: int,
        char_index: int,
        heading: int = 3,
        head_id: int = 0,
        description: str = "",
        respawn_time: int = 60,
        respawn_time_max: int = 120,
        gold_min: int = 5,
        gold_max: int = 20,
    ) -> NPC:
        """Crea un NPC hostil base con configuración común.

        Args:
            npc_id: ID del tipo de NPC.
            name: Nombre del NPC.
            body_id: ID del sprite del cuerpo.
            hp: HP máximo.
            level: Nivel del NPC.
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.
            heading: Dirección (1-4).
            head_id: ID del sprite de cabeza (0 = sin cabeza).
            description: Descripción del NPC.
            respawn_time: Tiempo mínimo de respawn en segundos.
            respawn_time_max: Tiempo máximo de respawn en segundos.
            gold_min: Oro mínimo que dropea.
            gold_max: Oro máximo que dropea.

        Returns:
            Instancia de NPC configurada.
        """
        return NPC(
            npc_id=npc_id,
            char_index=char_index,
            instance_id=str(uuid.uuid4()),
            map_id=map_id,
            x=x,
            y=y,
            heading=heading,
            name=name,
            description=description,
            body_id=body_id,
            head_id=head_id,
            hp=hp,
            max_hp=hp,
            level=level,
            is_hostile=True,
            is_attackable=True,
            is_merchant=False,
            is_banker=False,
            movement_type="random",
            respawn_time=respawn_time,
            respawn_time_max=respawn_time_max,
            gold_min=gold_min,
            gold_max=gold_max,
        )

    @staticmethod
    def _create_friendly_base(
        npc_id: int,
        name: str,
        body_id: int,
        x: int,
        y: int,
        map_id: int,
        char_index: int,
        heading: int = 3,
        head_id: int = 1,
        description: str = "",
        is_merchant: bool = False,
        is_banker: bool = False,
    ) -> NPC:
        """Crea un NPC amigable base con configuración común.

        Args:
            npc_id: ID del tipo de NPC.
            name: Nombre del NPC.
            body_id: ID del sprite del cuerpo.
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.
            heading: Dirección (1-4).
            head_id: ID del sprite de cabeza.
            description: Descripción del NPC.
            is_merchant: ¿Es mercader?
            is_banker: ¿Es banquero?

        Returns:
            Instancia de NPC configurada.
        """
        return NPC(
            npc_id=npc_id,
            char_index=char_index,
            instance_id=str(uuid.uuid4()),
            map_id=map_id,
            x=x,
            y=y,
            heading=heading,
            name=name,
            description=description,
            body_id=body_id,
            head_id=head_id,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=False,
            is_merchant=is_merchant,
            is_banker=is_banker,
            movement_type="static",
            respawn_time=0,  # NPCs amigables no respawnean
            respawn_time_max=0,
            gold_min=0,
            gold_max=0,
        )

    # ==================== NPCs Hostiles ====================

    @staticmethod
    def create_goblin(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Goblin - Criatura débil pero común.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Goblin.
        """
        return NPCFactory._create_hostile_base(
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=100,
            level=5,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un goblin pequeño y malicioso",
            gold_min=10,
            gold_max=50,
        )

    @staticmethod
    def create_lobo(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Lobo - Criatura rápida y agresiva.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Lobo.
        """
        return NPCFactory._create_hostile_base(
            npc_id=7,
            name="Lobo",
            body_id=138,
            hp=80,
            level=3,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un lobo salvaje y hambriento",
            gold_min=5,
            gold_max=20,
        )

    @staticmethod
    def create_orco(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Orco - Guerrero fuerte con buen equipo.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Orco.
        """
        return NPCFactory._create_hostile_base(
            npc_id=4,
            name="Orco",
            body_id=8,
            hp=200,
            level=10,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un orco brutal y poderoso",
            gold_min=20,
            gold_max=100,
        )

    @staticmethod
    def create_arana(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea una Araña Gigante - Criatura venenosa peligrosa.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Araña Gigante.
        """
        return NPCFactory._create_hostile_base(
            npc_id=8,
            name="Araña Gigante",
            body_id=149,
            hp=150,
            level=8,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Una araña gigante y venenosa",
            gold_min=15,
            gold_max=75,
        )

    # ==================== NPCs Amigables ====================

    @staticmethod
    def create_comerciante(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Comerciante - Mercader que vende items.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Comerciante.
        """
        return NPCFactory._create_friendly_base(
            npc_id=2,
            name="Comerciante",
            body_id=501,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un comerciante amigable",
            is_merchant=True,
        )

    @staticmethod
    def create_banquero(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Banquero - Gestiona la bóveda del jugador.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Banquero.
        """
        return NPCFactory._create_friendly_base(
            npc_id=5,
            name="Banquero",
            body_id=504,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un banquero confiable",
            is_banker=True,
        )

    @staticmethod
    def create_guardia(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Guardia Real - Protector de la ciudad.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Guardia Real.
        """
        return NPCFactory._create_friendly_base(
            npc_id=3,
            name="Guardia Real",
            body_id=502,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un guardia vigilante",
        )
