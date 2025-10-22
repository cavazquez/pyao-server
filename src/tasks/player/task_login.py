"""Tarea que maneja el login de usuarios."""

import asyncio
import logging
from typing import TYPE_CHECKING

from src.repositories.account_repository import AccountRepository
from src.services.player.authentication_service import AuthenticationService
from src.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.npc.npc_service import NPCService
from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.repositories.player_repository import PlayerRepository
from src.services.player.player_service import PlayerService
from src.repositories.server_repository import ServerRepository
from src.session_manager import SessionManager
from src.repositories.spellbook_repository import SpellbookRepository
from src.task import Task
from src.task_motd import TaskMotd

if TYPE_CHECKING:
    from src.repositories.account_repository import AccountRepository
    from src.repositories.equipment_repository import EquipmentRepository
    from src.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.services.npc.npc_service import NPCService
    from src.services.map.player_map_service import PlayerMapService
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import SpellbookRepository

logger = logging.getLogger(__name__)

# Constantes para tamaño del mapa
MAX_MAP_COORDINATE = 100


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
        player_map_service: PlayerMapService | None = None,
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
            player_map_service: Servicio de mapas de jugador.
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
        self.player_map_service = player_map_service

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
        # Usar PacketValidator para leer username y password
        # NOTA: task_login usa UTF-8, igual que task_account
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        username = validator.read_string(min_length=1, max_length=20, encoding="utf-8")
        password = validator.read_string(min_length=1, max_length=32, encoding="utf-8")

        if validator.has_errors() or username is None or password is None:
            logger.warning("Error validando login: %s", validator.get_error_message())
            return None

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
        # Validar repositorios
        if not self._validate_repositories():
            return

        # Autenticar usuario
        auth_result = await self._authenticate_user(username, password)
        if auth_result is None:
            return

        user_id, user_class = auth_result
        logger.info("Login exitoso para %s (ID: %d, Clase: %d)", username, user_id, user_class)

        # Configurar sesión
        self._setup_session(user_id, username)

        # Enviar paquetes iniciales y obtener posición
        position = await self._send_login_packets(user_id, user_class)

        # Buscar casilla libre si la posición está ocupada
        new_position = self._find_free_spawn_position(position)

        # Si cambió la posición, actualizar en Redis
        if new_position != position and self.player_repo:
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
        await self._initialize_player_data(user_id)

        # Enviar libro de hechizos
        await self._send_spellbook(user_id)

        # Spawn del jugador
        await self._spawn_player(user_id, username, position)

        # Enviar datos del mapa y finalizar login
        await self._send_map_data(user_id, username, position)

        # Enviar inventario y MOTD
        await self._finalize_login(user_id)

    async def _send_ground_items_to_player(self, map_id: int) -> None:
        """Envía OBJECT_CREATE de todos los ground items del mapa al jugador.

        Método legacy, usado solo como fallback si PlayerMapService no está disponible.

        Args:
            map_id: ID del mapa.
        """
        if not self.map_manager:
            return

        # Obtener todos los ground items del mapa
        items_sent = 0
        # Acceder a través del método público en lugar de atributo privado
        for (item_map_id, x, y), items in self.map_manager._ground_items.items():  # noqa: SLF001
            if item_map_id != map_id:
                continue

            # Enviar OBJECT_CREATE por cada item en ese tile
            for item in items:
                grh_index = item.get("grh_index")
                if grh_index and isinstance(grh_index, int):
                    await self.message_sender.send_object_create(x, y, grh_index)
                    items_sent += 1
                    # Pequeño delay para no saturar
                    await asyncio.sleep(0.01)

        if items_sent > 0:
            logger.info("Enviados %d ground items al jugador en mapa %d", items_sent, map_id)

    def _validate_repositories(self) -> bool:
        """Valida que los repositorios necesarios estén disponibles.

        Returns:
            True si están disponibles, False en caso contrario.
        """
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para login")
            # Enviar error al cliente (fire and forget)
            task = asyncio.create_task(self.message_sender.send_error_msg("Servicio no disponible"))
            task.add_done_callback(lambda _: None)  # Evitar warning de task no awaited
            return False
        return True

    async def _authenticate_user(self, username: str, password: str) -> tuple[int, int] | None:
        """Autentica al usuario.

        Args:
            username: Nombre de usuario.
            password: Contraseña.

        Returns:
            Tupla (user_id, user_class) si la autenticación es exitosa, None en caso contrario.
        """
        if self.account_repo is None:
            return None

        auth_service = AuthenticationService(self.account_repo, self.message_sender)
        return await auth_service.authenticate(username, password)

    def _setup_session(self, user_id: int, username: str) -> None:
        """Configura la sesión del usuario.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
        """
        if self.session_data is not None:
            SessionManager.set_user_session(self.session_data, user_id, username)

    def _find_free_spawn_position(self, position: dict[str, int]) -> dict[str, int]:
        """Busca una posición libre cercana si la posición de spawn está ocupada.

        Args:
            position: Posición original de spawn.

        Returns:
            Posición libre (original o una cercana).
        """
        if not self.map_manager:
            return position

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Verificar si la posición original está libre
        if not self.map_manager.is_tile_occupied(map_id, x, y):
            return position

        # Posición ocupada, buscar una libre cercana
        logger.info(
            "Spawn position (%d,%d) en mapa %d ocupada, buscando casilla libre...",
            x,
            y,
            map_id,
        )

        # Buscar en espiral hacia afuera (radio 1-5 tiles)
        for radius in range(1, 6):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    # Solo verificar el borde del radio actual
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    new_x = x + dx
                    new_y = y + dy

                    # Verificar que esté dentro del mapa
                    if (
                        new_x < 1
                        or new_y < 1
                        or new_x > MAX_MAP_COORDINATE
                        or new_y > MAX_MAP_COORDINATE
                    ):
                        continue

                    # Verificar que no esté bloqueado y no esté ocupado
                    if self.map_manager.can_move_to(
                        map_id, new_x, new_y
                    ) and not self.map_manager.is_tile_occupied(map_id, new_x, new_y):
                        logger.info(
                            "Casilla libre encontrada en (%d,%d), moviendo spawn de (%d,%d)",
                            new_x,
                            new_y,
                            x,
                            y,
                        )
                        return {
                            "x": new_x,
                            "y": new_y,
                            "map": map_id,
                            "heading": position["heading"],
                        }

        # No se encontró casilla libre (muy raro)
        logger.warning(
            "No se encontró casilla libre cerca de (%d,%d) en mapa %d, usando original",
            x,
            y,
            map_id,
        )
        return position

    async def _send_login_packets(self, user_id: int, user_class: int) -> dict[str, int]:
        """Envía los paquetes iniciales de login.

        IMPORTANTE: Orden de envío de paquetes durante el login.
        Este orden es crítico para evitar problemas de parsing en el cliente.

        Orden correcto:
        1. LOGGED (ID: 0)
        2. USER_CHAR_INDEX_IN_SERVER (ID: 28)
        3. CHANGE_MAP (ID: 21)
        4. ATTRIBUTES (ID: 50)
        5. UPDATE_USER_STATS (ID: 45)
        6. UPDATE_HUNGER_AND_THIRST (ID: 60)

        Args:
            user_id: ID del usuario.
            user_class: Clase del personaje.

        Returns:
            Diccionario con la posición del jugador.
        """
        # Enviar paquete Logged con la clase del personaje
        await self.message_sender.send_logged(user_class)

        # Enviar índice del personaje en el servidor
        await self.message_sender.send_user_char_index_in_server(user_id)

        # Crear servicio de jugador
        if self.player_repo is None:
            return {"x": 50, "y": 50, "map": 1, "heading": 3}

        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)

        # Obtener/crear y enviar posición (envía CHANGE_MAP)
        position = await player_service.send_position(user_id)

        # Crear atributos por defecto si no existen
        await player_service.send_attributes(user_id)

        # Obtener/crear y enviar stats
        await player_service.send_stats(user_id)

        return position

    async def _initialize_player_data(self, user_id: int) -> None:
        """Inicializa los datos del jugador.

        Args:
            user_id: ID del usuario.
        """
        # Resetear estado de meditación al hacer login
        if self.player_repo:
            await self.player_repo.set_meditating(user_id, is_meditating=False)
            logger.debug("Estado de meditación reseteado para user_id %d al hacer login", user_id)

        # Obtener/crear y enviar hambre/sed
        if self.player_repo:
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.send_hunger_thirst(user_id)

    async def _send_spellbook(self, user_id: int) -> None:
        """Envía el libro de hechizos al jugador.

        Args:
            user_id: ID del usuario.
        """
        if not self.spellbook_repo or not self.spell_catalog:
            return

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

    async def _spawn_player(self, user_id: int, username: str, position: dict[str, int]) -> None:
        """Realiza el spawn del jugador en el mundo.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        # Reproducir sonido de login
        await self.message_sender.play_sound_login()

        # Enviar CHARACTER_CREATE con delay post-spawn incluido (500ms)
        if self.player_repo:
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.spawn_character(user_id, username, position)

        # Enviar actualización de posición para actualizar el minimapa
        await self.message_sender.send_pos_update(position["x"], position["y"])

        # Mostrar efecto visual de spawn
        await self.message_sender.play_effect_spawn(char_index=user_id)

    async def _send_map_data(self, user_id: int, username: str, position: dict[str, int]) -> None:
        """Envía los datos del mapa al jugador.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        # Cargar ground items desde Redis si no están en memoria
        if self.map_manager:
            await self.map_manager.load_ground_items(position["map"])

        # Usar PlayerMapService para spawnear en el mapa
        if self.player_map_service:
            await self.player_map_service.spawn_in_map(
                user_id=user_id,
                map_id=position["map"],
                x=position["x"],
                y=position["y"],
                heading=position.get("heading", 3),
                message_sender=self.message_sender,
            )
        else:
            # Fallback al método legacy
            await self._send_map_data_legacy(user_id, username, position)

    async def _send_map_data_legacy(
        self, user_id: int, username: str, position: dict[str, int]
    ) -> None:
        """Envía datos del mapa usando método legacy.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        logger.warning("PlayerMapService no disponible, usando método legacy")

        if self.npc_service:
            await self.npc_service.send_npcs_in_map(position["map"], self.message_sender)

        if self.map_manager and self.account_repo and self.player_repo:
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

        if self.map_manager:
            await self._send_ground_items_to_player(position["map"])

    async def _finalize_login(self, user_id: int) -> None:
        """Finaliza el proceso de login.

        Args:
            user_id: ID del usuario.
        """
        # Enviar inventario
        if self.player_repo:
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.send_inventory(user_id, self.equipment_repo)

        # Enviar MOTD (Mensaje del Día)
        motd_task = TaskMotd(self.data, self.message_sender, self.server_repo)
        await motd_task.execute()
