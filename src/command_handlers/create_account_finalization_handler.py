"""Handler especializado para finalización de creación de cuenta (login automático y logging)."""

import logging
from typing import TYPE_CHECKING, cast

from src.command_handlers.login_handler import LoginCommandHandler
from src.game.character_constants import (
    GENDER_ID_TO_NAME,
    HOME_ID_TO_NAME,
    RACE_ID_TO_NAME,
)
from src.tasks.player.task_login import TaskLogin

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.services.map.player_map_service import PlayerMapService

logger = logging.getLogger(__name__)


class CreateAccountFinalizationHandler:
    """Handler especializado para finalización de creación de cuenta."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        map_manager: MapManager | None,
        server_repo: ServerRepository | None,
        spellbook_repo: SpellbookRepository | None,
        spell_catalog: SpellCatalog | None,
        equipment_repo: EquipmentRepository | None,
        player_map_service: PlayerMapService | None,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None,
    ) -> None:
        """Inicializa el handler de finalización.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            server_repo: Repositorio del servidor.
            spellbook_repo: Repositorio de libro de hechizos.
            spell_catalog: Catálogo de hechizos.
            equipment_repo: Repositorio de equipamiento.
            player_map_service: Servicio de mapas de jugador.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.server_repo = server_repo
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.equipment_repo = equipment_repo
        self.player_map_service = player_map_service
        self.message_sender = message_sender
        self.session_data = session_data

    async def execute_auto_login(self, username: str, password: str) -> None:
        """Ejecuta login automático después de crear la cuenta.

        Args:
            username: Nombre de usuario.
            password: Contraseña.
        """
        # Cast session_data para compatibilidad con LoginCommandHandler
        session_data_cast = cast("dict[str, dict[str, int]] | None", self.session_data)

        login_handler = LoginCommandHandler(
            player_repo=self.player_repo,
            account_repo=self.account_repo,
            map_manager=self.map_manager,
            server_repo=self.server_repo,
            spellbook_repo=self.spellbook_repo,
            spell_catalog=self.spell_catalog,
            equipment_repo=self.equipment_repo,
            player_map_service=self.player_map_service,
            message_sender=self.message_sender,
            session_data=session_data_cast,
        )

        login_task = TaskLogin(
            data=b"\x03",  # Dummy data para TaskLogin
            message_sender=self.message_sender,
            login_handler=login_handler,
            session_data=session_data_cast,
        )
        await login_task.execute_with_credentials(username, password)

    def log_character_summary(
        self,
        user_id: int,
        username: str,
        char_data: dict[str, int] | None,
        class_name: str,
        base_attributes: dict[str, int] | None,
        final_attributes: dict[str, int] | None,
        initial_stats: dict[str, int] | None,
        stats_data: dict[str, int] | None,
    ) -> None:
        """Loguea un resumen completo del personaje creado.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            char_data: Datos del personaje.
            class_name: Nombre de la clase.
            base_attributes: Atributos base.
            final_attributes: Atributos finales.
            initial_stats: Estadísticas iniciales.
            stats_data: Atributos de dados.
        """
        race_value = char_data.get("race") if char_data is not None else None
        gender_value = char_data.get("gender") if char_data is not None else None
        head_value = char_data.get("head") if char_data is not None else None
        home_value = char_data.get("home") if char_data is not None else None
        job_value = char_data.get("job") if char_data is not None else None

        race_name = RACE_ID_TO_NAME.get(race_value or 0, "Desconocida")
        gender_name = GENDER_ID_TO_NAME.get(gender_value or 0, "Desconocido")
        home_name = HOME_ID_TO_NAME.get(home_value or 0, "Desconocido")

        logger.info(
            (
                "Personaje creado: user_id=%d, username=%s, raza=%s (%s), clase=%s (job=%s), "
                "gender=%s (%s), head=%s, home=%s (%s), atributos_base=%s, "
                "atributos_finales=%s, stats_iniciales=%s, dice_attributes=%s"
            ),
            user_id,
            username,
            race_value,
            race_name,
            class_name,
            job_value,
            gender_value,
            gender_name,
            head_value,
            home_value,
            home_name,
            base_attributes,
            final_attributes,
            initial_stats,
            stats_data,
        )
