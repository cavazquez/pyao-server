"""Servicio de lógica de negocio para NPCs."""

import asyncio
import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.npc import NPC
    from src.npc_catalog import NPCCatalog
    from src.npc_repository import NPCRepository

logger = logging.getLogger(__name__)


class NPCService:
    """Servicio para gestión de NPCs en el mundo."""

    def __init__(
        self,
        npc_repository: NPCRepository,
        npc_catalog: NPCCatalog,
        map_manager: MapManager,
    ) -> None:
        """Inicializa el servicio de NPCs.

        Args:
            npc_repository: Repositorio para operaciones de NPCs en Redis.
            npc_catalog: Catálogo de NPCs.
            map_manager: Gestor de mapas para trackear NPCs.
        """
        self.npc_repository = npc_repository
        self.npc_catalog = npc_catalog
        self.map_manager = map_manager
        self._next_char_index = 10001  # CharIndex inicial para NPCs

    async def initialize_world_npcs(self, spawns_path: str = "data/map_npcs.toml") -> None:
        """Inicializa todos los NPCs del mundo al iniciar el servidor.

        Lee la configuración de spawns desde map_npcs.toml y crea las instancias
        de NPCs en Redis y en el MapManager.

        Args:
            spawns_path: Ruta al archivo de configuración de spawns.
        """
        logger.info("Inicializando NPCs del mundo...")

        # Limpiar NPCs existentes (reinicio limpio)
        await self.npc_repository.clear_all_npcs()

        # Cargar configuración de spawns
        try:
            path = Path(spawns_path)
            if not path.exists():  # noqa: ASYNC240
                logger.warning("Archivo de spawns no encontrado: %s", spawns_path)
                return

            # Leer archivo de forma síncrona (solo se ejecuta una vez al inicio)
            with path.open("rb") as f:  # noqa: ASYNC230
                data = tomllib.load(f)

            if "spawn" not in data:
                logger.warning("No se encontró la sección [spawn] en %s", spawns_path)
                return

            spawned_count = 0
            for spawn_data in data["spawn"]:
                map_id = spawn_data.get("map_id")
                npc_id = spawn_data.get("npc_id")
                x = spawn_data.get("x")
                y = spawn_data.get("y")
                heading = spawn_data.get("heading", 3)  # Sur por defecto

                if map_id is None or npc_id is None or x is None or y is None:
                    logger.warning("Spawn incompleto, ignorando: %s", spawn_data)
                    continue

                # Spawnear el NPC
                npc = await self.spawn_npc(npc_id, map_id, x, y, heading)
                if npc:
                    spawned_count += 1

            logger.info("NPCs inicializados: %d spawns creados", spawned_count)

        except Exception:
            logger.exception("Error al inicializar NPCs del mundo desde %s", spawns_path)

    async def spawn_npc(
        self, npc_id: int, map_id: int, x: int, y: int, heading: int = 3
    ) -> NPC | None:
        """Spawnea un NPC en el mundo.

        Args:
            npc_id: ID del tipo de NPC (del catálogo).
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).

        Returns:
            Instancia de NPC creada o None si hay error.
        """
        # Obtener datos del catálogo
        npc_data = self.npc_catalog.get_npc_data(npc_id)
        if not npc_data:
            logger.error("NPC ID %d no encontrado en el catálogo", npc_id)
            return None

        # Asignar CharIndex único
        char_index = self._next_char_index
        self._next_char_index += 1

        # Crear instancia en Redis
        npc = await self.npc_repository.create_npc_instance(
            npc_id=npc_id,
            char_index=char_index,
            map_id=map_id,
            x=x,
            y=y,
            heading=heading,
            name=cast("str", npc_data.get("nombre", "NPC")),
            description=cast("str", npc_data.get("descripcion", "")),
            body_id=cast("int", npc_data.get("body_id", 0)),
            head_id=cast("int", npc_data.get("head_id", 0)),
            hp=cast("int", npc_data.get("hp_max", 100)),
            max_hp=cast("int", npc_data.get("hp_max", 100)),
            level=cast("int", npc_data.get("nivel", 1)),
            is_hostile=cast("bool", npc_data.get("es_hostil", False)),
            is_attackable=cast("bool", npc_data.get("es_atacable", True)),
            movement_type="static",  # Por ahora todos estáticos
            respawn_time=cast("int", npc_data.get("respawn_time", 0)),
            gold_min=cast("int", npc_data.get("oro_min", 0)),
            gold_max=cast("int", npc_data.get("oro_max", 0)),
        )

        # Agregar al MapManager
        self.map_manager.add_npc(map_id, npc)

        logger.debug(
            "NPC spawneado: %s (CharIndex: %d) en mapa %d (%d, %d)",
            npc.name,
            npc.char_index,
            map_id,
            x,
            y,
        )

        return npc

    async def send_npcs_to_player(self, message_sender: MessageSender, map_id: int) -> None:
        """Envía CHARACTER_CREATE de todos los NPCs del mapa al jugador.

        Args:
            message_sender: MessageSender del jugador.
            map_id: ID del mapa.
        """
        npcs = self.map_manager.get_npcs_in_map(map_id)

        for npc in npcs:
            await message_sender.send_character_create(
                char_index=npc.char_index,
                body=npc.body_id,
                head=npc.head_id,
                heading=npc.heading,
                x=npc.x,
                y=npc.y,
                weapon=0,  # NPCs no tienen armas visibles por ahora
                shield=0,
                helmet=0,
                fx=0,  # Sin efecto visual
                loops=0,
                name=npc.name,
            )
            # Delay entre NPCs para que el cliente Godot los procese correctamente
            await asyncio.sleep(0.05)

        logger.debug("Enviados %d NPCs al jugador en mapa %d", len(npcs), map_id)

    async def remove_npc(self, npc: NPC) -> None:
        """Elimina un NPC del mundo.

        Args:
            npc: Instancia del NPC a eliminar.
        """
        # Remover del MapManager
        self.map_manager.remove_npc(npc.map_id, npc.instance_id)

        # Remover de Redis
        await self.npc_repository.remove_npc(npc.instance_id)

        logger.debug("NPC eliminado: %s (CharIndex: %d)", npc.name, npc.char_index)

    async def move_npc(self, npc: NPC, new_x: int, new_y: int, new_heading: int) -> None:
        """Mueve un NPC a una nueva posición.

        Args:
            npc: Instancia del NPC.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            new_heading: Nueva dirección.
        """
        # Actualizar en Redis
        await self.npc_repository.update_npc_position(npc.instance_id, new_x, new_y, new_heading)

        # Actualizar en memoria
        npc.x = new_x
        npc.y = new_y
        npc.heading = new_heading

        # TODO: Broadcast CHARACTER_MOVE a jugadores cercanos

        logger.debug(
            "NPC movido: %s (CharIndex: %d) a (%d, %d)",
            npc.name,
            npc.char_index,
            new_x,
            new_y,
        )
