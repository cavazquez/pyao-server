"""Tarea para login de usuarios."""

import logging
from typing import TYPE_CHECKING

from src.authentication_service import AuthenticationService
from src.player_service import PlayerService
from src.task import Task

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository
    from src.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class TaskLogin(Task):
    """Tarea que maneja el login de usuarios."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        server_repo: ServerRepository | None = None,
    ) -> None:
        """Inicializa la tarea de login.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión compartidos (opcional).
            server_repo: Repositorio del servidor para obtener el MOTD.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.session_data = session_data
        self.server_repo = server_repo

    def _parse_packet(self) -> tuple[str, str] | None:
        """Parsea el paquete de login.

        El formato esperado es:
        - Byte 0: PacketID (LOGIN)
        - Bytes 1-2: Longitud del username (int16, little-endian)
        - Bytes siguientes: Username (UTF-8)
        - Bytes siguientes (2): Longitud del password (int16, little-endian)
        - Bytes siguientes: Password (UTF-8)

        Returns:
            Tupla (username, password) o None si hay error.
        """
        try:
            offset = 1  # Saltar PacketID

            # Leer username
            if len(self.data) < offset + 2:
                return None
            username_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2

            if len(self.data) < offset + username_len:
                return None
            username = self.data[offset : offset + username_len].decode("utf-8")
            offset += username_len

            # Leer password
            if len(self.data) < offset + 2:
                return None
            password_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2

            if len(self.data) < offset + password_len:
                return None
            password = self.data[offset : offset + password_len].decode("utf-8")

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Error parseando paquete de login: %s", e)
            return None
        else:
            return (username, password)

    async def execute(self) -> None:
        """Ejecuta el login del usuario."""
        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de login inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        username, password = parsed
        await self.execute_with_credentials(username, password)

    async def execute_with_credentials(  # noqa: C901, PLR0914
        self, username: str, password: str
    ) -> None:
        """Ejecuta el login con credenciales ya parseadas.

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano.
        """
        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para login")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Autenticar usuario
        auth_service = AuthenticationService(self.account_repo, self.message_sender)
        auth_result = await auth_service.authenticate(username, password)

        if auth_result is None:
            # La autenticación falló (el servicio ya envió el error al cliente)
            return

        user_id, user_class = auth_result
        logger.info("Login exitoso para %s (ID: %d, Clase: %d)", username, user_id, user_class)

        # Guardar user_id y username en session_data para uso posterior
        if self.session_data is not None:
            self.session_data["user_id"] = user_id  # type: ignore[assignment]
            self.session_data["username"] = username  # type: ignore[assignment]
            logger.info("User ID %d y username %s guardados en sesión", user_id, username)

        # IMPORTANTE: Orden de envío de paquetes durante el login
        # Este orden es crítico para evitar problemas de parsing en el cliente.
        # El cliente lee los paquetes de forma secuencial y puede malinterpretar
        # los bytes si llegan concatenados por TCP en un orden incorrecto.
        #
        # Orden correcto:
        # 1. LOGGED (ID: 0)
        # 2. USER_CHAR_INDEX_IN_SERVER (ID: 28)
        # 3. CHANGE_MAP (ID: 21)
        # 4. ATTRIBUTES (ID: 50)
        # 5. UPDATE_USER_STATS (ID: 45)
        # 6. UPDATE_HUNGER_AND_THIRST (ID: 60)
        # 7. CHARACTER_CREATE (ID: 29) - DEBE IR AL FINAL antes del broadcast

        # Enviar paquete Logged con la clase del personaje
        await self.message_sender.send_logged(user_class)

        # Enviar índice del personaje en el servidor
        await self.message_sender.send_user_char_index_in_server(user_id)

        # Crear servicio de jugador para encapsular lógica de datos + envío
        player_service = PlayerService(self.player_repo, self.message_sender)

        # Obtener/crear y enviar posición (envía CHANGE_MAP)
        position = await player_service.send_position(user_id)

        # Crear atributos por defecto si no existen (NO se envían al login)
        # El cliente los solicitará con /EST
        await player_service.send_attributes(user_id)

        # Obtener/crear y enviar stats (envía UPDATE_USER_STATS)
        await player_service.send_stats(user_id)

        # Obtener/crear y enviar hambre/sed (envía UPDATE_HUNGER_AND_THIRST)
        await player_service.send_hunger_thirst(user_id)

        # Enviar CHARACTER_CREATE con delay post-spawn incluido (500ms)
        await player_service.spawn_character(user_id, username, position)

        # Broadcast multijugador: agregar jugador al mapa y notificar a otros
        if self.map_manager:
            map_id = position["map"]

            # Enviar CHARACTER_CREATE de todos los jugadores existentes al nuevo jugador
            existing_players = self.map_manager.get_players_in_map(map_id)
            for other_user_id in existing_players:
                # Obtener datos del otro jugador
                other_position = await self.player_repo.get_position(other_user_id)
                if other_position:
                    # Obtener datos visuales del otro jugador
                    other_account = await self.account_repo.get_account_by_user_id(other_user_id)
                    if other_account:
                        other_body = int(other_account.get("char_race", 1))
                        other_head = int(other_account.get("char_head", 1))
                        other_username = other_account.get("username", "")

                        if other_body == 0:
                            other_body = 1

                        # Enviar CHARACTER_CREATE del otro jugador al nuevo jugador
                        await self.message_sender.send_character_create(
                            char_index=other_user_id,
                            body=other_body,
                            head=other_head,
                            heading=other_position.get("heading", 3),
                            x=other_position["x"],
                            y=other_position["y"],
                            name=other_username,
                        )

            # Agregar el nuevo jugador al MapManager
            self.map_manager.add_player(map_id, user_id, self.message_sender, username)

            # Enviar CHARACTER_CREATE del nuevo jugador a todos los demás en el mapa
            # TODO: Obtener body, head, heading desde Redis cuando se implementen
            char_body = 1
            char_head = 1
            char_heading = 3  # Sur

            other_senders = self.map_manager.get_all_message_senders_in_map(
                map_id, exclude_user_id=user_id
            )
            for sender in other_senders:
                await sender.send_character_create(
                    char_index=user_id,
                    body=char_body,
                    head=char_head,
                    heading=char_heading,
                    x=position["x"],
                    y=position["y"],
                    name=username,
                )

            logger.info(
                "Jugador %d agregado al mapa %d. Notificados %d jugadores",
                user_id,
                map_id,
                len(other_senders),
            )

        # Enviar inventario (después del delay automático de spawn_character)
        await player_service.send_inventory(user_id)

        # Enviar MOTD (Mensaje del Día)
        if self.server_repo:
            motd = await self.server_repo.get_motd()
        else:
            motd = "Bienvenido a Argentum Online!\nServidor en desarrollo."

        await self.message_sender.send_multiline_console_msg(motd)
        logger.info("MOTD enviado a user_id %d", user_id)
