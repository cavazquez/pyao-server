"""Tarea de login de usuario."""

import logging
from typing import TYPE_CHECKING

from src.account_repository import AccountRepository
from src.authentication_service import AuthenticationService
from src.map_manager import MapManager
from src.message_sender import MessageSender
from src.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.npc_service import NPCService
from src.player_repository import PlayerRepository
from src.player_service import PlayerService
from src.server_repository import ServerRepository
from src.session_manager import SessionManager
from src.spellbook_repository import SpellbookRepository
from src.task import Task
from src.task_motd import TaskMotd

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.equipment_repository import EquipmentRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.npc_service import NPCService
    from src.player_repository import PlayerRepository
    from src.server_repository import ServerRepository
    from src.spell_catalog import SpellCatalog
    from src.spellbook_repository import SpellbookRepository

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
        npc_service: NPCService | None = None,
        server_repo: ServerRepository | None = None,
        spellbook_repo: SpellbookRepository | None = None,
        spell_catalog: SpellCatalog | None = None,
        equipment_repo: EquipmentRepository | None = None,
    ) -> None:
        """Inicializa la tarea de login.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión compartidos (opcional).
            npc_service: Servicio de NPCs para enviar NPCs al jugador.
            server_repo: Repositorio del servidor para obtener el MOTD.
            spellbook_repo: Repositorio de libro de hechizos.
            spell_catalog: Catálogo de hechizos.
            equipment_repo: Repositorio de equipamiento.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.session_data = session_data
        self.npc_service = npc_service
        self.server_repo = server_repo
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.equipment_repo = equipment_repo

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

    async def execute_with_credentials(self, username: str, password: str) -> None:
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
            SessionManager.set_user_session(self.session_data, user_id, username)

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

        # Inicializar y enviar hechizos desde Redis
        if self.spellbook_repo and self.spell_catalog:
            # Inicializar libro de hechizos con hechizos por defecto si es necesario
            await self.spellbook_repo.initialize_default_spells(user_id)

            # Cargar y enviar todos los hechizos del jugador
            logger.info("Cargando libro de hechizos para user_id %d desde Redis", user_id)
            spells = await self.spellbook_repo.get_all_spells(user_id)

            if spells:
                logger.info(
                    "user_id %d tiene %d hechizo(s) en su libro: %s",
                    user_id,
                    len(spells),
                    dict(sorted(spells.items())),
                )

                for slot, spell_id in sorted(spells.items()):
                    spell_data = self.spell_catalog.get_spell_data(spell_id)
                    if spell_data:
                        spell_name = spell_data.get("name", f"Spell {spell_id}")
                        await self.message_sender.send_change_spell_slot(slot, spell_id, spell_name)
                        logger.info(
                            "Hechizo enviado al cliente: slot=%d, spell_id=%d (%s)",
                            slot,
                            spell_id,
                            spell_name,
                        )
            else:
                logger.info("user_id %d no tiene hechizos en su libro", user_id)

        # Reproducir sonido de login
        await self.message_sender.play_sound_login()

        # TODO: Agregar música de fondo cuando el cliente implemente el handler de PLAY_MIDI

        # Enviar CHARACTER_CREATE con delay post-spawn incluido (500ms)
        await player_service.spawn_character(user_id, username, position)

        # Mostrar efecto visual de spawn
        await self.message_sender.play_effect_spawn(char_index=user_id)

        # Broadcast multijugador: agregar jugador al mapa y notificar a otros
        if self.map_manager and self.account_repo:
            broadcast_service = MultiplayerBroadcastService(
                self.map_manager,
                self.player_repo,
                self.account_repo,
            )
            await broadcast_service.notify_player_spawn(
                user_id,
                username,
                position,
                self.message_sender,
            )

        # Enviar NPCs del mapa al jugador
        if self.npc_service:
            await self.npc_service.send_npcs_to_player(
                self.message_sender,
                position["map"],
            )

        # Enviar inventario (después del delay automático de spawn_character)
        await player_service.send_inventory(user_id, self.equipment_repo)

        # Enviar MOTD (Mensaje del Día) - reutilizar TaskMotd
        motd_task = TaskMotd(self.data, self.message_sender, self.server_repo)
        await motd_task.execute()
