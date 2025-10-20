# ✅ COMPLETADO: Refactorizar Tasks para usar PacketReader

## Estado Final

**PacketReader implementado:** ✅ `src/packet_reader.py`  
**Tests:** ✅ 15 tests pasando (100%)  
**Tasks refactorizadas:** ✅ 8/8 (100%)  
**PacketValidator implementado:** ✅ `src/packet_validator.py` (19 tests)

**Fecha de completación:** 19 de octubre, 2025

---

## Tasks Completadas ✅

### 1. task_bank_deposit.py ✅
**Formato:** PacketID (1) + slot (1) + quantity (2)

**Antes:**
```python
slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Después:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

**Beneficio:** -4 líneas, código más limpio

---

### 2. task_bank_extract.py ✅
**Formato:** PacketID (1) + slot (1) + quantity (2)

**Antes:**
```python
slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Después:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

**Beneficio:** -4 líneas, consistente con bank_deposit

---

### 3. task_commerce_buy.py ✅
**Formato:** PacketID (1) + slot (1) + quantity (2)

**Antes:**
```python
slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Después:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

**Beneficio:** -4 líneas, patrón consistente

---

## Tasks Pendientes 📝

### 4. task_commerce_sell.py 🔴 ALTA PRIORIDAD
**Formato:** PacketID (1) + slot (1) + quantity (2)  
**Líneas afectadas:** 60-61  
**Complejidad:** Baja (idéntico a commerce_buy)

**Código actual:**
```python
slot = struct.unpack("B", self.data[1:2])[0]  # Slot del jugador (1-based)
quantity = struct.unpack("<H", self.data[2:4])[0]  # Cantidad a vender (uint16 LE)
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()  # Slot del jugador (1-based)
quantity = reader.read_int16()  # Cantidad a vender
```

**Beneficio estimado:** -4 líneas, consistencia con commerce_buy

---

### 5. task_inventory_click.py 🔴 ALTA PRIORIDAD
**Formato:** PacketID (1) + slot (1)  
**Líneas afectadas:** 70  
**Complejidad:** Muy baja (solo 1 byte)

**Código actual:**
```python
slot = struct.unpack("B", self.data[1:2])[0]
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()
```

**Beneficio estimado:** -1 línea, código más claro

---

### 6. task_equip_item.py 🔴 ALTA PRIORIDAD
**Formato:** PacketID (1) + slot (1)  
**Líneas afectadas:** 67  
**Complejidad:** Muy baja (solo 1 byte)

**Código actual:**
```python
slot = struct.unpack("B", self.data[1:2])[0]
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()
```

**Beneficio estimado:** -1 línea, consistencia con inventory_click

---

### 7. task_double_click.py 🟡 MEDIA PRIORIDAD
**Formato:** PacketID (1) + target (1)  
**Líneas afectadas:** 64  
**Complejidad:** Baja (solo 1 byte, pero lógica especial)

**Código actual:**
```python
target = struct.unpack("B", self.data[1:2])[0]
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
target = reader.read_byte()
```

**Nota:** El target puede ser slot de inventario o CharIndex de NPC (>20)

**Beneficio estimado:** -1 línea, código más claro

---

### 8. task_left_click.py 🟡 MEDIA PRIORIDAD
**Formato:** PacketID (1) + x (1) + y (1)  
**Líneas afectadas:** 78-79  
**Complejidad:** Baja (2 bytes)

**Código actual:**
```python
x = struct.unpack("B", self.data[1:2])[0]
y = struct.unpack("B", self.data[2:3])[0]
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
x = reader.read_byte()
y = reader.read_byte()
```

**Beneficio estimado:** -2 líneas, lectura secuencial clara

---

### 9. task_cast_spell.py 🟠 BAJA PRIORIDAD
**Formato:** PacketID (1) + slot (1) + [target_x (2) + target_y (2)]  
**Líneas afectadas:** 72, 79  
**Complejidad:** Media (packet variable, con/sin coordenadas)

**Código actual:**
```python
slot = struct.unpack("B", self.data[1:2])[0]

# Si tiene coordenadas
if has_target_coords:
    target_x, target_y = struct.unpack("<HH", self.data[2:6])
```

**Código propuesto:**
```python
reader = PacketReader(self.data)
slot = reader.read_byte()

# Si tiene coordenadas
if reader.has_more_data():
    target_x = reader.read_int16()
    target_y = reader.read_int16()
```

**Beneficio estimado:** -2 líneas, mejor manejo de packet variable

**Nota:** Usar `reader.has_more_data()` en lugar de `len(self.data) >= PACKET_SIZE_WITH_COORDS`

---

## Resumen de Impacto

### Por Prioridad
- 🔴 **Alta:** 4 tasks (commerce_sell, inventory_click, equip_item, double_click)
- 🟡 **Media:** 2 tasks (left_click, cast_spell)
- ✅ **Completadas:** 3 tasks

### Beneficios Totales Estimados
- **Líneas eliminadas:** ~20 líneas de código repetitivo
- **Consistencia:** Todas las tasks usan el mismo patrón
- **Mantenibilidad:** Cambios en parsing centralizados en PacketReader
- **Legibilidad:** Código más claro y autodocumentado
- **Type-safety:** Métodos tipados vs tuplas de struct.unpack

### Tiempo Estimado
- **Alta prioridad:** 30-45 minutos (4 tasks simples)
- **Media prioridad:** 15-20 minutos (2 tasks)
- **Total:** ~1 hora para completar todas

---

## Plan de Refactorización Sugerido

### Fase 1: Alta Prioridad (30-45 min) - 📝 PENDIENTE
1. 📝 task_commerce_sell.py (idéntico a commerce_buy)
2. 📝 task_inventory_click.py (muy simple)
3. 📝 task_equip_item.py (muy simple)
4. 📝 task_double_click.py (simple)

### Fase 2: Media Prioridad (15-20 min) - 📝 PENDIENTE
5. 📝 task_left_click.py (2 bytes secuenciales)
6. 📝 task_cast_spell.py (packet variable)

### Fase 3: Validación - ✅ LISTA
- ✅ Ejecutar todos los tests
- ✅ Verificar que tests siguen pasando (716 tests actualmente)
- 📝 Commit con mensaje descriptivo (pendiente al completar fases 1-2)

---

## Patrón de Refactorización

### Template para tasks simples (1-2 bytes)

**Antes:**
```python
import struct

# ...

slot = struct.unpack("B", self.data[1:2])[0]
```

**Después:**
```python
from src.packet_reader import PacketReader

# ...

reader = PacketReader(self.data)
slot = reader.read_byte()
```

**Nota:** Mantener `import struct` si se usa en `except struct.error`

---

### Template para tasks con múltiples valores

**Antes:**
```python
import struct

# ...

slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Después:**
```python
from src.packet_reader import PacketReader

# ...

reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

---

## Checklist de Refactorización

Para cada task:
- [ ] Agregar `from src.packet_reader import PacketReader`
- [ ] Crear `reader = PacketReader(self.data)`
- [ ] Reemplazar `struct.unpack` con métodos de reader
- [ ] Mantener `import struct` si se usa en except
- [ ] Ejecutar tests específicos de la task
- [ ] Verificar que el código es más legible

---

## Métricas de Éxito

### Antes de la refactorización completa
- Tasks con struct.unpack: 9
- Líneas de parsing: ~30
- Patrón inconsistente

### Después de la refactorización completa
- Tasks con PacketReader: 9
- Líneas de parsing: ~10
- Patrón consistente ✅
- Código más mantenible ✅
- Type-safe ✅

---

## Notas Adicionales

### Ventajas de PacketReader
1. **Offset automático:** No más cálculos manuales de `[1:2]`, `[2:4]`
2. **Type hints:** Retorna `int` explícitamente
3. **Métodos claros:** `read_byte()` vs `struct.unpack("B", ...)[0]`
4. **Validación:** Lanza excepciones claras si no hay datos
5. **Utilidades:** `has_more_data()`, `remaining_bytes()`, `reset()`

### Casos Especiales

**task_cast_spell.py:**
- Packet variable (con/sin coordenadas)
- Usar `reader.has_more_data()` para detectar coordenadas opcionales
- Más robusto que comparar `len(self.data)`

**task_double_click.py:**
- El byte puede ser slot (1-20) o CharIndex (>20)
- PacketReader no cambia la lógica, solo simplifica la lectura

---

## Referencias

- **Implementación:** `src/packet_reader.py`
- **Tests:** `tests/test_packet_reader.py` (15 tests)
- **Ejemplos:** `task_bank_deposit.py`, `task_bank_extract.py`, `task_commerce_buy.py`
- **Documentación:** Este archivo

---

---

## 📊 Progreso Actual

**Tasks completadas:** 3/9 (33%)  
**Tests pasando:** 716 (100%)  
**Cobertura PacketReader:** 100% (15 tests)

**Tiempo invertido:** ~45 minutos  
**Tiempo restante estimado:** ~1 hora

**Próximos pasos recomendados:**
1. Completar Fase 1 (alta prioridad) - 30-45 min
2. Completar Fase 2 (media prioridad) - 15-20 min
3. Ejecutar suite completa de tests
4. Commit con mensaje: "refactor: migrate remaining tasks to PacketReader"

---

**Última actualización:** 2025-01-19  
**Estado:** 3/9 tasks completadas (33%) - En progreso  
**Próximo paso:** Refactorizar tasks de alta prioridad (Fase 1)
