"""Registry para mapear packet_id a validadores usando Strategy Pattern."""

from typing import TYPE_CHECKING

from src.network.packet_id import ClientPacketID
from src.network.validators.auth import CreateAccountPacketValidator, LoginPacketValidator
from src.network.validators.bank import (
    BankDepositGoldPacketValidator,
    BankDepositPacketValidator,
    BankEndPacketValidator,
    BankExtractGoldPacketValidator,
    BankExtractItemPacketValidator,
)
from src.network.validators.chat import TalkPacketValidator
from src.network.validators.commerce import (
    CommerceBuyPacketValidator,
    CommerceEndPacketValidator,
    CommerceSellPacketValidator,
)
from src.network.validators.gm import GMCommandsPacketValidator
from src.network.validators.inventory import (
    DoubleClickPacketValidator,
    DropPacketValidator,
    EquipItemPacketValidator,
    LeftClickPacketValidator,
    PickupPacketValidator,
    UseItemPacketValidator,
)
from src.network.validators.movement import (
    AttackPacketValidator,
    ChangeHeadingPacketValidator,
    RequestPositionUpdatePacketValidator,
    WalkPacketValidator,
)
from src.network.validators.simple import (
    AyudaPacketValidator,
    InformationPacketValidator,
    MeditatePacketValidator,
    OnlinePacketValidator,
    PingPacketValidator,
    QuitPacketValidator,
    RequestAttributesPacketValidator,
    RequestMotdPacketValidator,
    RequestStatsPacketValidator,
    ThrowDicesPacketValidator,
    UptimePacketValidator,
)
from src.network.validators.spells import (
    CastSpellPacketValidator,
    MoveSpellPacketValidator,
    SpellInfoPacketValidator,
)

if TYPE_CHECKING:
    from src.network.validators.base import PacketValidatorProtocol


class PacketValidatorRegistry:
    """Registry que mapea packet_id a validadores."""

    def __init__(self) -> None:
        """Inicializa el registry con todos los validadores disponibles."""
        self._validators: dict[int, PacketValidatorProtocol] = {
            ClientPacketID.LOGIN: LoginPacketValidator(),
            ClientPacketID.THROW_DICES: ThrowDicesPacketValidator(),
            ClientPacketID.CREATE_ACCOUNT: CreateAccountPacketValidator(),
            ClientPacketID.TALK: TalkPacketValidator(),
            ClientPacketID.WALK: WalkPacketValidator(),
            ClientPacketID.REQUEST_POSITION_UPDATE: RequestPositionUpdatePacketValidator(),
            ClientPacketID.ATTACK: AttackPacketValidator(),
            ClientPacketID.PICK_UP: PickupPacketValidator(),
            ClientPacketID.REQUEST_ATTRIBUTES: RequestAttributesPacketValidator(),
            ClientPacketID.COMMERCE_END: CommerceEndPacketValidator(),
            ClientPacketID.BANK_END: BankEndPacketValidator(),
            ClientPacketID.DROP: DropPacketValidator(),
            ClientPacketID.CAST_SPELL: CastSpellPacketValidator(),
            ClientPacketID.LEFT_CLICK: LeftClickPacketValidator(),
            ClientPacketID.DOUBLE_CLICK: DoubleClickPacketValidator(),
            ClientPacketID.USE_ITEM: UseItemPacketValidator(),
            ClientPacketID.EQUIP_ITEM: EquipItemPacketValidator(),
            ClientPacketID.CHANGE_HEADING: ChangeHeadingPacketValidator(),
            ClientPacketID.COMMERCE_BUY: CommerceBuyPacketValidator(),
            ClientPacketID.SPELL_INFO: SpellInfoPacketValidator(),
            ClientPacketID.MOVE_SPELL: MoveSpellPacketValidator(),
            ClientPacketID.BANK_EXTRACT_ITEM: BankExtractItemPacketValidator(),
            ClientPacketID.COMMERCE_SELL: CommerceSellPacketValidator(),
            ClientPacketID.BANK_DEPOSIT: BankDepositPacketValidator(),
            ClientPacketID.ONLINE: OnlinePacketValidator(),
            ClientPacketID.QUIT: QuitPacketValidator(),
            ClientPacketID.MEDITATE: MeditatePacketValidator(),
            ClientPacketID.AYUDA: AyudaPacketValidator(),
            ClientPacketID.REQUEST_STATS: RequestStatsPacketValidator(),
            ClientPacketID.INFORMATION: InformationPacketValidator(),
            ClientPacketID.REQUEST_MOTD: RequestMotdPacketValidator(),
            ClientPacketID.UPTIME: UptimePacketValidator(),
            ClientPacketID.PING: PingPacketValidator(),
            ClientPacketID.BANK_EXTRACT_GOLD: BankExtractGoldPacketValidator(),
            ClientPacketID.BANK_DEPOSIT_GOLD: BankDepositGoldPacketValidator(),
            ClientPacketID.GM_COMMANDS: GMCommandsPacketValidator(),
        }

    def get_validator(self, packet_id: int) -> PacketValidatorProtocol | None:
        """Obtiene el validador registrado para un packet_id.

        Returns:
            El validador registrado o None si no existe.
        """
        return self._validators.get(packet_id)

    def has_validator(self, packet_id: int) -> bool:
        """Indica si existe un validador registrado para el packet_id.

        Returns:
            True si hay validador, False en caso contrario.
        """
        return packet_id in self._validators


_packet_validator_registry: PacketValidatorRegistry = PacketValidatorRegistry()


def get_packet_validator_registry() -> PacketValidatorRegistry:
    """Obtiene la instancia global del registry (singleton).

    Returns:
        Instancia única de PacketValidatorRegistry.
    """
    return _packet_validator_registry
