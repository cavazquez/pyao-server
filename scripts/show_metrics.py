#!/usr/bin/env python3
"""Script para mostrar métricas de rendimiento del servidor.

Este script se conecta a Redis para obtener información básica y muestra
cómo acceder a las métricas si el servidor está corriendo.

Uso:
    uv run python scripts/show_metrics.py

Nota: Para ver métricas en tiempo real, el servidor debe estar corriendo
y las métricas se muestran automáticamente en los logs cada 10-50 ticks.
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.server_initializer import ServerInitializer
from src.utils.redis_client import RedisClient


async def show_metrics() -> None:
    """Muestra las métricas de rendimiento del servidor."""
    print("=" * 60)
    print("MÉTRICAS DE RENDIMIENTO - PyAO Server")
    print("=" * 60)

    try:
        # Inicializar Redis
        redis_client = await RedisClient.connect()
        if not redis_client:
            print("❌ Error: No se pudo conectar a Redis")
            print("   Asegúrate de que Redis esté corriendo")
            return

        # Inicializar el servidor completo para acceder a game_tick
        print("\n📊 Inicializando servidor para acceder a métricas...")
        container, _, _ = await ServerInitializer.initialize_all()

        if not container.game_tick:
            print("❌ Error: GameTick no está disponible")
            return

        # Obtener métricas generales
        print("\n" + "=" * 60)
        print("MÉTRICAS GENERALES DEL GAMETICK")
        print("=" * 60)
        metrics = container.game_tick.get_metrics()

        print(f"\n📈 Total de ticks procesados: {metrics['total_ticks']}")
        print(f"⏱️  Tiempo promedio por tick: {metrics['avg_tick_time_ms']:.2f}ms")
        print(f"🔥 Tiempo máximo de tick: {metrics['max_tick_time_ms']:.2f}ms")

        # Métricas por efecto
        if metrics.get("effects"):
            print("\n" + "=" * 60)
            print("MÉTRICAS POR EFECTO")
            print("=" * 60)
            for effect_name, effect_metrics in metrics["effects"].items():
                print(f"\n📦 {effect_name}:")
                print(f"   Llamadas: {effect_metrics['count']}")
                print(f"   Tiempo promedio: {effect_metrics['avg_time_ms']:.2f}ms")
                print(f"   Tiempo máximo: {effect_metrics['max_time_ms']:.2f}ms")

        # Métricas específicas de NPCMovementEffect
        print("\n" + "=" * 60)
        print("MÉTRICAS DE NPCMOVEMENT EFFECT")
        print("=" * 60)
        npc_movement_found = False
        for effect in container.game_tick.effects:
            if effect.get_name() == "NPCMovement":
                if hasattr(effect, "get_metrics"):
                    npc_metrics = effect.get_metrics()
                    npc_movement_found = True
                    print(f"\n🤖 NPCs procesados: {npc_metrics['total_npcs_processed']}")
                    print(f"📊 Total de ticks: {npc_metrics['total_ticks']}")
                    print(f"⏱️  Tiempo promedio: {npc_metrics['avg_time_ms']:.2f}ms")
                    print(f"🔥 Tiempo máximo: {npc_metrics['max_time_ms']:.2f}ms")
                    print(
                        f"📈 NPCs promedio por tick: {npc_metrics['avg_npcs_per_tick']:.2f}"
                    )
                    break

        if not npc_movement_found:
            print("\n⚠️  NPCMovementEffect no encontrado o no tiene métricas")

        # Información adicional
        print("\n" + "=" * 60)
        print("INFORMACIÓN ADICIONAL")
        print("=" * 60)
        print(f"📋 Total de efectos activos: {len(container.game_tick.effects)}")
        print(f"⏰ Intervalo de tick: {container.game_tick.tick_interval}s")
        print(f"🔄 Estado: {'Corriendo' if container.game_tick._running else 'Detenido'}")

        # Conexiones activas
        if container.redis_client:
            connections = await container.redis_client.get_connections_count()
            print(f"👥 Conexiones activas: {connections}")

        print("\n" + "=" * 60)
        print("✅ Métricas obtenidas correctamente")
        print("=" * 60)
        print("\n💡 Tip: Las métricas también se muestran automáticamente en los logs:")
        print("   - NPCMovementEffect: cada 10 ticks")
        print("   - GameTick: cada 50 ticks")

    except Exception as e:
        print(f"\n❌ Error obteniendo métricas: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cerrar conexiones
        if "container" in locals() and container.redis_client:
            await container.redis_client.close()


if __name__ == "__main__":
    asyncio.run(show_metrics())

