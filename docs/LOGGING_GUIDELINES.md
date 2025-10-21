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
