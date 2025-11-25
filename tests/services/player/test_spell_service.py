"""Tests para SpellService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.services.player.spell_service import SpellService


@pytest.fixture
def mock_spell_catalog() -> MagicMock:
    """Crea un mock de SpellCatalog."""
    catalog = MagicMock()
    catalog.get_spell_data = MagicMock()
    return catalog


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Crea un mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_stats = AsyncMock()
    repo.get_position = AsyncMock()
    repo.set_stats = AsyncMock()
    return repo


@pytest.fixture
def mock_npc_repo() -> MagicMock:
    """Crea un mock de NPCRepository."""
    repo = MagicMock()
    repo.update_npc_hp = AsyncMock()
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Crea un mock de MapManager."""
    return MagicMock()


@pytest.fixture
def mock_npc_death_service() -> MagicMock:
    """Crea un mock de NPCDeathService."""
    service = MagicMock()
    service.handle_npc_death = AsyncMock()
    return service


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Crea un mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    sender.send_create_fx_at_position = AsyncMock()
    return sender


@pytest.fixture
def spell_service(
    mock_spell_catalog: MagicMock,
    mock_player_repo: MagicMock,
    mock_npc_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_npc_death_service: MagicMock,
) -> SpellService:
    """Crea una instancia de SpellService con mocks."""
    return SpellService(
        spell_catalog=mock_spell_catalog,
        player_repo=mock_player_repo,
        npc_repo=mock_npc_repo,
        map_manager=mock_map_manager,
        npc_death_service=mock_npc_death_service,
    )


@pytest.fixture
def sample_npc() -> NPC:
    """Crea un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance-1",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Orco",
        description="Un orco hostil",
        body_id=100,
        head_id=0,
        hp=50,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
    )


class TestCastSpell:
    """Tests para cast_spell."""

    @pytest.mark.asyncio
    async def test_cast_spell_success(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_npc_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo exitosamente."""
        # Setup
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 20,
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_player_repo.set_stats.assert_called_once()
        mock_npc_repo.update_npc_hp.assert_called_once()
        mock_message_sender.send_console_msg.assert_called()
        mock_message_sender.send_update_user_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_spell_not_found(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo inexistente."""
        # Setup
        mock_spell_catalog.get_spell_data.return_value = None

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=999,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False
        mock_message_sender.send_console_msg.assert_not_called()

    @pytest.mark.asyncio
    async def test_cast_spell_no_stats(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo sin stats del jugador."""
        # Setup
        mock_spell_catalog.get_spell_data.return_value = {"mana_cost": 10}
        mock_player_repo.get_stats.return_value = None

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_cast_spell_insufficient_mana(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo sin mana suficiente."""
        # Setup
        spell_data = {"mana_cost": 50}
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {"min_mana": 10}  # Menos del costo

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False
        mock_message_sender.send_console_msg.assert_called_once_with("No tienes suficiente mana.")

    @pytest.mark.asyncio
    async def test_cast_spell_no_position(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo sin posición del jugador."""
        # Setup
        spell_data = {"mana_cost": 10}
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {"min_mana": 50}
        mock_player_repo.get_position.return_value = None

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_cast_spell_no_target(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo sin objetivo en la posición."""
        # Setup
        spell_data = {"mana_cost": 10}
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {"min_mana": 50}
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = []  # Sin NPCs

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False
        mock_message_sender.send_console_msg.assert_called_once_with(
            "No hay objetivo válido en esa posición."
        )

    @pytest.mark.asyncio
    async def test_cast_spell_npc_dies(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_npc_death_service: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo que mata al NPC."""
        # Setup
        sample_npc.hp = 10  # HP bajo
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 20,
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        # Debe llamar al death service
        mock_npc_death_service.handle_npc_death.assert_called_once()
        # No debe actualizar HP en Redis (NPC murió)
        spell_service.npc_repo.update_npc_hp.assert_not_called()

    @pytest.mark.asyncio
    async def test_cast_spell_npc_dies_no_death_service(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo que mata al NPC sin death service."""
        # Setup
        spell_service.npc_death_service = None  # Sin death service
        sample_npc.hp = 10
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 20,
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        # Debe enviar mensaje de fallback
        mock_message_sender.send_console_msg.assert_any_call(f"Has matado a {sample_npc.name}!")

    @pytest.mark.asyncio
    async def test_cast_spell_with_intelligence_bonus(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo con bonus de inteligencia."""
        # Setup
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 50,  # 50 de inteligencia = 50% bonus
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        # El daño debe incluir el bonus de inteligencia

    @pytest.mark.asyncio
    async def test_cast_spell_with_fx(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo con efecto visual."""
        # Setup
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 2,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 20,
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_message_sender.send_create_fx_at_position.assert_called_once_with(50, 50, 100, 2)

    @pytest.mark.asyncio
    async def test_cast_spell_no_fx(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo sin efecto visual."""
        # Setup
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "caster_msg": "Has lanzado ",
            "fx_grh": 0,  # Sin FX
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {
            "min_mana": 50,
            "attr_int": 20,
        }
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        # No debe enviar FX si fx_grh es 0
        mock_message_sender.send_create_fx_at_position.assert_not_called()
