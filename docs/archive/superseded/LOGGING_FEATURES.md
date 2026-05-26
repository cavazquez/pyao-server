# Sistema de Logging por Features

## Descripción

El servidor usa un sistema de logging configurable por features/módulos que permite activar logs detallados solo para las partes del código que estás debuggeando, reduciendo el ruido en los logs.

## Uso Básico

### En Producción (Por Defecto)

Por defecto, la mayoría de módulos están en nivel `WARNING`, mostrando solo advertencias y errores:

```bash
uv run python src/server.py
```

### Modo Debug Global

Activa logs detallados para TODO el servidor:

```bash
uv run python src/server.py --debug
```

## Configuración por Features

Edita `src/logging_config.py` para cambiar el nivel de logging de features específicas:

```python
FEATURE_LOG_LEVELS: dict[str, LogLevel] = {
    # Core
    "core": "INFO",
    "server": "INFO",
    
    # Tasks
    "tasks.party": "DEBUG",  # ← Cambiar a DEBUG para ver logs de party
    "tasks.combat": "WARNING",
    
    # Services
    "services.party": "DEBUG",  # ← Cambiar a DEBUG para ver logs de party service
    "services.npc": "WARNING",
}
```

## Features Disponibles

### Core
- `core` - Inicialización y configuración
- `server` - Servidor principal

### Network
- `network` - Conexiones y red
- `packets` - Lectura/escritura de packets

### Tasks
- `tasks` - Todas las tasks
- `tasks.party` - Tasks de party (/pmsg, /party, etc.)
- `tasks.player` - Tasks de jugador (login, walk, etc.)
- `tasks.combat` - Tasks de combate (attack, etc.)

### Services
- `services` - Todos los servicios
- `services.party` - Servicio de party
- `services.map` - Servicios de mapas
- `services.npc` - Servicios de NPCs

### Messaging
- `messaging` - Sistema de mensajes
- `messaging.console` - Mensajes de consola

### Effects
- `effects` - Efectos del juego (hambre, meditación, etc.)

### Repositories
- `repositories` - Acceso a datos (Redis)

### Game
- `game` - Lógica del juego (MapManager, etc.)

## Presets Comunes

Puedes usar funciones helper para activar logging de features relacionadas:

### Debug de Party System

```python
from src.logging_config import enable_party_debug

enable_party_debug()  # Activa DEBUG para services.party y tasks.party
```

### Debug de Combate

```python
from src.logging_config import enable_combat_debug

enable_combat_debug()  # Activa DEBUG para tasks.combat y services.npc
```

### Debug de Red

```python
from src.logging_config import enable_network_debug

enable_network_debug()  # Activa DEBUG para network, packets, messaging
```

### Modo Silencioso

```python
from src.logging_config import quiet_mode

quiet_mode()  # Solo muestra errores
```

## Cambiar Niveles en Runtime

Puedes cambiar el nivel de logging de una feature mientras el servidor está corriendo:

```python
from src.logging_config import set_feature_log_level, enable_debug_for_feature

# Cambiar a un nivel específico
set_feature_log_level("services.party", "DEBUG")

# Activar DEBUG rápidamente
enable_debug_for_feature("services.party")

# Desactivar DEBUG
disable_debug_for_feature("services.party")
```

## Ejemplo: Debuggear Party System

1. Edita `src/logging_config.py`:

```python
FEATURE_LOG_LEVELS = {
    # ... otros ...
    "tasks.party": "DEBUG",      # ← Cambiar a DEBUG
    "services.party": "DEBUG",   # ← Cambiar a DEBUG
    # ... otros ...
}
```

2. Reinicia el servidor:

```bash
uv run python src/server.py
```

3. Ahora verás logs detallados solo de party:

```
2025-11-03 01:52:17 - src.tasks.task_party_message - DEBUG - Party message packet data (hex): 600400486f6c61
2025-11-03 01:52:17 - src.services.party_service - DEBUG - Sender attributes: {'strength': 9, ...}
2025-11-03 01:52:17 - src.services.party_service - INFO - Party message from qwe (ID:2): 'Hola'
```

Mientras que otros módulos permanecen silenciosos (WARNING).

## Niveles de Logging

- `DEBUG` - Información muy detallada para debugging
- `INFO` - Información general de operaciones
- `WARNING` - Advertencias (por defecto para la mayoría)
- `ERROR` - Errores que no detienen el servidor
- `CRITICAL` - Errores críticos

## Tips

1. **Mantén WARNING por defecto** - Solo cambia a DEBUG/INFO las features que estás debuggeando
2. **Usa presets** - Los presets como `enable_party_debug()` activan múltiples features relacionadas
3. **Revierte cambios** - Después de debuggear, vuelve las features a WARNING
4. **Modo silencioso en producción** - Usa `quiet_mode()` en producción para reducir logs

## Estructura de Nombres

Los nombres de features siguen la estructura de directorios:

```
src/
├── tasks/
│   ├── task_party_message.py  → "tasks.party"
│   └── task_attack.py          → "tasks.combat"
├── services/
│   ├── party_service.py        → "services.party"
│   └── npc_service.py          → "services.npc"
└── messaging/
    └── message_sender.py       → "messaging"
```

El logger se obtiene con:
```python
logger = logging.getLogger(__name__)  # __name__ = "src.services.party_service"
```

Y se mapea a la feature `"services.party"`.
