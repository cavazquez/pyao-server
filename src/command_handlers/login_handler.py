"""Handler para comando de login."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.login_authentication_handler import LoginAuthenticationHandler
from src.command_handlers.login_finalization_handler import LoginFinalizationHandler
from src.command_handlers.login_initialization_handler import LoginInitializationHandler
from src.command_handlers.login_spawn_handler import LoginSpawnHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.login_command import LoginCommand
from src.network.session_manager import SessionManager

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


class LoginCommandHandler(CommandHandler):
    """Handler para comando de login (solo lógica de negocio)."""

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
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            server_repo: Repositorio del servidor para obtener el MOTD.
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
        # IMPORTANTE: Mantener la misma referencia al diccionario mutable
        # No crear un nuevo diccionario vacío si session_data es None
        if session_data is None:
            # Solo crear un nuevo diccionario si realmente es None
            # Esto no debería pasar en producción, pero es un fallback seguro
            self.session_data = {}
        else:
            self.session_data = session_data

        # Inicializar handlers especializados
        self.auth_handler = LoginAuthenticationHandler(
            player_repo=player_repo,
            account_repo=account_repo,
            map_manager=map_manager,
            message_sender=message_sender,
        )

        self.init_handler = LoginInitializationHandler(
            player_repo=player_repo,
            account_repo=account_repo,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
            message_sender=message_sender,
        )

        self.spawn_handler = LoginSpawnHandler(
            player_repo=player_repo,
            account_repo=account_repo,
            map_manager=map_manager,
            player_map_service=player_map_service,
            message_sender=message_sender,
        )

        self.finalization_handler = LoginFinalizationHandler(
            player_repo=player_repo,
            account_repo=account_repo,
            equipment_repo=equipment_repo,
            server_repo=server_repo,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de login (solo lógica de negocio).

        Args:
            command: Comando de login.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, LoginCommand):
            return CommandResult.error("Comando inválido: se esperaba LoginCommand")

        username = command.username
        password = command.password

        logger.info("🔐 Inicio de login para usuario '%s'", username)

        # Validar repositorios
        if not self.auth_handler.validate_repositories():
            return CommandResult.error("Repositorios no disponibles")

        if not self.message_sender.connection.allow_authentication(username):
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return CommandResult.error("Autenticación fallida")

        # Autenticar usuario
        auth_result = await self.auth_handler.authenticate_user(username, password)
        if auth_result is None:
            return CommandResult.error("Autenticación fallida")

        user_id, user_class = auth_result

        # Verificar si el usuario ya está conectado
        if self.auth_handler.is_user_already_connected(username):
            logger.warning("⚠️ Usuario %s (ID: %d) ya está conectado", username, user_id)
            await self.message_sender.send_error_msg("Ya estás conectado desde otra sesión.")
            return CommandResult.error("Usuario ya conectado")

        if not await self.message_sender.connection.reserve_session(user_id):
            await self.message_sender.send_error_msg("Ya estás conectado desde otra sesión.")
            return CommandResult.error("Usuario ya conectado")
        try:
            return await self._complete_login(user_id, user_class, username)
        except BaseException:
            self.message_sender.connection.close()
            raise

    async def _complete_login(self, user_id: int, user_class: int, username: str) -> CommandResult:
        """Publica y completa el login únicamente después de obtener la reserva.

        Returns:
            Estado confirmado del jugador inicializado.
        """
        logger.info("✅ Login exitoso para %s (ID: %d, Clase: %d)", username, user_id, user_class)

        await self.player_repo.redis.hset(
            f"player:{user_id}:user_stats", "class_id", str(user_class)
        )

        # Configurar sesión
        self._setup_session(user_id, username)

        # Enviar paquetes iniciales y obtener posición
        position = await self.init_handler.send_login_packets(user_id, user_class)

        # Buscar casilla libre si la posición está ocupada
        new_position = self.spawn_handler.find_free_spawn_position(position)

        # Si cambió la posición, actualizar en Redis
        if new_position != position:
            await self.player_repo.set_position(
                user_id,
                new_position["x"],
                new_position["y"],
                new_position["map"],
                new_position["heading"],
            )
            # Enviar actualización al cliente también
            await self.message_sender.send_pos_update(new_position["x"], new_position["y"])

        position = new_position

        # Inicializar datos del jugador
        await self.init_handler.initialize_player_data(user_id)

        # Enviar libro de hechizos
        await self.init_handler.send_spellbook(user_id)

        # Spawn del jugador
        await self.spawn_handler.spawn_player(user_id, username, position)

        if await self.player_repo.is_sailing(user_id):
            await self.message_sender.send_navigate_toggle()

        # Enviar datos del mapa y finalizar login
        await self.spawn_handler.send_map_data(user_id, position)

        # Enviar inventario y MOTD
        await self.finalization_handler.finalize_login(user_id)

        self.message_sender.connection.mark_authenticated()
        return CommandResult.ok(
            data={
                "user_id": user_id,
                "username": username,
                "user_class": user_class,
                "position": position,
            }
        )

    def _setup_session(self, user_id: int, username: str) -> None:
        """Configura la sesión del usuario.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
        """
        SessionManager.set_user_session(self.session_data, user_id, username)
