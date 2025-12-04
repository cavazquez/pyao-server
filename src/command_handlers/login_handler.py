"""Handler para comando de login."""

import asyncio
import logging
from typing import TYPE_CHECKING

from src.command_handlers.motd_handler import MotdCommandHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.login_command import LoginCommand
from src.commands.motd_command import MotdCommand
from src.network.session_manager import SessionManager
from src.services.player.authentication_service import AuthenticationService
from src.services.player.player_service import PlayerService

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

# Constantes para tamaño del mapa
MAX_MAP_COORDINATE = 100


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
        self.map_manager = map_manager
        self.server_repo = server_repo
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.equipment_repo = equipment_repo
        self.player_map_service = player_map_service
        self.message_sender = message_sender
        # IMPORTANTE: Mantener la misma referencia al diccionario mutable
        # No crear un nuevo diccionario vacío si session_data es None
        if session_data is None:
            # Solo crear un nuevo diccionario si realmente es None
            # Esto no debería pasar en producción, pero es un fallback seguro
            self.session_data = {}
        else:
            self.session_data = session_data
        self._motd_handler: MotdCommandHandler | None = None

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

        logger.info("LoginCommandHandler: intento de login para '%s'", username)

        # Validar repositorios
        if not self._validate_repositories():
            return CommandResult.error("Repositorios no disponibles")

        # Autenticar usuario
        auth_result = await self._authenticate_user(username, password)
        if auth_result is None:
            return CommandResult.error("Autenticación fallida")

        user_id, user_class = auth_result

        # Verificar si el usuario ya está conectado
        if self._is_user_already_connected(username):
            logger.warning("Usuario %s (ID: %d) ya está conectado", username, user_id)
            await self.message_sender.send_error_msg("Ya estás conectado desde otra sesión.")
            return CommandResult.error("Usuario ya conectado")

        logger.info("Login exitoso para %s (ID: %d, Clase: %d)", username, user_id, user_class)

        # Configurar sesión
        self._setup_session(user_id, username)

        # Enviar paquetes iniciales y obtener posición
        position = await self._send_login_packets(user_id, user_class)

        # Buscar casilla libre si la posición está ocupada
        new_position = self._find_free_spawn_position(position)

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
        await self._initialize_player_data(user_id)

        # Enviar libro de hechizos
        await self._send_spellbook(user_id)

        # Spawn del jugador
        await self._spawn_player(user_id, username, position)

        # Enviar datos del mapa y finalizar login
        await self._send_map_data(user_id, position)

        # Enviar inventario y MOTD
        await self._finalize_login(user_id)

        return CommandResult.ok(
            data={
                "user_id": user_id,
                "username": username,
                "user_class": user_class,
                "position": position,
            }
        )

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

    def _is_user_already_connected(self, username: str) -> bool:
        """Verifica si el usuario ya tiene una sesión activa.

        Args:
            username: Nombre de usuario.

        Returns:
            True si el usuario ya está conectado, False en caso contrario.
        """
        if not self.map_manager:
            return False

        # Verificar si el username ya está en algún mapa
        existing_user_id = self.map_manager.find_player_by_username(username)
        return existing_user_id is not None

    async def _authenticate_user(self, username: str, password: str) -> tuple[int, int] | None:
        """Autentica al usuario.

        Args:
            username: Nombre de usuario.
            password: Contraseña.

        Returns:
            Tupla (user_id, user_class) si la autenticación es exitosa, None en caso contrario.
        """
        auth_service = AuthenticationService(self.account_repo, self.message_sender)
        return await auth_service.authenticate(username, password)

    def _setup_session(self, user_id: int, username: str) -> None:
        """Configura la sesión del usuario.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
        """
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
                            "heading": position.get("heading", 3),  # Default heading: South
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
        4. UPDATE_STRENGTH_AND_DEXTERITY (ID: 102)
        5. UPDATE_USER_STATS (ID: 45)

        Args:
            user_id: ID del usuario.
            user_class: Clase del personaje.

        Returns:
            Diccionario con la posición del jugador.
        """
        logger.info("[LOGIN-PACKETS] user_id=%d Iniciando envío de paquetes de login", user_id)

        # Enviar paquete Logged con la clase del personaje
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Enviando LOGGED (ID=0) class=%d", user_id, user_class
        )
        await self.message_sender.send_logged(user_class)

        # Enviar índice del personaje en el servidor
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Enviando USER_CHAR_INDEX_IN_SERVER (ID=28)", user_id
        )
        await self.message_sender.send_user_char_index_in_server(user_id)

        # Crear servicio de jugador
        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)

        # Obtener/crear y enviar posición (envía CHANGE_MAP)
        logger.info("[LOGIN-PACKETS] user_id=%d Enviando CHANGE_MAP (ID=21)", user_id)
        position = await player_service.send_position(user_id)
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Posición: map=%d x=%d y=%d",
            user_id,
            position["map"],
            position["x"],
            position["y"],
        )

        # Crear atributos por defecto si no existen
        attributes = await player_service.send_attributes(user_id)
        logger.info("[LOGIN-PACKETS] user_id=%d Atributos obtenidos: %s", user_id, attributes)

        if attributes:
            str_val = attributes.get("strength", 0)
            agi_val = attributes.get("agility", 0)
            logger.info(
                "[LOGIN-PACKETS] user_id=%d UPDATE_STRENGTH_AND_DEXTERITY str=%d agi=%d",
                user_id,
                str_val,
                agi_val,
            )
            await self.message_sender.send_update_strength_and_dexterity(
                strength=str_val,
                dexterity=agi_val,
            )

        # Obtener/crear y enviar stats
        logger.info("[LOGIN-PACKETS] user_id=%d Enviando UPDATE_USER_STATS (ID=45)", user_id)
        await player_service.send_stats(user_id)

        logger.info("[LOGIN-PACKETS] user_id=%d Paquetes de login enviados correctamente", user_id)
        return position

    async def _initialize_player_data(self, user_id: int) -> None:
        """Inicializa los datos del jugador.

        Args:
            user_id: ID del usuario.
        """
        # Resetear estado de meditación al hacer login
        await self.player_repo.set_meditating(user_id, is_meditating=False)
        logger.debug("Estado de meditación reseteado para user_id %d al hacer login", user_id)

        # Enviar hambre/sed (stats ya se enviaron en _send_login_packets)
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
        # Pasar spell_catalog para agregar TODOS los hechizos disponibles
        await self.spellbook_repo.initialize_default_spells(
            user_id, spell_catalog=self.spell_catalog
        )

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
        """Realiza el spawn del jugador en el mundo usando PlayerMapService.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        # Reproducir sonido de login
        await self.message_sender.play_sound_login()

        # Usar PlayerMapService para spawn (maneja toda la secuencia de 12 pasos)
        if self.player_map_service:
            # Para login, el jugador viene de "ningún mapa" (map 0)
            await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=0,  # No viene de ningún mapa
                current_x=0,  # Posición inválida (no importa)
                current_y=0,  # Posición inválida (no importa)
                new_map=position["map"],
                new_x=position["x"],
                new_y=position["y"],
                heading=position.get("heading", 3),
                message_sender=self.message_sender,
            )
        else:
            # Fallback por si acaso (no debería pasar con inyección correcta)
            logger.error("PlayerMapService no disponible para spawn, usando fallback")
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.spawn_character(user_id, username, position)
            await self.message_sender.send_pos_update(position["x"], position["y"])

        # Mostrar efecto visual de spawn
        await self.message_sender.play_effect_spawn(char_index=user_id)

    async def _send_map_data(self, user_id: int, position: dict[str, int]) -> None:
        """Envía los datos del mapa al jugador.

        Args:
            user_id: ID del usuario.
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
            logger.error("PlayerMapService no disponible para spawn en mapa")

    async def _finalize_login(self, user_id: int) -> None:
        """Finaliza el proceso de login.

        Args:
            user_id: ID del usuario.
        """
        logger.info("[LOGIN-FINALIZE] user_id=%d Iniciando finalización de login", user_id)

        # Enviar inventario
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando inventario", user_id)
        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
        await player_service.send_inventory(user_id, self.equipment_repo)

        # Habilitar botón de party en el cliente (después del spawn completo)
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando SHOW_PARTY_FORM (ID=101)", user_id)
        await self.message_sender.send_show_party_form()

        # NOTA: El envío de CLAN_DETAILS (packet 80) está deshabilitado hasta que el cliente
        # Godot implemente el handler para procesar GuildDetails.
        # Ver: docs/CLAN_BUTTON_ENABLING.md para instrucciones de cómo habilitarlo.

        # Enviar MOTD (Mensaje del Día)
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando MOTD", user_id)
        if self._motd_handler is None:
            self._motd_handler = MotdCommandHandler(
                server_repo=self.server_repo,
                message_sender=self.message_sender,
            )

        motd_command = MotdCommand()
        await self._motd_handler.handle(motd_command)

        logger.info("[LOGIN-FINALIZE] user_id=%d Login finalizado correctamente", user_id)
