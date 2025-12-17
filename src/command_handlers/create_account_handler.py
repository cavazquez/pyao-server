"""Handler para comando de creación de cuenta."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.create_account_character_handler import (
    CreateAccountCharacterHandler,
)
from src.command_handlers.create_account_finalization_handler import (
    CreateAccountFinalizationHandler,
)
from src.command_handlers.create_account_validation_handler import (
    CreateAccountValidationHandler,
)
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.create_account_command import CreateAccountCommand
from src.services.game.balance_service import get_balance_service
from src.utils.password_utils import hash_password

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


class CreateAccountCommandHandler(CommandHandler):
    """Handler para comando de creación de cuenta (solo lógica de negocio)."""

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
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa el handler.

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
        self.message_sender = message_sender
        self.session_data = session_data or {}

        # Inicializar handlers especializados
        self.validation_handler = CreateAccountValidationHandler(
            message_sender=message_sender,
        )

        self.character_handler = CreateAccountCharacterHandler(
            player_repo=player_repo,
        )

        self.finalization_handler = CreateAccountFinalizationHandler(
            player_repo=player_repo,
            account_repo=account_repo,
            map_manager=map_manager,
            server_repo=server_repo,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            equipment_repo=equipment_repo,
            player_map_service=player_map_service,
            message_sender=message_sender,
            session_data=self.session_data,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de creación de cuenta (solo lógica de negocio).

        Args:
            command: Comando de creación de cuenta.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, CreateAccountCommand):
            return CommandResult.error("Comando inválido: se esperaba CreateAccountCommand")

        username = command.username
        password = command.password
        email = command.email
        char_data = command.char_data

        logger.info(
            "CreateAccountCommandHandler: intento de creación de cuenta para '%s'",
            username,
        )

        balance_service = get_balance_service()
        validation_result = await self.validation_handler.validate_character_selection(
            char_data, balance_service
        )
        if validation_result is None:
            return CommandResult.error("Datos de personaje inválidos")

        class_name, race_name, class_id = validation_result

        # Log de datos recibidos
        logger.info(
            "Solicitud de creación de cuenta - Username: %s, Email: %s, CharData: %s",
            username,
            email,
            char_data,
        )

        # Validar datos básicos de cuenta
        if not await self.validation_handler.validate_account_fields(username, password, email):
            return CommandResult.error("Campos de cuenta inválidos")

        # Hash de la contraseña
        password_hash = hash_password(password)

        # Obtener atributos de dados de la sesión
        stats_data = self.character_handler.get_dice_attributes_from_session(self.session_data)

        # Crear cuenta en Redis con datos separados
        try:
            user_id = await self.account_repo.create_account(
                username=username,
                password_hash=password_hash,
                email=email,
                char_data=char_data,
            )

            logger.info(
                "Cuenta creada exitosamente: %s (ID: %d, Clase: %d)",
                username,
                user_id,
                char_data.get("job", 1) if char_data else 1,
            )

            (
                base_attributes,
                final_attributes,
                initial_stats,
            ) = await self.character_handler.create_attributes_and_stats(
                user_id,
                stats_data,
                race_name,
                class_name,
                class_id,
                balance_service,
            )

            await self.character_handler.create_initial_inventory(user_id)

            self.finalization_handler.log_character_summary(
                user_id,
                username,
                char_data,
                class_name,
                base_attributes,
                final_attributes,
                initial_stats,
                stats_data,
            )

            # Ejecutar login automático después de crear la cuenta
            await self.finalization_handler.execute_auto_login(username, password)

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "username": username,
                    "class_name": class_name,
                    "race_name": race_name,
                }
            )

        except ValueError as e:
            # Cuenta ya existe u otro error de validación
            logger.warning("Error creando cuenta para %s: %s", username, e)
            return CommandResult.error(str(e))
        except Exception:
            logger.exception("Error inesperado creando cuenta para %s", username)
            return CommandResult.error("Error interno del servidor")
