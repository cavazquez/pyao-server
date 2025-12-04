"""Factory para creación de NPCs con configuraciones predefinidas."""

import uuid

from src.models.npc import NPC


class NPCFactory:
    """Factory para crear instancias de NPCs.

    Este factory crea NPCs basándose en parámetros configurables.
    Los parámetros típicamente provienen de archivos TOML (npcs/hostiles.toml, etc.)
    y son procesados por NPCService.
    """

    @staticmethod
    def create_hostile(
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
        attack_damage: int = 10,
        attack_cooldown: float = 3.0,
        aggro_range: int = 8,
        fx: int = 0,
        fx_loop: int = 0,
    ) -> NPC:
        """Crea un NPC hostil genérico con configuración completa.

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
            attack_damage: Daño base del ataque.
            attack_cooldown: Segundos entre ataques.
            aggro_range: Tiles de detección/persecución.
            fx: ID de efecto visual al morir (one-shot).
            fx_loop: ID de efecto visual continuo (aura, loop infinito).

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
            attack_damage=attack_damage,
            attack_cooldown=attack_cooldown,
            aggro_range=aggro_range,
            fx=fx,
            fx_loop=fx_loop,
        )

    @staticmethod
    def create_friendly(
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
        """Crea un NPC amigable genérico con configuración completa.

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
        return NPCFactory.create_hostile(
            npc_id=1,
            name="Goblin",
            body_id=14,
            hp=110,
            level=5,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un goblin pequeño y malicioso",
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
            attack_damage=8,
            attack_cooldown=2.5,
            aggro_range=6,
            fx=5,  # Sangre al morir
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
        return NPCFactory.create_hostile(
            npc_id=7,
            name="Lobo",
            body_id=10,
            hp=80,
            level=3,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un lobo salvaje y hambriento",
            respawn_time=20,
            respawn_time_max=40,
            gold_min=5,
            gold_max=20,
            attack_damage=6,
            attack_cooldown=2.0,
            aggro_range=7,
            fx=5,  # Sangre al morir
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
        return NPCFactory.create_hostile(
            npc_id=4,
            name="Orco",
            body_id=185,
            hp=350,
            level=10,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un orco brutal y poderoso",
            respawn_time=60,
            respawn_time_max=120,
            gold_min=20,
            gold_max=114,
            attack_damage=35,
            attack_cooldown=3.0,
            aggro_range=10,
            fx=5,  # Sangre al morir
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
        return NPCFactory.create_hostile(
            npc_id=8,
            name="Araña Gigante",
            body_id=42,
            hp=150,
            level=8,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Una araña gigante y venenosa",
            gold_min=15,
            gold_max=75,
            attack_damage=12,
            attack_cooldown=2.5,
            aggro_range=8,
            fx=10,  # Veneno al morir
            fx_loop=15,  # Aura venenosa
        )

    @staticmethod
    def create_serpiente(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea una Serpiente - Criatura venenosa muy rápida.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Serpiente.
        """
        return NPCFactory.create_hostile(
            npc_id=9,
            name="Serpiente",
            body_id=13,
            hp=22,
            level=2,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Una serpiente venenosa y sigilosa",
            gold_min=1,
            gold_max=10,
            attack_damage=1,
            attack_cooldown=1.5,
            aggro_range=5,
            fx=10,  # Veneno al morir
        )

    @staticmethod
    def create_dragon_rojo(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Dragón Rojo - Boss poderoso con tesoros.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Dragón Rojo.
        """
        return NPCFactory.create_hostile(
            npc_id=10,
            name="Dragón Rojo",
            body_id=41,
            hp=5000,
            level=50,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un dragón ancestral rojo, guardián de tesoros legendarios",
            respawn_time=600,  # 10 minutos
            respawn_time_max=900,  # 15 minutos
            gold_min=1000,
            gold_max=4700,
            attack_damage=300,
            attack_cooldown=4.0,
            aggro_range=15,
            fx=25,  # Explosión de fuego al morir
            fx_loop=20,  # Aura de fuego
        )

    @staticmethod
    def create_esqueleto(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Esqueleto - No-muerto común.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Esqueleto.
        """
        return NPCFactory.create_hostile(
            npc_id=11,
            name="Esqueleto",
            body_id=12,
            hp=50,
            level=5,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un guerrero caído que vaga eternamente",
            gold_min=8,
            gold_max=16,
            attack_damage=8,
            attack_cooldown=3.0,
            aggro_range=7,
            fx=5,  # Sangre al morir
        )

    @staticmethod
    def create_zombie(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Zombie - No-muerto resistente.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Zombie.
        """
        return NPCFactory.create_hostile(
            npc_id=12,
            name="Zombie",
            body_id=196,
            hp=250,
            level=8,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            head_id=507,  # Zombie tiene cabeza
            description="Un muerto viviente que busca carne fresca",
            gold_min=21,
            gold_max=50,
            attack_damage=12,
            attack_cooldown=2.5,
            aggro_range=6,
            fx=10,  # Veneno/descomposición al morir
        )

    @staticmethod
    def create_gran_dragon_rojo(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Gran Dragón Rojo - Boss final épico.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Gran Dragón Rojo.
        """
        return NPCFactory.create_hostile(
            npc_id=13,
            name="Gran Dragón Rojo",
            body_id=82,
            hp=200000,
            level=100,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="El más poderoso de todos los dragones, un boss legendario",
            respawn_time=3600,  # 1 hora
            respawn_time_max=7200,  # 2 horas
            gold_min=50000,
            gold_max=65000,
            attack_damage=5000,
            attack_cooldown=5.0,
            aggro_range=20,
            fx=25,  # Explosión de fuego al morir
            fx_loop=20,  # Aura de fuego
        )

    @staticmethod
    def create_ogro(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Ogro - Gigante brutal.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Ogro.
        """
        return NPCFactory.create_hostile(
            npc_id=14,
            name="Ogro",
            body_id=76,
            hp=2250,
            level=18,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un ogro brutal que aplasta todo a su paso",
            gold_min=200,
            gold_max=512,
            attack_damage=232,
            attack_cooldown=3.5,
            aggro_range=10,
            fx=5,  # Sangre al morir
        )

    @staticmethod
    def create_demonio(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Demonio - Criatura infernal poderosa.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Demonio.
        """
        return NPCFactory.create_hostile(
            npc_id=15,
            name="Demonio",
            body_id=83,
            hp=5000,
            level=25,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Una criatura infernal surgida de las profundidades",
            respawn_time=300,  # 5 minutos
            respawn_time_max=600,  # 10 minutos
            gold_min=500,
            gold_max=2000,
            attack_damage=400,
            attack_cooldown=4.0,
            aggro_range=15,
            fx=25,  # Explosión al morir
            fx_loop=50,  # Aura oscura
        )

    @staticmethod
    def create_murcielago(x: int, y: int, map_id: int, char_index: int) -> NPC:
        """Crea un Murciélago - Criatura muy débil y rápida.

        Args:
            x: Posición X.
            y: Posición Y.
            map_id: ID del mapa.
            char_index: CharIndex único.

        Returns:
            Instancia de Murciélago.
        """
        return NPCFactory.create_hostile(
            npc_id=16,
            name="Murciélago",
            body_id=9,
            hp=15,
            level=1,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un murciélago salvaje de las cavernas",
            respawn_time=10,
            respawn_time_max=20,
            gold_min=1,
            gold_max=70,
            attack_damage=4,
            attack_cooldown=1.0,
            aggro_range=4,
            fx=5,  # Sangre al morir
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
        return NPCFactory.create_friendly(
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
        return NPCFactory.create_friendly(
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
        return NPCFactory.create_friendly(
            npc_id=3,
            name="Guardia Real",
            body_id=502,
            x=x,
            y=y,
            map_id=map_id,
            char_index=char_index,
            description="Un guardia vigilante",
        )
