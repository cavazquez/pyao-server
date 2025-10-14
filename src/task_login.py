"""Tarea para login de usuarios."""

import hashlib
import logging
from typing import TYPE_CHECKING

from src.inventory_repository import InventoryRepository
from src.items_catalog import get_item
from src.task import Task

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

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
    ) -> None:
        """Inicializa la tarea de login.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.session_data = session_data

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

    async def execute_with_credentials(  # noqa: C901, PLR0912, PLR0914, PLR0915
        self, username: str, password: str
    ) -> None:
        """Ejecuta el login con credenciales ya parseadas.

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano.
        """
        logger.info(
            "Intento de login desde %s - Username: %s",
            self.message_sender.connection.address,
            username,
        )

        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para login")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Obtener datos de la cuenta
        account_data = await self.account_repo.get_account(username)
        if not account_data:
            logger.warning("Intento de login con usuario inexistente: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return

        # Verificar contraseña
        password_hash = self._hash_password(password)
        if not await self.account_repo.verify_password(username, password_hash):
            logger.warning("Contraseña incorrecta para usuario: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return

        # Login exitoso
        user_id = int(account_data.get("user_id", 0))
        user_class = int(account_data.get("char_job", 1))  # Obtener clase del personaje
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

        # Obtener y enviar posición del personaje
        position = await self.player_repo.get_position(user_id)

        if position is None:
            # Si no existe posición, crear una por defecto
            default_x = 50
            default_y = 50
            default_map = 1
            await self.player_repo.set_position(user_id, default_x, default_y, default_map)
            logger.info(
                "Posición inicial creada para user_id %d: (%d, %d) en mapa %d",
                user_id,
                default_x,
                default_y,
                default_map,
            )
            position = {"x": default_x, "y": default_y, "map": default_map}

        # Enviar cambio de mapa
        await self.message_sender.send_change_map(position["map"])

        # Obtener y enviar atributos del personaje
        attributes = await self.player_repo.get_attributes(user_id)

        if attributes is None:
            # Si no existen atributos, crear valores por defecto
            attributes = {
                "strength": 10,
                "agility": 10,
                "intelligence": 10,
                "charisma": 10,
                "constitution": 10,
            }
            await self.player_repo.set_attributes(user_id=user_id, **attributes)
            logger.info("Atributos por defecto creados en Redis para user_id %d", user_id)

        await self.message_sender.send_attributes(
            strength=attributes["strength"],
            agility=attributes["agility"],
            intelligence=attributes["intelligence"],
            charisma=attributes["charisma"],
            constitution=attributes["constitution"],
        )

        # Obtener y enviar estadísticas completas del personaje
        user_stats = await self.player_repo.get_stats(user_id)

        if user_stats is None:
            # Si no existen stats, crear valores por defecto
            user_stats = {
                "max_hp": 100,
                "min_hp": 100,
                "max_mana": 100,
                "min_mana": 100,
                "max_sta": 100,
                "min_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "experience": 0,
            }
            await self.player_repo.set_stats(user_id=user_id, **user_stats)
            logger.info("Estadísticas por defecto creadas en Redis para user_id %d", user_id)

        await self.message_sender.send_update_user_stats(**user_stats)

        # Obtener y enviar hambre y sed (al final para evitar problemas de parsing)
        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)

        if hunger_thirst is None:
            # Si no existen, crear valores por defecto
            await self.player_repo.set_hunger_thirst(
                user_id=user_id,
                max_water=100,
                min_water=100,
                max_hunger=100,
                min_hunger=100,
                thirst_flag=0,
                hunger_flag=0,
                water_counter=0,
                hunger_counter=0,
            )
            logger.info("Hambre y sed por defecto creadas en Redis para user_id %d", user_id)
            hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)

        # Enviar solo los valores visibles al cliente
        if hunger_thirst:
            await self.message_sender.send_update_hunger_and_thirst(
                max_water=hunger_thirst["max_water"],
                min_water=hunger_thirst["min_water"],
                max_hunger=hunger_thirst["max_hunger"],
                min_hunger=hunger_thirst["min_hunger"],
            )

        # Enviar inventario completo
        inventory_repo = InventoryRepository(self.player_repo.redis)
        inventory = await inventory_repo.get_inventory(user_id)

        logger.info("Enviando inventario para user_id %d", user_id)
        for i in range(1, InventoryRepository.MAX_SLOTS + 1):
            slot_key = f"slot_{i}"
            slot_value = inventory.get(slot_key, "")

            if slot_value and isinstance(slot_value, str):
                try:
                    item_id, quantity = slot_value.split(":")
                    item = get_item(int(item_id))

                    if item:
                        logger.info(
                            "Enviando slot %d: %s (id=%d, grh=%d, type=%d, qty=%s)",
                            i,
                            item.name,
                            item.item_id,
                            item.graphic_id,
                            item.item_type.to_client_type(),
                            quantity,
                        )
                        await self.message_sender.send_change_inventory_slot(
                            slot=i,
                            item_id=item.item_id,
                            name=item.name,
                            amount=int(quantity),
                            equipped=False,
                            grh_id=item.graphic_id,
                            item_type=item.item_type.to_client_type(),
                            max_hit=item.max_damage,
                            min_hit=item.min_damage,
                            max_def=item.defense,
                            min_def=item.defense,
                            sale_price=float(item.value),
                        )
                except (ValueError, AttributeError) as e:
                    logger.warning("Error procesando slot %d: %s", i, e)

        # Obtener datos visuales del personaje
        char_body = int(account_data.get("char_race", 1))
        char_head = int(account_data.get("char_head", 1))

        # Si body es 0, usar valor por defecto (1 = humano)
        if char_body == 0:
            char_body = 1

        char_heading = 3  # Sur por defecto

        # Enviar CHARACTER_CREATE para mostrar el personaje en el mapa
        # (al final antes del broadcast, con efecto de aparición FX 1)
        await self.message_sender.send_character_create(
            char_index=user_id,
            body=char_body,
            head=char_head,
            heading=char_heading,
            x=position["x"],
            y=position["y"],
            fx=1,  # Efecto de aparición/spawn
            loops=-1,  # -1 = reproducir una vez
            name=username,
        )

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

    @staticmethod
    def _hash_password(password: str) -> str:
        """Genera un hash SHA-256 de la contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash hexadecimal de la contraseña.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
