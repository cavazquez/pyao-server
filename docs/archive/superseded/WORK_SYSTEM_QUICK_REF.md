# Sistema de Trabajo - Referencia Rápida

## 🎯 Diagrama de Secuencia

```
JUGADOR          CLIENTE GODOT        SERVIDOR PYTHON
   |                   |                      |
   | 1. Equipar caña   |                      |
   |------------------>|                      |
   |                   |                      |
   | 2. Presionar U    |                      |
   |------------------>|                      |
   |                   | USE_ITEM (30)        |
   |                   |--------------------->|
   |                   |                      | 3. Validar herramienta equipada
   |                   |                      |
   |                   | MULTI_MESSAGE (104)  |
   |                   |  - Index: 17         |
   |                   |  - Skill: 12 (Pesca) |
   |                   |<---------------------|
   |                   |                      |
   | 4. Cursor = 🎣    |                      |
   |<------------------|                      |
   |                   |                      |
   | 5. Click en agua  |                      |
   |------------------>|                      |
   |                   | WORK_LEFT_CLICK (33) |
   |                   |  - X: 9, Y: 39       |
   |                   |  - Skill: 12         |
   |                   |--------------------->|
   |                   |                      | 6. Validar agua en (9,39)
   |                   |                      | 7. add_item(68, qty=2)
   |                   |                      |
   |                   | CONSOLE_MSG (24)     |
   |                   | "Has obtenido 2..."  |
   |                   |<---------------------|
   |                   |                      |
   |                   | CHANGE_INVENTORY(47) |
   |                   |  - Slot: 5           |
   |                   |  - Item: 68 x2       |
   |                   |<---------------------|
   |                   |                      |
   | 8. Muestra 🐟x2   |                      |
   |<------------------|                      |
```

---

## 📋 Checklist de Implementación

### ✅ Servidor

- [x] Descomentado `WORK_LEFT_CLICK = 33`
- [x] Descomentado `MULTI_MESSAGE = 104`
- [x] Creado `TaskWorkLeftClick` handler
- [x] Creado `WorkMessageSender`
- [x] Agregado al `packet_handlers.py`
- [x] Factory con dependencias correctas
- [x] `MapResourcesService` cargado al inicio (NO en cada task)
- [x] Envío de `CHANGE_INVENTORY_SLOT` después de `add_item`

### ✅ Validaciones

- [x] Herramienta está equipada
- [x] Herramienta está en inventario
- [x] Recurso existe en coordenadas
- [x] Espacio en inventario

---

## 🔑 Valores Clave

```python
# ⚠️ NO CONFUNDIR ESTOS VALORES

# Packets
USE_ITEM = 30
WORK_LEFT_CLICK = 33
MULTI_MESSAGE = 104

# Mensaje dentro de MULTI_MESSAGE
WORK_REQUEST_TARGET_MSG = 17  # NO 18!

# Skills (según cliente)
SKILL_TALAR = 9     # NO 1
SKILL_PESCA = 12    # NO 3
SKILL_MINERIA = 13  # NO 2

# Herramientas
HACHA = 561
PICO = 562
CANA = 563

# Recursos
LENA = 58
PESCADO = 68
MINERAL = 70
```

---

## 💡 Snippet de Código

### Enviar WorkRequestTarget

```python
# ✅ CORRECTO
packet = struct.pack(
    "<BBB",
    ServerPacketID.MULTI_MESSAGE,  # 104
    WORK_REQUEST_TARGET_MSG,        # 17
    skill_type,                     # 9, 12 o 13
)

# ❌ INCORRECTO (crashea el cliente)
packet = struct.pack("<BB", 46, skill_type)
```

### Actualizar Inventario UI

```python
# Después de add_item, SIEMPRE:
slots = await inventory_repo.add_item(user_id, item_id, qty)
if slots:
    slot = slots[0][0]
    item = get_item(item_id)
    slot_data = await inventory_repo.get_slot(user_id, slot)
    total_qty = slot_data[1]
    
    # 🔥 CRÍTICO: Sin esto, UI no actualiza
    await message_sender.send_change_inventory_slot(
        slot=slot,
        item_id=item.item_id,
        name=item.name,
        amount=total_qty,
        # ... resto de campos
    )
```

---

## 🐛 Debugging

### Logs Esperados (Pesca exitosa)

```
INFO - user_id 1 hace click en slot 9
INFO - user_id 1 - Slot 9: Caña de pescar (Newbie) x1
INFO - Cursor cambiado a modo trabajo: skill_type=12
INFO - Usuario 1 hace WORK_LEFT_CLICK en (9, 39) con skill=12
INFO - Usuario 1 obtuvo 2 Pescado (item_id=68, slot=5)
```

### Cliente Crashea?

**Error:** "GetCharacterName in base Nil"
→ **Fix:** Cambiar índice de 18 a 17

**Error:** "Out of bounds get index '3'"
→ **Fix:** Usar skills 9, 12, 13 (no 1, 2, 3)

### Cursor No Cambia?

→ Verificar que envías MULTI_MESSAGE (104), no packet 46
→ Verificar índice del mensaje es 17
→ Verificar herramienta está equipada
→ **Nuevo 2025-11-13:** `USE_ITEM` valida herramienta equipada con `EquipmentRepository` antes de enviar WorkRequestTarget
→ **Nuevo 2025-11-13:** WORK_LEFT_CLICK requiere estar a distancia 1 del recurso (chequeo max(|Δx|,|Δy|) ≤ 1)

### Inventario No Actualiza?

→ Verificar envío de CHANGE_INVENTORY_SLOT
→ Verificar que usas el slot correcto del resultado de add_item

---

## 📊 Testing Rápido

```bash
# 1. Iniciar servidor
uv run python -m src.main

# 2. Logs a buscar:
✓ Servicio de recursos de mapas inicializado
✓ 290 mapas cargados

# 3. En el juego:
- Equipar caña (doble click)
- Presionar U
- ¿Cursor cambia? ✅
- Click en agua
- ¿Aparece pescado? ✅
- ¿Inventario actualiza? ✅
```

---

## 📚 Docs Relacionados

- **Documentación completa:** `docs/guides/WORK_SYSTEM.md`
- **Optimización de recursos:** `docs/MAP_RESOURCES_OPTIMIZATION.md`
- **Items y armaduras:** `docs/systems/ARMOR_SETS.md`

---

**Última actualización:** 21 de octubre, 2025
