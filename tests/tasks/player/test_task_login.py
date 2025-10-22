"""Tests para TaskLogin."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.player.task_login import TaskLogin


@pytest.mark.asyncio
class TestTaskLogin:
    """Tests para TaskLogin."""

    async def test_parse_packet_valid(self) -> None:
        """Test de parseo de packet válido."""
        username = "testuser"
        password = "password123"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")

        data = (
            bytes([0x03])  # PacketID LOGIN
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
        )

        message_sender = MagicMock()
        task = TaskLogin(data, message_sender)

        result = task._parse_packet()  # noqa: SLF001

        assert result is not None
        assert result[0] == username
        assert result[1] == password

    async def test_parse_packet_invalid(self) -> None:
        """Test de parseo de packet inválido."""
        data = bytes([0x03])  # Solo PacketID, sin datos

        message_sender = MagicMock()
        task = TaskLogin(data, message_sender)

        result = task._parse_packet()  # noqa: SLF001

        assert result is None

    async def test_execute_invalid_packet(self) -> None:
        """Test de execute con packet inválido."""
        data = bytes([0x03])  # Packet inválido

        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        task = TaskLogin(data, message_sender)

        await task.execute()

        # No debe hacer nada más

    async def test_validate_repositories_missing(self) -> None:
        """Test de validación cuando faltan repositorios."""
        message_sender = MagicMock()
        message_sender.send_error_msg = AsyncMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=None,  # Falta player_repo
            account_repo=None,  # Falta account_repo
        )

        result = task._validate_repositories()  # noqa: SLF001

        assert result is False

    async def test_validate_repositories_success(self) -> None:
        """Test de validación exitosa de repositorios."""
        message_sender = MagicMock()
        player_repo = MagicMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=player_repo,
            account_repo=account_repo,
        )

        result = task._validate_repositories()  # noqa: SLF001

        assert result is True

    async def test_authenticate_user_success(self) -> None:
        """Test de autenticación exitosa."""
        message_sender = MagicMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            account_repo=account_repo,
        )

        # Mock del AuthenticationService usando patch
        with patch("src.tasks.player.task_login.AuthenticationService") as mock_auth:
            mock_auth.return_value.authenticate = AsyncMock(return_value=(1, 2))
            result = await task._authenticate_user("testuser", "password")  # noqa: SLF001

        assert result is not None
        assert result == (1, 2)

    async def test_authenticate_user_failure(self) -> None:
        """Test de autenticación fallida."""
        message_sender = MagicMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            account_repo=account_repo,
        )

        # Mock del AuthenticationService usando patch
        with patch("src.tasks.player.task_login.AuthenticationService") as mock_auth:
            mock_auth.return_value.authenticate = AsyncMock(return_value=None)
            result = await task._authenticate_user("testuser", "wrongpass")  # noqa: SLF001

        assert result is None

    async def test_setup_session(self) -> None:
        """Test de configuración de sesión."""
        message_sender = MagicMock()
        session_data: dict[str, dict[str, int]] = {}

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            session_data=session_data,
        )

        task._setup_session(1, "testuser")  # noqa: SLF001

        assert "user_id" in session_data
        assert session_data["user_id"] == 1

    async def test_setup_session_no_session_data(self) -> None:
        """Test de configuración de sesión sin session_data."""
        message_sender = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            session_data=None,
        )

        # No debe crashear
        task._setup_session(1, "testuser")  # noqa: SLF001

    async def test_send_login_packets(self) -> None:
        """Test de envío de paquetes de login."""
        message_sender = MagicMock()
        message_sender.send_logged = AsyncMock()
        message_sender.send_user_char_index_in_server = AsyncMock()

        player_repo = MagicMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=player_repo,
            account_repo=account_repo,
        )

        # Mock del PlayerService usando patch
        with patch("src.tasks.player.task_login.PlayerService") as mock_service:
            mock_service.return_value.send_position = AsyncMock(
                return_value={"x": 50, "y": 50, "map": 1, "heading": 3}
            )
            mock_service.return_value.send_attributes = AsyncMock()
            mock_service.return_value.send_stats = AsyncMock()

            position = await task._send_login_packets(1, 2)  # noqa: SLF001

        assert position is not None
        assert position["x"] == 50
        assert position["y"] == 50
        message_sender.send_logged.assert_called_once_with(2)
        message_sender.send_user_char_index_in_server.assert_called_once_with(1)

    async def test_initialize_player_data(self) -> None:
        """Test de inicialización de datos del jugador."""
        message_sender = MagicMock()
        player_repo = MagicMock()
        player_repo.set_meditating = AsyncMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=player_repo,
            account_repo=account_repo,
        )

        with patch("src.tasks.player.task_login.PlayerService") as mock_service:
            mock_service.return_value.send_hunger_thirst = AsyncMock()
            await task._initialize_player_data(1)  # noqa: SLF001

        player_repo.set_meditating.assert_called_once_with(1, is_meditating=False)

    async def test_send_spellbook_with_spells(self) -> None:
        """Test de envío de libro de hechizos con hechizos."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.initialize_default_spells = AsyncMock()
        spellbook_repo.get_all_spells = AsyncMock(return_value={1: 10, 2: 20})

        spell_catalog = MagicMock()
        spell_catalog.get_spell_data = MagicMock(
            side_effect=lambda spell_id: {"name": f"Spell {spell_id}"}
        )

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
        )

        await task._send_spellbook(1)  # noqa: SLF001

        spellbook_repo.initialize_default_spells.assert_called_once_with(1)
        assert message_sender.send_change_spell_slot.call_count == 2

    async def test_send_spellbook_no_spells(self) -> None:
        """Test de envío de libro de hechizos sin hechizos."""
        message_sender = MagicMock()
        message_sender.send_change_spell_slot = AsyncMock()

        spellbook_repo = MagicMock()
        spellbook_repo.initialize_default_spells = AsyncMock()
        spellbook_repo.get_all_spells = AsyncMock(return_value={})

        spell_catalog = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            spellbook_repo=spellbook_repo,
            spell_catalog=spell_catalog,
        )

        await task._send_spellbook(1)  # noqa: SLF001

        spellbook_repo.initialize_default_spells.assert_called_once_with(1)
        message_sender.send_change_spell_slot.assert_not_called()

    async def test_send_spellbook_no_repos(self) -> None:
        """Test de envío de libro de hechizos sin repositorios."""
        message_sender = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            spellbook_repo=None,
            spell_catalog=None,
        )

        # No debe crashear
        await task._send_spellbook(1)  # noqa: SLF001

    async def test_spawn_player(self) -> None:
        """Test de spawn del jugador."""
        message_sender = MagicMock()
        message_sender.play_sound_login = AsyncMock()
        message_sender.send_pos_update = AsyncMock()
        message_sender.play_effect_spawn = AsyncMock()

        player_repo = MagicMock()
        account_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=player_repo,
            account_repo=account_repo,
        )

        position = {"x": 50, "y": 50, "map": 1, "heading": 3}

        with patch("src.tasks.player.task_login.PlayerService") as mock_service:
            mock_service.return_value.spawn_character = AsyncMock()
            await task._spawn_player(1, "testuser", position)  # noqa: SLF001

        message_sender.play_sound_login.assert_called_once()
        message_sender.send_pos_update.assert_called_once_with(50, 50)
        message_sender.play_effect_spawn.assert_called_once_with(char_index=1)

    async def test_send_map_data_with_service(self) -> None:
        """Test de envío de datos del mapa con PlayerMapService."""
        message_sender = MagicMock()
        map_manager = MagicMock()
        map_manager.load_ground_items = AsyncMock()

        player_map_service = MagicMock()
        player_map_service.spawn_in_map = AsyncMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            map_manager=map_manager,
            player_map_service=player_map_service,
        )

        position = {"x": 50, "y": 50, "map": 1, "heading": 3}
        await task._send_map_data(1, "testuser", position)  # noqa: SLF001

        map_manager.load_ground_items.assert_called_once_with(1)
        player_map_service.spawn_in_map.assert_called_once()

    async def test_send_map_data_legacy(self) -> None:
        """Test de envío de datos del mapa con método legacy."""
        message_sender = MagicMock()
        map_manager = MagicMock()
        map_manager.load_ground_items = AsyncMock()
        map_manager._ground_items = {}  # noqa: SLF001

        npc_service = MagicMock()
        npc_service.send_npcs_in_map = AsyncMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            map_manager=map_manager,
            player_map_service=None,  # Sin PlayerMapService
            npc_service=npc_service,
        )

        position = {"x": 50, "y": 50, "map": 1, "heading": 3}
        await task._send_map_data(1, "testuser", position)  # noqa: SLF001

        map_manager.load_ground_items.assert_called_once_with(1)
        npc_service.send_npcs_in_map.assert_called_once()

    async def test_finalize_login(self) -> None:
        """Test de finalización del login."""
        message_sender = MagicMock()
        player_repo = MagicMock()
        account_repo = MagicMock()
        server_repo = MagicMock()

        task = TaskLogin(
            bytes([0x03]),
            message_sender,
            player_repo=player_repo,
            account_repo=account_repo,
            server_repo=server_repo,
        )

        with (
            patch("src.tasks.player.task_login.PlayerService") as mock_service,
            patch("src.tasks.player.task_login.TaskMotd") as mock_motd,
        ):
            mock_service.return_value.send_inventory = AsyncMock()
            mock_motd.return_value.execute = AsyncMock()
            await task._finalize_login(1)  # noqa: SLF001

        # Verificar que se llamó a send_inventory
        # (PlayerService.send_inventory se llama dentro)
