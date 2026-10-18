"""Límites efectivos de inventario compartidos por validación y almacenamiento."""

from unittest.mock import MagicMock, patch

import pytest

from src.config.config_manager import config_manager
from src.network.packet_reader import PacketReader
from src.network.validators.bank import BankDepositPacketValidator, BankExtractItemPacketValidator
from src.network.validators.base import ValidationContext
from src.network.validators.inventory import (
    DropPacketValidator,
    EquipItemPacketValidator,
    MoveItemPacketValidator,
    UseItemPacketValidator,
)
from src.repositories.inventory_repository import InventoryRepository


@pytest.mark.parametrize("limit", [25, 30])
@pytest.mark.parametrize("slot", [0, 1, 25, 26, 30, 31])
def test_all_inventory_validators_follow_canonical_configuration(limit: int, slot: int) -> None:
    """Los slots altos son válidos sólo cuando están dentro del límite configurado."""
    original = config_manager.get

    def configured(key, default=None):
        return limit if key == "game.inventory.max_slots" else original(key, default)

    with patch.object(config_manager, "get", side_effect=configured):
        repository = InventoryRepository(MagicMock())
        assert repository.MAX_SLOTS == repository.storage.MAX_SLOTS == limit
        cases = [
            (UseItemPacketValidator(), bytes([30, slot])),
            (EquipItemPacketValidator(), bytes([36, slot])),
            (DropPacketValidator(), bytes([24, slot, 1, 0])),
            (MoveItemPacketValidator(), bytes([129, slot, 2])),
            (BankDepositPacketValidator(), bytes([43, slot, 1, 0])),
        ]
        for validator, packet in cases:
            result = validator.validate(ValidationContext(PacketReader(packet), []))
            assert result.success == (1 <= slot <= limit), (limit, slot, type(validator))
        # El origen de una extracción es el banco, cuyo límite sigue siendo independiente.
        result = BankExtractItemPacketValidator().validate(
            ValidationContext(PacketReader(bytes([41, 31, 1, 0])), [])
        )
        assert result.success


@pytest.mark.asyncio
async def test_slot_30_survives_repository_reconnect(redis_client) -> None:
    """Un item existente en el slot 30 no se trunca al recrear la fachada."""
    repository = InventoryRepository(redis_client)
    assert await repository.set_slot(12345, 30, 42, 3)
    reconnected = InventoryRepository(redis_client)
    assert await reconnected.get_slot(12345, 30) == (42, 3)
    assert not await reconnected.set_slot(12345, 31, 42, 3)
    assert not await reconnected.set_slot(12345, 0, 42, 3)
    assert await reconnected.get_slot(12345, 30) == (42, 3)
