"""Tests para efectos visuales y sonoros cuando NPCs atacan jugadores."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.npc import NPC
from src.services.npc.npc_ai_service import NPCAIService
from src.utils.sounds import SoundID
from src.utils.visual_effects import VisualEffectID


@pytest.fixture
def mock_services():
    """Crea mocks de los servicios necesarios."""
    npc_service = MagicMock()
    map_manager = MagicMock()
    player_repo = MagicMock()
    combat_service = MagicMock()
    broadcast_service = MagicMock()

    return {
        "npc_service": npc_service,
        "map_manager": map_manager,
        "player_repo": player_repo,
        "combat_service": combat_service,
        "broadcast_service": broadcast_service,
    }


@pytest.fixture
def npc_ai_service(mock_services):
    """Crea instancia de NPCAIService con mocks."""
    return NPCAIService(
        npc_service=mock_services["npc_service"],
        map_manager=mock_services["map_manager"],
        player_repo=mock_services["player_repo"],
        combat_service=mock_services["combat_service"],
        broadcast_service=mock_services["broadcast_service"],
    )


@pytest.fixture
def test_npc():
    """Crea un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-npc-1",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Goblin de Prueba",
        description="NPC para testing",
        body_id=14,
        head_id=0,
        hp=100,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
        attack_damage=10,
        attack_cooldown=2.5,
        aggro_range=8,
        last_attack_time=0.0,
    )


@pytest.mark.asyncio
async def test_npc_attack_sends_damage_message(npc_ai_service, mock_services, test_npc):
    """Verifica que al atacar se envíe el mensaje NPCHitUser."""
    # Configurar mocks
    target_user_id = 1
    damage = 15

    # Mock combat_service.npc_attack_player
    mock_services["combat_service"].npc_attack_player = AsyncMock(
        return_value={"damage": damage, "player_died": False, "new_hp": 85}
    )

    # Mock player_repo
    mock_services["player_repo"].get_stats = AsyncMock(return_value={"min_hp": 85, "max_hp": 100})
    mock_services["player_repo"].get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})

    # Mock message_sender
    message_sender = MagicMock()
    message_sender.send_npc_hit_user = AsyncMock()
    message_sender.send_play_wave = AsyncMock()
    message_sender.send_create_fx = AsyncMock()
    message_sender.send_update_user_stats = AsyncMock()

    mock_services["map_manager"].get_message_sender = MagicMock(return_value=message_sender)

    # Ejecutar ataque
    with patch("time.time", return_value=10.0):
        result = await npc_ai_service.try_attack_player(test_npc, target_user_id)

    # Verificar que se llamó send_npc_hit_user
    assert result is True
    message_sender.send_npc_hit_user.assert_called_once_with(damage)


@pytest.mark.asyncio
async def test_npc_attack_sends_sound_effect(npc_ai_service, mock_services, test_npc):
    """Verifica que al atacar se envíe el sonido SWORD_HIT."""
    target_user_id = 1
    damage = 15

    # Configurar mocks
    mock_services["combat_service"].npc_attack_player = AsyncMock(
        return_value={"damage": damage, "player_died": False, "new_hp": 85}
    )
    mock_services["player_repo"].get_stats = AsyncMock(return_value={"min_hp": 85, "max_hp": 100})
    mock_services["player_repo"].get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})

    message_sender = MagicMock()
    message_sender.send_npc_hit_user = AsyncMock()
    message_sender.send_play_wave = AsyncMock()
    message_sender.send_create_fx = AsyncMock()
    message_sender.send_update_user_stats = AsyncMock()

    mock_services["map_manager"].get_message_sender = MagicMock(return_value=message_sender)

    # Ejecutar ataque
    with patch("time.time", return_value=10.0):
        await npc_ai_service.try_attack_player(test_npc, target_user_id)

    # Verificar que se llamó send_play_wave con SWORD_HIT
    message_sender.send_play_wave.assert_called_once_with(SoundID.SWORD_HIT, test_npc.x, test_npc.y)


@pytest.mark.asyncio
async def test_npc_attack_sends_visual_effect(npc_ai_service, mock_services, test_npc):
    """Verifica que al atacar se envíe el efecto visual BLOOD."""
    target_user_id = 1
    damage = 15

    # Configurar mocks
    mock_services["combat_service"].npc_attack_player = AsyncMock(
        return_value={"damage": damage, "player_died": False, "new_hp": 85}
    )
    mock_services["player_repo"].get_stats = AsyncMock(return_value={"min_hp": 85, "max_hp": 100})
    mock_services["player_repo"].get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})

    message_sender = MagicMock()
    message_sender.send_npc_hit_user = AsyncMock()
    message_sender.send_play_wave = AsyncMock()
    message_sender.send_create_fx = AsyncMock()
    message_sender.send_update_user_stats = AsyncMock()

    mock_services["map_manager"].get_message_sender = MagicMock(return_value=message_sender)

    # Ejecutar ataque
    with patch("time.time", return_value=10.0):
        await npc_ai_service.try_attack_player(test_npc, target_user_id)

    # Verificar que se llamó send_create_fx con BLOOD
    message_sender.send_create_fx.assert_called_once_with(
        target_user_id,  # char_index del jugador
        VisualEffectID.BLOOD,
        loops=1,
    )


@pytest.mark.asyncio
async def test_npc_attack_no_effects_if_no_damage(npc_ai_service, mock_services, test_npc):
    """Verifica que no se envíen efectos si el ataque no hace daño."""
    target_user_id = 1

    # Configurar mock para ataque sin daño
    mock_services["combat_service"].npc_attack_player = AsyncMock(
        return_value={"damage": 0, "player_died": False}
    )
    mock_services["player_repo"].get_stats = AsyncMock(return_value={"min_hp": 100, "max_hp": 100})
    mock_services["player_repo"].get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})

    message_sender = MagicMock()
    message_sender.send_npc_hit_user = AsyncMock()
    message_sender.send_play_wave = AsyncMock()
    message_sender.send_create_fx = AsyncMock()

    mock_services["map_manager"].get_message_sender = MagicMock(return_value=message_sender)

    # Ejecutar ataque
    with patch("time.time", return_value=10.0):
        await npc_ai_service.try_attack_player(test_npc, target_user_id)

    # Verificar que NO se llamaron los métodos de efectos
    message_sender.send_npc_hit_user.assert_not_called()
    message_sender.send_play_wave.assert_not_called()
    message_sender.send_create_fx.assert_not_called()


@pytest.mark.asyncio
async def test_npc_attack_complete_sequence(npc_ai_service, mock_services, test_npc):
    """Verifica la secuencia completa: mensaje + sonido + FX + stats."""
    target_user_id = 1
    damage = 20

    # Configurar mocks
    mock_services["combat_service"].npc_attack_player = AsyncMock(
        return_value={"damage": damage, "player_died": False, "new_hp": 80}
    )
    mock_services["player_repo"].get_stats = AsyncMock(
        return_value={
            "min_hp": 80,
            "max_hp": 100,
            "min_mana": 50,
            "max_mana": 50,
            "min_sta": 100,
            "max_sta": 100,
            "gold": 100,
            "level": 5,
            "elu": 300,
            "exp": 1000,
        }
    )
    mock_services["player_repo"].get_position = AsyncMock(return_value={"map": 1, "x": 51, "y": 50})

    message_sender = MagicMock()
    message_sender.send_npc_hit_user = AsyncMock()
    message_sender.send_play_wave = AsyncMock()
    message_sender.send_create_fx = AsyncMock()
    message_sender.send_update_user_stats = AsyncMock()

    mock_services["map_manager"].get_message_sender = MagicMock(return_value=message_sender)

    # Ejecutar ataque
    with patch("time.time", return_value=10.0):
        result = await npc_ai_service.try_attack_player(test_npc, target_user_id)

    # Verificar secuencia completa
    assert result is True

    # 1. Mensaje de daño
    message_sender.send_npc_hit_user.assert_called_once_with(damage)

    # 2. Sonido
    message_sender.send_play_wave.assert_called_once_with(SoundID.SWORD_HIT, test_npc.x, test_npc.y)

    # 3. Efecto visual
    message_sender.send_create_fx.assert_called_once_with(
        target_user_id, VisualEffectID.BLOOD, loops=1
    )

    # 4. Update stats
    message_sender.send_update_user_stats.assert_called_once()

    # Verificar orden de llamadas
    calls = message_sender.method_calls
    call_names = [call[0] for call in calls]

    # Las llamadas deben estar en orden
    assert call_names.index("send_npc_hit_user") < call_names.index("send_play_wave")
    assert call_names.index("send_play_wave") < call_names.index("send_create_fx")
