"""Orquestador principal de inicialización del servidor."""

import logging

from src.dependency_container import DependencyContainer
from src.game_tick_initializer import GameTickInitializer
from src.ground_items_repository import GroundItemsRepository
from src.map_manager import MapManager
from src.redis_initializer import RedisInitializer
from src.repository_initializer import RepositoryInitializer
from src.service_initializer import ServiceInitializer

logger = logging.getLogger(__name__)


class ServerInitializer:
    """Orquestador principal de inicialización del servidor."""

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
        )
        game_tick = await game_tick_init.initialize()

        # 6. Crear DependencyContainer
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
            npc_repo=repositories["npc_repo"],
            spellbook_repo=repositories["spellbook_repo"],
            ground_items_repo=ground_items_repo,
            server_repo=repositories["server_repo"],
            # Servicios
            combat_service=services["combat_service"],
            commerce_service=services["commerce_service"],
            spell_service=services["spell_service"],
            npc_service=services["npc_service"],
            npc_ai_service=services["npc_ai_service"],
            npc_respawn_service=services["npc_respawn_service"],
            loot_table_service=services["loot_table_service"],
            broadcast_service=services["broadcast_service"],
            # Managers
            map_manager=map_manager,
            game_tick=game_tick,
            # Catálogos
            npc_catalog=services["npc_catalog"],
            spell_catalog=services["spell_catalog"],
            item_catalog=services["item_catalog"],
        )

        logger.info("=" * 60)
        logger.info("✓ SERVIDOR INICIALIZADO CORRECTAMENTE")
        logger.info("=" * 60)

        return container, host, port
