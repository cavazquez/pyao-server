# Fix: Transiciones de Mapa - Cliente Congelado

**Fecha:** 2025-01-20  
**Versión:** 0.5.1-alpha  
**Archivo:** `src/task_walk.py`

## Problema

Al cambiar de mapa, el cliente se congelaba mostrando una pantalla negra. El jugador podía moverse (el servidor procesaba los movimientos) pero no veía nada en pantalla.

### Causa Raíz

El método `_handle_map_transition()` en `task_walk.py` solo enviaba:
1. CHANGE_MAP (carga el nuevo mapa)
2. POS_UPDATE (posiciona al jugador)
3. CHARACTER_REMOVE (broadcast en mapa anterior)

**Faltaba enviar:**
- CHARACTER_CREATE del propio jugador (para que aparezca en su cliente)
- Todos los jugadores existentes en el nuevo mapa
- Todos los NPCs del nuevo mapa
- Todos los objetos del suelo en el nuevo mapa
- Broadcast del CHARACTER_CREATE a otros jugadores en el nuevo mapa

## Solución Implementada

### Flujo Completo de Transición de Mapa

```python
async def _handle_map_transition(
    user_id, heading, current_x, current_y, current_map, new_x, new_y, new_map
):
    # 1. Enviar CHANGE_MAP - Cliente carga nuevo mapa
    await message_sender.send_change_map(new_map)
    
    # 2. Actualizar posición en Redis
    await player_repo.set_position(user_id, new_x, new_y, new_map, heading)
    
    # 3. Enviar POS_UPDATE - Cliente posiciona jugador
    await message_sender.send_pos_update(new_x, new_y)
    
    # 4. Remover jugador del mapa anterior en MapManager
    map_manager.remove_player(current_map, user_id)
    
    # 5. Broadcast CHARACTER_REMOVE en mapa anterior
    await broadcast_service.broadcast_character_remove(current_map, user_id)
    
    # 6. Agregar jugador al nuevo mapa en MapManager
    map_manager.add_player(new_map, user_id, message_sender, username)
    
    # 7. Enviar CHARACTER_CREATE del propio jugador ✅ NUEVO
    await message_sender.send_character_create(
        char_index=user_id,
        body=char_body,
        head=char_head,
        heading=heading,
        x=new_x,
        y=new_y,
        name=username,
    )
    
    # 8. Enviar todos los jugadores existentes en el nuevo mapa ✅ NUEVO
    for other_user_id in map_manager.get_players_in_map(new_map):
        if other_user_id == user_id:
            continue
        await message_sender.send_character_create(...)
    
    # 9. Enviar todos los NPCs del nuevo mapa ✅ NUEVO
    for npc in map_manager.get_npcs_in_map(new_map):
        await message_sender.send_character_create(...)
    
    # 10. Enviar todos los objetos del suelo ✅ NUEVO
    for (map_id, x, y), items in map_manager._ground_items.items():
        if map_id == new_map:
            await message_sender.send_object_create(x, y, grh_index)
    
    # 11. Broadcast CHARACTER_CREATE a otros jugadores ✅ NUEVO
    await broadcast_service.broadcast_character_create(
        map_id=new_map,
        char_index=user_id,
        body=char_body,
        head=char_head,
        heading=heading,
        x=new_x,
        y=new_y,
        name=username,
    )
```

### Cambios Realizados

**Archivo:** `src/task_walk.py`

1. **Paso 6:** Agregar jugador al MapManager del nuevo mapa
   - Obtiene username desde AccountRepository
   - Llama a `map_manager.add_player()`

2. **Paso 7:** Enviar CHARACTER_CREATE del propio jugador
   - Obtiene body/head desde AccountRepository
   - Envía al cliente para que se vea a sí mismo

3. **Paso 8:** Enviar jugadores existentes en el nuevo mapa
   - Itera sobre `map_manager.get_players_in_map(new_map)`
   - Envía CHARACTER_CREATE de cada jugador
   - Delay de 0.01s entre cada uno

4. **Paso 9:** Enviar NPCs del nuevo mapa
   - Itera sobre `map_manager.get_npcs_in_map(new_map)`
   - Envía CHARACTER_CREATE de cada NPC
   - Delay de 0.01s entre cada uno

5. **Paso 10:** Enviar objetos del suelo
   - Itera sobre `map_manager._ground_items`
   - Filtra por `map_id == new_map`
   - Envía OBJECT_CREATE de cada item
   - Delay de 0.01s entre cada uno

6. **Paso 11:** Broadcast a otros jugadores
   - Llama a `broadcast_service.broadcast_character_create()`
   - Notifica a otros jugadores en el nuevo mapa

### Actualización del Índice Espacial

El MapManager ahora:
- **Remueve** al jugador del mapa anterior con `remove_player()`
- **Agrega** al jugador al nuevo mapa con `add_player()`

Esto mantiene sincronizado el índice espacial `_players_by_map`.

## Resultado

✅ El cliente ahora ve correctamente:
- Su propio personaje en el nuevo mapa
- Todos los jugadores existentes
- Todos los NPCs
- Todos los objetos del suelo
- Otros jugadores ven al jugador que cambió de mapa

✅ No más pantalla negra congelada
✅ Transiciones de mapa fluidas
✅ Sincronización correcta del estado del mundo

## Tests

- ✅ 807 tests pasando (100%)
- ✅ 0 errores de linting
- ✅ Todos los tests de `test_task_walk.py` pasan

## Notas Técnicas

### Delays entre Packets

Se agregaron delays de `0.01s` entre envíos de CHARACTER_CREATE y OBJECT_CREATE para evitar saturar el cliente con demasiados packets simultáneos.

### AccountRepository

Se importa dinámicamente dentro del método para evitar dependencias circulares:

```python
from src.account_repository import AccountRepository  # noqa: PLC0415
```

### Complejidad del Método

El método `_handle_map_transition()` tiene el noqa `PLR0915` (too many statements) porque es inherentemente complejo. Cada paso es necesario para una transición correcta.

## Próximos Pasos

- [ ] Optimizar envío de entidades (batch de packets)
- [ ] Implementar rango visible (solo enviar entidades cercanas)
- [ ] Agregar efectos visuales de transición
- [ ] Implementar precarga de mapas adyacentes

## Referencias

- **Protocolo AO:** CHANGE_MAP (21), POS_UPDATE (22), CHARACTER_CREATE (27)
- **Broadcast:** `multiplayer_broadcast_service.py`
- **MapManager:** `map_manager.py`
- **Transiciones:** `map_transition_service.py`
