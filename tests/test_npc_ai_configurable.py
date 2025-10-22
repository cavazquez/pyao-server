"""Tests para sistema de IA configurable de NPCs."""

import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.npc import NPC
from src.services.npc.npc_ai_service import NPCAIService
from src.repositories.npc_repository import NPCRepository

if TYPE_CHECKING:
    from src.redis_client import RedisClient


@pytest.mark.asyncio
class TestNPCConfigurableAI:
    """Tests para parámetros de IA configurables en NPCs."""

    async def test_create_npc_with_custom_attack_damage(self, redis_client: RedisClient) -> None:
        """Test que los NPCs se crean con daño de ataque personalizado."""
        repo = NPCRepository(redis_client)

        # Crear NPC con daño bajo (Serpiente)
        weak_npc = await repo.create_npc_instance(
            npc_id=9,
            char_index=10001,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Serpiente",
            description="Una serpiente rápida pero débil",
            body_id=84,
            head_id=0,
            hp=60,
            max_hp=60,
            level=4,
            is_hostile=True,
            is_attackable=True,
            respawn_time=15,
            respawn_time_max=30,
            gold_min=3,
            gold_max=15,
            attack_damage=5,  # Daño bajo
            attack_cooldown=1.5,
            aggro_range=5,
        )

        assert weak_npc.attack_damage == 5

        # Crear NPC con daño alto (Dragón)
        boss_npc = await repo.create_npc_instance(
            npc_id=10,
            char_index=10002,
            map_id=1,
            x=60,
            y=60,
            heading=3,
            name="Dragón",
            description="Un dragón devastador",
            body_id=200,
            head_id=0,
            hp=1000,
            max_hp=1000,
            level=50,
            is_hostile=True,
            is_attackable=True,
            respawn_time=600,
            respawn_time_max=900,
            gold_min=500,
            gold_max=1000,
            attack_damage=50,  # Daño muy alto
            attack_cooldown=4.0,
            aggro_range=15,
        )

        assert boss_npc.attack_damage == 50

    async def test_create_npc_with_custom_attack_cooldown(self, redis_client: RedisClient) -> None:
        """Test que los NPCs se crean con cooldown de ataque personalizado."""
        repo = NPCRepository(redis_client)

        # Crear NPC rápido (Serpiente)
        fast_npc = await repo.create_npc_instance(
            npc_id=9,
            char_index=10003,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Serpiente",
            description="Ataca muy rápido",
            body_id=84,
            head_id=0,
            hp=60,
            max_hp=60,
            level=4,
            is_hostile=True,
            is_attackable=True,
            respawn_time=15,
            respawn_time_max=30,
            gold_min=3,
            gold_max=15,
            attack_damage=5,
            attack_cooldown=1.5,  # Muy rápido
            aggro_range=5,
        )

        assert fast_npc.attack_cooldown == 1.5

        # Crear NPC lento (Dragón)
        slow_npc = await repo.create_npc_instance(
            npc_id=10,
            char_index=10004,
            map_id=1,
            x=60,
            y=60,
            heading=3,
            name="Dragón",
            description="Ataca lento pero fuerte",
            body_id=200,
            head_id=0,
            hp=1000,
            max_hp=1000,
            level=50,
            is_hostile=True,
            is_attackable=True,
            respawn_time=600,
            respawn_time_max=900,
            gold_min=500,
            gold_max=1000,
            attack_damage=50,
            attack_cooldown=4.0,  # Lento
            aggro_range=15,
        )

        assert slow_npc.attack_cooldown == 4.0

    async def test_create_npc_with_custom_aggro_range(self, redis_client: RedisClient) -> None:
        """Test que los NPCs se crean con rango de agresión personalizado."""
        repo = NPCRepository(redis_client)

        # Crear NPC con rango corto (Serpiente)
        short_range_npc = await repo.create_npc_instance(
            npc_id=9,
            char_index=10005,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Serpiente",
            description="Rango de detección corto",
            body_id=84,
            head_id=0,
            hp=60,
            max_hp=60,
            level=4,
            is_hostile=True,
            is_attackable=True,
            respawn_time=15,
            respawn_time_max=30,
            gold_min=3,
            gold_max=15,
            attack_damage=5,
            attack_cooldown=1.5,
            aggro_range=5,  # Rango corto
        )

        assert short_range_npc.aggro_range == 5

        # Crear NPC con rango largo (Dragón)
        long_range_npc = await repo.create_npc_instance(
            npc_id=10,
            char_index=10006,
            map_id=1,
            x=60,
            y=60,
            heading=3,
            name="Dragón",
            description="Detecta jugadores de muy lejos",
            body_id=200,
            head_id=0,
            hp=1000,
            max_hp=1000,
            level=50,
            is_hostile=True,
            is_attackable=True,
            respawn_time=600,
            respawn_time_max=900,
            gold_min=500,
            gold_max=1000,
            attack_damage=50,
            attack_cooldown=4.0,
            aggro_range=15,  # Rango largo
        )

        assert long_range_npc.aggro_range == 15

    async def test_npc_persistence_with_configurable_params(
        self, redis_client: RedisClient
    ) -> None:
        """Test que los parámetros configurables persisten en Redis."""
        repo = NPCRepository(redis_client)

        # Crear NPC con parámetros específicos
        created_npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10007,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Goblin",
            description="Un goblin con IA configurada",
            body_id=58,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
            attack_damage=8,
            attack_cooldown=2.5,
            aggro_range=6,
        )

        # Recuperar NPC de Redis
        retrieved_npc = await repo.get_npc(created_npc.instance_id)

        # Verificar que todos los parámetros se guardaron correctamente
        assert retrieved_npc is not None
        assert retrieved_npc.attack_damage == 8
        assert retrieved_npc.attack_cooldown == 2.5
        assert retrieved_npc.aggro_range == 6

    async def test_npc_default_values_for_configurable_params(
        self, redis_client: RedisClient
    ) -> None:
        """Test que los NPCs usan valores por defecto si no se especifican."""
        repo = NPCRepository(redis_client)

        # Crear NPC sin especificar parámetros configurables
        npc = await repo.create_npc_instance(
            npc_id=1,
            char_index=10008,
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Goblin Base",
            description="Goblin con valores por defecto",
            body_id=58,
            head_id=0,
            hp=100,
            max_hp=100,
            level=5,
            is_hostile=True,
            is_attackable=True,
            respawn_time=30,
            respawn_time_max=60,
            gold_min=10,
            gold_max=50,
            # No se especifican attack_damage, attack_cooldown, aggro_range
        )

        # Verificar valores por defecto
        assert npc.attack_damage == 10  # Default
        assert npc.attack_cooldown == 3.0  # Default
        assert npc.aggro_range == 8  # Default

    async def test_npc_ai_respects_attack_cooldown(self) -> None:
        """Test que NPCAIService respeta el cooldown de ataque configurado."""
        # Crear mocks
        npc_service = MagicMock()
        map_manager = MagicMock()
        player_repo = AsyncMock()
        combat_service = AsyncMock()
        broadcast_service = AsyncMock()

        # Configurar map_manager para que retorne None (no hay message_sender)
        map_manager.get_message_sender.return_value = None

        # Crear servicio de IA
        ai_service = NPCAIService(
            npc_service, map_manager, player_repo, combat_service, broadcast_service
        )

        # Crear NPC con cooldown corto
        npc = NPC(
            npc_id=9,
            char_index=10009,
            instance_id="test-serpiente",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Serpiente",
            description="Serpiente rápida",
            body_id=84,
            head_id=0,
            hp=60,
            max_hp=60,
            level=4,
            is_hostile=True,
            is_attackable=True,
            respawn_time=15,
            respawn_time_max=30,
            gold_min=3,
            gold_max=15,
            attack_damage=5,
            attack_cooldown=0.5,  # Cooldown muy corto para testing
            aggro_range=5,
            last_attack_time=time.time(),  # Acabó de atacar
        )

        # Configurar mocks
        player_repo.get_stats.return_value = {"min_hp": 100}
        player_repo.get_position.return_value = {"x": 50, "y": 51, "map": 1}

        # Intentar atacar inmediatamente (debería fallar por cooldown)
        result = await ai_service.try_attack_player(npc, 1)
        assert result is False  # No puede atacar por cooldown

        # Simular espera del cooldown
        npc.last_attack_time = time.time() - 0.6  # Ya pasó el cooldown

        # Configurar mock de combat_service
        combat_service.npc_attack_player.return_value = {"damage": 5, "player_died": False}

        # Ahora sí debería poder atacar
        result = await ai_service.try_attack_player(npc, 1)
        assert result is True  # Sí puede atacar

    async def test_npc_ai_uses_custom_aggro_range(self) -> None:
        """Test que NPCAIService usa el rango de agresión configurado."""
        # Crear mocks
        npc_service = MagicMock()
        map_manager = MagicMock()
        player_repo = AsyncMock()
        combat_service = AsyncMock()
        broadcast_service = AsyncMock()

        # Configurar map_manager
        map_manager.get_players_in_map.return_value = [1]

        # Crear servicio de IA
        ai_service = NPCAIService(
            npc_service, map_manager, player_repo, combat_service, broadcast_service
        )

        # Crear NPC con rango corto
        npc_short_range = NPC(
            npc_id=9,
            char_index=10010,
            instance_id="test-serpiente-short",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Serpiente",
            description="Rango corto",
            body_id=84,
            head_id=0,
            hp=60,
            max_hp=60,
            level=4,
            is_hostile=True,
            is_attackable=True,
            respawn_time=15,
            respawn_time_max=30,
            gold_min=3,
            gold_max=15,
            attack_damage=5,
            attack_cooldown=1.5,
            aggro_range=5,  # Rango corto
        )

        # Configurar jugador a distancia 6 (fuera de rango)
        player_repo.get_stats.return_value = {"min_hp": 100}
        player_repo.get_position.return_value = {"x": 56, "y": 50, "map": 1}

        # Buscar jugador (no debería encontrarlo)
        nearest = await ai_service.find_nearest_player(npc_short_range)
        assert nearest is None  # Fuera de rango

        # Crear NPC con rango largo
        npc_long_range = NPC(
            npc_id=10,
            char_index=10011,
            instance_id="test-dragon",
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name="Dragón",
            description="Rango largo",
            body_id=200,
            head_id=0,
            hp=1000,
            max_hp=1000,
            level=50,
            is_hostile=True,
            is_attackable=True,
            respawn_time=600,
            respawn_time_max=900,
            gold_min=500,
            gold_max=1000,
            attack_damage=50,
            attack_cooldown=4.0,
            aggro_range=15,  # Rango largo
        )

        # Mismo jugador a distancia 6 (ahora dentro de rango)
        nearest = await ai_service.find_nearest_player(npc_long_range)
        assert nearest is not None  # Dentro de rango
        assert nearest[0] == 1  # user_id
