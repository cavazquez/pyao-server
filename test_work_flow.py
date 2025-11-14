"""Test completo para flujo de trabajo (tala)."""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from network.packet_id import ClientPacketID
from services.map.map_resources_service import MapResourcesService
from tasks.work.task_work_left_click import SKILL_TALAR, TaskWorkLeftClick

HACHA_LENADOR_ID = 561
LENA_ID = 58
WORK_X = 74
WORK_Y = 92


@dataclass
class MockItemSlot:
    """Mock para simular un slot de inventario."""

    item_id: int
    quantity: int
    equipped: bool


async def test_work_flow() -> bool:
    """Test completo del flujo de trabajo.

    Returns:
        bool: True si el test se completó exitosamente
    """
    print("🔧 Test: Flujo completo de TALA")
    print("=" * 50)

    # Mocks
    message_sender = MagicMock()
    message_sender.console = AsyncMock()
    message_sender.send_change_inventory_slot = AsyncMock()

    player_repo = AsyncMock()
    player_repo.get_position.return_value = {"map": 1}

    # Mock inventario con hacha
    hacha_slot = MockItemSlot(item_id=HACHA_LENADOR_ID, quantity=1, equipped=1)

    inventory_repo = AsyncMock()
    inventory_repo.get_inventory_slots.return_value = {1: hacha_slot}
    inventory_repo.add_item.return_value = [(1, 5)]  # slot 1, 5 leña

    map_resources = MapResourcesService()
    map_manager = MagicMock()

    # Crear packet: [PacketID, X=74, Y=92, Skill=9]
    packet_data = bytes(
        [ClientPacketID.WORK_LEFT_CLICK, WORK_X, WORK_Y, SKILL_TALAR]
    )  # WorkLeftClick packet

    # Crear task
    task = TaskWorkLeftClick(
        data=packet_data,
        message_sender=message_sender,
        player_repo=player_repo,
        inventory_repo=inventory_repo,
        map_resources=map_resources,
        map_manager=map_manager,
        session_data={"user_id": 1},
    )

    print("📊 Configuración:")
    print("   📍 Posición jugador: mapa 1")
    print(f"   🎯 Click en: ({WORK_X}, {WORK_Y})")
    print("   🪓 Skill: Talar (9)")
    print(f"   🌳 Árbol en ({WORK_X}, {WORK_Y}): {map_resources.has_tree(1, WORK_X, WORK_Y)}")
    print(f"   🔨 Hacha en inventario: {hacha_slot.item_id == HACHA_LENADOR_ID}")

    # Ejecutar task
    print("\n🚀 Ejecutando WorkLeftClick...")
    await task.execute()

    # Verificar resultados
    print("\n📋 Resultados:")

    # Verificar si se llamó a add_item (significa que funcionó)
    if inventory_repo.add_item.called:
        print("   ✅ add_item fue llamado")
        print(f"   📊 Call args: {inventory_repo.add_item.call_args}")

        # Verificar mensaje de éxito
        if message_sender.console.send_console_msg.called:
            msg_call = message_sender.console.send_console_msg.call_args[0]
            print(f"   ✅ Mensaje enviado: '{msg_call[0]}'")

            return True
        print("   ❌ No se envió mensaje de éxito")
    else:
        print("   ❌ No se llamó a add_item (no se pudo trabajar)")

        # Verificar si hay mensajes de error
        if message_sender.console.send_console_msg.called:
            msg_call = message_sender.console.send_console_msg.call_args[0]
            print(f"   ⚠️  Mensaje: '{msg_call[0]}'")

    return False


if __name__ == "__main__":
    success = asyncio.run(test_work_flow())
    print("\n" + "=" * 50)
    if success:
        print("🎉 RESULTADO: El flujo de TALA funciona correctamente")
        print("💡 El problema debe estar en el cliente o en la comunicación")
    else:
        print("🚨 RESULTADO: Hay un problema en el flujo del servidor")

    sys.exit(0 if success else 1)
