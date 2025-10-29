"""Tests para NPCMessageSender."""

import asyncio
import sys
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.messaging.senders.message_npc_sender import NPCMessageSender


class MockClientConnection:
    """Mock de ClientConnection para tests."""

    def __init__(self) -> None:
        """Inicializa mock de conexión."""
        self.sent_packets = []
        self.address = "127.0.0.1:1234"

    async def send(self, packet: bytes) -> None:
        """Simula envío de paquete."""
        self.sent_packets.append(packet)


class TestNPCMessageSender:
    """Tests para NPCMessageSender."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.mock_connection = MockClientConnection()
        self.sender = NPCMessageSender(self.mock_connection)

    def test_sender_initialization(self) -> None:
        """Test inicialización del sender."""
        assert self.sender is not None
        assert self.sender.connection == self.mock_connection

    def test_get_npc_index_consistency(self) -> None:
        """Test consistencia de índices de NPC."""
        instance_id = "1_1_50_50"

        # Mismo instance_id debe dar mismo índice
        index1 = self.sender.get_npc_index(instance_id)
        index2 = self.sender.get_npc_index(instance_id)

        assert index1 == index2
        assert 1000 <= index1 <= 9999

    def test_get_npc_index_uniqueness(self) -> None:
        """Test unicidad de índices para NPCs diferentes."""
        instance_id_1 = "1_1_50_50"
        instance_id_2 = "1_2_51_51"
        instance_id_3 = "34_1_30_30"

        index1 = self.sender.get_npc_index(instance_id_1)
        index2 = self.sender.get_npc_index(instance_id_2)
        index3 = self.sender.get_npc_index(instance_id_3)

        # Deben ser diferentes
        assert index1 != index2
        assert index2 != index3
        assert index1 != index3

    def test_send_npc_create_basic(self) -> None:
        """Test envío básico de NPC CREATE."""
        npc_data = {
            "instance_id": "1_1_50_50",
            "name": "Test NPC",
            "x": 50,
            "y": 50,
            "direction": 3,
            "id": 1,
            "hostile": False,
            "appearance": {"body": 1, "head": 2},
        }

        async def test_send():
            await self.sender.send_npc_create(npc_data)

        asyncio.run(test_send())

        # Debe haber enviado un paquete
        assert len(self.mock_connection.sent_packets) == 1
        packet = self.mock_connection.sent_packets[0]

        # Verificar estructura del paquete CHARACTER_CREATE
        assert len(packet) > 20  # Debe tener header + datos
        assert packet[0] == 29  # CHARACTER_CREATE packet ID

    def test_send_npc_create_hostile(self) -> None:
        """Test envío de NPC hostil."""
        hostile_npc = {
            "instance_id": "1_2_80_80",
            "name": "Goblin",
            "x": 80,
            "y": 80,
            "direction": 1,
            "id": 2,
            "hostile": True,
            "trader": False,
        }

        async def test_send():
            await self.sender.send_npc_create(hostile_npc)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1

    def test_send_npc_create_trader(self) -> None:
        """Test envío de NPC comerciante."""
        trader_npc = {
            "instance_id": "1_3_55_48",
            "name": "Mercader",
            "x": 55,
            "y": 48,
            "direction": 2,
            "id": 3,
            "hostile": False,
            "trader": True,
        }

        async def test_send():
            await self.sender.send_npc_create(trader_npc)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1

    def test_send_npc_remove(self) -> None:
        """Test envío de NPC REMOVE."""
        instance_id = "1_1_50_50"

        async def test_send():
            await self.sender.send_npc_remove(instance_id)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1
        packet = self.mock_connection.sent_packets[0]

        # Verificar estructura del paquete CHARACTER_REMOVE
        assert packet[0] == 30  # CHARACTER_REMOVE packet ID

    def test_send_npc_move(self) -> None:
        """Test envío de NPC MOVE."""
        npc_data = {"instance_id": "1_1_50_50", "name": "Test NPC", "x": 51, "y": 52}

        async def test_send():
            await self.sender.send_npc_move(npc_data)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1
        packet = self.mock_connection.sent_packets[0]

        # Verificar estructura del paquete CHARACTER_MOVE
        assert packet[0] == 32  # CHARACTER_MOVE packet ID

    def test_send_npc_change(self) -> None:
        """Test envío de NPC CHANGE."""
        npc_data = {
            "instance_id": "1_1_50_50",
            "name": "Test NPC",
            "direction": 4,
            "id": 1,  # Agregar ID faltante
            "appearance": {"body": 5, "head": 1},
        }

        async def test_send():
            await self.sender.send_npc_change(npc_data)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1
        packet = self.mock_connection.sent_packets[0]

        # Verificar estructura del paquete CHARACTER_CHANGE
        assert packet[0] == 34  # CHARACTER_CHANGE packet ID

    def test_send_npc_combat_start(self) -> None:
        """Test envío de inicio de combate."""
        npc_data = {
            "instance_id": "1_2_80_80",
            "name": "Goblin Enemigo",
            "x": 80,
            "y": 80,
            "direction": 1,
            "id": 2,  # Agregar ID faltante
            "hostile": True,
        }

        async def test_send():
            await self.sender.send_npc_combat_start(npc_data)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1
        packet = self.mock_connection.sent_packets[0]

        # Debe ser CHARACTER_CHANGE con efecto de combate
        assert packet[0] == 34  # CHARACTER_CHANGE packet ID

    def test_send_npc_combat_end(self) -> None:
        """Test envío de fin de combate."""
        npc_data = {
            "instance_id": "1_2_80_80",
            "name": "Goblin Enemigo",
            "x": 80,
            "y": 80,
            "direction": 1,
            "id": 2,  # Agregar ID faltante
            "hostile": True,
        }

        async def test_send():
            await self.sender.send_npc_combat_end(npc_data)

        asyncio.run(test_send())

        assert len(self.mock_connection.sent_packets) == 1

    def test_sync_all_npcs(self) -> None:
        """Test sincronización de múltiples NPCs."""
        spawned_npcs = {
            "1_1_50_50": {
                "instance_id": "1_1_50_50",
                "name": "NPC 1",
                "x": 50,
                "y": 50,
                "direction": 1,
                "id": 1,
            },
            "1_2_55_55": {
                "instance_id": "1_2_55_55",
                "name": "NPC 2",
                "x": 55,
                "y": 55,
                "direction": 2,
                "id": 2,
            },
            "34_1_30_30": {
                "instance_id": "34_1_30_30",
                "name": "NPC 3",
                "x": 30,
                "y": 30,
                "direction": 3,
                "id": 3,
            },
        }

        async def test_sync():
            await self.sender.sync_all_npcs(spawned_npcs)

        asyncio.run(test_sync())

        # Debe haber enviado 3 paquetes CHARACTER_CREATE
        assert len(self.mock_connection.sent_packets) == 3

        for packet in self.mock_connection.sent_packets:
            assert packet[0] == 29  # CHARACTER_CREATE packet ID

    def test_npc_appearance_fallback(self) -> None:
        """Test fallback de apariencia cuando no hay datos."""
        npc_data = {
            "instance_id": "1_1_50_50",
            "name": "Minimal NPC",
            "x": 50,
            "y": 50,
            "direction": 3,
            "id": 42,  # Body será 42 por defecto
            "hostile": False,
            # Sin campo "appearance"
        }

        async def test_send():
            await self.sender.send_npc_create(npc_data)

        asyncio.run(test_send())

        # Debe funcionar sin error
        assert len(self.mock_connection.sent_packets) == 1

    def test_error_handling(self) -> None:
        """Test manejo de errores con datos inválidos."""
        # NPC con campos mínimos
        minimal_npc = {
            "instance_id": "test",
            "name": "Test",
            "x": 1,
            "y": 1,
            "direction": 1,
            "id": 1,
        }

        async def test_minimal():
            await self.sender.send_npc_create(minimal_npc)

        # No debe lanzar excepción
        asyncio.run(test_minimal())
        assert len(self.mock_connection.sent_packets) == 1


class TestNPCMessageSenderIntegration:
    """Tests de integración para NPCMessageSender."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.mock_connection = MockClientConnection()
        self.sender = NPCMessageSender(self.mock_connection)

    def test_complete_npc_lifecycle(self) -> None:
        """Test ciclo completo de vida de un NPC."""
        npc_data = {
            "instance_id": "1_1_50_50",
            "name": "Test NPC",
            "x": 50,
            "y": 50,
            "direction": 3,
            "id": 1,
            "hostile": False,
        }

        async def test_lifecycle():
            # 1. Crear NPC
            await self.sender.send_npc_create(npc_data)
            assert len(self.mock_connection.sent_packets) == 1

            # 2. Mover NPC
            npc_data["x"] = 51
            npc_data["y"] = 51
            await self.sender.send_npc_move(npc_data)
            assert len(self.mock_connection.sent_packets) == 2

            # 3. Cambiar dirección
            npc_data["direction"] = 1
            await self.sender.send_npc_change(npc_data)
            assert len(self.mock_connection.sent_packets) == 3

            # 4. Iniciar combate
            await self.sender.send_npc_combat_start(npc_data)
            assert len(self.mock_connection.sent_packets) == 4

            # 5. Terminar combate
            await self.sender.send_npc_combat_end(npc_data)
            assert len(self.mock_connection.sent_packets) == 5

            # 6. Remover NPC
            await self.sender.send_npc_remove(npc_data["instance_id"])
            assert len(self.mock_connection.sent_packets) == 6

        asyncio.run(test_lifecycle())

        # Verificar tipos de paquetes enviados
        packet_ids = [p[0] for p in self.mock_connection.sent_packets]
        expected_ids = [29, 32, 34, 34, 34, 30]  # CREATE, MOVE, CHANGE, CHANGE, CHANGE, REMOVE
        assert packet_ids == expected_ids

    def test_multiple_npcs_different_maps(self) -> None:
        """Test múltiples NPCs en diferentes mapas."""
        npcs = [
            {
                "instance_id": "1_1_50_50",
                "name": "NPC Ulla",
                "x": 50,
                "y": 50,
                "direction": 1,
                "id": 1,
            },
            {
                "instance_id": "34_2_30_30",
                "name": "NPC Nix",
                "x": 30,
                "y": 30,
                "direction": 2,
                "id": 2,
            },
            {
                "instance_id": "46_3_25_25",
                "name": "NPC Band",
                "x": 25,
                "y": 25,
                "direction": 3,
                "id": 3,
            },
        ]

        async def test_multiple():
            for npc in npcs:
                await self.sender.send_npc_create(npc)

        asyncio.run(test_multiple())

        # Todos deben haber sido creados
        assert len(self.mock_connection.sent_packets) == 3

        # Índices deben ser únicos
        indices = []
        for packet in self.mock_connection.sent_packets:
            # Extraer char_index del paquete (después del packet ID)
            char_index = int.from_bytes(packet[1:3], byteorder="little", signed=True)
            indices.append(char_index)

        assert len(set(indices)) == 3  # Todos únicos
