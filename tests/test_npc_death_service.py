"""Tests para NPCDeathService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.npc import NPC
from src.services.npc.npc_death_service import NPCDeathService


@pytest.mark.asyncio
class TestNPCDeathService:
    """Tests para el servicio de muerte de NPCs."""

    async def test_handle_npc_death_gives_experience(self) -> None:
        """Test que el jugador recibe experiencia al matar un NPC."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_stats = AsyncMock(return_value={"exp": 100})
        player_repo.update_experience = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
        )

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
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
        )

        # Execute
        await service.handle_npc_death(
            npc=npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert
        player_repo.update_experience.assert_called_once_with(1, 150)  # 100 + 50
        message_sender.send_update_exp.assert_called_once_with(150)
        message_sender.send_console_msg.assert_called()

    async def test_handle_npc_death_removes_npc(self) -> None:
        """Test que el NPC es removido del juego al morir."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_stats = AsyncMock(return_value={"exp": 100})
        player_repo.update_experience = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
        )

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
            respawn_time=30,
            respawn_time_max=60,
            gold_min=0,
            gold_max=0,
        )

        # Execute
        await service.handle_npc_death(
            npc=npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="hechizo",
        )

        # Assert - NPC removido del MapManager
        map_manager.remove_npc.assert_called_once_with(1, "100")

        # Assert - Broadcast CHARACTER_REMOVE
        broadcast_service.broadcast_character_remove.assert_called_once_with(
            map_id=1, char_index=100
        )

        # Assert - NPC eliminado de Redis
        npc_repo.remove_npc.assert_called_once_with("npc_123")

    async def test_handle_npc_death_drops_gold(self) -> None:
        """Test que el NPC dropea oro al morir."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.add_ground_item = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_stats = AsyncMock(return_value={"exp": 100})
        player_repo.update_experience = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
        )

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
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
        )

        # Execute
        await service.handle_npc_death(
            npc=npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert - Oro dropeado
        map_manager.add_ground_item.assert_called_once()
        broadcast_service.broadcast_object_create.assert_called()

    async def test_drop_position_avoids_blocked_tiles(self) -> None:
        """Test que los drops no caen en tiles bloqueados."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        # Primera posición bloqueada, segunda libre
        map_manager.can_move_to = MagicMock(side_effect=[False, True])
        map_manager.add_ground_item = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_stats = AsyncMock(return_value={"exp": 100})
        player_repo.update_experience = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
        )

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
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
        )

        # Execute
        await service.handle_npc_death(
            npc=npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert - can_move_to llamado al menos 2 veces (primera bloqueada, segunda libre)
        assert map_manager.can_move_to.call_count >= 2

        # Assert - Oro dropeado en posición válida
        map_manager.add_ground_item.assert_called_once()

    async def test_handle_npc_death_with_loot_table(self) -> None:
        """Test que el NPC dropea items según su loot table."""
        # Setup
        map_manager = MagicMock()
        map_manager.remove_npc = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])
        map_manager.can_move_to = MagicMock(return_value=True)
        map_manager.add_ground_item = MagicMock()

        npc_repo = MagicMock()
        npc_repo.remove_npc = AsyncMock()

        player_repo = MagicMock()
        player_repo.get_stats = AsyncMock(return_value={"exp": 100})
        player_repo.update_experience = AsyncMock()

        broadcast_service = MagicMock()
        broadcast_service.broadcast_character_remove = AsyncMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        loot_table_service = MagicMock()
        loot_table_service.get_loot_for_npc = MagicMock(
            return_value=[(1, 1), (2, 2)]  # item_id, quantity
        )

        item_catalog = MagicMock()
        item_catalog.get_grh_index = MagicMock(return_value=100)
        item_catalog.get_item_name = MagicMock(return_value="Espada")

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()
        message_sender.send_update_exp = AsyncMock()

        service = NPCDeathService(
            map_manager=map_manager,
            npc_repo=npc_repo,
            player_repo=player_repo,
            broadcast_service=broadcast_service,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
        )

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
            respawn_time=30,
            respawn_time_max=60,
            gold_min=0,
            gold_max=0,
        )

        # Execute
        await service.handle_npc_death(
            npc=npc,
            killer_user_id=1,
            experience=50,
            message_sender=message_sender,
            death_reason="combate",
        )

        # Assert - Items dropeados (2 items)
        assert map_manager.add_ground_item.call_count == 2
        assert broadcast_service.broadcast_object_create.call_count == 2
