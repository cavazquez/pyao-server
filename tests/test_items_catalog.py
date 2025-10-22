"""Tests para el catálogo de items."""

from src.models.item import Item, ItemType
from src.models.items_catalog import ITEMS_CATALOG, get_all_items, get_item


class TestItemsCatalog:
    """Tests para el catálogo de items."""

    def test_items_catalog_loaded(self):
        """Verifica que el catálogo se haya cargado correctamente."""
        assert len(ITEMS_CATALOG) > 0
        assert isinstance(ITEMS_CATALOG, dict)

    def test_items_catalog_has_expected_count(self):
        """Verifica que se hayan cargado aproximadamente 1049 items."""
        # Puede variar ligeramente según el archivo TOML
        assert len(ITEMS_CATALOG) >= 1000
        assert len(ITEMS_CATALOG) <= 1100

    def test_items_catalog_keys_are_ints(self):
        """Verifica que las claves sean enteros."""
        for key in ITEMS_CATALOG.keys():
            assert isinstance(key, int)

    def test_items_catalog_values_are_items(self):
        """Verifica que los valores sean instancias de Item."""
        for item in ITEMS_CATALOG.values():
            assert isinstance(item, Item)

    def test_specific_items_exist(self):
        """Verifica que items específicos existan en el catálogo."""
        # Item 1: Manzana Roja
        assert 1 in ITEMS_CATALOG
        assert ITEMS_CATALOG[1].name == "Manzana Roja"
        assert ITEMS_CATALOG[1].graphic_id == 506

        # Item 38: Poción Roja
        assert 38 in ITEMS_CATALOG
        assert ITEMS_CATALOG[38].name == "Poción Roja"
        assert ITEMS_CATALOG[38].graphic_id == 542

        # Item 2: Espada Larga
        assert 2 in ITEMS_CATALOG
        assert ITEMS_CATALOG[2].name == "Espada Larga"
        assert ITEMS_CATALOG[2].graphic_id == 504


class TestGetItem:
    """Tests para la función get_item."""

    def test_get_item_existing(self):
        """Verifica que get_item retorne un item existente."""
        item = get_item(1)
        assert item is not None
        assert isinstance(item, Item)
        assert item.item_id == 1

    def test_get_item_non_existing(self):
        """Verifica que get_item retorne None para items inexistentes."""
        item = get_item(99999)
        assert item is None

    def test_get_item_potion(self):
        """Verifica que get_item retorne una poción correctamente."""
        potion = get_item(38)
        assert potion is not None
        assert potion.name == "Poción Roja"
        assert potion.item_type == ItemType.POTION
        assert potion.consumable is True

    def test_get_item_weapon(self):
        """Verifica que get_item retorne un arma correctamente."""
        weapon = get_item(2)
        assert weapon is not None
        assert weapon.name == "Espada Larga"
        assert weapon.item_type == ItemType.WEAPON
        assert weapon.min_damage is not None
        assert weapon.max_damage is not None


class TestGetAllItems:
    """Tests para la función get_all_items."""

    def test_get_all_items_returns_list(self):
        """Verifica que get_all_items retorne una lista."""
        items = get_all_items()
        assert isinstance(items, list)

    def test_get_all_items_count(self):
        """Verifica que get_all_items retorne todos los items."""
        items = get_all_items()
        assert len(items) == len(ITEMS_CATALOG)

    def test_get_all_items_contains_items(self):
        """Verifica que get_all_items contenga instancias de Item."""
        items = get_all_items()
        assert all(isinstance(item, Item) for item in items)

    def test_get_all_items_not_empty(self):
        """Verifica que get_all_items no retorne una lista vacía."""
        items = get_all_items()
        assert len(items) > 0


class TestItemProperties:
    """Tests para las propiedades de los items cargados."""

    def test_food_items_are_consumable(self):
        """Verifica que los items de comida sean consumibles."""
        manzana = get_item(1)  # Manzana Roja
        assert manzana is not None
        assert manzana.item_type == ItemType.FOOD
        assert manzana.consumable is True

    def test_potions_are_consumable(self):
        """Verifica que las pociones sean consumibles."""
        potion = get_item(38)  # Poción Roja
        assert potion is not None
        assert potion.item_type == ItemType.POTION
        assert potion.consumable is True

    def test_weapons_have_damage(self):
        """Verifica que las armas tengan daño."""
        weapon = get_item(2)  # Espada Larga
        assert weapon is not None
        assert weapon.item_type == ItemType.WEAPON
        assert weapon.min_damage is not None
        assert weapon.max_damage is not None
        assert weapon.min_damage > 0
        assert weapon.max_damage >= weapon.min_damage

    def test_items_have_graphic_id(self):
        """Verifica que todos los items tengan un graphic_id."""
        for item in get_all_items():
            assert hasattr(item, "graphic_id")
            assert isinstance(item.graphic_id, int)

    def test_items_have_name(self):
        """Verifica que todos los items tengan un nombre."""
        for item in get_all_items():
            assert hasattr(item, "name")
            assert isinstance(item.name, str)
            assert len(item.name) > 0

    def test_potion_red_properties(self):
        """Verifica las propiedades específicas de la Poción Roja."""
        potion = get_item(38)
        assert potion is not None
        assert potion.name == "Poción Roja"
        assert potion.graphic_id == 542
        assert potion.value == 20
        assert potion.restore_hp == 30
        assert potion.item_type == ItemType.POTION
