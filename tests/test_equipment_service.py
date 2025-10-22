"""Tests para EquipmentService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.player.equipment_service import EquipmentService
from src.equipment_slot import EquipmentSlot
from src.item import Item, ItemType


@pytest.fixture
def mock_equipment_repo() -> MagicMock:
    """Crea un mock de EquipmentRepository."""
    return MagicMock()


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Crea un mock de InventoryRepository."""
    return MagicMock()


@pytest.fixture
def equipment_service(
    mock_equipment_repo: MagicMock, mock_inventory_repo: MagicMock
) -> EquipmentService:
    """Crea un servicio de equipamiento para tests."""
    return EquipmentService(mock_equipment_repo, mock_inventory_repo)


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Crea un mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


class TestEquipmentService:
    """Tests para EquipmentService."""

    @pytest.mark.asyncio
    async def test_equip_weapon(
        self,
        equipment_service: EquipmentService,
        mock_equipment_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_message_sender: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test equipar un arma."""
        user_id = 1
        inventory_slot = 5

        # Mock del inventario
        mock_inventory_repo.get_inventory = AsyncMock(
            return_value={"slot_5": "2:1"}  # item_id=2 (Espada), quantity=1
        )

        # Mock del equipamiento (no hay nada equipado)
        mock_equipment_repo.is_slot_equipped = AsyncMock(return_value=None)
        mock_equipment_repo.get_equipped_slot = AsyncMock(return_value=None)
        mock_equipment_repo.equip_item = AsyncMock(return_value=True)

        # Mock del item (arma equipable)
        mock_item = Item(
            item_id=2,
            name="Espada Larga",
            item_type=ItemType.WEAPON,
            graphic_id=248,
            equippable=True,
            max_damage=8,
            min_damage=1,
        )

        def mock_get_item(item_id: int) -> Item | None:
            return mock_item if item_id == 2 else None

        monkeypatch.setattr("src.services.player.equipment_service.get_item", mock_get_item)

        # Equipar
        result = await equipment_service.toggle_equip_item(
            user_id, inventory_slot, mock_message_sender
        )

        assert result is True
        mock_equipment_repo.equip_item.assert_called_once_with(
            user_id, EquipmentSlot.WEAPON, inventory_slot
        )
        mock_message_sender.send_console_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_unequip_weapon(
        self,
        equipment_service: EquipmentService,
        mock_equipment_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_message_sender: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test desequipar un arma."""
        user_id = 1
        inventory_slot = 5

        # Mock del inventario
        mock_inventory_repo.get_inventory = AsyncMock(
            return_value={"slot_5": "2:1"}  # item_id=2 (Espada), quantity=1
        )

        # Mock del equipamiento (el item está equipado)
        mock_equipment_repo.is_slot_equipped = AsyncMock(return_value=EquipmentSlot.WEAPON)
        mock_equipment_repo.unequip_item = AsyncMock(return_value=True)

        # Mock del item
        mock_item = Item(
            item_id=2,
            name="Espada Larga",
            item_type=ItemType.WEAPON,
            graphic_id=248,
            equippable=True,
        )

        def mock_get_item(item_id: int) -> Item | None:
            return mock_item if item_id == 2 else None

        monkeypatch.setattr("src.services.player.equipment_service.get_item", mock_get_item)

        # Desequipar
        result = await equipment_service.toggle_equip_item(
            user_id, inventory_slot, mock_message_sender
        )

        assert result is True
        mock_equipment_repo.unequip_item.assert_called_once_with(user_id, EquipmentSlot.WEAPON)
        mock_message_sender.send_console_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_equip_non_equippable_item(
        self,
        equipment_service: EquipmentService,
        mock_inventory_repo: MagicMock,
        mock_message_sender: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test intentar equipar un item no equipable."""
        user_id = 1
        inventory_slot = 5

        # Mock del inventario
        mock_inventory_repo.get_inventory = AsyncMock(
            return_value={"slot_5": "1:5"}  # item_id=1 (Manzana), quantity=5
        )

        # Mock del item (no equipable)
        mock_item = Item(
            item_id=1,
            name="Manzana Roja",
            item_type=ItemType.FOOD,
            graphic_id=250,
            equippable=False,
        )

        def mock_get_item(item_id: int) -> Item | None:
            return mock_item if item_id == 1 else None

        monkeypatch.setattr("src.services.player.equipment_service.get_item", mock_get_item)

        # Intentar equipar
        result = await equipment_service.toggle_equip_item(
            user_id, inventory_slot, mock_message_sender
        )

        assert result is False
        mock_message_sender.send_console_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_equip_empty_slot(
        self,
        equipment_service: EquipmentService,
        mock_inventory_repo: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test intentar equipar desde un slot vacío."""
        user_id = 1
        inventory_slot = 5

        # Mock del inventario (slot vacío)
        mock_inventory_repo.get_inventory = AsyncMock(return_value={})

        # Intentar equipar
        result = await equipment_service.toggle_equip_item(
            user_id, inventory_slot, mock_message_sender
        )

        assert result is False
        mock_message_sender.send_console_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_replace_equipped_item(
        self,
        equipment_service: EquipmentService,
        mock_equipment_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_message_sender: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test equipar un item cuando ya hay otro equipado en ese slot."""
        user_id = 1
        inventory_slot = 5

        # Mock del inventario
        mock_inventory_repo.get_inventory = AsyncMock(
            return_value={"slot_5": "2:1"}  # Nueva espada
        )

        # Mock del equipamiento (hay otra arma equipada en slot 3)
        mock_equipment_repo.is_slot_equipped = AsyncMock(return_value=None)
        mock_equipment_repo.get_equipped_slot = AsyncMock(return_value=3)  # Slot 3 equipado
        mock_equipment_repo.unequip_item = AsyncMock(return_value=True)
        mock_equipment_repo.equip_item = AsyncMock(return_value=True)

        # Mock del item
        mock_item = Item(
            item_id=2,
            name="Espada Larga",
            item_type=ItemType.WEAPON,
            graphic_id=248,
            equippable=True,
        )

        def mock_get_item(item_id: int) -> Item | None:
            return mock_item if item_id == 2 else None

        monkeypatch.setattr("src.services.player.equipment_service.get_item", mock_get_item)

        # Equipar (debería desequipar el anterior)
        result = await equipment_service.toggle_equip_item(
            user_id, inventory_slot, mock_message_sender
        )

        assert result is True
        # Verificar que desequipó el anterior
        mock_equipment_repo.unequip_item.assert_called_once_with(user_id, EquipmentSlot.WEAPON)
        # Y equipó el nuevo
        mock_equipment_repo.equip_item.assert_called_once_with(
            user_id, EquipmentSlot.WEAPON, inventory_slot
        )

    @pytest.mark.asyncio
    async def test_get_equipped_items(
        self,
        equipment_service: EquipmentService,
        mock_equipment_repo: MagicMock,
    ) -> None:
        """Test obtener items equipados."""
        user_id = 1

        # Mock del equipamiento
        mock_equipment_repo.get_all_equipment = AsyncMock(
            return_value={
                EquipmentSlot.WEAPON: 5,
                EquipmentSlot.ARMOR: 3,
                EquipmentSlot.HELMET: 2,
            }
        )

        # Obtener items equipados
        equipped = await equipment_service.get_equipped_items(user_id)

        assert equipped == {5: True, 3: True, 2: True}
