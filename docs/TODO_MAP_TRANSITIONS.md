# TODO: Sistema de Transiciones entre Mapas

**Fecha:** 2025-10-19  
**Prioridad:** ALTA  
**Estado:** Planificado

## 🐛 Problema Identificado

Cuando un jugador llega al borde del mapa (coordenadas 1 o 100), el movimiento se detiene pero **NO cambia de mapa**. El código actual en `task_walk.py` usa `min()` y `max()` para limitar las coordenadas, lo que impide el cambio de mapa.

### Código Actual (Problemático)

```python
# task_walk.py líneas 138-145
if heading == HEADING_NORTH:
    new_y = max(MIN_MAP_COORDINATE, current_y - 1)  # Se detiene en y=1
elif heading == HEADING_EAST:
    new_x = min(MAX_MAP_COORDINATE, current_x + 1)  # Se detiene en x=100
elif heading == HEADING_SOUTH:
    new_y = min(MAX_MAP_COORDINATE, current_y + 1)  # Se detiene en y=100
elif heading == HEADING_WEST:
    new_x = max(MIN_MAP_COORDINATE, current_x - 1)  # Se detiene en x=1
```

## 📋 Plan de Implementación

### Paso 1: Crear Configuración de Transiciones de Mapa

**Archivo:** `data/map_transitions.toml`

```toml
# Transiciones entre mapas
# Define qué mapa se carga cuando el jugador cruza un borde

# Mapa 1 - Ullathorpe (ciudad inicial)
[[transition]]
from_map = 1
edge = "north"      # Borde norte (y = 0)
to_map = 2          # Mapa del bosque norte
to_x = 50           # Posición X de entrada
to_y = 99           # Posición Y de entrada (borde sur del nuevo mapa)

[[transition]]
from_map = 1
edge = "south"
to_map = 3          # Mapa del campo sur
to_x = 50
to_y = 2

[[transition]]
from_map = 1
edge = "east"
to_map = 4          # Mapa del bosque este
to_x = 2
to_y = 50

[[transition]]
from_map = 1
edge = "west"
to_map = 5          # Mapa de las montañas oeste
to_x = 99
to_y = 50

# Mapa 2 - Bosque Norte (conexiones de vuelta)
[[transition]]
from_map = 2
edge = "south"
to_map = 1
to_x = 50
to_y = 2

# ... más transiciones para otros mapas
```

### Paso 2: Crear MapTransitionService

**Archivo:** `src/map_transition_service.py`

```python
"""Servicio para manejar transiciones entre mapas."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MapTransition:
    """Transición entre mapas."""
    
    from_map: int
    edge: str  # "north", "south", "east", "west"
    to_map: int
    to_x: int
    to_y: int


class MapTransitionService:
    """Servicio que maneja las transiciones entre mapas."""
    
    def __init__(self, transitions_path: str = "data/map_transitions.toml") -> None:
        """Inicializa el servicio de transiciones.
        
        Args:
            transitions_path: Ruta al archivo de transiciones.
        """
        self._transitions: dict[tuple[int, str], MapTransition] = {}
        self._load_transitions(transitions_path)
    
    def _load_transitions(self, path: str) -> None:
        """Carga las transiciones desde el archivo TOML."""
        try:
            file_path = Path(path)
            if not file_path.exists():
                logger.warning("Archivo de transiciones no encontrado: %s", path)
                return
            
            with file_path.open("rb") as f:
                data = tomllib.load(f)
            
            for trans_data in data.get("transition", []):
                transition = MapTransition(
                    from_map=trans_data["from_map"],
                    edge=trans_data["edge"],
                    to_map=trans_data["to_map"],
                    to_x=trans_data["to_x"],
                    to_y=trans_data["to_y"],
                )
                
                key = (transition.from_map, transition.edge)
                self._transitions[key] = transition
                
                logger.debug(
                    "Transición cargada: Mapa %d (%s) -> Mapa %d (%d, %d)",
                    transition.from_map,
                    transition.edge,
                    transition.to_map,
                    transition.to_x,
                    transition.to_y,
                )
            
            logger.info("Transiciones de mapa cargadas: %d", len(self._transitions))
        
        except Exception:
            logger.exception("Error al cargar transiciones desde %s", path)
    
    def get_transition(self, from_map: int, edge: str) -> MapTransition | None:
        """Obtiene la transición para un mapa y borde específicos.
        
        Args:
            from_map: ID del mapa actual.
            edge: Borde del mapa ("north", "south", "east", "west").
        
        Returns:
            MapTransition si existe, None si no hay transición configurada.
        """
        return self._transitions.get((from_map, edge))
    
    def has_transition(self, from_map: int, edge: str) -> bool:
        """Verifica si existe una transición para un mapa y borde.
        
        Args:
            from_map: ID del mapa actual.
            edge: Borde del mapa.
        
        Returns:
            True si existe transición, False si no.
        """
        return (from_map, edge) in self._transitions
```

### Paso 3: Modificar task_walk.py

**Cambios necesarios:**

```python
# Agregar import
from src.map_transition_service import MapTransitionService

# En __init__, agregar parámetro
def __init__(
    self,
    data: bytes,
    message_sender: MessageSender,
    player_repo: PlayerRepository | None = None,
    map_manager: MapManager | None = None,
    broadcast_service: MultiplayerBroadcastService | None = None,
    map_transition_service: MapTransitionService | None = None,  # NUEVO
    session_data: dict[str, dict[str, int]] | None = None,
) -> None:
    # ...
    self.map_transition_service = map_transition_service

# Reemplazar la lógica de movimiento (líneas 134-157)
async def _calculate_new_position(
    self, heading: int, current_x: int, current_y: int, current_map: int
) -> tuple[int, int, int, bool]:
    """Calcula nueva posición y detecta transiciones de mapa.
    
    Returns:
        Tupla (new_x, new_y, new_map, changed_map)
    """
    new_x = current_x
    new_y = current_y
    new_map = current_map
    changed_map = False
    
    # Detectar si estamos en el borde y hay transición
    edge = None
    
    if heading == HEADING_NORTH and current_y == MIN_MAP_COORDINATE:
        edge = "north"
    elif heading == HEADING_EAST and current_x == MAX_MAP_COORDINATE:
        edge = "east"
    elif heading == HEADING_SOUTH and current_y == MAX_MAP_COORDINATE:
        edge = "south"
    elif heading == HEADING_WEST and current_x == MIN_MAP_COORDINATE:
        edge = "west"
    
    # Si estamos en un borde, verificar transición
    if edge and self.map_transition_service:
        transition = self.map_transition_service.get_transition(current_map, edge)
        
        if transition:
            # Cambiar de mapa
            new_map = transition.to_map
            new_x = transition.to_x
            new_y = transition.to_y
            changed_map = True
            
            logger.info(
                "Transición de mapa: %d -> %d, pos (%d,%d) -> (%d,%d)",
                current_map,
                new_map,
                current_x,
                current_y,
                new_x,
                new_y,
            )
            
            return new_x, new_y, new_map, changed_map
    
    # Movimiento normal (sin transición)
    if heading == HEADING_NORTH:
        new_y = max(MIN_MAP_COORDINATE, current_y - 1)
    elif heading == HEADING_EAST:
        new_x = min(MAX_MAP_COORDINATE, current_x + 1)
    elif heading == HEADING_SOUTH:
        new_y = min(MAX_MAP_COORDINATE, current_y + 1)
    elif heading == HEADING_WEST:
        new_x = max(MIN_MAP_COORDINATE, current_x - 1)
    
    return new_x, new_y, new_map, changed_map

# En execute(), usar la nueva función
new_x, new_y, new_map, changed_map = await self._calculate_new_position(
    heading, current_x, current_y, current_map
)

# Si cambió de mapa, enviar CHANGE_MAP
if changed_map:
    await self.message_sender.send_change_map(new_map)
    
    # Remover personaje del mapa anterior
    await self.map_manager.remove_character(user_id, current_map)
    
    # Agregar personaje al nuevo mapa
    await self.map_manager.add_character(user_id, new_map, new_x, new_y)
    
    # Broadcast CHARACTER_REMOVE en mapa anterior
    await self.broadcast_service.broadcast_character_remove(
        current_map, user_id, exclude_user_id=user_id
    )
    
    # Broadcast CHARACTER_CREATE en nuevo mapa
    # (esto se hace más adelante en el flujo normal)
```

### Paso 4: Integrar en server_initializer.py

```python
# En service_initializer.py

from src.map_transition_service import MapTransitionService

# Crear servicio
map_transition_service = MapTransitionService()
logger.info("✓ Sistema de transiciones de mapa inicializado")

# Agregar a services dict
services = {
    # ... otros servicios ...
    "map_transition_service": map_transition_service,
}

# En server_initializer.py, pasar a TaskWalk
task = TaskWalk(
    data=data,
    message_sender=message_sender,
    player_repo=repositories["player_repo"],
    map_manager=map_manager,
    broadcast_service=services["broadcast_service"],
    map_transition_service=services["map_transition_service"],  # NUEVO
    session_data=session_data,
)
```

### Paso 5: Tests

**Archivo:** `tests/test_map_transition_service.py`

```python
"""Tests para MapTransitionService."""

from src.map_transition_service import MapTransitionService


class TestMapTransitionService:
    """Tests para MapTransitionService."""
    
    def test_init(self) -> None:
        """Test de inicialización."""
        service = MapTransitionService()
        assert service is not None
    
    def test_has_transition(self) -> None:
        """Test de verificación de transiciones."""
        service = MapTransitionService()
        
        # Debería tener transiciones configuradas
        # (asumiendo que data/map_transitions.toml existe)
        assert service.has_transition(1, "north") is True
    
    def test_get_transition(self) -> None:
        """Test de obtención de transición."""
        service = MapTransitionService()
        
        transition = service.get_transition(1, "north")
        
        if transition:
            assert transition.from_map == 1
            assert transition.edge == "north"
            assert transition.to_map > 0
            assert transition.to_x > 0
            assert transition.to_y > 0
    
    def test_no_transition(self) -> None:
        """Test cuando no hay transición."""
        service = MapTransitionService()
        
        # Mapa que no existe
        transition = service.get_transition(99999, "north")
        assert transition is None
```

## 📝 Checklist de Implementación

- [ ] Crear `data/map_transitions.toml` con transiciones básicas
- [ ] Crear `src/map_transition_service.py`
- [ ] Modificar `src/task_walk.py`:
  - [ ] Agregar parámetro `map_transition_service`
  - [ ] Crear método `_calculate_new_position()`
  - [ ] Detectar bordes de mapa
  - [ ] Aplicar transiciones cuando existan
  - [ ] Enviar `CHANGE_MAP` cuando cambie de mapa
  - [ ] Actualizar broadcast de personajes
- [ ] Integrar en `src/service_initializer.py`
- [ ] Integrar en `src/server_initializer.py` (TaskWalk)
- [ ] Crear `tests/test_map_transition_service.py`
- [ ] Actualizar documentación

## 🎯 Beneficios

✅ **Mundo conectado** - Mapas conectados entre sí  
✅ **Exploración fluida** - Cambio automático de mapa  
✅ **Configurable** - Fácil agregar nuevas transiciones  
✅ **Flexible** - Posición de entrada personalizable  
✅ **Testeable** - Lógica separada y testeable

## ⚠️ Consideraciones

1. **Sincronización de personajes:**
   - Remover del mapa anterior
   - Agregar al nuevo mapa
   - Broadcast correcto a jugadores en ambos mapas

2. **NPCs en bordes:**
   - Los NPCs NO deberían cambiar de mapa
   - Validar que solo jugadores pueden transicionar

3. **Colisiones:**
   - Verificar que la posición de destino no esté bloqueada
   - Si está bloqueada, no permitir la transición

4. **Performance:**
   - Cache de transiciones en memoria (ya lo hace el servicio)
   - Evitar lookups innecesarios

## 📚 Referencias

- `src/task_walk.py` - Lógica de movimiento actual
- `src/message_sender.py` - Método `send_change_map()`
- `src/player_service.py` - Método `send_position()`
- `docs/LOOT_SYSTEM.md` - Ejemplo de sistema con TOML

## 🚀 Próximos Pasos

1. Implementar MapTransitionService básico
2. Configurar transiciones para Mapa 1
3. Modificar task_walk.py
4. Probar con 2 mapas conectados
5. Expandir a más mapas según necesidad
