"""Tests para SpellService."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.models.player_stats import PlayerAttributes, PlayerStats
from src.services.player.spell_service import SpellService

# Constantes movidas al módulo de efectos
SPELL_ID_PARALYZE = 9
SPELL_TYPE_STATUS = 2


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
    repo.get_player_stats = AsyncMock(
        return_value=PlayerStats(min_hp=100, max_hp=100, min_mana=100, max_mana=100, min_sta=100, max_sta=100, gold=0, level=1, elu=300, experience=0)
    )
    repo.get_mana = AsyncMock(return_value=(100, 100))
    repo.get_current_hp = AsyncMock(return_value=100)
    repo.get_max_hp = AsyncMock(return_value=100)
    repo.get_player_attributes = AsyncMock(
        return_value=PlayerAttributes(strength=10, agility=10, intelligence=10, charisma=10, constitution=10)
    )
    repo.update_mana = AsyncMock()
    repo.update_hp = AsyncMock()
    repo.get_position = AsyncMock()
    repo.set_stats = AsyncMock()
    repo.get_dumb_until = AsyncMock(return_value=0.0)  # No estúpido por defecto
    repo.update_dumb_until = AsyncMock()
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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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
        mock_player_repo.update_mana.assert_called_once()
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
        mock_player_repo.get_player_stats.return_value = None
        mock_player_repo.get_mana.return_value = (0, 100)

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
        mock_player_repo.get_mana.return_value = (10, 100)  # Menos del costo
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=10, charisma=10, constitution=10
        )

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
        # Setup - hechizo que requiere NPC (target=2) para que no permita auto-cast
        spell_data = {"mana_cost": 10, "target": 2, "name": "Test Spell"}
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats.return_value = {"min_mana": 50}
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = []  # Sin NPCs
        mock_map_manager.get_players_in_map.return_value = []  # Sin jugadores

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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=50, charisma=10, constitution=10
        )
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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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

    @pytest.mark.asyncio
    async def test_cast_spell_dumb_until(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo cuando el jugador está aturdido."""
        # Setup
        spell_data = {"mana_cost": 10, "name": "Test Spell"}
        mock_spell_catalog.get_spell_data.return_value = spell_data
        future_time = time.time() + 10.0
        mock_player_repo.get_dumb_until.return_value = future_time

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
        mock_message_sender.send_console_msg.assert_called_once()
        assert "aturdido" in mock_message_sender.send_console_msg.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_cast_spell_heal_npc(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_npc_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo de curación sobre NPC."""
        # Setup
        sample_npc.hp = 50  # HP bajo
        spell_data = {
            "name": "Curación",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "heals_hp": True,
            "caster_msg": "Has curado ",
            "fx_grh": 0,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
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
        assert sample_npc.hp > 50  # Debe curar
        mock_npc_repo.update_npc_hp.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_auto_cast(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo con auto-cast (target = Usuario)."""
        # Setup - hechizo que permite auto-cast (target=1)
        spell_data = {
            "name": "Curación Propia",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "target": 1,  # Usuario
            "heals_hp": True,
            "self_msg": "Te has curado",
            "fx_grh": 0,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_current_hp.return_value = 50
        mock_player_repo.get_max_hp.return_value = 100
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.get_player_stats.return_value = PlayerStats(
            min_hp=50, max_hp=100, min_mana=50, max_mana=100, min_sta=100, max_sta=100, gold=0, level=1, elu=300, experience=0
        )
        mock_player_repo.update_hp = AsyncMock()
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = []  # Sin NPCs
        mock_map_manager.get_players_in_map.return_value = []  # Sin otros jugadores

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
        mock_message_sender.send_console_msg.assert_called()

    @pytest.mark.asyncio
    async def test_cast_spell_on_player(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo sobre otro jugador."""
        # Setup
        spell_data = {
            "name": "Bola de Fuego",
            "mana_cost": 10,
            "min_damage": 10,
            "max_damage": 20,
            "caster_msg": "Has lanzado ",
            "fx_grh": 100,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.get_position = AsyncMock(
            side_effect=[
                {"map": 1, "x": 50, "y": 50, "heading": 3},  # Caster position
                {"map": 1, "x": 51, "y": 51, "heading": 3},  # Target position
            ]
        )
        mock_map_manager.get_npcs_in_map.return_value = []  # Sin NPCs
        mock_map_manager.get_players_in_map.return_value = [1, 2]  # Jugadores en el mapa
        mock_map_manager.get_player_username = MagicMock(return_value="TargetPlayer")

        # Target player stats
        async def get_player_stats_side_effect(user_id: int) -> PlayerStats | None:
            if user_id == 1:
                return PlayerStats(
                    min_hp=100, max_hp=100, min_mana=50, max_mana=100, min_sta=100, max_sta=100, gold=0, level=1, elu=300, experience=0
                )
            return PlayerStats(
                min_hp=80, max_hp=100, min_mana=100, max_mana=100, min_sta=100, max_sta=100, gold=0, level=1, elu=300, experience=0
            )

        async def get_mana_side_effect(user_id: int) -> tuple[int, int]:
            if user_id == 1:
                return (50, 100)
            return (100, 100)

        async def get_player_attributes_side_effect(user_id: int) -> PlayerAttributes | None:
            return PlayerAttributes(strength=10, agility=10, intelligence=20, charisma=10, constitution=10)

        mock_player_repo.get_player_stats = AsyncMock(side_effect=get_player_stats_side_effect)
        mock_player_repo.get_mana = AsyncMock(side_effect=get_mana_side_effect)
        mock_player_repo.get_player_attributes = AsyncMock(side_effect=get_player_attributes_side_effect)
        mock_player_repo.get_current_hp = AsyncMock(side_effect=lambda uid: 80 if uid == 2 else 100)
        mock_player_repo.get_max_hp = AsyncMock(return_value=100)
        mock_player_repo.update_hp = AsyncMock()
        mock_player_repo.is_alive = AsyncMock(side_effect=lambda uid: uid == 2)  # Solo el target está vivo

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=51,
            target_y=51,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_player_repo.update_hp.assert_called()  # Debe actualizar HP del target

    @pytest.mark.asyncio
    async def test_cast_spell_revive(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo de resurrección."""
        # Setup
        spell_data = {
            "name": "Resurrección",
            "mana_cost": 10,
            "revives": True,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.is_alive = AsyncMock(side_effect=lambda uid: uid != 2)  # Target está muerto
        mock_player_repo.get_current_hp = AsyncMock(side_effect=lambda uid: 0 if uid == 2 else 50)
        mock_player_repo.get_max_hp.return_value = 100
        mock_player_repo.update_hp = AsyncMock()
        mock_player_repo.get_player_stats = AsyncMock(
            side_effect=lambda uid: PlayerStats(
                min_hp=0 if uid == 2 else 50,
                max_hp=100,
                min_mana=50 if uid == 1 else 100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=0,
            )
        )

        async def get_position_side_effect(user_id: int) -> dict[str, int] | None:
            if user_id == 1:
                return {"map": 1, "x": 50, "y": 50, "heading": 3}
            if user_id == 2:
                return {"map": 1, "x": 51, "y": 51, "heading": 3}
            return None

        mock_player_repo.get_position = AsyncMock(side_effect=get_position_side_effect)
        mock_map_manager.get_npcs_in_map.return_value = []
        mock_map_manager.get_players_in_map.return_value = [1, 2]
        mock_map_manager.get_player_username = MagicMock(return_value="Muerto")
        mock_map_manager.get_player_message_sender = MagicMock(return_value=mock_message_sender)

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=51,
            target_y=51,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_message_sender.send_console_msg.assert_any_call("Has resucitado a Muerto.")

    @pytest.mark.asyncio
    async def test_cast_spell_revive_not_dead(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test intentar resucitar a un jugador que no está muerto."""
        # Setup
        spell_data = {
            "name": "Resurrección",
            "mana_cost": 10,
            "revives": True,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.is_alive = AsyncMock(return_value=True)  # Target está vivo
        mock_player_repo.get_current_hp.return_value = 50
        mock_player_repo.get_max_hp.return_value = 100
        mock_player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=50, max_hp=100, min_mana=50, max_mana=100, min_sta=100, max_sta=100, gold=0, level=1, elu=300, experience=0
            )
        )

        async def get_position_side_effect(user_id: int) -> dict[str, int] | None:
            if user_id == 1:
                return {"map": 1, "x": 50, "y": 50, "heading": 3}
            if user_id == 2:
                return {"map": 1, "x": 51, "y": 51, "heading": 3}
            return None

        mock_player_repo.get_position = AsyncMock(side_effect=get_position_side_effect)
        mock_map_manager.get_npcs_in_map.return_value = []
        mock_map_manager.get_players_in_map.return_value = [1, 2]
        mock_map_manager.get_player_username = MagicMock(return_value="Vivo")

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=51,
            target_y=51,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is False
        mock_message_sender.send_console_msg.assert_any_call("Vivo no está muerto.")

    @pytest.mark.asyncio
    async def test_cast_spell_poison_npc(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_npc_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo que envenena a un NPC."""
        # Setup
        spell_data = {
            "name": "Veneno",
            "mana_cost": 10,
            "min_damage": 5,
            "max_damage": 10,
            "poisons": True,
            "caster_msg": "Has envenenado ",
            "fx_grh": 0,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]
        mock_npc_repo.update_npc_poisoned_until = AsyncMock()

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
        mock_npc_repo.update_npc_poisoned_until.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_paralyze_npc(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_npc_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
        sample_npc: NPC,
    ) -> None:
        """Test lanzar hechizo que paraliza a un NPC."""
        # Setup
        spell_data = {
            "name": "Paralizar",
            "mana_cost": 10,
            "min_damage": 0,
            "max_damage": 0,
            "type": SPELL_TYPE_STATUS,
            "caster_msg": "Has paralizado ",
            "fx_grh": 0,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_mana.return_value = (50, 100)
        mock_player_repo.get_player_attributes.return_value = PlayerAttributes(
            strength=10, agility=10, intelligence=20, charisma=10, constitution=10
        )
        mock_player_repo.get_position.return_value = {"map": 1, "x": 50, "y": 50, "heading": 3}
        mock_map_manager.get_npcs_in_map.return_value = [sample_npc]
        mock_npc_repo.update_npc_paralyzed_until = AsyncMock()

        # Execute - usar spell_id de paralizar
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=SPELL_ID_PARALYZE,
            target_x=50,
            target_y=50,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_npc_repo.update_npc_paralyzed_until.assert_called_once()

    @pytest.mark.asyncio
    async def test_cast_spell_heal_player(
        self,
        spell_service: SpellService,
        mock_spell_catalog: MagicMock,
        mock_player_repo: MagicMock,
        mock_map_manager: MagicMock,
        mock_message_sender: MagicMock,
    ) -> None:
        """Test lanzar hechizo de curación sobre jugador."""
        # Setup
        spell_data = {
            "name": "Curación",
            "mana_cost": 10,
            "min_damage": 20,
            "max_damage": 30,
            "heals_hp": True,
            "caster_msg": "Has curado ",
            "fx_grh": 0,
            "loops": 1,
        }
        mock_spell_catalog.get_spell_data.return_value = spell_data
        mock_player_repo.get_stats = AsyncMock(
            side_effect=lambda uid: {
                "min_mana": 50,
                "attr_int": 20,
                "min_hp": 50 if uid == 1 else 30,
                "max_hp": 100,
            }
        )
        mock_player_repo.get_position = AsyncMock(
            side_effect=[
                {"map": 1, "x": 50, "y": 50, "heading": 3},
                {"map": 1, "x": 51, "y": 51, "heading": 3},
            ]
        )
        mock_map_manager.get_npcs_in_map.return_value = []
        mock_map_manager.get_players_in_map.return_value = [1, 2]
        mock_map_manager.get_player_username = MagicMock(return_value="TargetPlayer")
        mock_map_manager.get_player_message_sender = MagicMock(return_value=mock_message_sender)

        # Execute
        result = await spell_service.cast_spell(
            user_id=1,
            spell_id=1,
            target_x=51,
            target_y=51,
            message_sender=mock_message_sender,
        )

        # Assert
        assert result is True
        mock_player_repo.update_hp.assert_called()  # Debe actualizar HP del target
