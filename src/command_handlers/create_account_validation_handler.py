"""Handler especializado para validaciones de creación de cuenta."""

import logging
from typing import TYPE_CHECKING

from src.constants.gameplay import MIN_PASSWORD_LENGTH, MIN_USERNAME_LENGTH
from src.game.character_constants import JOB_ID_TO_CLASS_NAME, RACE_ID_TO_NAME
from src.services.game.class_service import get_class_service

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.game.balance_service import BalanceService

logger = logging.getLogger(__name__)


class CreateAccountValidationHandler:
    """Handler especializado para validaciones de creación de cuenta."""

    def __init__(self, message_sender: MessageSender) -> None:
        """Inicializa el handler de validaciones.

        Args:
            message_sender: Enviador de mensajes.
        """
        self.message_sender = message_sender

    async def validate_account_fields(self, username: str, password: str, email: str) -> bool:
        """Valida username, password y email.

        Args:
            username: Nombre de usuario.
            password: Contraseña.
            email: Email.

        Returns:
            True si todos los campos son válidos.
            False si alguno es inválido (el error ya fue enviado al cliente).
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

    async def validate_character_selection(
        self,
        char_data: dict[str, int] | None,
        balance_service: BalanceService,
    ) -> tuple[str, str, int] | None:
        """Valida clase (job) y raza recibidas en los datos del personaje.

        Args:
            char_data: Datos del personaje.
            balance_service: Servicio de balance.

        Returns:
            Tupla (class_name, race_name, class_id) cuando la selección es válida.
            None si hay error (ya enviado al cliente).
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
