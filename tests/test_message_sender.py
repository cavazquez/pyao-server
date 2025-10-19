"""Tests para MessageSender - Verificación de delegación a componentes.

Estos tests verifican que MessageSender:
1. Se inicializa correctamente con todos los componentes
2. Delega correctamente a cada componente especializado
3. Mantiene la retrocompatibilidad con el código existente

Los tests específicos de cada componente están en sus propios archivos:
- test_message_map_sender.py
- test_message_console_sender.py
- test_message_audio_sender.py
- test_message_visual_effects_sender.py
- test_message_player_stats_sender.py
- test_message_character_sender.py
- test_message_inventory_sender.py
- test_message_session_sender.py
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender


def test_message_sender_initialization() -> None:
    """Verifica que MessageSender se inicialice con todos los componentes."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Verificar que la conexión se guardó
    assert message_sender.connection is connection

    # Verificar que todos los componentes fueron inicializados
    assert message_sender.audio is not None
    assert message_sender.character is not None
    assert message_sender.console is not None
    assert message_sender.inventory is not None
    assert message_sender.map is not None
    assert message_sender.player_stats is not None
    assert message_sender.session is not None
    assert message_sender.visual_effects is not None


@pytest.mark.asyncio
async def test_delegation_to_session_component() -> None:
    """Verifica que los métodos de sesión deleguen correctamente a SessionMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente session
    message_sender.session.send_dice_roll = AsyncMock()
    message_sender.session.send_attributes = AsyncMock()
    message_sender.session.send_logged = AsyncMock()
    message_sender.session.send_user_char_index_in_server = AsyncMock()

    # Llamar métodos
    await message_sender.send_dice_roll(10, 12, 14, 16, 18)
    await message_sender.send_attributes(15, 15, 15, 15, 15)
    await message_sender.send_logged(5)
    await message_sender.send_user_char_index_in_server(100)

    # Verificar que delegó correctamente
    message_sender.session.send_dice_roll.assert_called_once_with(10, 12, 14, 16, 18)
    message_sender.session.send_attributes.assert_called_once_with(15, 15, 15, 15, 15)
    message_sender.session.send_logged.assert_called_once_with(5)
    message_sender.session.send_user_char_index_in_server.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_delegation_to_console_component() -> None:
    """Verifica que los métodos de consola deleguen correctamente a ConsoleMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente console
    message_sender.console.send_console_msg = AsyncMock()
    message_sender.console.send_error_msg = AsyncMock()
    message_sender.console.send_multiline_console_msg = AsyncMock()

    # Llamar métodos
    await message_sender.send_console_msg("Test message", 7)
    await message_sender.send_error_msg("Error message")
    await message_sender.send_multiline_console_msg("Line1\nLine2", 5)

    # Verificar delegación
    message_sender.console.send_console_msg.assert_called_once_with("Test message", 7)
    message_sender.console.send_error_msg.assert_called_once_with("Error message")
    message_sender.console.send_multiline_console_msg.assert_called_once_with("Line1\nLine2", 5)


@pytest.mark.asyncio
async def test_delegation_to_map_component() -> None:
    """Verifica que los métodos de mapa deleguen correctamente a MapMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente map
    message_sender.map.send_change_map = AsyncMock()
    message_sender.map.send_pos_update = AsyncMock()
    message_sender.map.send_object_create = AsyncMock()
    message_sender.map.send_object_delete = AsyncMock()
    message_sender.map.send_block_position = AsyncMock()

    # Llamar métodos
    await message_sender.send_change_map(1, 0)
    await message_sender.send_pos_update(50, 75)
    await message_sender.send_object_create(10, 20, 100)
    await message_sender.send_object_delete(10, 20)
    await message_sender.send_block_position(15, 25, True)  # noqa: FBT003

    # Verificar delegación
    message_sender.map.send_change_map.assert_called_once_with(1, 0)
    message_sender.map.send_pos_update.assert_called_once_with(50, 75)
    message_sender.map.send_object_create.assert_called_once_with(10, 20, 100)
    message_sender.map.send_object_delete.assert_called_once_with(10, 20)
    message_sender.map.send_block_position.assert_called_once_with(15, 25, True)  # noqa: FBT003


@pytest.mark.asyncio
async def test_delegation_to_audio_component() -> None:
    """Verifica que los métodos de audio deleguen correctamente a AudioMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente audio
    message_sender.audio.send_play_midi = AsyncMock()
    message_sender.audio.send_play_wave = AsyncMock()
    message_sender.audio.play_sound_login = AsyncMock()
    message_sender.audio.play_music_main_theme = AsyncMock()

    # Llamar métodos
    await message_sender.send_play_midi(5)
    await message_sender.send_play_wave(10, 50, 75)
    await message_sender.play_sound_login()
    await message_sender.play_music_main_theme()

    # Verificar delegación
    message_sender.audio.send_play_midi.assert_called_once_with(5)
    message_sender.audio.send_play_wave.assert_called_once_with(10, 50, 75)
    message_sender.audio.play_sound_login.assert_called_once()
    message_sender.audio.play_music_main_theme.assert_called_once()


@pytest.mark.asyncio
async def test_delegation_to_visual_effects_component() -> None:
    """Verifica que los métodos de efectos visuales deleguen correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente visual_effects
    message_sender.visual_effects.send_create_fx = AsyncMock()
    message_sender.visual_effects.play_effect_spawn = AsyncMock()
    message_sender.visual_effects.send_create_fx_at_position = AsyncMock()

    # Llamar métodos
    await message_sender.send_create_fx(100, 5, 1)
    await message_sender.play_effect_spawn(100)
    await message_sender.send_create_fx_at_position(10, 20, 5, 1)

    # Verificar delegación
    message_sender.visual_effects.send_create_fx.assert_called_once_with(100, 5, 1)
    message_sender.visual_effects.play_effect_spawn.assert_called_once_with(100)
    message_sender.visual_effects.send_create_fx_at_position.assert_called_once_with(10, 20, 5, 1)


@pytest.mark.asyncio
async def test_delegation_to_player_stats_component() -> None:
    """Verifica que los métodos de stats deleguen correctamente a PlayerStatsMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente player_stats
    message_sender.player_stats.send_update_hp = AsyncMock()
    message_sender.player_stats.send_update_mana = AsyncMock()
    message_sender.player_stats.send_update_sta = AsyncMock()
    message_sender.player_stats.send_update_exp = AsyncMock()
    message_sender.player_stats.send_update_hunger_and_thirst = AsyncMock()
    message_sender.player_stats.send_update_user_stats = AsyncMock()

    # Llamar métodos
    await message_sender.send_update_hp(150)
    await message_sender.send_update_mana(200)
    await message_sender.send_update_sta(180)
    await message_sender.send_update_exp(50000)
    await message_sender.send_update_hunger_and_thirst(100, 75, 100, 50)
    await message_sender.send_update_user_stats(
        200, 150, 300, 250, 180, 160, 10000, 25, 5000, 100000
    )

    # Verificar delegación
    message_sender.player_stats.send_update_hp.assert_called_once_with(150)
    message_sender.player_stats.send_update_mana.assert_called_once_with(200)
    message_sender.player_stats.send_update_sta.assert_called_once_with(180)
    message_sender.player_stats.send_update_exp.assert_called_once_with(50000)
    message_sender.player_stats.send_update_hunger_and_thirst.assert_called_once_with(
        100, 75, 100, 50
    )
    message_sender.player_stats.send_update_user_stats.assert_called_once_with(
        200, 150, 300, 250, 180, 160, 10000, 25, 5000, 100000
    )


@pytest.mark.asyncio
async def test_delegation_to_character_component() -> None:
    """Verifica que los métodos de personajes deleguen correctamente a CharacterMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente character
    message_sender.character.send_character_create = AsyncMock()
    message_sender.character.send_character_change = AsyncMock()
    message_sender.character.send_character_remove = AsyncMock()
    message_sender.character.send_character_move = AsyncMock()

    # Llamar métodos
    await message_sender.send_character_create(
        100, 1, 2, 3, 50, 75, 10, 20, 30, 5, 1, "Player", 0, 0
    )
    await message_sender.send_character_change(100, 1, 2, 3, 10, 20, 30, 5, 1)
    await message_sender.send_character_remove(100)
    await message_sender.send_character_move(100, 51, 76)

    # Verificar delegación
    message_sender.character.send_character_create.assert_called_once()
    message_sender.character.send_character_change.assert_called_once()
    message_sender.character.send_character_remove.assert_called_once_with(100)
    message_sender.character.send_character_move.assert_called_once_with(100, 51, 76)


@pytest.mark.asyncio
async def test_delegation_to_inventory_component() -> None:
    """Verifica que los métodos de inventario deleguen correctamente a InventoryMessageSender."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock del componente inventory
    message_sender.inventory.send_change_inventory_slot = AsyncMock()
    message_sender.inventory.send_change_bank_slot = AsyncMock()
    message_sender.inventory.send_bank_init_empty = AsyncMock()
    message_sender.inventory.send_bank_end = AsyncMock()
    message_sender.inventory.send_commerce_init = AsyncMock()
    message_sender.inventory.send_commerce_init_empty = AsyncMock()
    message_sender.inventory.send_commerce_end = AsyncMock()
    message_sender.inventory.send_change_spell_slot = AsyncMock()
    message_sender.inventory.send_meditate_toggle = AsyncMock()

    # Llamar métodos
    await message_sender.send_change_inventory_slot(
        1,
        100,
        "Espada",
        1,
        equipped=True,
        grh_id=500,
        item_type=1,
        max_hit=50,
        min_hit=30,
        max_def=0,
        min_def=0,
        sale_price=1000.0,
    )
    await message_sender.send_change_bank_slot(5, 200, "Poción", 10, 600, 2, 0, 0, 0, 0)
    await message_sender.send_bank_init_empty()
    await message_sender.send_bank_end()
    await message_sender.send_commerce_init(1, [])
    await message_sender.send_commerce_init_empty()
    await message_sender.send_commerce_end()
    await message_sender.send_change_spell_slot(2, 50, "Apocalipsis")
    await message_sender.send_meditate_toggle()

    # Verificar delegación
    message_sender.inventory.send_change_inventory_slot.assert_called_once()
    message_sender.inventory.send_change_bank_slot.assert_called_once()
    message_sender.inventory.send_bank_init_empty.assert_called_once()
    message_sender.inventory.send_bank_end.assert_called_once()
    message_sender.inventory.send_commerce_init.assert_called_once_with(1, [])
    message_sender.inventory.send_commerce_init_empty.assert_called_once()
    message_sender.inventory.send_commerce_end.assert_called_once()
    message_sender.inventory.send_change_spell_slot.assert_called_once_with(2, 50, "Apocalipsis")
    message_sender.inventory.send_meditate_toggle.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_components_integration() -> None:
    """Verifica que se puedan usar múltiples componentes en secuencia."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Mock de varios componentes
    message_sender.session.send_logged = AsyncMock()
    message_sender.console.send_console_msg = AsyncMock()
    message_sender.map.send_change_map = AsyncMock()
    message_sender.player_stats.send_update_hp = AsyncMock()
    message_sender.audio.play_sound_login = AsyncMock()

    # Simular secuencia de login
    await message_sender.send_logged(1)
    await message_sender.send_console_msg("Bienvenido!", 7)
    await message_sender.send_change_map(1, 0)
    await message_sender.send_update_hp(100)
    await message_sender.play_sound_login()

    # Verificar que todos fueron llamados
    message_sender.session.send_logged.assert_called_once()
    message_sender.console.send_console_msg.assert_called_once()
    message_sender.map.send_change_map.assert_called_once()
    message_sender.player_stats.send_update_hp.assert_called_once()
    message_sender.audio.play_sound_login.assert_called_once()
