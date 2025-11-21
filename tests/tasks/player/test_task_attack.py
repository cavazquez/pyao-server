"""Tests para TaskAttack."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC
from src.repositories.player_repository import PlayerRepository
from src.tasks.player.task_attack import TaskAttack


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Crea un mock de MessageSender."""
    sender = MagicMock()
    sender.connection.address = "127.0.0.1:1234"
    sender.send_console_msg = AsyncMock()
    sender.send_play_wave = AsyncMock()
    sender.send_create_fx = AsyncMock()
    return sender


@pytest.fixture
def mock_npc() -> NPC:
    """Crea un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance-1",
        map_id=1,
        x=50,
        y=49,  # Norte del jugador
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


@pytest.mark.asyncio
class TestTaskAttackBasic:
    """Tests básicos de validación para TaskAttack."""

    async def test_attack_without_session(self, mock_message_sender: MagicMock) -> None:
        """Test de ataque sin sesión activa."""
        player_repo = MagicMock(spec=PlayerRepository)
        data = bytes([0x08])  # ATTACK packet
        session_data = {}  # Sin user_id

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            session_data=session_data,
        )

        await task.execute()

        # No debe hacer nada

    async def test_attack_without_dependencies(self, mock_message_sender: MagicMock) -> None:
        """Test sin dependencias necesarias."""
        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=None,  # Sin dependencias
            combat_service=None,
            map_manager=None,
            session_data=session_data,
        )

        await task.execute()

        # No debe hacer nada

    async def test_attack_missing_npc_service(self, mock_message_sender: MagicMock) -> None:
        """Test sin npc_service (dependencia requerida)."""
        player_repo = MagicMock()
        combat_service = MagicMock()
        map_manager = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=None,  # Falta dependencia
            session_data=session_data,
        )

        await task.execute()

        # Debe salir temprano por falta de dependencias

    async def test_attack_no_position(self, mock_message_sender: MagicMock, mock_npc: NPC) -> None:
        """Test cuando el jugador no tiene posición."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(return_value=None)  # Sin posición

        combat_service = MagicMock()
        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        # No debe hacer nada

    async def test_attack_insufficient_stamina(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test cuando el jugador no tiene suficiente stamina."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=False)  # Sin stamina

        combat_service = MagicMock()
        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            stamina_service=stamina_service,
            session_data=session_data,
        )

        await task.execute()

        # No debe atacar
        combat_service.player_attack_npc.assert_not_called()


@pytest.mark.asyncio
class TestTaskAttackTargeting:
    """Tests para el sistema de targeting."""

    async def test_attack_no_npc_at_target(self, mock_message_sender: MagicMock) -> None:
        """Test cuando no hay NPC en la posición objetivo."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        combat_service = MagicMock()
        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[])  # Sin NPCs

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_called_once_with("No hay nada que atacar ahí.")
        mock_message_sender.send_play_wave.assert_called_once()
        combat_service.player_attack_npc.assert_not_called()

    async def test_attack_npc_not_attackable(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el NPC no es atacable."""
        friendly_npc = NPC(
            npc_id=2,
            char_index=10002,
            instance_id="test-instance-2",
            map_id=1,
            x=50,
            y=49,
            heading=3,
            name="Mercader",
            description="Un mercader amigable",
            body_id=200,
            head_id=1,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=False,
            is_attackable=False,  # No atacable
        )

        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[friendly_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_called_once_with("No puedes atacar a Mercader.")
        combat_service.player_attack_npc.assert_not_called()

    async def test_get_target_position_north(self) -> None:
        """Test cálculo de posición objetivo hacia el norte."""
        task = TaskAttack(bytes([0x08]), MagicMock())
        x, y = task._get_target_position(50, 50, 1)  # Norte
        assert x == 50
        assert y == 49

    async def test_get_target_position_east(self) -> None:
        """Test cálculo de posición objetivo hacia el este."""
        task = TaskAttack(bytes([0x08]), MagicMock())
        x, y = task._get_target_position(50, 50, 2)  # Este
        assert x == 51
        assert y == 50

    async def test_get_target_position_south(self) -> None:
        """Test cálculo de posición objetivo hacia el sur."""
        task = TaskAttack(bytes([0x08]), MagicMock())
        x, y = task._get_target_position(50, 50, 3)  # Sur
        assert x == 50
        assert y == 51

    async def test_get_target_position_west(self) -> None:
        """Test cálculo de posición objetivo hacia el oeste."""
        task = TaskAttack(bytes([0x08]), MagicMock())
        x, y = task._get_target_position(50, 50, 4)  # Oeste
        assert x == 49
        assert y == 50


@pytest.mark.asyncio
class TestTaskAttackCombat:
    """Tests para el sistema de combate."""

    async def test_attack_success_normal_hit(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test ataque exitoso con golpe normal."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 25,
                "critical": False,
                "dodged": False,
                "npc_died": False,
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        combat_service.player_attack_npc.assert_called_once()
        mock_message_sender.send_play_wave.assert_called_once()
        mock_message_sender.send_create_fx.assert_called_once()
        mock_message_sender.send_console_msg.assert_any_call("Le hiciste 25 de daño a Orco.")

    async def test_attack_success_critical_hit(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test ataque exitoso con golpe crítico."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 50,
                "critical": True,  # Crítico
                "dodged": False,
                "npc_died": False,
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_any_call(
            "¡Golpe crítico! Le hiciste 50 de daño a Orco."
        )
        # Debe mostrar efecto de crítico (send_create_fx debe ser llamado)
        assert mock_message_sender.send_create_fx.call_count >= 1

    async def test_attack_npc_dodges(self, mock_message_sender: MagicMock, mock_npc: NPC) -> None:
        """Test cuando el NPC esquiva el ataque."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 0,
                "critical": False,
                "dodged": True,  # Esquivó
                "npc_died": False,
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_called_with("¡Orco esquivó tu ataque!")
        mock_message_sender.send_create_fx.assert_called_once()

    async def test_attack_npc_dies_with_death_service(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test cuando el NPC muere (con NPCDeathService)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 50,
                "critical": False,
                "dodged": False,
                "npc_died": True,  # Murió
                "experience": 100,
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()
        npc_service.remove_npc = AsyncMock()

        npc_death_service = MagicMock()
        npc_death_service.handle_npc_death = AsyncMock()

        npc_respawn_service = MagicMock()
        npc_respawn_service.schedule_respawn = AsyncMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            npc_death_service=npc_death_service,
            npc_respawn_service=npc_respawn_service,
            session_data=session_data,
        )

        await task.execute()

        # Debe usar NPCDeathService (que maneja remove_npc internamente)
        npc_death_service.handle_npc_death.assert_called_once()
        # remove_npc y schedule_respawn son manejados por NPCDeathService

    async def test_attack_npc_dies_without_death_service(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test cuando el NPC muere (sin NPCDeathService, fallback)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 50,
                "critical": False,
                "dodged": False,
                "npc_died": True,
                "experience": 100,
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])
        map_manager.get_ground_items = MagicMock(return_value=[])  # Posición libre
        map_manager.add_ground_item = MagicMock()

        npc_service = MagicMock()
        npc_service.remove_npc = AsyncMock()

        loot_table_service = MagicMock()
        loot_table_service.get_loot_for_npc = MagicMock(return_value=[(1, 1)])  # 1x item ID 1

        item_catalog = MagicMock()
        item_catalog.get_grh_index = MagicMock(return_value=100)
        item_catalog.get_item_name = MagicMock(return_value="Manzana")

        broadcast_service = MagicMock()
        broadcast_service.broadcast_object_create = AsyncMock()

        npc_respawn_service = MagicMock()
        npc_respawn_service.schedule_respawn = AsyncMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            npc_respawn_service=npc_respawn_service,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
            broadcast_service=broadcast_service,
            session_data=session_data,
        )

        await task.execute()

        # Debe usar fallback
        mock_message_sender.send_console_msg.assert_any_call("¡Has matado a Orco! Ganaste 100 EXP.")
        npc_service.remove_npc.assert_called_once_with(mock_npc)
        map_manager.add_ground_item.assert_called_once()
        broadcast_service.broadcast_object_create.assert_called_once()

    async def test_attack_npc_survives_shows_hp(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test cuando el NPC sobrevive (muestra HP restante)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        # NPC con 25 HP restantes de 100
        mock_npc.hp = 25
        mock_npc.max_hp = 100

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(
            return_value={
                "damage": 25,
                "critical": False,
                "dodged": False,
                "npc_died": False,  # No murió
            }
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_any_call("Orco tiene 25/100 HP (25%).")

    async def test_attack_combat_service_fails(
        self, mock_message_sender: MagicMock, mock_npc: NPC
    ) -> None:
        """Test cuando el servicio de combate falla."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        combat_service = MagicMock()
        combat_service.player_attack_npc = AsyncMock(return_value=None)  # Falla

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[mock_npc])

        npc_service = MagicMock()

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            player_repo=player_repo,
            combat_service=combat_service,
            map_manager=map_manager,
            npc_service=npc_service,
            session_data=session_data,
        )

        await task.execute()

        mock_message_sender.send_console_msg.assert_called_once_with(
            "No puedes atacar en este momento."
        )


@pytest.mark.asyncio
class TestTaskAttackFindFreePosition:
    """Tests para _find_free_position_for_drop."""

    async def test_find_free_position_center_free(self) -> None:
        """Test cuando la posición central está libre."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])  # Libre

        task = TaskAttack(bytes([0x08]), MagicMock(), map_manager=map_manager)

        pos = task._find_free_position_for_drop(1, 50, 50, radius=2)

        assert pos == (50, 50)
        map_manager.get_ground_items.assert_called_once_with(1, 50, 50)

    async def test_find_free_position_center_occupied(self) -> None:
        """Test cuando la posición central está ocupada."""
        map_manager = MagicMock()
        # Primera llamada: ocupada, segunda: libre
        map_manager.get_ground_items = MagicMock(
            side_effect=[[{"item_id": 1}], []]  # Primera ocupada, segunda libre
        )

        task = TaskAttack(bytes([0x08]), MagicMock(), map_manager=map_manager)

        pos = task._find_free_position_for_drop(1, 50, 50, radius=2)

        # Debe encontrar una posición libre
        assert pos is not None
        assert pos != (50, 50)  # No es la central

    async def test_find_free_position_no_map_manager(self) -> None:
        """Test sin MapManager."""
        task = TaskAttack(bytes([0x08]), MagicMock(), map_manager=None)

        pos = task._find_free_position_for_drop(1, 50, 50, radius=2)

        assert pos is None

    async def test_find_free_position_all_occupied(self) -> None:
        """Test cuando todas las posiciones están ocupadas."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": 1}]  # Siempre ocupada
        )

        task = TaskAttack(bytes([0x08]), MagicMock(), map_manager=map_manager)

        pos = task._find_free_position_for_drop(1, 50, 50, radius=2)

        # Después de 20 intentos, debe retornar None
        assert pos is None

    async def test_find_free_position_out_of_bounds(self) -> None:
        """Test cuando las posiciones están fuera de límites."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 1}])

        task = TaskAttack(bytes([0x08]), MagicMock(), map_manager=map_manager)

        # Posición en el borde (x=1, y=1) - algunos offsets estarán fuera
        pos = task._find_free_position_for_drop(1, 1, 1, radius=2)

        # Puede retornar None si todos los intentos están fuera de límites
        # o una posición válida si encuentra una dentro de límites
        assert pos is None or (1 <= pos[0] <= 100 and 1 <= pos[1] <= 100)
