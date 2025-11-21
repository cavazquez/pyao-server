"""Tests para CommerceService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.item import Item, ItemType
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.player_repository import PlayerRepository
from src.services.commerce_service import CommerceService


@pytest.fixture
def mock_item() -> Item:
    """Crea un item de prueba."""
    return Item(
        item_id=1,
        name="Poción de Vida",
        item_type=ItemType.POTION,
        graphic_id=100,
        value=100,  # Precio de compra: 100 oro
        stackable=True,
    )


@pytest.fixture
def mock_item_no_value() -> Item:
    """Crea un item sin precio (no vendible)."""
    return Item(
        item_id=2,
        name="Item Especial",
        item_type=ItemType.MISC,
        graphic_id=101,
        value=0,  # Sin precio
        stackable=False,
    )


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Crea un mock de InventoryRepository."""
    repo = MagicMock(spec=InventoryRepository)
    repo.has_space = AsyncMock(return_value=True)
    repo.add_item = AsyncMock(return_value=[(1, 5)])  # Slot 1, cantidad 5
    repo.remove_item = AsyncMock(return_value=True)
    repo.get_slot = AsyncMock(return_value=(1, 10))  # item_id=1, quantity=10
    return repo


@pytest.fixture
def mock_merchant_repo() -> MagicMock:
    """Crea un mock de MerchantRepository."""
    repo = MagicMock(spec=MerchantRepository)
    repo.get_item = AsyncMock(return_value=MagicMock(item_id=1, quantity=10))
    repo.remove_item = AsyncMock(return_value=True)
    repo.add_item = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Crea un mock de PlayerRepository."""
    repo = MagicMock(spec=PlayerRepository)
    repo.get_gold = AsyncMock(return_value=1000)  # 1000 oro
    repo.update_gold = AsyncMock()
    return repo


@pytest.fixture
def commerce_service(
    mock_inventory_repo: MagicMock,
    mock_merchant_repo: MagicMock,
    mock_player_repo: MagicMock,
    mock_item: Item,
) -> CommerceService:
    """Crea una instancia de CommerceService con mocks."""
    item_catalog = {1: mock_item}
    return CommerceService(
        inventory_repo=mock_inventory_repo,
        merchant_repo=mock_merchant_repo,
        item_catalog=item_catalog,
        player_repo=mock_player_repo,
    )


@pytest.mark.asyncio
class TestCommerceServiceBuyItem:
    """Tests para el método buy_item de CommerceService."""

    async def test_buy_item_success(
        self,
        commerce_service: CommerceService,
    ) -> None:
        """Test de compra exitosa."""
        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is True
        assert "Has comprado 5x Poción de Vida por 500 oro" in message
        commerce_service.player_repo.update_gold.assert_called_once_with(1, 500)  # 1000 - 500
        commerce_service.inventory_repo.add_item.assert_called_once_with(1, 1, 5)
        commerce_service.merchant_repo.remove_item.assert_called_once_with(2, 1, 5)

    async def test_buy_item_invalid_quantity(
        self,
        commerce_service: CommerceService,
    ) -> None:
        """Test con cantidad inválida (0 o negativa)."""
        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=0)

        assert success is False
        assert message == "Cantidad inválida"

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=-1)

        assert success is False
        assert message == "Cantidad inválida"

    async def test_buy_item_merchant_has_no_item(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
    ) -> None:
        """Test cuando el mercader no tiene el item."""
        mock_merchant_repo.get_item = AsyncMock(return_value=None)

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "El mercader no tiene ese item"

    async def test_buy_item_insufficient_merchant_quantity(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
    ) -> None:
        """Test cuando el mercader no tiene suficiente cantidad."""
        merchant_item = MagicMock(item_id=1, quantity=3)  # Solo tiene 3
        mock_merchant_repo.get_item = AsyncMock(return_value=merchant_item)

        success, message = await commerce_service.buy_item(
            user_id=1,
            npc_id=2,
            slot=1,
            quantity=5,  # Intenta comprar 5
        )

        assert success is False
        assert "El mercader solo tiene 3 disponibles" in message

    async def test_buy_item_not_in_catalog(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
    ) -> None:
        """Test cuando el item no está en el catálogo."""
        merchant_item = MagicMock(item_id=999, quantity=10)  # Item inexistente
        mock_merchant_repo.get_item = AsyncMock(return_value=merchant_item)

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Item no encontrado"

    async def test_buy_item_no_price(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
        mock_item_no_value: Item,
    ) -> None:
        """Test cuando el item no tiene precio."""
        merchant_item = MagicMock(item_id=2, quantity=10)
        mock_merchant_repo.get_item = AsyncMock(return_value=merchant_item)
        commerce_service.items_catalog[2] = mock_item_no_value

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Este item no está a la venta"

    async def test_buy_item_insufficient_gold(
        self,
        commerce_service: CommerceService,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador no tiene suficiente oro."""
        mock_player_repo.get_gold = AsyncMock(return_value=100)  # Solo 100 oro
        # Precio total: 100 * 5 = 500 oro

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert "No tienes suficiente oro" in message
        assert "Necesitas 500 oro" in message

    async def test_buy_item_inventory_full(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test cuando el inventario está lleno."""
        mock_inventory_repo.has_space = AsyncMock(return_value=False)

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Tu inventario está lleno"

    async def test_buy_item_add_item_fails(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando falla agregar item al inventario (rollback de oro)."""
        mock_inventory_repo.add_item = AsyncMock(return_value=None)  # Falla
        initial_gold = 1000

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert "No se pudo agregar el item al inventario" in message
        # Verificar rollback: se devuelve el oro original
        assert mock_player_repo.update_gold.call_count == 2  # Resta y luego rollback
        mock_player_repo.update_gold.assert_any_call(1, initial_gold)  # Rollback

    async def test_buy_item_remove_merchant_item_fails(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_player_repo: MagicMock,
    ) -> None:
        """Test cuando falla remover item del mercader (rollback completo)."""
        mock_merchant_repo.remove_item = AsyncMock(return_value=False)  # Falla
        initial_gold = 1000

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert "Error al procesar la compra" in message
        # Verificar rollback: oro y items
        assert mock_player_repo.update_gold.call_count == 2  # Resta y luego rollback
        mock_player_repo.update_gold.assert_any_call(1, initial_gold)  # Rollback
        mock_inventory_repo.remove_item.assert_called_once_with(1, 1, 5)  # Rollback items

    async def test_buy_item_exception_handling(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test manejo de excepciones durante la transacción."""
        # La excepción debe ocurrir dentro del bloque try/except
        # Simulamos que falla al agregar el item (dentro del try)
        mock_inventory_repo.add_item = AsyncMock(side_effect=Exception("Error de conexión"))

        success, message = await commerce_service.buy_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Error al procesar la compra"


@pytest.mark.asyncio
class TestCommerceServiceSellItem:
    """Tests para el método sell_item de CommerceService."""

    async def test_sell_item_success(
        self,
        commerce_service: CommerceService,
    ) -> None:
        """Test de venta exitosa."""
        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is True
        assert "Has vendido 5x Poción de Vida por 250 oro" in message  # 50% de 100 * 5
        commerce_service.inventory_repo.remove_item.assert_called_once_with(1, 1, 5)
        commerce_service.player_repo.update_gold.assert_called_once_with(1, 1250)  # 1000 + 250
        commerce_service.merchant_repo.add_item.assert_called_once_with(2, 1, 5)

    async def test_sell_item_invalid_quantity(
        self,
        commerce_service: CommerceService,
    ) -> None:
        """Test con cantidad inválida."""
        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=0)

        assert success is False
        assert message == "Cantidad inválida"

    async def test_sell_item_player_has_no_item(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador no tiene el item."""
        mock_inventory_repo.get_slot = AsyncMock(return_value=None)

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "No tienes ese item"

    async def test_sell_item_insufficient_quantity(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test cuando el jugador no tiene suficiente cantidad."""
        mock_inventory_repo.get_slot = AsyncMock(return_value=(1, 3))  # Solo tiene 3

        success, message = await commerce_service.sell_item(
            user_id=1,
            npc_id=2,
            slot=1,
            quantity=5,  # Intenta vender 5
        )

        assert success is False
        assert "Solo tienes 3 disponibles" in message

    async def test_sell_item_not_in_catalog(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test cuando el item no está en el catálogo."""
        mock_inventory_repo.get_slot = AsyncMock(return_value=(999, 10))  # Item inexistente

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Item no encontrado"

    async def test_sell_item_cannot_sell(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
        mock_item_no_value: Item,
    ) -> None:
        """Test cuando el item no se puede vender (value=0)."""
        mock_inventory_repo.get_slot = AsyncMock(return_value=(2, 10))
        commerce_service.items_catalog[2] = mock_item_no_value

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Este item no se puede vender"

    async def test_sell_item_remove_fails(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test cuando falla remover el item del inventario."""
        mock_inventory_repo.remove_item = AsyncMock(return_value=False)

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "No se pudo remover el item"

    async def test_sell_item_merchant_inventory_full(
        self,
        commerce_service: CommerceService,
        mock_merchant_repo: MagicMock,
    ) -> None:
        """Test cuando el inventario del mercader está lleno (no hace rollback)."""
        mock_merchant_repo.add_item = AsyncMock(return_value=False)  # Mercader lleno
        initial_gold = 1000

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        # La venta es exitosa aunque el mercader no pueda recibir el item
        assert success is True
        assert "Has vendido 5x Poción de Vida por 250 oro" in message
        # El jugador recibió el oro (no hay rollback)
        commerce_service.player_repo.update_gold.assert_called_once_with(1, initial_gold + 250)

    async def test_sell_item_exception_handling(
        self,
        commerce_service: CommerceService,
        mock_inventory_repo: MagicMock,
    ) -> None:
        """Test manejo de excepciones durante la venta."""
        mock_inventory_repo.remove_item = AsyncMock(side_effect=Exception("Error de conexión"))

        success, message = await commerce_service.sell_item(user_id=1, npc_id=2, slot=1, quantity=5)

        assert success is False
        assert message == "Error al procesar la venta"
