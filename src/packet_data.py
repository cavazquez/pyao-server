"""Dataclasses para datos validados de packets."""

from dataclasses import dataclass


@dataclass
class BankDepositData:
    """Datos validados de un packet BANK_DEPOSIT.

    Attributes:
        slot: Slot del inventario (1-20).
        quantity: Cantidad a depositar (>0).
    """

    slot: int
    quantity: int


@dataclass
class BankExtractData:
    """Datos validados de un packet BANK_EXTRACT.

    Attributes:
        slot: Slot del banco (1-20).
        quantity: Cantidad a extraer (>0).
    """

    slot: int
    quantity: int


@dataclass
class CommerceBuyData:
    """Datos validados de un packet COMMERCE_BUY.

    Attributes:
        slot: Slot del inventario del mercader.
        quantity: Cantidad a comprar (>0).
    """

    slot: int
    quantity: int


@dataclass
class CommerceSellData:
    """Datos validados de un packet COMMERCE_SELL.

    Attributes:
        slot: Slot del inventario del jugador.
        quantity: Cantidad a vender (>0).
    """

    slot: int
    quantity: int


@dataclass
class LeftClickData:
    """Datos validados de un packet LEFT_CLICK.

    Attributes:
        x: Coordenada X (1-100).
        y: Coordenada Y (1-100).
    """

    x: int
    y: int


@dataclass
class LoginData:
    """Datos validados de un packet LOGIN.

    Attributes:
        username: Nombre de usuario (1-20 caracteres).
        password: Contraseña (6-32 caracteres).
    """

    username: str
    password: str


@dataclass
class DropData:
    """Datos validados de un packet DROP.

    Attributes:
        slot: Slot del inventario (1-20).
        quantity: Cantidad a tirar (>0).
    """

    slot: int
    quantity: int


@dataclass
class EquipItemData:
    """Datos validados de un packet EQUIP_ITEM.

    Attributes:
        slot: Slot del inventario (1-20).
    """

    slot: int


@dataclass
class InventoryClickData:
    """Datos validados de un packet INVENTORY_CLICK.

    Attributes:
        slot: Slot del inventario (1-20).
    """

    slot: int


@dataclass
class CastSpellData:
    """Datos validados de un packet CAST_SPELL.

    Attributes:
        slot: Slot del hechizo (1-35).
        target_x: Coordenada X del objetivo (opcional).
        target_y: Coordenada Y del objetivo (opcional).
    """

    slot: int
    target_x: int | None = None
    target_y: int | None = None
