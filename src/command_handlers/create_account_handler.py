"""Handler para comando de creación de cuenta."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.login_handler import LoginCommandHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.create_account_command import CreateAccountCommand
from src.config.config_manager import ConfigManager, config_manager
from src.game.character_constants import (
    GENDER_ID_TO_NAME,
    HOME_ID_TO_NAME,
    JOB_ID_TO_CLASS_NAME,
    RACE_ID_TO_NAME,
)
from src.repositories.inventory_repository import InventoryRepository
from src.services.game.balance_service import BalanceService, get_balance_service
from src.services.game.class_service import get_class_service
from src.tasks.player.task_login import TaskLogin
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


class CreateAccountCommandHandler(CommandHandler):
    """Handler para comando de creación de cuenta (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        map_manager: MapManager | None,
        npc_service: NPCService | None,
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
            map_manager: Gestor de mapas.
            npc_service: Servicio de NPCs.
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
        self.npc_service = npc_service
        self.server_repo = server_repo
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.equipment_repo = equipment_repo
        self.player_map_service = player_map_service
        self.message_sender = message_sender
        self.session_data = session_data or {}

    async def handle(self, command: Command) -> CommandResult:  # noqa: PLR0914
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
        validation_result = await self._validate_character_selection(char_data, balance_service)
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
        if not await self._validate_account_fields(username, password, email):
            return CommandResult.error("Campos de cuenta inválidos")

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
                "Cuenta creada exitosamente: %s (ID: %d, Clase: %d)",
                username,
                user_id,
                char_data.get("job", 1) if char_data else 1,
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
                class_id,
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
                session_data=self.session_data,
            )

            login_task = TaskLogin(
                data=b"\x03",  # Dummy data para TaskLogin
                message_sender=self.message_sender,
                login_handler=login_handler,
                session_data=self.session_data,
            )
            await login_task.execute_with_credentials(username, password)

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

    async def _validate_character_selection(
        self,
        char_data: dict[str, int] | None,
        balance_service: BalanceService,
    ) -> tuple[str, str, int] | None:
        """Valida clase (job) y raza recibidas en los datos del personaje.

        Returns:
            Tupla ``(class_name, race_name, class_id)`` cuando la selección es válida.
            ``None`` si hay error (ya enviado al cliente).
        """
        if char_data is None:
            logger.warning("CharData vacío en creación de cuenta")
            await self.message_sender.send_error_msg("Datos de personaje inválidos")
            return None

        # Validar clase
        job_value = char_data.get("job")
        if not isinstance(job_value, int) or job_value not in JOB_ID_TO_CLASS_NAME:
            logger.warning("Clase inválida en creación de cuenta: job=%s", job_value)
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return None

        class_name = JOB_ID_TO_CLASS_NAME[job_value]
        if not balance_service.validate_class(class_name):
            logger.warning(
                "Clase '%s' (job=%s) no existe en balance de clases",
                class_name,
                job_value,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return None

        # Validar que la clase existe en ClassService
        class_service = get_class_service()
        if not class_service.validate_class(job_value):
            logger.warning(
                "Clase ID %d ('%s') no existe en ClassService",
                job_value,
                class_name,
            )
            await self.message_sender.send_error_msg("Clase de personaje inválida")
            return None

        # Validar raza
        race_value = char_data.get("race")
        race_name = RACE_ID_TO_NAME.get(race_value or 0)
        if race_name is None or not balance_service.validate_race(race_name):
            logger.warning("Raza inválida en creación de cuenta: race=%s", race_value)
            await self.message_sender.send_error_msg("Raza de personaje inválida")
            return None

        return (class_name, race_name, job_value)

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
        class_id: int,
        balance_service: BalanceService,
    ) -> tuple[dict[str, int] | None, dict[str, int] | None, dict[str, int] | None]:
        """Crea atributos finales y estadísticas iniciales del personaje.

        Args:
            user_id: ID del usuario.
            stats_data: Atributos de dados.
            race_name: Nombre de la raza.
            class_name: Nombre de la clase.
            class_id: ID de la clase.
            balance_service: Servicio de balance.

        Returns:
            Tupla ``(base_attributes, final_attributes, initial_stats)`` cuando
            hay datos de dados. Si ``stats_data`` es ``None``, devuelve
            ``(None, None, None)`` y no modifica atributos ni stats.
        """
        if stats_data is None:
            return (None, None, None)

        # Obtener atributos base de dados
        dice_attributes: dict[str, int] = {
            "strength": stats_data.get("strength", 10),
            "agility": stats_data.get("agility", 10),
            "intelligence": stats_data.get("intelligence", 10),
            "charisma": stats_data.get("charisma", 10),
            "constitution": stats_data.get("constitution", 10),
        }

        # Aplicar atributos base de clase
        class_service = get_class_service()
        base_attributes = class_service.apply_class_base_attributes(dice_attributes, class_id)

        # Aplicar modificadores raciales
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
        await self.player_repo.set_stats(user_id=user_id, **initial_stats)
        logger.info(
            "Estadísticas iniciales creadas para user_id %d: HP=%d MANA=%d",
            user_id,
            initial_stats["max_hp"],
            initial_stats["max_mana"],
        )

        # Aplicar skills iniciales por clase
        initial_skills = class_service.get_initial_skills(class_id)
        if initial_skills:
            await self.player_repo.set_skills(user_id=user_id, **initial_skills)
            logger.info(
                "Skills iniciales asignadas para user_id %d (clase %s): %s",
                user_id,
                class_name,
                initial_skills,
            )

        return (base_attributes, final_attributes, initial_stats)

    async def _create_initial_inventory(self, user_id: int) -> None:
        """Crea el inventario inicial del personaje."""
        inventory_repo = InventoryRepository(self.player_repo.redis)

        # Pociones - 30 de cada tipo (6 tipos principales)
        # Poción Amarilla (Agilidad)
        await inventory_repo.add_item(user_id, item_id=36, quantity=30)
        # Poción Azul (Mana)
        await inventory_repo.add_item(user_id, item_id=37, quantity=30)
        # Poción Roja (HP/Vida)
        await inventory_repo.add_item(user_id, item_id=38, quantity=30)
        # Poción Verde (Fuerza)
        await inventory_repo.add_item(user_id, item_id=39, quantity=30)
        # Poción Violeta (Cura Veneno)
        await inventory_repo.add_item(user_id, item_id=166, quantity=30)
        # Poción Negra (Invisible)
        await inventory_repo.add_item(user_id, item_id=645, quantity=30)

        # Comida y bebida
        await inventory_repo.add_item(user_id, item_id=3, quantity=10)  # 10 Manzanas
        await inventory_repo.add_item(user_id, item_id=4, quantity=10)  # 10 Aguas

        # Equipamiento inicial
        await inventory_repo.add_item(user_id, item_id=11, quantity=1)  # 1 Daga
        # Armadura inicial (Newbie)
        await inventory_repo.add_item(user_id, item_id=1073, quantity=1)  # Armadura de Aprendiz

        # Herramientas de trabajo (Newbie)
        await inventory_repo.add_item(user_id, item_id=561, quantity=1)  # Hacha de Leñador
        await inventory_repo.add_item(user_id, item_id=562, quantity=1)  # Piquete de Minero
        await inventory_repo.add_item(user_id, item_id=563, quantity=1)  # Caña de Pescar

        logger.info(
            "Inventario inicial creado para user_id %d (30 pociones de cada tipo + equipamiento)",
            user_id,
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
