# TODO: Refactorings y Mejoras

**Estado:** 🔄 En progreso - PacketReader implementado, MessageSender completado  
**Prioridad:** Media  
**Versión objetivo:** 0.5.0+

---

## 🎯 Mejoras de Arquitectura

### 1. ✅ PacketReader - IMPLEMENTADO

**Estado:** ✅ **COMPLETADO** - 3/9 tasks refactorizadas (33%)

**Problema original:**
Cada Task leía los parámetros del packet usando `struct.unpack` directamente sobre `self.data`, resultando en código repetitivo y propenso a errores.

**Ejemplo anterior:**
```python
# Código antiguo en cada task:
slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Solución implementada:**
Clase `PacketReader` en `src/packet_reader.py` que encapsula la lectura de diferentes tipos de datos:

```python
# src/packet_reader.py
class PacketReader:
    """Helper para leer parámetros de packets del cliente."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 1  # Saltar PacketID
    
    def read_byte(self) -> int:
        """Lee un byte (uint8)."""
        value = struct.unpack("B", self.data[self.offset:self.offset + 1])[0]
        self.offset += 1
        return value
    
    def read_int16(self) -> int:
        """Lee un int16 little-endian."""
        value = struct.unpack("<H", self.data[self.offset:self.offset + 2])[0]
        self.offset += 2
        return value
    
    def read_int32(self) -> int:
        """Lee un int32 little-endian."""
        value = struct.unpack("<I", self.data[self.offset:self.offset + 4])[0]
        self.offset += 4
        return value
    
    def read_string(self) -> str:
        """Lee un string con formato: length (uint16 LE) + UTF-16LE bytes."""
        length = self.read_int16()
        value = self.data[self.offset:self.offset + length].decode("utf-16-le")
        self.offset += length
        return value
```

**Uso actual en tasks:**
```python
# Ejemplo real en TaskCommerceBuy:
reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

**Tasks refactorizadas (3/9):**
- ✅ `task_bank_deposit.py`
- ✅ `task_bank_extract.py`
- ✅ `task_commerce_buy.py`

**Tasks pendientes (6/9):**
- 📝 `task_commerce_sell.py` (alta prioridad)
- 📝 `task_inventory_click.py` (alta prioridad)
- 📝 `task_equip_item.py` (alta prioridad)
- 📝 `task_double_click.py` (media prioridad)
- 📝 `task_left_click.py` (media prioridad)
- 📝 `task_cast_spell.py` (baja prioridad)

**Beneficios logrados:**
- ✅ Código más limpio y legible
- ✅ Menos propenso a errores de offset
- ✅ Centraliza la lógica de parsing
- ✅ Facilita agregar validaciones
- ✅ Type hints completos
- ✅ 15 tests unitarios pasando (100% cobertura)

**Archivos creados:**
- ✅ `src/packet_reader.py` (implementado)
- ✅ `tests/test_packet_reader.py` (15 tests)

**Documentación:**
- Ver `docs/TODO_PACKET_READER_REFACTORING.md` para detalles completos

**Próximos pasos:**
- Refactorizar las 6 tasks pendientes (~1 hora)
- Priorizar tasks de alta prioridad primero

---

---

### 2. ✅ MessageSender Refactoring - COMPLETADO

**Estado:** ✅ **COMPLETADO** - Migración 100% finalizada

**Logros:**
- ✅ 8 componentes especializados creados
- ✅ 75 tests unitarios nuevos (100% cobertura)
- ✅ 49 métodos delegados a componentes
- ✅ Patrón Facade implementado
- ✅ Todos los imports de `msg.py` delegados
- ✅ 716 tests pasando (100%)

**Componentes creados:**
1. `message_console_sender.py` - Mensajes de consola
2. `message_audio_sender.py` - Música y sonidos
3. `message_visual_effects_sender.py` - Efectos visuales
4. `message_player_stats_sender.py` - Stats del jugador
5. `message_character_sender.py` - Personajes y NPCs
6. `message_inventory_sender.py` - Inventario, banco, comercio
7. `message_map_sender.py` - Mapa y objetos
8. `message_session_sender.py` - Login y sesión

**Documentación:**
- Ver `docs/REFACTOR_MSG_COMPLETED.md` para detalles completos
- Ver memorias del sistema para historial de migración

**Nota importante:**
⚠️ `send_error_msg()` usa CONSOLE_MSG (24) en lugar de ERROR_MSG (55). Esto debe revertirse cuando se actualice el cliente Godot.

---

## 🔄 Otras Mejoras Pendientes

### 3. NPC Factory Pattern

**Estado:** 📝 Diseño propuesto - Pendiente implementación

Crear factory methods para encapsular creación de NPCs y evitar duplicación.

**Documentación:** Ver `docs/TODO_NPC_FACTORY.md`

**Beneficios:**
- DRY: No duplicar código entre criaturas similares
- Type-safe: Métodos tipados que retornan `NPC`
- Efectos visuales integrados (fx, fx_loop)
- Centralizado: Un solo lugar para crear NPCs

**Prioridad:** Media  
**Esfuerzo:** 3-4 horas

---

### 4. Service Container / Dependency Injection

**Estado:** 📝 Propuesta pendiente

Mejorar la creación de tasks con dependencias usando un contenedor de servicios.

**Documentación:** Ver `docs/TODO_ARQUITECTURA.md` (pendiente crear)

**Prioridad:** Baja  
**Esfuerzo:** 4-6 horas

---

### 5. Validación de Packets

**Estado:** 📝 Pendiente

Agregar validación de longitud de packets antes de parsear para evitar errores de índice fuera de rango.

**Implementación sugerida:**
```python
class PacketReader:
    def validate_length(self, expected: int) -> bool:
        return len(self.data) >= self.offset + expected
```

**Prioridad:** Media  
**Esfuerzo:** 1-2 horas

---

### 6. Logging Estructurado

**Estado:** 📝 Pendiente

Considerar usar logging estructurado (JSON) para facilitar análisis de logs en producción.

**Opciones:**
- `structlog` - Logging estructurado para Python
- `python-json-logger` - JSON formatter para logging estándar

**Prioridad:** Baja  
**Esfuerzo:** 2-3 horas

---

---

## 📊 Resumen de Estado

### Completadas ✅
1. **PacketReader** - 3/9 tasks refactorizadas (33%)
2. **MessageSender Refactoring** - 100% completado

### En Progreso 🔄
1. **PacketReader** - 6 tasks pendientes de refactorizar

### Pendientes 📝
1. **NPC Factory** - Diseño completo, pendiente implementación
2. **Service Container** - Propuesta pendiente
3. **Validación de Packets** - Mejora de robustez
4. **Logging Estructurado** - Mejora de observabilidad

---

**Última actualización:** 2025-01-19  
**Autor:** Actualizado con estado actual del proyecto  
**Estado:** 🔄 En progreso - 2/6 mejoras completadas
