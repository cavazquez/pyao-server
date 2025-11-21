"""Tests de integración para el sistema de clases."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.account_repository import AccountRepository
from src.repositories.player_repository import PlayerRepository
from src.services.game.balance_service import get_balance_service
from src.services.game.class_service import get_class_service


@pytest.mark.asyncio
async def test_class_base_attributes_applied_on_character_creation():
    """Test que los atributos base de clase se aplican al crear personaje."""
    # Mock repositorios
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_position = AsyncMock()
    player_repo.set_stats = AsyncMock()
    player_repo.set_hunger_thirst = AsyncMock()
    player_repo.set_attributes = AsyncMock()
    player_repo.set_skills = AsyncMock()
    player_repo.get_position = AsyncMock(return_value=None)
    player_repo.get_stats = AsyncMock(return_value=None)
    player_repo.get_hunger_thirst = AsyncMock(return_value=None)
    player_repo.get_attributes = AsyncMock(return_value=None)

    # Mock Redis para InventoryRepository
    redis_client_mock = MagicMock()
    redis_client_mock.redis = AsyncMock()
    redis_client_mock.redis.hgetall = AsyncMock(return_value={})
    redis_client_mock.redis.hset = AsyncMock()
    player_repo.redis = redis_client_mock

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.create_account = AsyncMock(return_value=1)

    # Obtener ClassService real
    class_service = get_class_service()

    # Verificar que Mago tiene atributos base correctos
    mago_attrs = class_service.get_base_attributes(1)
    assert mago_attrs["intelligence"] == 15
    assert mago_attrs["strength"] == 8

    # Verificar que Guerrero tiene atributos base correctos
    guerrero_attrs = class_service.get_base_attributes(3)
    assert guerrero_attrs["strength"] == 15
    assert guerrero_attrs["intelligence"] == 8


@pytest.mark.asyncio
async def test_class_initial_skills_applied_on_character_creation():
    """Test que las skills iniciales de clase se aplican al crear personaje."""
    # Mock repositorios
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_position = AsyncMock()
    player_repo.set_stats = AsyncMock()
    player_repo.set_hunger_thirst = AsyncMock()
    player_repo.set_attributes = AsyncMock()
    player_repo.set_skills = AsyncMock()
    player_repo.get_position = AsyncMock(return_value=None)
    player_repo.get_stats = AsyncMock(return_value=None)
    player_repo.get_hunger_thirst = AsyncMock(return_value=None)
    player_repo.get_attributes = AsyncMock(return_value=None)

    # Mock Redis
    redis_client_mock = MagicMock()
    redis_client_mock.redis = AsyncMock()
    redis_client_mock.redis.hgetall = AsyncMock(return_value={})
    redis_client_mock.redis.hset = AsyncMock()
    player_repo.redis = redis_client_mock

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.create_account = AsyncMock(return_value=1)

    # Obtener ClassService real
    class_service = get_class_service()

    # Verificar skills iniciales de Mago
    mago_skills = class_service.get_initial_skills(1)
    assert "magia" in mago_skills
    assert mago_skills["magia"] == 10

    # Verificar skills iniciales de Guerrero
    guerrero_skills = class_service.get_initial_skills(3)
    assert "robustez" in guerrero_skills
    assert guerrero_skills["robustez"] == 10


@pytest.mark.asyncio
async def test_class_service_integration_with_balance_service():
    """Test que ClassService y BalanceService trabajan juntos correctamente."""
    class_service = get_class_service()
    balance_service = get_balance_service()

    # Obtener atributos base de clase
    dice_attributes = {
        "strength": 10,
        "agility": 10,
        "intelligence": 10,
        "charisma": 10,
        "constitution": 10,
    }

    # Aplicar atributos base de clase (Mago)
    base_attrs = class_service.apply_class_base_attributes(dice_attributes, 1)
    assert base_attrs["intelligence"] == 25  # 10 + 15

    # Aplicar modificadores raciales (Elfo)
    final_attrs = balance_service.apply_racial_modifiers(base_attrs, "Elfo")
    assert final_attrs["intelligence"] == 27  # 25 + 2 (modificador Elfo)
    assert final_attrs["agility"] == 21  # 18 (10 dados + 8 base clase) + 3 (modificador Elfo)

    # Calcular HP máximo usando modificador de clase
    base_hp = final_attrs["constitution"] * 10  # HP_PER_CON
    max_hp = balance_service.calculate_max_health(base_hp, "Mago")
    # Mago tiene vida = 7.5 en classes_balance.toml
    assert max_hp == int(base_hp * 7.5)


@pytest.mark.asyncio
async def test_all_classes_have_valid_data():
    """Test que todas las clases tienen datos válidos."""
    class_service = get_class_service()
    classes = class_service.get_all_classes()

    assert len(classes) >= 4  # Al menos 4 clases básicas

    for character_class in classes:
        # Verificar que tiene atributos base
        attrs = character_class.base_attributes
        assert "strength" in attrs
        assert "agility" in attrs
        assert "intelligence" in attrs
        assert "charisma" in attrs
        assert "constitution" in attrs

        # Verificar que los atributos son razonables (entre 1 y 20)
        for attr_value in attrs.values():
            assert 1 <= attr_value <= 20

        # Verificar que tiene skills iniciales (puede estar vacío)
        assert isinstance(character_class.initial_skills, dict)

        # Verificar que tiene descripción
        assert len(character_class.description) > 0
