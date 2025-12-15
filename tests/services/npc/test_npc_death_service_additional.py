"""Tests adicionales para NPCDeathService - métodos no cubiertos."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.models.party import Party
from src.models.player_stats import PlayerStats
from src.services.npc.npc_death_service import NPCDeathService


@pytest.fixture
def sample_npc() -> NPC:
    """Crea un NPC de prueba."""
    return NPC(
        instance_id="npc_123",
        npc_id=1,
        char_index=100,
        name="Goblin",
        description="Un goblin hostil",
        x=50,
        y=50,
        map_id=1,
        heading=1,
        body_id=58,
        head_id=0,
        hp=0,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
        respawn_time=30,
        respawn_time_max=60,
        gold_min=10,
        gold_max=50,
    )


class TestPartyExperience:
    """Tests para distribución de experiencia en party."""

    @pytest.mark.asyncio
    async def test_handle_npc_death_with_party(self, sample_npc: NPC) -> None:
        """Test que la experiencia se distribuye en party."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()
        member_sender = MagicMock()
        member_sender.send_console_msg = AsyncMock()
        member_sender.send_update_exp = AsyncMock()
        member_sender.send_update_user_stats = AsyncMock()
        map_manager.get_player_message_sender = MagicMock(return_value=member_sender)

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.update_max_hp = AsyncMock()
        player_repo.update_max_mana = AsyncMock()
        player_repo.update_max_stamina = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        party_service = MagicMock()
        party = Party(party_id=1, leader_id=1, leader_username="leader")
        party.add_member(1, "leader", 1)
        party.add_member(2, "member2", 1)
        party_service.get_party_info = AsyncMock(return_value=party)
        party_service.distribute_experience = AsyncMock(
            return_value={1: 30.0, 2: 20.0}  # Experiencia distribuida
        )

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
            party_service=party_service,
        )

        # Execute
        await service.handle_npc_death(
            npc=sample_npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert - No debe enviar mensaje individual (party lo maneja)
        # El mensaje de party se envía en _give_experience
        party_service.distribute_experience.assert_called_once()

    @pytest.mark.asyncio
    async def test_distribute_party_experience(self, sample_npc: NPC) -> None:
        """Test distribución de experiencia a party."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_player_message_sender = MagicMock(
            side_effect=lambda uid: MagicMock(
                send_console_msg=AsyncMock(),
                send_update_exp=AsyncMock(),
                send_update_user_stats=AsyncMock(),
            )
            if uid in {1, 2}
            else None
        )

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.get_player_attributes = AsyncMock(return_value=None)
        player_repo.set_stats = AsyncMock()

        party_service = MagicMock()
        party_service.distribute_experience = AsyncMock(return_value={1: 30.0, 2: 20.0})

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
            party_service=party_service,
        )

        party = Party(party_id=1, leader_id=1, leader_username="leader")
        party.add_member(1, "leader", 1)
        party.add_member(2, "member2", 1)

        # Execute
        await service._distribute_party_experience(1, 50, sample_npc, party)

        # Assert
        assert player_repo.update_experience.call_count == 2  # 2 miembros recibieron exp

    @pytest.mark.asyncio
    async def test_distribute_party_experience_no_party_service(self, sample_npc: NPC) -> None:
        """Test distribución sin party_service."""
        service = NPCDeathService(
            map_manager=MagicMock(),
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
            party_service=None,
        )

        party = Party(party_id=1, leader_id=1, leader_username="leader")

        # Execute - No debe crashear
        await service._distribute_party_experience(1, 50, sample_npc, party)

    @pytest.mark.asyncio
    async def test_update_member_experience_killer(self, sample_npc: NPC) -> None:
        """Test actualización de experiencia del killer en party."""
        # Setup
        map_manager = MagicMock()
        member_sender = MagicMock()
        member_sender.send_console_msg = AsyncMock()
        member_sender.send_update_exp = AsyncMock()
        member_sender.send_update_user_stats = AsyncMock()
        map_manager.get_player_message_sender = MagicMock(return_value=member_sender)

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.get_player_attributes = AsyncMock(return_value=None)
        player_repo.set_stats = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
        )

        # Execute
        await service._update_member_experience(1, 30.0, 1, sample_npc, 50)

        # Assert - Killer recibe mensaje especial
        member_sender.send_console_msg.assert_called()
        call_args = member_sender.send_console_msg.call_args[0][0]
        assert "Has matado" in call_args
        assert "Tu party ganó" in call_args

    @pytest.mark.asyncio
    async def test_update_member_experience_other_member(self, sample_npc: NPC) -> None:
        """Test actualización de experiencia de otro miembro de party."""
        # Setup
        map_manager = MagicMock()
        member_sender = MagicMock()
        member_sender.send_console_msg = AsyncMock()
        member_sender.send_update_exp = AsyncMock()
        member_sender.send_update_user_stats = AsyncMock()
        map_manager.get_player_message_sender = MagicMock(return_value=member_sender)

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.get_player_attributes = AsyncMock(return_value=None)
        player_repo.set_stats = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
        )

        # Execute - member_id != killer_id
        await service._update_member_experience(2, 20.0, 1, sample_npc, 50)

        # Assert - Otro miembro recibe mensaje diferente
        member_sender.send_console_msg.assert_called()
        call_args = member_sender.send_console_msg.call_args[0][0]
        assert "Tu party mató" in call_args

    @pytest.mark.asyncio
    async def test_update_member_experience_no_stats(self, sample_npc: NPC) -> None:
        """Test actualización sin stats del miembro."""
        # Setup
        map_manager = MagicMock()
        member_sender = MagicMock()
        member_sender.send_console_msg = AsyncMock()
        member_sender.send_update_exp = AsyncMock()
        map_manager.get_player_message_sender = MagicMock(return_value=member_sender)

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(0, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.get_player_stats = AsyncMock(return_value=None)  # Sin stats

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
        )

        # Execute - No debe crashear
        await service._update_member_experience(1, 30.0, 1, sample_npc, 50)

    @pytest.mark.asyncio
    async def test_notify_party_kill(self, sample_npc: NPC) -> None:
        """Test notificación de kill a party."""
        # Setup
        map_manager = MagicMock()
        member_sender = MagicMock()
        member_sender.send_console_msg = AsyncMock()
        map_manager.get_player_message_sender = MagicMock(return_value=member_sender)

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        party = Party(party_id=1, leader_id=1, leader_username="leader")
        party.add_member(1, "leader", 1)
        party.add_member(2, "member2", 1)

        # Execute
        await service._notify_party_kill(party, 1, sample_npc)

        # Assert - Solo member2 debe recibir notificación (killer ya recibió su mensaje)
        member_sender.send_console_msg.assert_called_once()
        call_args = member_sender.send_console_msg.call_args
        assert call_args[0][0] == f"Tu party mató a {sample_npc.name}."
        assert call_args[1]["font_color"] == 7  # FONTTYPE_PARTY

    @pytest.mark.asyncio
    async def test_notify_party_kill_no_map_manager(self, sample_npc: NPC) -> None:
        """Test notificación sin map_manager."""
        service = NPCDeathService(
            map_manager=None,  # type: ignore[arg-type]
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        party = Party(party_id=1, leader_id=1, leader_username="leader")

        # Execute - No debe crashear
        await service._notify_party_kill(party, 1, sample_npc)


class TestLevelUp:
    """Tests para manejo de level up."""

    @pytest.mark.asyncio
    async def test_check_and_handle_level_up_no_level_up(self) -> None:
        """Test cuando no hay level up."""
        # Setup
        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.update_level_and_elu = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_update_user_stats = AsyncMock()

        service = NPCDeathService(
            map_manager=MagicMock(),
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
        )

        # Execute - Experiencia no suficiente para subir de nivel
        await service._check_and_handle_level_up(1, 1, 100, message_sender)

        # Assert - Solo actualiza ELU, no sube de nivel
        player_repo.update_level_and_elu.assert_called_once()

    @pytest.mark.asyncio
    async def test_give_solo_experience_no_stats(self) -> None:
        """Test dar experiencia sin stats."""
        # Setup
        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(0, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.get_player_stats = AsyncMock(return_value=None)  # Sin stats

        service = NPCDeathService(
            map_manager=MagicMock(),
            npc_repo=MagicMock(),
            player_repo=player_repo,
            broadcast_service=MagicMock(),
        )

        message_sender = MagicMock()
        message_sender.send_update_exp = AsyncMock()

        # Execute - No debe crashear
        await service._give_solo_experience(1, 50, message_sender)


class TestDropPosition:
    """Tests para búsqueda de posición para drops."""

    def test_find_free_position_for_drop_center_valid(self) -> None:
        """Test encontrar posición libre en el centro."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.is_tile_occupied = MagicMock(return_value=False)
        map_manager.can_move_to = MagicMock(return_value=True)

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        pos = service._find_free_position_for_drop(1, 50, 50)

        # Assert
        assert pos == (50, 50)  # Debe usar la posición central

    def test_find_free_position_for_drop_center_blocked(self) -> None:
        """Test cuando el centro está bloqueado."""
        # Setup
        map_manager = MagicMock()

        def can_move_to_side_effect(_map_id: int, x: int, y: int) -> bool:
            """Retorna False para el centro, True para otras posiciones."""
            return not (x == 50 and y == 50)  # Centro bloqueado, otras posiciones libres

        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.is_tile_occupied = MagicMock(return_value=False)
        map_manager.can_move_to = MagicMock(side_effect=can_move_to_side_effect)

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        pos = service._find_free_position_for_drop(1, 50, 50)

        # Assert
        assert pos is not None
        assert pos != (50, 50)  # No es la central

    def test_find_free_position_for_drop_no_position(self) -> None:
        """Test cuando no se encuentra posición libre."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.is_tile_occupied = MagicMock(return_value=False)
        map_manager.can_move_to = MagicMock(return_value=False)  # Todas bloqueadas

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        pos = service._find_free_position_for_drop(1, 50, 50, max_attempts=5)  # Pocos intentos

        # Assert
        assert pos is None

    def test_is_valid_drop_position_valid(self) -> None:
        """Test validación de posición válida."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.is_tile_occupied = MagicMock(return_value=False)
        map_manager.can_move_to = MagicMock(return_value=True)

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        is_valid = service._is_valid_drop_position(1, 50, 50)

        # Assert
        assert is_valid is True

    def test_is_valid_drop_position_has_items(self) -> None:
        """Test validación cuando hay items en la posición."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 1}])  # Hay items
        map_manager.can_move_to = MagicMock(return_value=True)

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        is_valid = service._is_valid_drop_position(1, 50, 50)

        # Assert
        assert is_valid is False

    def test_is_valid_drop_position_blocked(self) -> None:
        """Test validación cuando la posición está bloqueada."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.can_move_to = MagicMock(return_value=False)  # Bloqueada

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        is_valid = service._is_valid_drop_position(1, 50, 50)

        # Assert
        assert is_valid is False


class TestDropGold:
    """Tests para drop de oro."""

    @pytest.mark.asyncio
    async def test_drop_gold_no_position(self, sample_npc: NPC) -> None:
        """Test drop de oro sin posición libre."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.can_move_to = MagicMock(return_value=False)  # Todas bloqueadas
        map_manager.add_ground_item = MagicMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=broadcast_service,
        )

        # Execute
        await service._drop_gold(sample_npc)

        # Assert - No debe dropear oro
        map_manager.add_ground_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_drop_gold_zero_amount(self) -> None:
        """Test drop de oro con cantidad 0."""
        # Setup
        npc = NPC(
            instance_id="npc_123",
            npc_id=1,
            char_index=100,
            name="Goblin",
            description="Un goblin hostil",
            x=50,
            y=50,
            map_id=1,
            heading=1,
            body_id=58,
            head_id=0,
            hp=0,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            gold_min=0,
            gold_max=0,  # Sin oro
        )

        map_manager = MagicMock()
        map_manager.add_ground_item = MagicMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
        )

        # Execute
        await service._drop_gold(npc)

        # Assert - No debe dropear oro
        map_manager.add_ground_item.assert_not_called()


class TestRemoveNPC:
    """Tests para remover NPC del juego."""

    @pytest.mark.asyncio
    async def test_remove_npc_from_game_with_fx(self, sample_npc: NPC) -> None:
        """Test remover NPC con efecto visual de muerte."""
        # Setup
        sample_npc.fx = 100  # FX de muerte
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_create_fx = AsyncMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=broadcast_service,
        )

        # Execute
        await service._remove_npc_from_game(sample_npc)

        # Assert - Debe enviar FX de muerte
        broadcast_service.broadcast_create_fx.assert_called_once_with(
            map_id=1, char_index=100, fx=100, loops=1
        )
        broadcast_service.broadcast_character_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_npc_from_game_no_fx(self, sample_npc: NPC) -> None:
        """Test remover NPC sin efecto visual."""
        # Setup
        sample_npc.fx = 0  # Sin FX
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_create_fx = AsyncMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=broadcast_service,
        )

        # Execute
        await service._remove_npc_from_game(sample_npc)

        # Assert - No debe enviar FX
        broadcast_service.broadcast_create_fx.assert_not_called()
        broadcast_service.broadcast_character_remove.assert_called_once()


class TestDropLoot:
    """Tests para drop de loot."""

    @pytest.mark.asyncio
    async def test_drop_loot_no_loot_table_service(self, sample_npc: NPC) -> None:
        """Test drop de loot sin loot_table_service."""
        service = NPCDeathService(
            map_manager=MagicMock(),
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
            loot_table_service=None,
            item_catalog=MagicMock(),
        )

        # Execute - No debe crashear
        await service._drop_loot(sample_npc)

    @pytest.mark.asyncio
    async def test_drop_loot_no_item_catalog(self, sample_npc: NPC) -> None:
        """Test drop de loot sin item_catalog."""
        service = NPCDeathService(
            map_manager=MagicMock(),
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=MagicMock(),
            loot_table_service=MagicMock(),
            item_catalog=None,
        )

        # Execute - No debe crashear
        await service._drop_loot(sample_npc)

    @pytest.mark.asyncio
    async def test_drop_loot_no_grh_index(self, sample_npc: NPC) -> None:
        """Test drop de loot cuando el item no tiene GrhIndex."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.is_tile_occupied = MagicMock(return_value=False)
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.add_ground_item = MagicMock()

        loot_table_service = MagicMock()
        loot_table_service.get_loot_for_npc = MagicMock(return_value=[(1, 1)])  # item_id, quantity

        item_catalog = MagicMock()
        item_catalog.get_grh_index = MagicMock(return_value=None)  # Sin GrhIndex
        item_catalog.get_item_name = MagicMock(return_value="Item")

        broadcast_service = MagicMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=broadcast_service,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
        )

        # Execute
        await service._drop_loot(sample_npc)

        # Assert - No debe dropear item sin GrhIndex
        map_manager.add_ground_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_drop_loot_no_position(self, sample_npc: NPC) -> None:
        """Test drop de loot sin posición libre."""
        # Setup
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.can_move_to = MagicMock(return_value=False)  # Todas bloqueadas
        map_manager.add_ground_item = MagicMock()

        loot_table_service = MagicMock()
        loot_table_service.get_loot_for_npc = MagicMock(return_value=[(1, 1)])

        item_catalog = MagicMock()
        item_catalog.get_grh_index = MagicMock(return_value=100)
        item_catalog.get_item_name = MagicMock(return_value="Item")

        broadcast_service = MagicMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=MagicMock(),
            player_repo=MagicMock(),
            broadcast_service=broadcast_service,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
        )

        # Execute
        await service._drop_loot(sample_npc)

        # Assert - No debe dropear item
        map_manager.add_ground_item.assert_not_called()


class TestRespawn:
    """Tests para respawn de NPCs."""

    @pytest.mark.asyncio
    async def test_handle_npc_death_with_respawn(self, sample_npc: NPC) -> None:
        """Test que se programa respawn al morir."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_experience = AsyncMock(return_value=(100, 300))
        player_repo.get_level = AsyncMock(return_value=1)
        player_repo.get_player_stats = AsyncMock(
            return_value=PlayerStats(
                min_hp=100,
                max_hp=100,
                min_mana=100,
                max_mana=100,
                min_sta=100,
                max_sta=100,
                gold=0,
                level=1,
                elu=300,
                experience=100,
            )
        )
        player_repo.update_experience = AsyncMock()
        player_repo.update_level_and_elu = AsyncMock()
        player_repo.update_max_hp = AsyncMock()
        player_repo.update_max_mana = AsyncMock()
        player_repo.update_max_stamina = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        respawn_service = MagicMock()
        respawn_service.schedule_respawn = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()
        message_sender.send_update_user_stats = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
            npc_respawn_service=respawn_service,
        )

        # Execute
        await service.handle_npc_death(
            npc=sample_npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert - Debe programar respawn
        respawn_service.schedule_respawn.assert_called_once_with(sample_npc)
