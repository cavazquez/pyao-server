# Métricas de Rendimiento

El servidor incluye métricas de rendimiento para monitorear el sistema de GameTick y efectos.

## 📊 Métricas Disponibles

### 1. Métricas de GameTick (Generales)

Métricas del sistema de ticks completo:
- `total_ticks`: Total de ticks procesados
- `avg_tick_time_ms`: Tiempo promedio por tick en milisegundos
- `max_tick_time_ms`: Tiempo máximo de un tick en milisegundos
- `effects`: Métricas por efecto individual

### 2. Métricas de NPCMovementEffect

Métricas específicas del efecto de movimiento de NPCs:
- `total_npcs_processed`: Total de NPCs procesados
- `total_ticks`: Total de ticks ejecutados
- `avg_time_ms`: Tiempo promedio de ejecución en milisegundos
- `max_time_ms`: Tiempo máximo de ejecución en milisegundos
- `avg_npcs_per_tick`: Promedio de NPCs procesados por tick

## 🔍 Cómo Ver las Métricas

### Opción 1: Comando `/METRICS` en el Juego (Más Fácil)

Desde el juego, escribe `/METRICS` en el chat para ver las métricas en tiempo real:

```
=== MÉTRICAS DE RENDIMIENTO ===
Total ticks: 1250
Tiempo promedio: 15.30ms
Tiempo máximo: 45.20ms

--- Por Efecto ---
HungerThirst: 150 calls, avg=2.10ms, max=8.50ms
NPCMovement: 10 calls, avg=2.50ms, max=5.20ms
Meditation: 150 calls, avg=0.50ms, max=2.10ms

--- NPC Movement ---
NPCs procesados: 500
Ticks: 10
Avg tiempo: 2.50ms
Max tiempo: 5.20ms
NPCs/tick: 50.00
```

### Opción 2: Logs Automáticos (Recomendado)

Las métricas se registran automáticamente en los logs:

**NPCMovementEffect**: Cada 10 ticks
```
INFO - NPCMovement metrics: 50 NPCs procesados en 10 ticks, avg=2.50ms, max=5.20ms
```

**GameTick**: Cada 50 ticks
```
INFO - GameTick metrics: 50 ticks, avg=15.30ms, max=45.20ms
INFO -   Effect 'HungerThirst': 150 calls, avg=2.10ms, max=8.50ms
INFO -   Effect 'NPCMovement': 10 calls, avg=2.50ms, max=5.20ms
INFO -   Effect 'Meditation': 150 calls, avg=0.50ms, max=2.10ms
```

### Opción 3: Script de Consola

Ejecuta el script `scripts/show_metrics.py` mientras el servidor está corriendo:

```bash
uv run python scripts/show_metrics.py
```

Este script se conecta a Redis, inicializa el servidor y muestra todas las métricas disponibles.

### Opción 4: Acceso Programático

Desde cualquier lugar donde tengas acceso a `DependencyContainer`:

```python
# En src/server.py, tasks, services, etc.
if self.deps and self.deps.game_tick:
    # Métricas generales del GameTick
    metrics = self.deps.game_tick.get_metrics()

    print(f"Total ticks: {metrics['total_ticks']}")
    print(f"Avg tick time: {metrics['avg_tick_time_ms']:.2f}ms")
    print(f"Max tick time: {metrics['max_tick_time_ms']:.2f}ms")

    # Métricas por efecto
    for effect_name, effect_metrics in metrics["effects"].items():
        print(f"\n{effect_name}:")
        print(f"  Calls: {effect_metrics['count']}")
        print(f"  Avg time: {effect_metrics['avg_time_ms']:.2f}ms")
        print(f"  Max time: {effect_metrics['max_time_ms']:.2f}ms")

    # Métricas específicas de NPCMovementEffect
    for effect in self.deps.game_tick.effects:
        if effect.get_name() == "NPCMovement":
            npc_metrics = effect.get_metrics()
            print(f"\nNPC Movement Metrics:")
            print(f"  Total NPCs processed: {npc_metrics['total_npcs_processed']}")
            print(f"  Total ticks: {npc_metrics['total_ticks']}")
            print(f"  Avg time: {npc_metrics['avg_time_ms']:.2f}ms")
            print(f"  Max time: {npc_metrics['max_time_ms']:.2f}ms")
            print(f"  Avg NPCs per tick: {npc_metrics['avg_npcs_per_tick']:.2f}")
```

## 📈 Interpretación de Métricas

### Tiempos Normales
- **GameTick promedio**: < 20ms (con pocos jugadores)
- **NPCMovementEffect**: < 5ms por ejecución
- **Otros efectos**: < 2ms por ejecución

### Señales de Problemas
- **GameTick promedio > 50ms**: Posible cuello de botella
- **Max tick time > 100ms**: Efecto específico muy lento
- **NPCMovementEffect > 10ms**: Demasiados NPCs o procesamiento ineficiente

## 🔧 Optimizaciones Aplicadas

1. **NPCMovementEffect**: Procesa máximo 10 NPCs por tick (configurable)
2. **Procesamiento paralelo**: Usa `asyncio.gather` para chunks
3. **Métricas automáticas**: Sin overhead significativo

## 📝 Notas

- Las métricas se acumulan desde el inicio del servidor
- Los logs automáticos se muestran cada 10-50 ticks
- Las métricas se pueden resetear reiniciando el servidor
- El overhead de las métricas es mínimo (< 0.1ms por tick)

