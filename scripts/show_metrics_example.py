"""Ejemplo de cómo acceder a las métricas de GameTick y NPCMovementEffect.

Este script muestra cómo obtener las métricas programáticamente.
En el servidor real, puedes acceder a través de DependencyContainer.
"""

# Ejemplo 1: Acceder desde DependencyContainer (en el servidor)
# En src/server.py o cualquier task/service:
# 
# if self.deps and self.deps.game_tick:
#     metrics = self.deps.game_tick.get_metrics()
#     print(f"Total ticks: {metrics['total_ticks']}")
#     print(f"Avg tick time: {metrics['avg_tick_time_ms']:.2f}ms")
#     print(f"Max tick time: {metrics['max_tick_time_ms']:.2f}ms")
#     
#     # Métricas por efecto
#     for effect_name, effect_metrics in metrics['effects'].items():
#         print(f"\n{effect_name}:")
#         print(f"  Calls: {effect_metrics['count']}")
#         print(f"  Avg time: {effect_metrics['avg_time_ms']:.2f}ms")
#         print(f"  Max time: {effect_metrics['max_time_ms']:.2f}ms")
#
# # Ejemplo 2: Acceder a métricas de NPCMovementEffect específicamente
# for effect in self.deps.game_tick.effects:
#     if effect.get_name() == "NPCMovement":
#         npc_metrics = effect.get_metrics()
#         print(f"\nNPC Movement Metrics:")
#         print(f"  Total NPCs processed: {npc_metrics['total_npcs_processed']}")
#         print(f"  Total ticks: {npc_metrics['total_ticks']}")
#         print(f"  Avg time: {npc_metrics['avg_time_ms']:.2f}ms")
#         print(f"  Max time: {npc_metrics['max_time_ms']:.2f}ms")
#         print(f"  Avg NPCs per tick: {npc_metrics['avg_npcs_per_tick']:.2f}")

print("Este es un archivo de ejemplo.")
print("Las métricas están disponibles en:")
print("1. Logs automáticos (cada 10-50 ticks)")
print("2. game_tick.get_metrics() - métricas generales")
print("3. effect.get_metrics() - métricas por efecto (si el efecto las implementa)")

