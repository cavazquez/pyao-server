"""Orquestador principal de inicialización del servidor."""

import logging
import time
from pathlib import Path

from src.core.dependency_container import DependencyContainer
from src.core.game_tick_initializer import GameTickInitializer
from src.core.redis_initializer import RedisInitializer
from src.core.repository_initializer import RepositoryInitializer
from src.core.service_initializer import ServiceInitializer
from src.game.map_manager import MapManager
from src.network.session_manager import SessionManager
from src.repositories.ground_items_repository import GroundItemsRepository

logger = logging.getLogger(__name__)


class ServerInitializer:
    """Orquestador principal de inicialización del servidor."""

    @staticmethod
    def _load_map_tiles(map_manager: MapManager) -> None:
        """Carga tiles bloqueados de todos los mapas.

        Args:
            map_manager: Instancia del MapManager.
        """
        logger.info("Iniciando carga de mapas...")
        start_time = time.perf_counter()

        map_data_dir = Path("map_data")
        if not map_data_dir.exists():
            logger.warning("⚠️  Directorio map_data/ no encontrado")
            return

        loaded_maps = 0
        ranges = [
            (1, 51, "metadata_001-051.json"),
            (52, 101, "metadata_052-101.json"),
            (102, 151, "metadata_102-151.json"),
            (152, 201, "metadata_152-201.json"),
            (202, 251, "metadata_202-251.json"),
            (252, 290, "metadata_252-290.json"),
        ]

        for start_id, end_id, filename in ranges:
            metadata_path = map_data_dir / filename
            if not metadata_path.exists():
                continue

            for map_id in range(start_id, end_id + 1):
                map_manager.load_map_data(map_id, metadata_path)
                loaded_maps += 1

        elapsed_time = time.perf_counter() - start_time
        logger.info(
            "✓ %d mapas cargados con tiles bloqueados en %.3f segundos",
            loaded_maps,
            elapsed_time,
        )

    @staticmethod
    async def initialize_all() -> tuple[DependencyContainer, str, int]:
        """Inicializa todos los componentes del servidor.

        Returns:
            Tupla con (DependencyContainer, host, port)
        """
        logger.info("=" * 60)
        logger.info("INICIANDO SERVIDOR ARGENTUM ONLINE")
        logger.info("=" * 60)

        # 1. Inicializar Redis y datos
        redis_client = await RedisInitializer.initialize()

        # Obtener configuración de host y port desde Redis
        host = await redis_client.get_server_host()
        port = await redis_client.get_server_port()
        logger.info("✓ Configuración cargada: %s:%d", host, port)

        # 2. Inicializar repositorios
        repo_init = RepositoryInitializer(redis_client)
        repositories = repo_init.initialize_all()

        # 3. Inicializar MapManager y ground items
        ground_items_repo = GroundItemsRepository(redis_client)
        map_manager = MapManager(ground_items_repo)
        logger.info("✓ MapManager inicializado")

        # Cargar tiles bloqueados y datos de todos los mapas
        ServerInitializer._load_map_tiles(map_manager)

        # Cargar ground items del mapa principal
        await map_manager.load_ground_items(1)
        logger.info("✓ Ground items cargados para mapa 1")

        # 4. Inicializar servicios
        service_init = ServiceInitializer(repositories, map_manager)
        services = await service_init.initialize_all()

        # 5. Inicializar Game Tick y efectos
        game_tick_init = GameTickInitializer(
            repositories["player_repo"],
            repositories["server_repo"],
            map_manager,
            services["npc_service"],
            services["npc_ai_service"],
            services["stamina_service"],
        )
        game_tick = await game_tick_init.initialize()

        # 6. Crear SessionManager
        session_manager = SessionManager()
        logger.info("✓ SessionManager inicializado")

        # 7. Crear DependencyContainer
        container = DependencyContainer(
            # Infraestructura
            redis_client=redis_client,
            # Repositorios
            player_repo=repositories["player_repo"],
            account_repo=repositories["account_repo"],
            inventory_repo=repositories["inventory_repo"],
            equipment_repo=repositories["equipment_repo"],
            merchant_repo=repositories["merchant_repo"],
            bank_repo=repositories["bank_repo"],
            door_repo=repositories["door_repo"],
            npc_repo=repositories["npc_repo"],
            clan_repo=repositories["clan_repo"],
            party_repo=repositories["party_repo"],
            spellbook_repo=repositories["spellbook_repo"],
            ground_items_repo=ground_items_repo,
            server_repo=repositories["server_repo"],
            # Servicios
            combat_service=services["combat_service"],
            commerce_service=services["commerce_service"],
            spell_service=services["spell_service"],
            npc_service=services["npc_service"],
            npc_ai_service=services["npc_ai_service"],
            npc_death_service=services["npc_death_service"],
            npc_respawn_service=services["npc_respawn_service"],
            npc_world_manager=services["npc_world_manager"],
            loot_table_service=services["loot_table_service"],
            map_resources_service=services["map_resources_service"],
            door_service=services["door_service"],
            broadcast_service=services["broadcast_service"],
            stamina_service=services["stamina_service"],
            player_map_service=services["player_map_service"],
            party_service=services["party_service"],
            clan_service=services["clan_service"],
            trade_service=services["trade_service"],
            summon_service=services["summon_service"],
            # Managers
            map_manager=map_manager,
            game_tick=game_tick,
            session_manager=session_manager,
            # Catálogos
            npc_catalog=services["npc_catalog"],
            spell_catalog=services["spell_catalog"],
            item_catalog=services["item_catalog"],
        )

        logger.info("=" * 60)
        logger.info("✓ SERVIDOR INICIALIZADO CORRECTAMENTE")
        logger.info("=" * 60)

        return container, host, port
