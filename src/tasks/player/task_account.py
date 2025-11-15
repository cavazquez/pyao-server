"""Tarea para creación de cuentas."""

import logging
from typing import TYPE_CHECKING

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
    from src.services.map.player_map_service import PlayerMapService
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 32

# Mapping de IDs de clase (cliente Godot / protocolo AO) a nombres de clase
# usados en el archivo data/classes_balance.toml.
JOB_ID_TO_CLASS_NAME: dict[int, str] = {
    1: "Mago",
    2: "Clerigo",
    3: "Guerrero",
    4: "Asesino",
    5: "Ladron",
    6: "Bardo",
    7: "Druida",
    8: "Bandido",
    9: "Paladin",
    10: "Cazador",
    11: "Trabajador",
    12: "Pirata",
}

RACE_ID_TO_NAME: dict[int, str] = {
    1: "Humano",
    2: "Elfo",
    3: "Drow",
    4: "Gnomo",
    5: "Enano",
}

GENDER_ID_TO_NAME: dict[int, str] = {
    1: "Hombre",
    2: "Mujer",
}

HOME_ID_TO_NAME: dict[int, str] = {
    1: "Ullathorpe",
    2: "Nix",
    3: "Banderbill",
    4: "Lindos",
    5: "Arghal",
    6: "Arkhein",
}


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
            # [0, 13, 0] + race (u8) + gender (u8) + job (u8) + head (u16)
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

    async def execute(self) -> None:  # noqa: PLR0915
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

        # Validar que se haya recibido una clase (job) válida mapeable a una
        # clase conocida por el sistema de balance.
        job_value = char_data.get("job") if char_data is not None else None
        if not isinstance(job_value, int) or job_value not in JOB_ID_TO_CLASS_NAME:
            logger.warning(
                "Clase inválida en creación de cuenta desde %s: job=%s",
                self.message_sender.connection.address,
                job_value,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return

        class_name = JOB_ID_TO_CLASS_NAME[job_value]
        balance_service = get_balance_service()
        if not balance_service.validate_class(class_name):
            logger.warning(
                "Clase '%s' (job=%s) no existe en balance de clases",
                class_name,
                job_value,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return

        # Validar raza recibida
        race_value = char_data.get("race") if char_data is not None else None
        race_name = RACE_ID_TO_NAME.get(race_value or 0)
        if race_name is None or not balance_service.validate_race(race_name):
            logger.warning(
                "Raza inválida en creación de cuenta desde %s: race=%s",
                self.message_sender.connection.address,
                race_value,
            )
            await self.message_sender.send_error_msg("Raza de personaje inválida")
            return

        # Log de datos recibidos
        logger.info(
            "Solicitud de creación de cuenta desde %s - Username: %s, Email: %s, CharData: %s",
            self.message_sender.connection.address,
            username,
            email,
            char_data,
        )

        # Validar datos
        if not username or len(username) < MIN_USERNAME_LENGTH:
            logger.warning("Username muy corto: %s (len=%d)", username, len(username))
            await self.message_sender.send_error_msg(
                f"El nombre de usuario debe tener al menos {MIN_USERNAME_LENGTH} caracteres"
            )
            return

        if not password or len(password) < MIN_PASSWORD_LENGTH:
            logger.warning("Password muy corto: len=%d", len(password))
            await self.message_sender.send_error_msg(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )
            return

        if not email or "@" not in email:
            await self.message_sender.send_error_msg("Email inválido")
            return

        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para crear cuenta")
            await self.message_sender.send_error_msg("Servicio de cuentas no disponible")
            return

        # Hash de la contraseña
        password_hash = hash_password(password)

        # Obtener atributos de dados de la sesión
        stats_data = None
        if self.session_data and "dice_attributes" in self.session_data:
            stats_data = self.session_data["dice_attributes"]
            logger.info("Atributos de dados recuperados de sesión: %s", stats_data)
        else:
            logger.warning("No se encontraron atributos de dados en la sesión")

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

            final_attributes = None
            base_attributes = None

            # Guardar atributos de dados en Redis si existen
            if stats_data:
                base_attributes = {
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

                await self.player_repo.set_attributes(user_id=user_id, **final_attributes)
                logger.info(
                    "Atributos guardados en Redis para user_id %d (base=%s, final=%s)",
                    user_id,
                    base_attributes,
                    final_attributes,
                )

                # Crear estadísticas iniciales basadas en atributos + clase
                constitution = final_attributes.get("constitution", 10)
                intelligence = final_attributes.get("intelligence", 10)
                base_hp = constitution * 10
                max_hp = balance_service.calculate_max_health(base_hp, class_name)
                initial_stats = {
                    "max_hp": max_hp,
                    "min_hp": max_hp,
                    "max_mana": intelligence * 10,
                    "min_mana": intelligence * 10,
                    "max_sta": 100,
                    "min_sta": 100,
                    "gold": 0,
                    "level": 1,
                    "elu": 300,
                    "experience": 0,
                }
                await self.player_repo.set_stats(user_id=user_id, **initial_stats)
                logger.info(
                    "Estadísticas iniciales creadas para user_id %d: HP=%d MANA=%d",
                    user_id,
                    initial_stats["max_hp"],
                    initial_stats["max_mana"],
                )

            # Crear inventario inicial con items básicos
            inventory_repo = InventoryRepository(self.player_repo.redis)
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

            # Log resumen del personaje creado (atributos completos)
            race_value = char_data.get("race") if char_data is not None else None
            gender_value = char_data.get("gender") if char_data is not None else None
            head_value = char_data.get("head") if char_data is not None else None
            home_value = char_data.get("home") if char_data is not None else None

            race_name = RACE_ID_TO_NAME.get(race_value or 0, "Desconocida")
            gender_name = GENDER_ID_TO_NAME.get(gender_value or 0, "Desconocido")
            home_name = HOME_ID_TO_NAME.get(home_value or 0, "Desconocido")

            logger.info(
                (
                    "Personaje creado: user_id=%d, username=%s, raza=%s (%s), clase=%s (job=%s), "
                    "gender=%s (%s), head=%s, home=%s (%s), atributos_base=%s, atributos_finales=%s, "
                    "stats_iniciales=%s"
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
                initial_stats if stats_data else None,
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
