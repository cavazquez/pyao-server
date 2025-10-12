"""Definición de IDs de paquetes del protocolo Argentum Online."""

from enum import IntEnum


class ClientPacketID(IntEnum):
    """IDs de paquetes enviados por el cliente."""

    LOGIN = 0
    THROW_DICES = 1
    CREATE_ACCOUNT = 2
    REQUEST_ATTRIBUTES = 13


class ServerPacketID(IntEnum):
    """IDs de paquetes enviados por el servidor."""

    LOGIN_SUCCESS = 66
    DICE_ROLL = 67
    ACCOUNT_CREATED = 68
    ACCOUNT_ERROR = 69
    ATTRIBUTES = 70
    LOGIN_ERROR = 71
