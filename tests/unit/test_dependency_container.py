"""Tests para DependencyContainer."""

from unittest.mock import Mock

from src.core.dependency_container import DependencyContainer


def test_dependency_container_creation() -> None:  # noqa: PLR0914, PLR0915
    """Verifica que DependencyContainer se puede crear con todas las dependencias."""
    # Crear mocks para todas las dependencias
    redis_client = Mock()
    player_repo = Mock()
    account_repo = Mock()
    inventory_repo = Mock()
    equipment_repo = Mock()
    merchant_repo = Mock()
    bank_repo = Mock()
    npc_repo = Mock()
    spellbook_repo = Mock()
    ground_items_repo = Mock()
    server_repo = Mock()
    combat_service = Mock()
    commerce_service = Mock()
    spell_service = Mock()
    npc_service = Mock()
    npc_ai_service = Mock()
    npc_death_service = Mock()
    npc_respawn_service = Mock()
    loot_table_service = Mock()
    map_resources_service = Mock()
    broadcast_service = Mock()
    stamina_service = Mock()
    player_map_service = Mock()
    map_manager = Mock()
    game_tick = Mock()
    npc_catalog = Mock()
    spell_catalog = Mock()
    item_catalog = Mock()

    # Crear container
    container = DependencyContainer(
        redis_client=redis_client,
        player_repo=player_repo,
        account_repo=account_repo,
        inventory_repo=inventory_repo,
        equipment_repo=equipment_repo,
        merchant_repo=merchant_repo,
        bank_repo=bank_repo,
        npc_repo=npc_repo,
        spellbook_repo=spellbook_repo,
        ground_items_repo=ground_items_repo,
        server_repo=server_repo,
        combat_service=combat_service,
        commerce_service=commerce_service,
        spell_service=spell_service,
        npc_service=npc_service,
        npc_ai_service=npc_ai_service,
        npc_death_service=npc_death_service,
        npc_respawn_service=npc_respawn_service,
        loot_table_service=loot_table_service,
        map_transition_service=Mock(),
        map_resources_service=map_resources_service,
        broadcast_service=broadcast_service,
        stamina_service=stamina_service,
        player_map_service=player_map_service,
        map_manager=map_manager,
        game_tick=game_tick,
        npc_catalog=npc_catalog,
        spell_catalog=spell_catalog,
        item_catalog=item_catalog,
    )

    # Verificar que todas las dependencias están accesibles
    assert container.redis_client is redis_client
    assert container.player_repo is player_repo
    assert container.account_repo is account_repo
    assert container.inventory_repo is inventory_repo
    assert container.equipment_repo is equipment_repo
    assert container.merchant_repo is merchant_repo
    assert container.bank_repo is bank_repo
    assert container.npc_repo is npc_repo
    assert container.spellbook_repo is spellbook_repo
    assert container.ground_items_repo is ground_items_repo
    assert container.server_repo is server_repo
    assert container.combat_service is combat_service
    assert container.commerce_service is commerce_service
    assert container.spell_service is spell_service
    assert container.npc_service is npc_service
    assert container.npc_ai_service is npc_ai_service
    assert container.npc_death_service is npc_death_service
    assert container.npc_respawn_service is npc_respawn_service
    assert container.loot_table_service is loot_table_service
    assert container.map_resources_service is map_resources_service
    assert container.broadcast_service is broadcast_service
    assert container.stamina_service is stamina_service
    assert container.player_map_service is player_map_service
    assert container.map_manager is map_manager
    assert container.game_tick is game_tick
    assert container.npc_catalog is npc_catalog
    assert container.spell_catalog is spell_catalog
    assert container.item_catalog is item_catalog
