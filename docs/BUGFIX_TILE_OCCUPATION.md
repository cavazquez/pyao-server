# Bug Fix: Tile Occupation al Remover NPCs

## Problema

Cuando un NPC moría y dropeaba oro, los jugadores no podían moverse sobre el tile donde estaba el oro, a pesar de que el oro era visible en el cliente.

## Síntomas

1. NPC muere y dropea oro en su posición
2. El oro aparece visualmente en el cliente
3. El jugador intenta moverse sobre el oro
4. El cliente valida que puede moverse (`_CanMoveTo` retorna `true`)
5. El cliente envía packet `WALK` al servidor
6. **El servidor rechaza el movimiento silenciosamente**
7. El jugador no puede recoger el oro porque no puede llegar a la posición

## Diagnóstico

### Logs del Cliente (Godot)
```
[DEBUG] Puedo mover a (52,49)
[OUTGOING] Walk | heading: 4
```

### Logs del Servidor
```
TaskWalk.execute() llamado - data=0604
User 1 no puede moverse a (52,49) - posición bloqueada por MapManager
```

El servidor recibía el packet WALK pero lo rechazaba porque `MapManager.can_move_to()` retornaba `false`.

## Causa Raíz

En `src/map_manager.py`, el método `remove_npc()` eliminaba el NPC de `_npcs_by_map` pero **NO limpiaba `_tile_occupation`**:

```python
def remove_npc(self, map_id: int, instance_id: str) -> None:
    if map_id in self._npcs_by_map and instance_id in self._npcs_by_map[map_id]:
        npc_name = self._npcs_by_map[map_id][instance_id].name
        del self._npcs_by_map[map_id][instance_id]  # ← Solo elimina del diccionario
        # ❌ NO limpiaba _tile_occupation
```

El método `can_move_to()` en `src/map_manager_spatial.py` verifica `_tile_occupation`:

```python
def can_move_to(self, map_id: int, x: int, y: int) -> bool:
    # Verificar si hay un jugador o NPC en esa posición
    key = (map_id, x, y)
    return key not in self._tile_occupation  # ← Retornaba False
```

Como el tile seguía en `_tile_occupation` marcado como `npc:instance_id`, el servidor bloqueaba el movimiento.

## Solución

Modificar `remove_npc()` para limpiar `_tile_occupation`:

```python
def remove_npc(self, map_id: int, instance_id: str) -> None:
    if map_id in self._npcs_by_map and instance_id in self._npcs_by_map[map_id]:
        npc = self._npcs_by_map[map_id][instance_id]
        npc_name = npc.name
        
        # ✅ Limpiar tile occupation para que el tile quede libre
        tile_key = (map_id, npc.x, npc.y)
        if tile_key in self._tile_occupation:
            del self._tile_occupation[tile_key]
            logger.debug("Tile (%d,%d) liberado al remover NPC %s", npc.x, npc.y, npc_name)
        
        del self._npcs_by_map[map_id][instance_id]
        logger.debug("NPC %s removido del mapa %d", npc_name, map_id)
```

## Archivos Modificados

- `src/map_manager.py` - Limpiar `_tile_occupation` al remover NPC
- `src/task_attack.py` - Simplificado (no necesita enviar `BLOCK_POSITION`)
- `src/task_walk.py` - Logs de debug mejorados para diagnóstico

## Testing

### Caso de Prueba

1. Conectarse al servidor
2. Atacar y matar un NPC (Goblin, Lobo, etc.)
3. El NPC dropea oro en su posición
4. Intentar moverse sobre el oro
5. **Resultado esperado:** El jugador se mueve sobre el oro sin problemas
6. Presionar tecla de recoger
7. **Resultado esperado:** El oro se recoge correctamente

### Verificación en Logs

**Antes del fix:**
```
User 1 no puede moverse a (52,49) - posición bloqueada por MapManager
```

**Después del fix:**
```
Tile (52,49) liberado al remover NPC Goblin
User 1 se movió de (51,49) a (52,49) en dirección 2
Jugador 1 recogió 67 de oro en (52,49)
```

## Lecciones Aprendidas

1. **Índices espaciales requieren mantenimiento:** Cuando se usa un índice espacial (`_tile_occupation`) para optimizar colisiones, es crítico mantenerlo sincronizado con el estado del juego.

2. **Validación cliente vs servidor:** El cliente puede validar que puede moverse, pero el servidor tiene la autoridad final. La desincronización entre ambas validaciones causó confusión.

3. **Logs de debug son esenciales:** Sin logs detallados, este bug hubiera sido muy difícil de diagnosticar. Los logs mostraron exactamente dónde se rechazaba el movimiento.

4. **Testing de flujos completos:** Este bug solo aparecía en el flujo completo: matar NPC → dropear oro → intentar recoger. Tests unitarios de `remove_npc()` no lo hubieran detectado.

## Prevención

Para evitar bugs similares en el futuro:

1. **Documentar invariantes:** `_tile_occupation` debe estar sincronizado con `_npcs_by_map` y `_players_by_map`
2. **Tests de integración:** Agregar tests que verifiquen flujos completos (combate → loot → pickup)
3. **Assertions:** Considerar agregar assertions que verifiquen la consistencia de `_tile_occupation`

## Referencias

- Issue: Jugadores no pueden moverse sobre oro dropeado por NPCs
- Fecha: 2025-10-17
- Severidad: Alta (bloqueaba gameplay core)
- Tiempo de diagnóstico: ~2 horas
- Archivos afectados: 3
- Tests agregados: Pendiente

---

**Versión:** 0.2.0-alpha  
**Autor:** Cristian Vazquez  
**Fecha:** 2025-10-17
