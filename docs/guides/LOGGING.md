> **Última consolidación:** 2026-05

# Guía de Niveles de Logging

## Propósito

Esta guía establece convenciones claras para el uso de niveles de logging en el servidor PyAO.

---

## Niveles de Logging

### 🔴 **ERROR** - Errores que requieren atención

**Usar para:**
- Excepciones no manejadas
- Errores de conexión a Redis
- Errores críticos que afectan funcionalidad
- Fallos en carga de datos críticos

**Ejemplos:**
```python
logger.error("Error conectando a Redis: %s", error)
logger.exception("Error inesperado procesando packet")
```

---

### ⚠️  **WARNING** - Situaciones anormales no críticas

**Usar para:**
- Archivos de configuración faltantes (con fallback)
- Datos inconsistentes que pueden recuperarse
- Operaciones deprecadas
- Rate limiting activado

**Ejemplos:**
```python
logger.warning("Archivo de mapa no encontrado: %s (usando default)", map_file)
logger.warning("Usuario %d intenta moverse demasiado rápido", user_id)
```

---

### ℹ️  **INFO** - Eventos importantes del negocio

**Usar para:**
- **Inicio/apagado del servidor**
- **Usuario se conectó/desconectó**
- **NPC murió** (evento importante del juego)
- **Jugador cambió de mapa** (transición)
- **Jugador subió de nivel**
- **Sistema cargado exitosamente** (startup)
- **Logros importantes del juego**

**Ejemplos:**
```python
logger.info("Servidor escuchando en %s:%d", host, port)
logger.info("Usuario %s (ID:%d) conectado desde %s", username, user_id, address)
logger.info("NPC %s eliminado tras ser matado por user_id %d", npc.name, user_id)
logger.info("Exit tile detectado: Transición %d -> %d", current_map, new_map)
logger.info("✓ 145 mapas cargados con tiles bloqueados")
```

**NO usar para:**
- Movimientos individuales de jugadores (demasiado verboso)
- Validaciones de tiles normales
- Updates de HP/Mana/Stamina rutinarios
- Operaciones CRUD normales

---

### 🔍 **DEBUG** - Información útil para debugging

**Usar para:**
- **Movimientos de jugadores** (posición detallada)
- **Validaciones de tiles**
- **Cálculos de pathfinding**
- **Updates de stats** (HP, mana, stamina)
- **Operaciones de Redis** (get/set)
- **Parsing de packets**
- **Lógica de combate detallada**

**Ejemplos:**
```python
logger.debug("User %d se movió de (%d,%d) a (%d,%d)", user_id, old_x, old_y, new_x, new_y)
logger.debug("Verificando tile (%d,%d): bloqueado=%s", x, y, is_blocked)
logger.debug("HP actualizado para user_id %d: %d", user_id, hp)
logger.debug("TaskWalk: Recibido WALK con heading=%d", heading)
logger.debug("PathfindingService: Calculando ruta desde (%d,%d) a (%d,%d)", x1, y1, x2, y2)
```

---

## Reglas Generales

### ✅ **DO:**
- Usar f-strings solo para construir mensajes complejos, preferir parámetros
- Incluir contexto relevante (user_id, npc_id, map_id, etc.)
- Ser consistente con el nivel de detalle
- Usar logger.exception() para excepciones (incluye traceback)

### ❌ **DON'T:**
- Loggear contraseñas, tokens, o datos sensibles
- Loggear en loops de alto rendimiento (ej: cada tick del game loop)
- Usar INFO para debugging de desarrollo
- Crear mensajes de log sin contexto ("Error", "Falló")

---

## Ejemplos de Migración

### ❌ **Antes (Incorrecto)**
```python
# INFO usado para debugging rutinario
logger.info("User %d se movió de (%d,%d) a (%d,%d)", user_id, x1, y1, x2, y2)
logger.info("Verificando tile (%d,%d): bloqueado=%s", x, y, blocked)

# DEBUG usado para eventos importantes
logger.debug("NPC %s murió", npc.name)
```

### ✅ **Después (Correcto)**
```python
# DEBUG para movimientos rutinarios
logger.debug("User %d se movió de (%d,%d) a (%d,%d)", user_id, x1, y1, x2, y2)
logger.debug("Verificando tile (%d,%d): bloqueado=%s", x, y, blocked)

# INFO para eventos importantes del juego
logger.info("NPC %s eliminado tras ser matado por user_id %d", npc.name, user_id)
```

---

## Configuración en Producción

En producción, el nivel recomendado es **INFO**:
- Se loggean eventos importantes del negocio
- Se filtran movimientos y validaciones rutinarias
- Suficiente para monitoreo y troubleshooting
- No abruma los logs

Para debugging temporal, cambiar a **DEBUG** en el archivo de configuración.

---

## Checklist de Revisión

Al agregar logging nuevo, preguntarse:

1. **¿Es un error?** → ERROR
2. **¿Es anormal pero recuperable?** → WARNING
3. **¿Es un evento importante del negocio?** → INFO
4. **¿Es útil solo para debugging?** → DEBUG
5. **¿Ocurre muy frecuentemente?** → Probablemente DEBUG
6. **¿Un admin lo vería en producción?** → Probablemente INFO

---

## Referencias

- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Best Practices for Logging](https://docs.python-guide.org/writing/logging/)

---

## Features: LOGGING_GUIDELINES.md

> Documento fuente archivado en [`archive/superseded/LOGGING_GUIDELINES.md`](../archive/superseded/LOGGING_GUIDELINES.md).

## Propósito

Esta guía establece convenciones claras para el uso de niveles de logging en el servidor PyAO.

---

## Niveles de Logging

### 🔴 **ERROR** - Errores que requieren atención

**Usar para:**
- Excepciones no manejadas
- Errores de conexión a Redis
- Errores críticos que afectan funcionalidad
- Fallos en carga de datos críticos

**Ejemplos:**
```python
logger.error("Error conectando a Redis: %s", error)
logger.exception("Error inesperado procesando packet")
```

---

### ⚠️  **WARNING** - Situaciones anormales no críticas

**Usar para:**
- Archivos de configuración faltantes (con fallback)
- Datos inconsistentes que pueden recuperarse
- Operaciones deprecadas
- Rate limiting activado

**Ejemplos:**
```python
logger.warning("Archivo de mapa no encontrado: %s (usando default)", map_file)
logger.warning("Usuario %d intenta moverse demasiado rápido", user_id)
```

---

### ℹ️  **INFO** - Eventos importantes del negocio

**Usar para:**
- **Inicio/apagado del servidor**
- **Usuario se conectó/desconectó**
- **NPC murió** (evento importante del juego)
- **Jugador cambió de mapa** (transición)
- **Jugador subió de nivel**
- **Sistema cargado exitosamente** (startup)
- **Logros importantes del juego**

**Ejemplos:**
```python
logger.info("Servidor escuchando en %s:%d", host, port)
logger.info("Usuario %s (ID:%d) conectado desde %s", username, user_id, address)
logger.info("NPC %s eliminado tras ser matado por user_id %d", npc.name, user_id)
logger.info("Exit tile detectado: Transición %d -> %d", current_map, new_map)
logger.info("✓ 145 mapas cargados con tiles bloqueados")
```

**NO usar para:**
- Movimientos individuales de jugadores (demasiado verboso)
- Validaciones de tiles normales
- Updates de HP/Mana/Stamina rutinarios
- Operaciones CRUD normales

---

### 🔍 **DEBUG** - Información útil para debugging

**Usar para:**
- **Movimientos de jugadores** (posición detallada)
- **Validaciones de tiles**
- **Cálculos de pathfinding**
- **Updates de stats** (HP, mana, stamina)
- **Operaciones de Redis** (get/set)
- **Parsing de packets**
- **Lógica de combate detallada**

**Ejemplos:**
```python
logger.debug("User %d se movió de (%d,%d) a (%d,%d)", user_id, old_x, old_y, new_x, new_y)
logger.debug("Verificando tile (%d,%d): bloqueado=%s", x, y, is_blocked)
logger.debug("HP actualizado para user_id %d: %d", user_id, hp)
logger.debug("TaskWalk: Recibido WALK con heading=%d", heading)
logger.debug("PathfindingService: Calculando ruta desde (%d,%d) a (%d,%d)", x1, y1, x2, y2)
```

---

## Reglas Generales

### ✅ **DO:**
- Usar f-strings solo para construir mensajes complejos, preferir parámetros
- Incluir contexto relevante (user_id, npc_id, map_id, etc.)
- Ser consistente con el nivel de detalle
- Usar logger.exception() para excepciones (incluye traceback)

### ❌ **DON'T:**
- Loggear contraseñas, tokens, o datos sensibles
- Loggear en loops de alto rendimiento (ej: cada tick del game loop)
- Usar INFO para debugging de desarrollo
- Crear mensajes de log sin contexto ("Error", "Falló")

---

## Ejemplos de Migración

### ❌ **Antes (Incorrecto)**
```python
# INFO usado para debugging rutinario
logger.info("User %d se movió de (%d,%d) a (%d,%d)", user_id, x1, y1, x2, y2)
logger.info("Verificando tile (%d,%d): bloqueado=%s", x, y, blocked)

# DEBUG usado para eventos importantes
logger.debug("NPC %s murió", npc.name)
```

### ✅ **Después (Correcto)**
```python
# DEBUG para movimientos rutinarios
logger.debug("User %d se movió de (%d,%d) a (%d,%d)", user_id, x1, y1, x2, y2)
logger.debug("Verificando tile (%d,%d): bloqueado=%s", x, y, blocked)

# INFO para eventos importantes del juego
logger.info("NPC %s eliminado tras ser matado por user_id %d", npc.name, user_id)
```

---

## Configuración en Producción

En producción, el nivel recomendado es **INFO**:
- Se loggean eventos importantes del negocio
- Se filtran movimientos y validaciones rutinarias
- Suficiente para monitoreo y troubleshooting
- No abruma los logs

Para debugging temporal, cambiar a **DEBUG** en el archivo de configuración.

---

## Checklist de Revisión

Al agregar logging nuevo, preguntarse:

1. **¿Es un error?** → ERROR
2. **¿Es anormal pero recuperable?** → WARNING
3. **¿Es un evento importante del negocio?** → INFO
4. **¿Es útil solo para debugging?** → DEBUG
5. **¿Ocurre muy frecuentemente?** → Probablemente DEBUG
6. **¿Un admin lo vería en producción?** → Probablemente INFO

---

## Referencias

- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Best Practices for Logging](https://docs.python-guide.org/writing/logging/)

## Features: LOGGING_FEATURES.md

> Documento fuente archivado en [`archive/superseded/LOGGING_FEATURES.md`](../archive/superseded/LOGGING_FEATURES.md).

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

