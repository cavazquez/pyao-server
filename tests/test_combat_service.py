"""Tests de integración para CombatService.

Estos tests verifican que CombatService coordina correctamente
los componentes: DamageCalculator, RewardCalculator, CombatValidator
y WeaponService.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.combat.combat_service import CombatService
from src.npc import NPC


@pytest.mark.asyncio
class TestCombatService:
    """Tests de integración para CombatService."""

    async def test_init_with_all_repos(self) -> None:
        """Test de inicialización con todos los repositorios."""
        player_repo = MagicMock()
        npc_repo = MagicMock()
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        service = CombatService(player_repo, npc_repo, equipment_repo, inventory_repo)

        assert service.player_repo == player_repo
        assert service.npc_repository == npc_repo
        assert service.equipment_repo == equipment_repo
        assert service.inventory_repo == inventory_repo
        assert service.damage_calculator is not None
        assert service.reward_calculator is not None
        assert service.validator is not None
        assert service.weapon_service is not None

    async def test_init_without_optional_repos(self) -> None:
        """Test de inicialización sin repositorios opcionales."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        service = CombatService(player_repo, npc_repo)

        assert service.weapon_service is None

    async def test_player_attack_npc_success(self) -> None:
        """Test de ataque exitoso de jugador a NPC."""
        player_repo = MagicMock()
        npc_repo = MagicMock()
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        # Setup mocks
        player_repo.get_stats = AsyncMock(return_value={"strength": 20})
        player_repo.get_attributes = AsyncMock(return_value={"agility": 10})
        npc_repo.update_npc_hp = AsyncMock()
        equipment_repo.get_all_equipment = AsyncMock(return_value={})
        inventory_repo.get_slot = AsyncMock(return_value=None)

        service = CombatService(player_repo, npc_repo, equipment_repo, inventory_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=50,
            max_hp=50,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        with patch("src.combat_critical_calculator.random.random", return_value=1.0):
            result = await service.player_attack_npc(1, npc)

        assert result is not None
        assert "damage" in result
        assert "critical" in result
        assert "npc_died" in result
        assert result["damage"] > 0
        assert result["critical"] is False

    async def test_player_attack_npc_kills_npc(self) -> None:
        """Test de ataque que mata al NPC."""
        player_repo = MagicMock()
        npc_repo = MagicMock()
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        # Setup mocks
        player_repo.get_stats = AsyncMock(return_value={"strength": 100, "exp": 0})
        player_repo.get_attributes = AsyncMock(return_value={"agility": 10})
        player_repo.update_experience = AsyncMock()
        npc_repo.update_npc_hp = AsyncMock()
        equipment_repo.get_all_equipment = AsyncMock(return_value={})

        service = CombatService(player_repo, npc_repo, equipment_repo, inventory_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=10,  # Poco HP
            max_hp=50,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        with patch("src.combat_critical_calculator.random.random", return_value=1.0):
            result = await service.player_attack_npc(1, npc)

        assert result is not None
        assert result["npc_died"] is True
        assert "experience" in result
        assert "gold" in result
        assert result["experience"] > 0
        assert result["gold"] > 0

    async def test_player_attack_non_attackable_npc(self) -> None:
        """Test de ataque a NPC no atacable."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        service = CombatService(player_repo, npc_repo)

        npc = NPC(
            instance_id=1,
            npc_id=2,
            name="Comerciante",
            body_id=501,
            hp=100,
            max_hp=100,
            level=10,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=False,  # No atacable
            is_hostile=False,
            char_index=0,
            description="",
            head_id=0,
        )

        result = await service.player_attack_npc(1, npc)

        assert result is None

    async def test_player_attack_without_stats(self) -> None:
        """Test de ataque sin stats del jugador."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        player_repo.get_stats = AsyncMock(return_value=None)

        service = CombatService(player_repo, npc_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=50,
            max_hp=50,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        result = await service.player_attack_npc(1, npc)

        assert result is None

    async def test_player_attack_with_weapon(self) -> None:
        """Test de ataque con arma equipada."""
        player_repo = MagicMock()
        npc_repo = MagicMock()
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        player_repo.get_stats = AsyncMock(return_value={"strength": 20})
        player_repo.get_attributes = AsyncMock(return_value={"agility": 10})
        npc_repo.update_npc_hp = AsyncMock()
        equipment_repo.get_all_equipment = AsyncMock(
            return_value={1: 5}  # Arma en slot 5
        )
        inventory_repo.get_slot = AsyncMock(return_value=(2, 1))  # Espada

        service = CombatService(player_repo, npc_repo, equipment_repo, inventory_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=100,
            max_hp=100,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        with patch("src.combat_critical_calculator.random.random", return_value=1.0):
            result = await service.player_attack_npc(1, npc)

        assert result is not None
        # El daño debería ser positivo (la defensa reduce mucho)
        assert result["damage"] > 0

    async def test_npc_attack_player_success(self) -> None:
        """Test de ataque exitoso de NPC a jugador."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        player_repo.get_stats = AsyncMock(return_value={"min_hp": 100, "strength": 20})
        player_repo.update_hp = AsyncMock()

        service = CombatService(player_repo, npc_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=50,
            max_hp=50,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        with patch("src.combat_damage_calculator.random.uniform", return_value=1.0):
            result = await service.npc_attack_player(npc, 1)

        assert result is not None
        assert "damage" in result
        assert "player_died" in result
        assert result["damage"] > 0
        assert result["player_died"] is False

    async def test_npc_attack_kills_player(self) -> None:
        """Test de ataque de NPC que mata al jugador."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        player_repo.get_stats = AsyncMock(
            return_value={"min_hp": 5, "strength": 20}  # Poco HP
        )
        player_repo.update_hp = AsyncMock()

        service = CombatService(player_repo, npc_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Dragon",
            body_id=200,
            hp=1000,
            max_hp=1000,
            level=20,  # Nivel alto
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        with patch("src.combat_damage_calculator.random.uniform", return_value=1.2):
            result = await service.npc_attack_player(npc, 1)

        assert result is not None
        assert result["player_died"] is True

    async def test_npc_attack_without_player_stats(self) -> None:
        """Test de ataque de NPC sin stats del jugador."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        player_repo.get_stats = AsyncMock(return_value=None)

        service = CombatService(player_repo, npc_repo)

        npc = NPC(
            instance_id=1,
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=50,
            max_hp=50,
            level=5,
            x=50,
            y=50,
            map_id=1,
            heading=3,
            is_attackable=True,
            is_hostile=True,
            char_index=0,
            description="",
            head_id=0,
        )

        result = await service.npc_attack_player(npc, 1)

        assert result is None

    async def test_can_attack_delegates_to_validator(self) -> None:
        """Test que can_attack delega al validador."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        service = CombatService(player_repo, npc_repo)

        attacker = {"x": 50, "y": 50}
        target = {"x": 51, "y": 50}

        result = service.can_attack(attacker, target)

        # Distancia 1, debería estar en rango
        assert result is True

    async def test_can_attack_out_of_range(self) -> None:
        """Test de ataque fuera de rango."""
        player_repo = MagicMock()
        npc_repo = MagicMock()

        service = CombatService(player_repo, npc_repo)

        attacker = {"x": 50, "y": 50}
        target = {"x": 55, "y": 55}

        result = service.can_attack(attacker, target)

        # Distancia 10, fuera de rango
        assert result is False

    async def test_components_are_initialized(self) -> None:
        """Test que todos los componentes se inicializan correctamente."""
        player_repo = MagicMock()
        npc_repo = MagicMock()
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        service = CombatService(player_repo, npc_repo, equipment_repo, inventory_repo)

        # Verificar que los componentes existen
        assert hasattr(service, "damage_calculator")
        assert hasattr(service, "reward_calculator")
        assert hasattr(service, "validator")
        assert hasattr(service, "weapon_service")

        # Verificar que tienen los métodos esperados
        assert hasattr(service.damage_calculator, "calculate_player_damage")
        assert hasattr(service.reward_calculator, "calculate_experience")
        assert hasattr(service.validator, "can_attack")
        assert hasattr(service.weapon_service, "get_weapon_damage")
