"""Handler especializado para ejecución de trabajo con click."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.constants.items import ResourceItemID

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)

# Tipos de habilidades de trabajo (enum Skill del cliente)
SKILL_TALAR = 9
SKILL_PESCA = 12
SKILL_MINERIA = 13

# Constantes de experiencia (desde configuración)
EXP_LENA = ConfigManager.as_int(config_manager.get("game.work.exp_wood", 10))
EXP_MINERAL = ConfigManager.as_int(config_manager.get("game.work.exp_mineral", 15))
EXP_PESCADO = ConfigManager.as_int(config_manager.get("game.work.exp_fish", 12))


class WorkLeftClickExecutionHandler:
    """Handler especializado para ejecución de trabajo con click."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de ejecución.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_resources: Servicio de recursos del mapa.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender

    async def try_work_at_position(
        self,
        user_id: int,
        map_id: int,
        target_x: int,
        target_y: int,
        skill_type: int,
        has_hacha: bool,
        has_pico: bool,
        has_cana: bool,
    ) -> tuple[str, int, int, int, str, int, bool] | None:
        """Intenta trabajar en una posición específica.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa.
            target_x: Coordenada X del click.
            target_y: Coordenada Y del click.
            skill_type: Tipo de habilidad (9=Talar, 12=Pesca, 13=Minería).
            has_hacha: Si tiene hacha.
            has_pico: Si tiene pico.
            has_cana: Si tiene caña.

        Returns:
            Tupla (nombre_recurso, item_id, cantidad, slot, skill_nombre, exp_ganada, subio_nivel)
            si se pudo trabajar, None si no.
        """
        if not self.map_resources:
            return None

        # Verificar recursos según el tipo de skill
        if (
            skill_type == SKILL_TALAR
            and has_hacha
            and self.map_resources.has_tree(map_id, target_x, target_y)
        ):
            return await self._handle_chop(user_id)

        if (
            skill_type == SKILL_MINERIA
            and has_pico
            and self.map_resources.has_mine(map_id, target_x, target_y)
        ):
            return await self._handle_mine(user_id)

        if (
            skill_type == SKILL_PESCA
            and has_cana
            and self.map_resources.has_water(map_id, target_x, target_y)
        ):
            return await self._handle_fish(user_id)

        return None

    async def _handle_chop(self, user_id: int) -> tuple[str, int, int, int, str, int, bool] | None:
        """Maneja la tala de árboles.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla con datos del trabajo realizado o None si falla.
        """
        slots = await self.inventory_repo.add_item(user_id, item_id=ResourceItemID.LENA, quantity=5)
        if slots:
            # Dar experiencia en talar
            _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                user_id, "talar", EXP_LENA
            )
            return (
                "Leña",
                ResourceItemID.LENA,
                5,
                slots[0][0],
                "Talar",
                EXP_LENA,
                leveled_up,
            )
        return None

    async def _handle_mine(self, user_id: int) -> tuple[str, int, int, int, str, int, bool] | None:
        """Maneja la minería.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla con datos del trabajo realizado o None si falla.
        """
        slots = await self.inventory_repo.add_item(
            user_id, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
        )
        if slots:
            # Dar experiencia en minería
            _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                user_id, "mineria", EXP_MINERAL
            )
            return (
                "Mineral de Hierro",
                ResourceItemID.MINERAL_HIERRO,
                3,
                slots[0][0],
                "Minería",
                EXP_MINERAL,
                leveled_up,
            )
        return None

    async def _handle_fish(self, user_id: int) -> tuple[str, int, int, int, str, int, bool] | None:
        """Maneja la pesca.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla con datos del trabajo realizado o None si falla.
        """
        slots = await self.inventory_repo.add_item(
            user_id, item_id=ResourceItemID.PESCADO, quantity=2
        )
        if slots:
            # Dar experiencia en pesca
            _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                user_id, "pesca", EXP_PESCADO
            )
            return (
                "Pescado",
                ResourceItemID.PESCADO,
                2,
                slots[0][0],
                "Pesca",
                EXP_PESCADO,
                leveled_up,
            )
        return None
