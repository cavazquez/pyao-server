"""Handler especializado para creación de atributos, stats e inventario del personaje."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.repositories.inventory_repository import InventoryRepository
from src.services.game.class_service import get_class_service

if TYPE_CHECKING:
    from src.repositories.player_repository import PlayerRepository
    from src.services.game.balance_service import BalanceService

logger = logging.getLogger(__name__)

# Constantes de creación de personaje desde configuración
HP_PER_CON = ConfigManager.as_int(
    config_manager.get("game.character.hp_per_con", 10),
    default=10,
)
MANA_PER_INT = ConfigManager.as_int(
    config_manager.get("game.character.mana_per_int", 10),
    default=10,
)
INITIAL_GOLD = ConfigManager.as_int(
    config_manager.get("game.character.initial_gold", 0),
    default=0,
)
INITIAL_ELU = ConfigManager.as_int(
    config_manager.get("game.character.initial_elu", 300),
    default=300,
)


class CreateAccountCharacterHandler:
    """Handler especializado para creación de atributos, stats e inventario del personaje."""

    def __init__(self, player_repo: PlayerRepository) -> None:
        """Inicializa el handler de creación de personaje.

        Args:
            player_repo: Repositorio de jugadores.
        """
        self.player_repo = player_repo

    def get_dice_attributes_from_session(
        self, session_data: dict[str, dict[str, int] | int | str] | None
    ) -> dict[str, int] | None:
        """Obtiene atributos de dados desde la sesión si existen.

        Args:
            session_data: Datos de sesión.

        Returns:
            Diccionario con atributos de dados o None si no hay datos en sesión.
        """
        if session_data and "dice_attributes" in session_data:
            stats_data = session_data["dice_attributes"]
            if isinstance(stats_data, dict):
                logger.info("Atributos de dados recuperados de sesión: %s", stats_data)
                return stats_data

        logger.warning("No se encontraron atributos de dados en la sesión")
        return None

    async def create_attributes_and_stats(
        self,
        user_id: int,
        stats_data: dict[str, int] | None,
        race_name: str,
        class_name: str,
        class_id: int,
        balance_service: BalanceService,
    ) -> tuple[dict[str, int] | None, dict[str, int] | None, dict[str, int] | None]:
        """Crea atributos finales y estadísticas iniciales del personaje.

        Args:
            user_id: ID del usuario.
            stats_data: Atributos de dados.
            race_name: Nombre de la raza.
            class_name: Nombre de la clase.
            class_id: ID de la clase.
            balance_service: Servicio de balance.

        Returns:
            Tupla (base_attributes, final_attributes, initial_stats) cuando
            hay datos de dados. Si stats_data es None, devuelve
            (None, None, None) y no modifica atributos ni stats.
        """
        if stats_data is None:
            return (None, None, None)

        # Obtener atributos base de dados
        dice_attributes: dict[str, int] = {
            "strength": stats_data.get("strength", 10),
            "agility": stats_data.get("agility", 10),
            "intelligence": stats_data.get("intelligence", 10),
            "charisma": stats_data.get("charisma", 10),
            "constitution": stats_data.get("constitution", 10),
        }

        # Aplicar atributos base de clase
        class_service = get_class_service()
        base_attributes = class_service.apply_class_base_attributes(dice_attributes, class_id)

        # Aplicar modificadores raciales
        final_attributes = balance_service.apply_racial_modifiers(
            base_attributes,
            race_name,
        )

        await self.player_repo.set_attributes(user_id=user_id, **final_attributes)
        logger.info(
            "Atributos guardados en Redis para user_id %d (base=%s, final=%s)",
            user_id,
            base_attributes,
            final_attributes,
        )

        constitution = final_attributes.get("constitution", 10)
        intelligence = final_attributes.get("intelligence", 10)
        base_hp = constitution * HP_PER_CON
        max_hp = balance_service.calculate_max_health(base_hp, class_name)
        initial_stats: dict[str, int] = {
            "max_hp": max_hp,
            "min_hp": max_hp,
            "max_mana": intelligence * MANA_PER_INT,
            "min_mana": intelligence * MANA_PER_INT,
            "max_sta": 100,
            "min_sta": 100,
            "gold": INITIAL_GOLD,
            "level": 1,
            "elu": INITIAL_ELU,
            "experience": 0,
        }
        await self.player_repo.set_stats(user_id=user_id, **initial_stats)
        logger.info(
            "Estadísticas iniciales creadas para user_id %d: HP=%d MANA=%d",
            user_id,
            initial_stats["max_hp"],
            initial_stats["max_mana"],
        )

        # Aplicar skills iniciales por clase
        initial_skills = class_service.get_initial_skills(class_id)
        if initial_skills:
            await self.player_repo.set_skills(user_id=user_id, **initial_skills)
            logger.info(
                "Skills iniciales asignadas para user_id %d (clase %s): %s",
                user_id,
                class_name,
                initial_skills,
            )

        return (base_attributes, final_attributes, initial_stats)

    async def create_initial_inventory(self, user_id: int) -> None:
        """Crea el inventario inicial del personaje.

        Args:
            user_id: ID del usuario.
        """
        inventory_repo = InventoryRepository(self.player_repo.redis)

        # Pociones - 30 de cada tipo (6 tipos principales)
        # Poción Amarilla (Agilidad)
        await inventory_repo.add_item(user_id, item_id=36, quantity=30)
        # Poción Azul (Mana)
        await inventory_repo.add_item(user_id, item_id=37, quantity=30)
        # Poción Roja (HP/Vida)
        await inventory_repo.add_item(user_id, item_id=38, quantity=30)
        # Poción Verde (Fuerza)
        await inventory_repo.add_item(user_id, item_id=39, quantity=30)
        # Poción Violeta (Cura Veneno)
        await inventory_repo.add_item(user_id, item_id=166, quantity=30)
        # Poción Negra (Invisible)
        await inventory_repo.add_item(user_id, item_id=645, quantity=30)

        # Comida y bebida
        await inventory_repo.add_item(user_id, item_id=3, quantity=10)  # 10 Manzanas
        await inventory_repo.add_item(user_id, item_id=4, quantity=10)  # 10 Aguas

        # Equipamiento inicial
        await inventory_repo.add_item(user_id, item_id=11, quantity=1)  # 1 Daga
        # Armadura inicial (Newbie)
        await inventory_repo.add_item(user_id, item_id=1073, quantity=1)  # Armadura de Aprendiz

        # Herramientas de trabajo (Newbie)
        await inventory_repo.add_item(user_id, item_id=561, quantity=1)  # Hacha de Leñador
        await inventory_repo.add_item(user_id, item_id=562, quantity=1)  # Piquete de Minero
        await inventory_repo.add_item(user_id, item_id=563, quantity=1)  # Caña de Pescar

        logger.info(
            "Inventario inicial creado para user_id %d (30 pociones de cada tipo + equipamiento)",
            user_id,
        )
