"""Mensajes del servidor."""


class ServerMessages:
    """Mensajes que el servidor envía a los clientes."""

    # Mensajes de dados
    DICE_ROLL_RESULT = "Tiraste los dados y obtuviste: {result}"
    DICE_ROLL_SUCCESS = "¡Excelente tirada!"
    DICE_ROLL_POOR = "Mala suerte, intenta de nuevo."
