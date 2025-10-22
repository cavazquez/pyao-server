#!/usr/bin/env python3
"""Script para agregar items de prueba al inventario de un usuario."""

import asyncio
import sys

from src.repositories.inventory_repository import InventoryRepository
from src.utils.redis_client import RedisClient


async def add_test_items(user_id: int) -> None:
    """Agrega items de prueba al inventario de un usuario.

    Args:
        user_id: ID del usuario.
    """
    redis_client = RedisClient()
    await redis_client.connect()

    try:
        inventory_repo = InventoryRepository(redis_client)

        # Items de prueba
        test_items = [
            (1, 10),  # Manzana Roja x10
            (2, 1),  # Espada Larga x1
            (38, 5),  # Poción Roja x5
            (39, 3),  # Poción Verde x3
            (3, 1),  # Hacha x1
        ]

        print(f"Agregando items de prueba al inventario del usuario {user_id}...")

        for item_id, quantity in test_items:
            slot = await inventory_repo.add_item(user_id, item_id, quantity)
            if slot:
                print(f"  ✓ Item {item_id} x{quantity} agregado en slot {slot}")
            else:
                print(f"  ✗ No se pudo agregar item {item_id}")

        print("\n✅ Items agregados exitosamente!")
        print("Ahora puedes hacer login y verás los items en tu inventario.")

    finally:
        await redis_client.disconnect()


if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(add_test_items(user_id))
