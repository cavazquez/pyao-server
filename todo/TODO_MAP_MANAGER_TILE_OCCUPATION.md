# TODO: MapManager y _tile_occupation

**Fecha:** 2025-11-18  
**Prioridad:** MEDIA  
**Estado:** Planificado  

## Opción 2 – Consistencia de índice espacial para jugadores

- Implementar que los jugadores marquen `_tile_occupation` al entrar en un mapa, no solo al moverse:
  - Login / spawn inicial (`PlayerMapService.spawn_in_map`).
  - Cambio de mapa (`PlayerMapService.transition_to_map` / `MapTransitionOrchestrator`).
- Reutilizar `update_player_tile(user_id, map_id, old_x, old_y, new_x, new_y)` con:
  - `old_x == new_x`
  - `old_y == new_y`
- Mantener la lógica actual de limpieza de `_tile_occupation`:
  - `remove_player` y `remove_player_from_all_maps` para jugadores.
  - `move_npc` y `remove_npc` para NPCs.

### Notas técnicas

- Actualmente `_tile_occupation` solo se actualiza:
  - Cuando el jugador se mueve (`TaskWalk._update_position_and_spatial_index`).
  - Cuando se teleporta dentro del mismo mapa (`PlayerMapService.teleport_in_same_map`).
- Consecuencia:
  - Jugadores recién spawneados pueden no aparecer en `_tile_occupation` hasta que se mueven.
  - `_find_free_spawn_position` en `TaskLogin` puede no considerar a todos los jugadores quietos.
- Objetivo de la Opción 2:
  - Que el índice espacial sea consistente desde el momento del spawn / cambio de mapa.
  - Centralizar la escritura de `_tile_occupation` en `update_player_tile`.
