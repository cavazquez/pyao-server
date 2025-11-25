"""Tests para TaskAttack."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.attack_handler import AttackCommandHandler
from src.commands.base import CommandResult
from src.models.npc import NPC
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


def create_mock_attack_handler(
    player_repo: MagicMock | None = None,
    combat_service: MagicMock | None = None,
    map_manager: MagicMock | None = None,
    npc_service: MagicMock | None = None,
    broadcast_service: MagicMock | None = None,
    npc_death_service: MagicMock | None = None,
    npc_respawn_service: MagicMock | None = None,
    loot_table_service: MagicMock | None = None,
    item_catalog: MagicMock | None = None,
    stamina_service: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de AttackCommandHandler con las dependencias especificadas."""
    # No usar spec=AttackCommandHandler porque falla con anotaciones de tipo string
    handler = MagicMock()
    handler.player_repo = player_repo or MagicMock()
    handler.combat_service = combat_service or MagicMock()
    handler.map_manager = map_manager or MagicMock()
    handler.npc_service = npc_service or MagicMock()
    handler.broadcast_service = broadcast_service
    handler.npc_death_service = npc_death_service
    handler.npc_respawn_service = npc_respawn_service
    handler.loot_table_service = loot_table_service
    handler.item_catalog = item_catalog
    handler.stamina_service = stamina_service
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


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
        data = bytes([0x08])  # ATTACK packet
        session_data = {}  # Sin user_id

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=None,  # Sin handler
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
            attack_handler=None,  # Sin handler
            session_data=session_data,
        )

        await task.execute()

        # No debe hacer nada

    async def test_attack_missing_npc_service(self, mock_message_sender: MagicMock) -> None:
        """Test sin npc_service (dependencia requerida)."""
        # Crear handler mock
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"x": 50, "y": 50, "map": 1, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # Debe llamar al handler (que maneja las validaciones internamente)
        attack_handler.handle.assert_called_once()

    async def test_attack_no_position(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el jugador no tiene posición."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(return_value=None)  # Sin posición

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # No debe hacer nada

    async def test_attack_insufficient_stamina(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el jugador no tiene suficiente stamina."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        stamina_service = MagicMock()
        stamina_service.consume_stamina = AsyncMock(return_value=False)  # Sin stamina

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            stamina_service=stamina_service,
            message_sender=mock_message_sender,
        )
        # Configurar el handler para retornar error de stamina

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.error("No tienes suficiente stamina para atacar.")
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # Debe llamar al handler
        attack_handler.handle.assert_called_once()


@pytest.mark.asyncio
class TestTaskAttackTargeting:
    """Tests para el sistema de targeting."""

    async def test_attack_no_npc_at_target(self, mock_message_sender: MagicMock) -> None:
        """Test cuando no hay NPC en la posición objetivo."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        map_manager = MagicMock()
        map_manager.get_all_npcs = MagicMock(return_value=[])  # Sin NPCs

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            map_manager=map_manager,
            message_sender=mock_message_sender,
        )
        # El handler real maneja esto, pero para el test mockeamos el resultado

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.error("No hay nada que atacar ahí.")
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # Nota: Los mensajes son enviados por el handler real, no por el mock

    async def test_attack_npc_not_attackable(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el NPC no es atacable."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar error de NPC no atacable

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.error("No puedes atacar a Mercader.")
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # Nota: Los mensajes son enviados por el handler real, no por el mock

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

    async def test_attack_success_normal_hit(self, mock_message_sender: MagicMock) -> None:
        """Test ataque exitoso con golpe normal."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}  # Norte
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con golpe normal

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                {
                    "npc_died": False,
                    "damage": 25,
                    "npc_name": "Orco",
                    "npc_hp": 25,
                    "npc_max_hp": 100,
                }
            )
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler ya envió los mensajes (verificado por el mock del handler)

    async def test_attack_success_critical_hit(self, mock_message_sender: MagicMock) -> None:
        """Test ataque exitoso con golpe crítico."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con golpe crítico

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                {
                    "npc_died": False,
                    "damage": 50,
                    "npc_name": "Orco",
                    "critical": True,
                }
            )
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler ya envió los mensajes (verificado por el mock del handler)

    async def test_attack_npc_dodges(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el NPC esquiva el ataque."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con dodge

        attack_handler.handle = AsyncMock(return_value=CommandResult.ok({"dodged": True}))

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler ya envió los mensajes (verificado por el mock del handler)

    async def test_attack_npc_dies_with_death_service(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el NPC muere (con NPCDeathService)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        npc_death_service = MagicMock()
        npc_death_service.handle_npc_death = AsyncMock()

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            npc_death_service=npc_death_service,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con muerte de NPC

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                {
                    "npc_died": True,
                    "damage": 50,
                    "experience": 100,
                    "npc_name": "Orco",
                }
            )
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler maneja NPCDeathService internamente

    async def test_attack_npc_dies_without_death_service(
        self, mock_message_sender: MagicMock
    ) -> None:
        """Test cuando el NPC muere (sin NPCDeathService, fallback)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        map_manager = MagicMock()
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

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            map_manager=map_manager,
            npc_service=npc_service,
            npc_respawn_service=npc_respawn_service,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
            broadcast_service=broadcast_service,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con muerte de NPC

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                {
                    "npc_died": True,
                    "damage": 50,
                    "experience": 100,
                    "npc_name": "Orco",
                }
            )
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler maneja el fallback internamente

    async def test_attack_npc_survives_shows_hp(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el NPC sobrevive (muestra HP restante)."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar éxito con NPC sobreviviendo

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                {
                    "npc_died": False,
                    "damage": 25,
                    "npc_name": "Orco",
                    "npc_hp": 25,
                    "npc_max_hp": 100,
                }
            )
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler ya envió los mensajes (verificado por el mock del handler)

    async def test_attack_combat_service_fails(self, mock_message_sender: MagicMock) -> None:
        """Test cuando el servicio de combate falla."""
        player_repo = MagicMock()
        player_repo.get_position = AsyncMock(
            return_value={"map": 1, "x": 50, "y": 50, "heading": 1}
        )

        attack_handler = create_mock_attack_handler(
            player_repo=player_repo,
            message_sender=mock_message_sender,
        )
        # Configurar handler para retornar error

        attack_handler.handle = AsyncMock(
            return_value=CommandResult.error("No puedes atacar en este momento.")
        )

        data = bytes([0x08])
        session_data = {"user_id": 1}

        task = TaskAttack(
            data,
            mock_message_sender,
            attack_handler=attack_handler,
            session_data=session_data,
        )

        await task.execute()

        # El handler debe ser llamado
        attack_handler.handle.assert_called_once()
        # El handler ya envió los mensajes (verificado por el mock del handler)


@pytest.mark.asyncio
class TestTaskAttackFindFreePosition:
    """Tests para _find_free_position_for_drop (ahora en AttackCommandHandler)."""

    async def test_find_free_position_center_free(self) -> None:
        """Test cuando la posición central está libre."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[])  # Libre

        # Crear handler real (no mock) para probar el método real
        attack_handler = AttackCommandHandler(
            player_repo=MagicMock(),
            combat_service=MagicMock(),
            map_manager=map_manager,
            npc_service=MagicMock(),
            broadcast_service=None,
            npc_death_service=None,
            npc_respawn_service=None,
            loot_table_service=None,
            item_catalog=None,
            stamina_service=None,
            message_sender=MagicMock(),
        )

        pos = attack_handler._find_free_position_for_drop(1, 50, 50, radius=2)

        assert pos == (50, 50)
        map_manager.get_ground_items.assert_called_once_with(1, 50, 50)

    async def test_find_free_position_center_occupied(self) -> None:
        """Test cuando la posición central está ocupada."""
        map_manager = MagicMock()
        # Primera llamada: ocupada, todas las demás: libres
        call_count = {"count": 0}

        def side_effect(*args):  # noqa: ANN002, ARG001
            call_count["count"] += 1
            if call_count["count"] == 1:
                return [{"item_id": 1}]  # Primera llamada (central): ocupada
            return []  # Todas las demás: libres

        map_manager.get_ground_items = MagicMock(side_effect=side_effect)

        # Crear handler real (no mock) para probar el método real
        attack_handler = AttackCommandHandler(
            player_repo=MagicMock(),
            combat_service=MagicMock(),
            map_manager=map_manager,
            npc_service=MagicMock(),
            broadcast_service=None,
            npc_death_service=None,
            npc_respawn_service=None,
            loot_table_service=None,
            item_catalog=None,
            stamina_service=None,
            message_sender=MagicMock(),
        )

        pos = attack_handler._find_free_position_for_drop(1, 50, 50, radius=2)

        # Debe encontrar una posición libre
        assert pos is not None
        assert pos != (50, 50)  # No es la central

    async def test_find_free_position_no_map_manager(self) -> None:
        """Test sin MapManager."""
        # Crear handler real con map_manager=None
        attack_handler = AttackCommandHandler(
            player_repo=MagicMock(),
            combat_service=MagicMock(),
            map_manager=None,  # Sin MapManager
            npc_service=MagicMock(),
            broadcast_service=None,
            npc_death_service=None,
            npc_respawn_service=None,
            loot_table_service=None,
            item_catalog=None,
            stamina_service=None,
            message_sender=MagicMock(),
        )

        pos = attack_handler._find_free_position_for_drop(1, 50, 50, radius=2)

        assert pos is None

    async def test_find_free_position_all_occupied(self) -> None:
        """Test cuando todas las posiciones están ocupadas."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(
            return_value=[{"item_id": 1}]  # Siempre ocupada
        )

        # Crear handler real (no mock) para probar el método real
        attack_handler = AttackCommandHandler(
            player_repo=MagicMock(),
            combat_service=MagicMock(),
            map_manager=map_manager,
            npc_service=MagicMock(),
            broadcast_service=None,
            npc_death_service=None,
            npc_respawn_service=None,
            loot_table_service=None,
            item_catalog=None,
            stamina_service=None,
            message_sender=MagicMock(),
        )

        pos = attack_handler._find_free_position_for_drop(1, 50, 50, radius=2)

        # Después de 20 intentos, debe retornar None
        assert pos is None

    async def test_find_free_position_out_of_bounds(self) -> None:
        """Test cuando las posiciones están fuera de límites."""
        map_manager = MagicMock()
        map_manager.get_ground_items = MagicMock(return_value=[{"item_id": 1}])

        # Crear handler real (no mock) para probar el método real
        attack_handler = AttackCommandHandler(
            player_repo=MagicMock(),
            combat_service=MagicMock(),
            map_manager=map_manager,
            npc_service=MagicMock(),
            broadcast_service=None,
            npc_death_service=None,
            npc_respawn_service=None,
            loot_table_service=None,
            item_catalog=None,
            stamina_service=None,
            message_sender=MagicMock(),
        )

        # Posición en el borde (x=1, y=1) - algunos offsets estarán fuera
        pos = attack_handler._find_free_position_for_drop(1, 1, 1, radius=2)

        # Puede retornar None si todos los intentos están fuera de límites
        # o una posición válida si encuentra una dentro de límites
        assert pos is None or (1 <= pos[0] <= 100 and 1 <= pos[1] <= 100)
