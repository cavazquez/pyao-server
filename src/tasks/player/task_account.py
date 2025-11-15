"""Tarea para creación de cuentas."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.game.character_constants import (
    GENDER_ID_TO_NAME,
    HOME_ID_TO_NAME,
    JOB_ID_TO_CLASS_NAME,
    RACE_ID_TO_NAME,
)
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.repositories.inventory_repository import InventoryRepository
from src.services.game.balance_service import get_balance_service
from src.tasks.player.task_login import TaskLogin
from src.tasks.task import Task
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
    from src.services.game.balance_service import BalanceService
    from src.services.map.player_map_service import PlayerMapService
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 32

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


class TaskCreateAccount(Task):
    """Tarea que maneja la creación de cuentas."""

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
        inventory_repo: InventoryRepository | None = None,
    ) -> None:
        """Inicializa la tarea de creación de cuenta.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas (pasado a TaskLogin en login automático).
            session_data: Datos de sesión compartidos (opcional).
            npc_service: Servicio de NPCs.
            server_repo: Repositorio del servidor.
            spellbook_repo: Repositorio de libro de hechizos.
            spell_catalog: Catálogo de hechizos.
            equipment_repo: Repositorio de equipamiento.
            player_map_service: Servicio de mapas de jugador.
            inventory_repo: Repositorio de inventario.
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
        self.inventory_repo = inventory_repo

    def _parse_packet(self) -> tuple[str, str, str, dict[str, int]] | None:
        """Parsea el paquete de creación de cuenta.

        El formato esperado es:
        - Byte 0: PacketID (CREATE_ACCOUNT)
        - Bytes 1-2: Longitud del username (int16, little-endian)
        - Bytes siguientes: Username (UTF-8)
        - Bytes siguientes (2): Longitud del password (int16, little-endian)
        - Bytes siguientes: Password (UTF-8)
        - Byte siguiente: race (1 byte)
        - Bytes siguientes (2): Longitud de algo? (int16)
        - Byte siguiente: gender (1 byte)
        - Byte siguiente: class/job (1 byte)
        - Byte siguiente: ? (1 byte)
        - Bytes siguientes (2): head (int16)
        - Bytes siguientes (2): Longitud del email (int16, little-endian)
        - Bytes siguientes: Email (UTF-8)
        - Byte siguiente: home (1 byte)

        Returns:
            Tupla (username, password, email, char_data) o None si hay error.
        """
        try:
            # Usar PacketValidator para leer username y password
            # NOTA: task_account usa UTF-8, no UTF-16LE como otros packets
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)

            username = validator.read_string(
                min_length=MIN_USERNAME_LENGTH, max_length=MAX_USERNAME_LENGTH, encoding="utf-8"
            )
            password = validator.read_string(
                min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH, encoding="utf-8"
            )

            if validator.has_errors() or username is None or password is None:
                logger.warning(
                    "Error validando username/password: %s", validator.get_error_message()
                )
                return None

            logger.debug("Username: %s", username)
            logger.debug("Password parsed")

            # Actualizar offset para continuar leyendo datos del personaje
            offset = reader.offset

            # Leer datos del personaje (vienen antes del email)
            char_data = {}
            # Validar que haya suficientes bytes para los datos del personaje
            # Protocolo cliente (ver GameProtocol.WriteLoginNewChar):
            # [0, 13, 0] + race (u8) + gender (u8) + job (u8) + head (u16) noqa: ERA001
            if len(self.data) >= offset + 9:
                # Saltar los 3 bytes fijos (0, 13, 0)
                offset += 3

                char_data["race"] = self.data[offset]
                offset += 1

                char_data["gender"] = self.data[offset]
                offset += 1

                char_data["job"] = self.data[offset]
                offset += 1

                # Leer head (int16)
                char_data["head"] = int.from_bytes(
                    self.data[offset : offset + 2],
                    byteorder="little",
                    signed=False,
                )
                offset += 2
                logger.debug("Char data parsed, offset: %d", offset)

            # Leer email usando PacketValidator
            # Actualizar el reader al offset actual
            reader.offset = offset

            email = validator.read_string() if not validator.has_errors() else ""
            if email is None:
                email = ""
            offset = reader.offset
            logger.debug("Email: %s, offset: %d", email, offset)

            # Leer home (último byte) - validar que haya al menos 1 byte más
            # Leer home (último byte)
            if len(self.data) >= offset + 1:
                char_data["home"] = self.data[offset]
                logger.debug("Home: %d", char_data["home"])

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Error parseando paquete de creación de cuenta: %s", e)
            return None
        else:
            return (username, password, email, char_data)

    async def execute(self) -> None:  # noqa: PLR0914
        """Ejecuta la creación de cuenta."""
        logger.info("TaskCreateAccount.execute() llamado")

        # Log de datos recibidos en hexadecimal para debugging
        hex_data = " ".join(f"{byte:02X}" for byte in self.data[:64])
        logger.info(
            "Datos recibidos para creación de cuenta (%d bytes): %s",
            len(self.data),
            hex_data,
        )

        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de creación de cuenta inválido desde %s",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_error_msg("Formato de paquete inválido")
            return

        username, password, email, char_data = parsed

        balance_service = get_balance_service()
        class_name, race_name = await self._validate_character_selection(
            char_data,
            balance_service,
        )
        if class_name is None or race_name is None:
            return

        # Log de datos recibidos
        logger.info(
            "Solicitud de creación de cuenta desde %s - Username: %s, Email: %s, CharData: %s",
            self.message_sender.connection.address,
            username,
            email,
            char_data,
        )

        # Validar datos básicos de cuenta
        if not await self._validate_account_fields(username, password, email):
            return

        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para crear cuenta")
            await self.message_sender.send_error_msg("Servicio de cuentas no disponible")
            return

        # Hash de la contraseña
        password_hash = hash_password(password)

        # Obtener atributos de dados de la sesión
        stats_data = self._get_dice_attributes_from_session()

        # Crear cuenta en Redis con datos separados
        try:
            user_id = await self.account_repo.create_account(
                username=username,
                password_hash=password_hash,
                email=email,
                char_data=char_data,
            )

            logger.info(
                "Cuenta creada exitosamente: %s (ID: %d, Clase: %d) desde %s",
                username,
                user_id,
                char_data.get("job", 1) if char_data else 1,
                self.message_sender.connection.address,
            )

            (
                base_attributes,
                final_attributes,
                initial_stats,
            ) = await self._create_attributes_and_stats(
                user_id,
                stats_data,
                race_name,
                class_name,
                balance_service,
            )

            await self._create_initial_inventory(user_id)

            await self._log_character_summary(
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
            login_task = TaskLogin(
                data=self.data,
                message_sender=self.message_sender,
                player_repo=self.player_repo,
                account_repo=self.account_repo,
                map_manager=self.map_manager,
                session_data=self.session_data,
                server_repo=self.server_repo,
                spellbook_repo=self.spellbook_repo,
                spell_catalog=self.spell_catalog,
                equipment_repo=self.equipment_repo,
                player_map_service=self.player_map_service,
            )
            await login_task.execute_with_credentials(username, password)

        except ValueError as e:
            # Cuenta ya existe u otro error de validación
            logger.warning("Error creando cuenta para %s: %s", username, e)
            await self.message_sender.send_error_msg(str(e))
        except Exception:
            logger.exception("Error inesperado creando cuenta para %s", username)
            await self.message_sender.send_error_msg("Error interno del servidor")

    async def _validate_character_selection(
        self,
        char_data: dict[str, int] | None,
        balance_service: BalanceService,
    ) -> tuple[str | None, str | None]:
        """Valida clase (job) y raza recibidas en los datos del personaje.

        Returns:
            Tupla ``(class_name, race_name)`` cuando la selección es válida.
            ``(None, None)`` si hay error (ya enviado al cliente).
        """
        if char_data is None:
            logger.warning(
                "CharData vacío en creación de cuenta desde %s",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_error_msg("Datos de personaje inválidos")
            return (None, None)

        # Validar clase
        job_value = char_data.get("job")
        if not isinstance(job_value, int) or job_value not in JOB_ID_TO_CLASS_NAME:
            logger.warning(
                "Clase inválida en creación de cuenta desde %s: job=%s",
                self.message_sender.connection.address,
                job_value,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return (None, None)

        class_name = JOB_ID_TO_CLASS_NAME[job_value]
        if not balance_service.validate_class(class_name):
            logger.warning(
                "Clase '%s' (job=%s) no existe en balance de clases",
                class_name,
                job_value,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return (None, None)

        # Validar raza
        race_value = char_data.get("race")
        race_name = RACE_ID_TO_NAME.get(race_value or 0)
        if race_name is None or not balance_service.validate_race(race_name):
            logger.warning(
                "Raza inválida en creación de cuenta desde %s: race=%s",
                self.message_sender.connection.address,
                race_value,
            )
            await self.message_sender.send_error_msg("Raza de personaje inválida")
            return (None, None)

        return (class_name, race_name)

    async def _validate_account_fields(
        self,
        username: str,
        password: str,
        email: str,
    ) -> bool:
        """Valida username, password y email.

        Returns:
            ``True`` si todos los campos son válidos.
            ``False`` si alguno es inválido (el error ya fue enviado al cliente).
        """
        if not username or len(username) < MIN_USERNAME_LENGTH:
            logger.warning("Username muy corto: %s (len=%d)", username, len(username))
            await self.message_sender.send_error_msg(
                f"El nombre de usuario debe tener al menos {MIN_USERNAME_LENGTH} caracteres"
            )
            return False

        if not password or len(password) < MIN_PASSWORD_LENGTH:
            logger.warning("Password muy corto: len=%d", len(password))
            await self.message_sender.send_error_msg(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )
            return False

        if not email or "@" not in email:
            await self.message_sender.send_error_msg("Email inválido")
            return False

        return True

    def _get_dice_attributes_from_session(self) -> dict[str, int] | None:
        """Obtiene atributos de dados desde la sesión si existen.

        Returns:
            Diccionario con atributos de dados o ``None`` si no hay datos en sesión.
        """
        if self.session_data and "dice_attributes" in self.session_data:
            stats_data = self.session_data["dice_attributes"]
            logger.info("Atributos de dados recuperados de sesión: %s", stats_data)
            return stats_data

        logger.warning("No se encontraron atributos de dados en la sesión")
        return None

    async def _create_attributes_and_stats(
        self,
        user_id: int,
        stats_data: dict[str, int] | None,
        race_name: str,
        class_name: str,
        balance_service: BalanceService,
    ) -> tuple[dict[str, int] | None, dict[str, int] | None, dict[str, int] | None]:
        """Crea atributos finales y estadísticas iniciales del personaje.

        Returns:
            Tupla ``(base_attributes, final_attributes, initial_stats)`` cuando
            hay datos de dados. Si ``stats_data`` es ``None``, devuelve
            ``(None, None, None)`` y no modifica atributos ni stats.
        """
        if stats_data is None:
            return (None, None, None)

        # En execute() ya se validó que player_repo no sea None, pero añadimos
        # esta verificación defensiva para el type checker y para runtime.
        if self.player_repo is None:
            logger.error("player_repo es None al crear atributos/stats para user_id %d", user_id)
            return (None, None, None)

        player_repo = self.player_repo

        base_attributes: dict[str, int] = {
            "strength": stats_data.get("strength", 10),
            "agility": stats_data.get("agility", 10),
            "intelligence": stats_data.get("intelligence", 10),
            "charisma": stats_data.get("charisma", 10),
            "constitution": stats_data.get("constitution", 10),
        }

        final_attributes = balance_service.apply_racial_modifiers(
            base_attributes,
            race_name,
        )

        await player_repo.set_attributes(user_id=user_id, **final_attributes)
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
        await player_repo.set_stats(user_id=user_id, **initial_stats)
        logger.info(
            "Estadísticas iniciales creadas para user_id %d: HP=%d MANA=%d",
            user_id,
            initial_stats["max_hp"],
            initial_stats["max_mana"],
        )

        return (base_attributes, final_attributes, initial_stats)

    async def _create_initial_inventory(self, user_id: int) -> None:
        """Crea el inventario inicial del personaje."""
        inventory_repo = InventoryRepository(self.player_repo.redis)  # type: ignore[union-attr]
        await inventory_repo.add_item(user_id, item_id=1, quantity=5)  # 5 Pociones Rojas
        await inventory_repo.add_item(user_id, item_id=2, quantity=5)  # 5 Pociones Azules
        await inventory_repo.add_item(user_id, item_id=3, quantity=10)  # 10 Manzanas
        await inventory_repo.add_item(user_id, item_id=4, quantity=10)  # 10 Aguas
        await inventory_repo.add_item(user_id, item_id=11, quantity=1)  # 1 Daga
        # Armadura inicial (Newbie)
        await inventory_repo.add_item(user_id, item_id=1073, quantity=1)  # Armadura de Aprendiz
        # Herramientas de trabajo (Newbie)
        await inventory_repo.add_item(user_id, item_id=561, quantity=1)  # Hacha de Leñador
        await inventory_repo.add_item(user_id, item_id=562, quantity=1)  # Piquete de Minero
        await inventory_repo.add_item(user_id, item_id=563, quantity=1)  # Caña de Pescar
        logger.info(
            "Inventario inicial creado para user_id %d (incluye Armadura de Aprendiz)", user_id
        )

    async def _log_character_summary(  # noqa: PLR6301
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
        """Loguea un resumen completo del personaje creado."""
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
