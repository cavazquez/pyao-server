"""Definición de IDs de paquetes del protocolo Argentum Online."""

from enum import IntEnum


class ClientPacketID(IntEnum):
    """IDs de paquetes enviados por el cliente."""

    THROW_DICES = 1
    CREATE_ACCOUNT = 2


class ServerPacketID(IntEnum):
    """IDs de paquetes enviados por el servidor."""

    DICE_ROLL = 67
    ACCOUNT_CREATED = 68
    ACCOUNT_ERROR = 69
