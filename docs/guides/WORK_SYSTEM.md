> **Última consolidación:** 2026-05

# Protocolo del Sistema de Trabajo (Pesca, Tala, Minería)

**Fecha:** 21 de octubre, 2025  
**Versión:** 0.6.0-alpha  
**Estado:** ✅ COMPLETAMENTE FUNCIONAL

## Resumen

Este documento describe el protocolo completo para el sistema de trabajo con herramientas en Argentum Online, incluyendo pesca, tala y minería. El protocolo fue descubierto mediante análisis del cliente Godot y el servidor VB6 original.

---

## Flujo Completo del Jugador

```
1. Equipar herramienta (caña/hacha/pico)
   ↓
2. Presionar tecla U en el slot de la herramienta
   ↓
3. Servidor envía MULTI_MESSAGE.WorkRequestTarget
   ↓
4. Cliente cambia cursor a modo trabajo
   ↓
5. Jugador hace click en recurso (agua/árbol/mina)
   ↓
6. Cliente envía WORK_LEFT_CLICK con coordenadas
   ↓
7. Servidor valida recurso y herramienta
   ↓
8. Servidor agrega item al inventario
   ↓
9. Servidor envía CHANGE_INVENTORY_SLOT para actualizar UI
   ↓
10. Cliente muestra item en inventario automáticamente
```

---

## 📡 Protocolo de Red

### 1. Cliente → Servidor: USE_ITEM (Presionar U)

**PacketID:** `30` (ClientPacketID.USE_ITEM)

**Formato:**
```
Byte 0: PacketID = 30
Byte 1: Slot del inventario (1-based)
```

**Cuándo se envía:**
- Al presionar tecla U en un slot del inventario
- El slot debe estar seleccionado visualmente en el cliente

**Comportamiento del servidor:**
- Si el slot contiene una herramienta (IDs: 561, 562, 563)
- Verifica en `EquipmentRepository` que la herramienta esté equipada
- Si **está equipada** → Envía `WorkRequestTarget` (skill 9/12/13) para cambiar el cursor
- Si **NO está equipada** → Envía mensaje de consola: "Debes tener equipada la herramienta para trabajar"
- Si la herramienta no tiene comportamiento (no está equipada) loguea `Item sin comportamiento definido`
- Verifica que el tile clickeado esté a **distancia 1** del jugador; en caso contrario envía
  "Debes estar a un tile de distancia para trabajar" y no entrega recursos

---

### 2. Servidor → Cliente: MULTI_MESSAGE.WorkRequestTarget

**PacketID:** `104` (ServerPacketID.MULTI_MESSAGE)

**Formato:**
```
Byte 0: PacketID = 104 (MULTI_MESSAGE)
Byte 1: Message Index = 17 (WorkRequestTarget)
Byte 2: Skill Type (ver tabla abajo)
```

**⚠️ IMPORTANTE - Descubrimientos Clave:**

1. **NO usar packet 46 directamente** - WorkRequestTarget debe ir dentro de MULTI_MESSAGE
2. **Índice del mensaje es 17** (no 18) - Basado en `enum Messages` del cliente Godot
3. **Skills correctos:**
   - `9` = Talar (no 1)
   - `12` = Pesca (no 3)
   - `13` = Minería (no 2)

**Tabla de Skills (según cliente Godot):**
```gdscript
enum Skill {
    None = 0,
    Magia = 1,
    Robar = 2,
    // ...
    Talar = 9,          ← Hacha
    // ...
    Pesca = 12,         ← Caña
    Mineria = 13,       ← Pico
    // ...
}
```

**Mapeo de Herramientas a Skills:**
```python
work_tools = {
    561: 9,   # Hacha de Leñador → Talar (Skill.Talar)
    562: 13,  # Piquete de Minero → Minería (Skill.Mineria)
    563: 12,  # Caña de pescar → Pesca (Skill.Pesca)
}
```

**Efecto en el cliente:**
```gdscript
Enums.Messages.WorkRequestTarget:
    _gameContext.usingSkill = p.arg1  # Guarda el skill activo
    _gameInput.ShowConsoleMessage(...)  # Muestra mensaje
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE  # Mouse visible
```

---

### 3. Cliente → Servidor: WORK_LEFT_CLICK

**PacketID:** `33` (ClientPacketID.WORK_LEFT_CLICK)

**Formato:**
```
Byte 0: PacketID = 33
Byte 1: X (coordenada del click)
Byte 2: Y (coordenada del click)
Byte 3: Skill Type (9, 12 o 13)
```

**Cuándo se envía:**
- Cuando el jugador hace click en el mapa estando en modo trabajo
- El cliente envía las coordenadas exactas del click

**⚠️ Diferencia con WORK (packet 28):**
- `WORK` (28): Usa dirección del jugador (heading)
- `WORK_LEFT_CLICK` (33): Usa coordenadas del click ← **El cliente Godot usa este**

---

### 4. Servidor → Cliente: CONSOLE_MSG (Confirmación)

**PacketID:** `24` (ServerPacketID.CONSOLE_MSG)

**Mensajes:**
```python
# Éxito
"Has obtenido {cantidad} {recurso}"
# Ejemplos:
"Has obtenido 2 Pescado"
"Has obtenido 5 Leña"
"Has obtenido 3 Mineral de Hierro"

# Error
"No hay nada para trabajar en esa posición"
"Necesitas una herramienta (hacha, pico o caña de pescar)"
```

---

### 5. Servidor → Cliente: CHANGE_INVENTORY_SLOT

**PacketID:** `47` (ServerPacketID.CHANGE_INVENTORY_SLOT)

**Formato:**
```python
struct.pack(
    "<BBHH",
    47,                    # PacketID
    slot,                  # Slot del inventario (1-20)
    item.item_id,          # ID del item
    len(item.name) * 2,    # Longitud del nombre (UTF-16)
)
# ... + nombre (UTF-16LE)
# ... + cantidad, equipped, grh_id, etc.
```

**⚠️ CRÍTICO:**
- **SIEMPRE enviar este packet después de agregar items**
- Sin este packet, el cliente NO actualiza la UI del inventario
- El jugador no verá el item hasta cerrar/abrir el inventario

**Implementación:**
```python
# Después de add_item()
slots = await self.inventory_repo.add_item(user_id, item_id=68, quantity=2)
if slots:
    slot = slots[0][0]  # Obtener slot donde se agregó
    await self._update_inventory_ui(user_id, item_id, slot)
```

---

## 🛠️ Validaciones del Servidor

### 1. Validar Herramienta Equipada

```python
# En TaskInventoryClick (cuando presiona U)
if item_id in work_tools:
    if is_equipped:
        skill_type = work_tools[item_id]
        await self.message_sender.send_work_request_target(skill_type)
    else:
        await self.message_sender.send_console_msg(
            "Debes tener equipada la herramienta para trabajar."
        )
```

### 2. Validar Herramienta en Inventario

```python
# En TaskWorkLeftClick (cuando hace click en modo trabajo)
has_hacha = any(slot.item_id == 561 for slot in inventory.values())
has_pico = any(slot.item_id == 562 for slot in inventory.values())
has_cana = any(slot.item_id == 563 for slot in inventory.values())
```

### 3. Validar Recurso en Coordenadas

```python
# Verificar si hay recurso en las coordenadas exactas del click
if skill_type == SKILL_TALAR:
    if self.map_resources.has_tree(map_id, target_x, target_y):
        # Otorgar leña
        
if skill_type == SKILL_PESCA:
    if self.map_resources.has_water(map_id, target_x, target_y):
        # Otorgar pescado
        
if skill_type == SKILL_MINERIA:
    if self.map_resources.has_mine(map_id, target_x, target_y):
        # Otorgar mineral
```

---

## 📊 Recursos y Recompensas

| Skill | Tool ID | Tool Name | Recurso | Item ID | Cantidad |
|-------|---------|-----------|---------|---------|----------|
| 9 (Talar) | 561 | Hacha de Leñador | Leña | 58 | 5 |
| 12 (Pesca) | 563 | Caña de pescar | Pescado | 68 | 2 |
| 13 (Minería) | 562 | Piquete de Minero | Mineral de Hierro | 70 | 3 |

---

## 🐛 Errores Comunes y Soluciones

### Error 1: Cliente crashea con "GetCharacterName in base Nil"

**Causa:** Índice de mensaje incorrecto (18 en vez de 17)

**Solución:**
```python
WORK_REQUEST_TARGET_MSG = 17  # No 18!
```

### Error 2: Cliente crashea con "Out of bounds get index '3'"

**Causa:** Skill type incorrecto (usando 1, 2, 3 en vez de 9, 12, 13)

**Solución:**
```python
work_tools = {
    561: 9,   # Talar (no 1)
    562: 13,  # Minería (no 2)
    563: 12,  # Pesca (no 3)
}
```

### Error 3: El cursor no cambia a modo trabajo

**Causa:** Enviando packet 46 directamente en vez de MULTI_MESSAGE

**Solución:**
```python
# ❌ MAL
packet = struct.pack("<BB", 46, skill_type)

# ✅ BIEN
packet = struct.pack("<BBB", 104, 17, skill_type)
#                      ^    ^   ^
#                      |    |   skill_type
#                      |    WorkRequestTarget index
#                      MULTI_MESSAGE
```

### Error 4: Inventario no se actualiza después de pescar/talar

**Causa:** No enviar CHANGE_INVENTORY_SLOT después de add_item

**Solución:**
```python
slots = await self.inventory_repo.add_item(user_id, item_id, quantity)
if slots:
    slot = slots[0][0]
    # ✅ CRÍTICO: Actualizar UI del cliente
    await self._update_inventory_ui(user_id, item_id, slot)
```

---

## 📁 Archivos Implementados

### Nuevos Archivos

1. **`src/task_work_left_click.py`** (237 líneas)
   - Handler principal de trabajo con coordenadas
   - Validación de herramientas y recursos
   - Actualización de inventario

2. **`src/message_work_sender.py`** (49 líneas)
   - Envío de MULTI_MESSAGE.WorkRequestTarget
   - Constantes de skills

### Archivos Modificados

1. **`src/packet_id.py`**
   - `WORK_LEFT_CLICK = 33`
   - `MULTI_MESSAGE = 104`

2. **`src/task_inventory_click.py`**
   - Detección de herramientas equipadas
   - Envío de WorkRequestTarget

3. **`src/message_sender.py`**
   - Integración de WorkMessageSender

4. **`src/packet_handlers.py`**
   - Mapeo de WORK_LEFT_CLICK → TaskWorkLeftClick

5. **`src/task_factory.py`**
   - Factory para TaskWorkLeftClick con dependencias

---

## 🔬 Cómo Descubrimos el Protocolo

### 1. Análisis del Cliente Godot

**Archivo:** `clientes/ArgentumOnlineGodot/engine/autoload/game_protocol.gd`

```gdscript
static func WriteWorkLeftClick(x:int, y:int, skill:int) -> void:
    _writer.put_u8(Enums.ClientPacketID.WorkLeftClick)  # 33
    _writer.put_u8(x)
    _writer.put_u8(y)
    _writer.put_u8(skill)
```

**Descubrimiento:** Cliente usa WORK_LEFT_CLICK (33), no WORK (28)

---

### 2. Análisis del Servidor VB6

**Archivo:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/InvUsuario.bas`

```vb
' Lo tiene equipado?
If .Invent.WeaponEqpObjIndex = ObjIndex Then
    Call WriteMultiMessage(UserIndex, eMessages.WorkRequestTarget, eSkill.Pesca)
Else
    Call WriteConsoleMsg(UserIndex, "Debes tener equipada la herramienta...")
End If
```

**Descubrimiento:** VB6 usa `WriteMultiMessage`, no packet separado

---

### 3. Análisis de Enums del Cliente

**Archivo:** `clientes/ArgentumOnlineGodot/common/enums/enums.gd`

```gdscript
enum Messages {
    DontSeeAnything,      // 0
    NPCSwing,             // 1
    // ...
    UserHittedUser,       // 16
    WorkRequestTarget,    // 17 ← ÍNDICE CORRECTO
    HaveKilledUser,       // 18
    // ...
}

enum Skill {
    None = 0,
    Magia = 1,
    Robar = 2,
    // ...
    Talar = 9,      ← SKILL CORRECTO
    // ...
    Pesca = 12,     ← SKILL CORRECTO
    Mineria = 13,   ← SKILL CORRECTO
}
```

**Descubrimiento:** Índices y valores correctos de enums

---

### 4. Análisis del Handler de Mensajes

**Archivo:** `clientes/ArgentumOnlineGodot/network/commands/MultiMessage.gd`

```gdscript
Enums.Messages.WorkRequestTarget:
    arg1 = reader.get_u8()  # Lee skill_type como 1 byte
```

**Descubrimiento:** Formato exacto del mensaje

---

## 🎯 Tests

**Archivo:** Tests manuales realizados

1. ✅ Equipar caña → Presionar U → Cursor cambia a modo pesca
2. ✅ Click en agua → Obtiene 2 pescados
3. ✅ Inventario se actualiza automáticamente
4. ✅ Click sin agua → Mensaje de error
5. ✅ Presionar U sin equipar → Mensaje de error
6. ✅ Talar árbol → Obtiene 5 leña
7. ✅ Minar → Obtiene 3 mineral de hierro

---

## 📝 Notas de Implementación

### Orden de Envío de Packets

```python
# 1. Mensaje de consola
await self.message_sender.console.send_console_msg(f"Has obtenido {qty} {name}")

# 2. Actualizar inventario en Redis
slots = await self.inventory_repo.add_item(user_id, item_id, quantity)

# 3. CRÍTICO: Actualizar UI del cliente
await self.message_sender.send_change_inventory_slot(...)
```

### MapResourcesService

```python
# Cargado UNA SOLA VEZ al inicio del servidor
# NO instanciar en cada task (causaría lag)
# Lee *_blocked.json y detecta agua/árboles/minas + tiles bloqueados
map_resources_service = MapResourcesService()  # En ServiceInitializer
```

### Constantes Importantes

```python
# IDs de Herramientas
HACHA_LENADOR = 561
PIQUETE_MINERO = 562
CANA_PESCAR = 563

# Skills (enum Skill del cliente)
SKILL_TALAR = 9
SKILL_PESCA = 12
SKILL_MINERIA = 13

# IDs de Recursos
LENA = 58
PESCADO = 68
MINERAL_HIERRO = 70

# Mensaje WorkRequestTarget
WORK_REQUEST_TARGET_MSG = 17  # En MULTI_MESSAGE
```

---

## 🚀 Próximas Mejoras Sugeridas

1. **Cooldown entre trabajos** - Evitar spam de clicks
2. **Experiencia de skills** - Subir nivel de Talar/Pesca/Minería
3. **Fallos aleatorios** - No siempre obtener recurso
4. **Consumo de stamina** - Cada acción consume energía
5. **Animaciones** - Mostrar animación de trabajo en el cliente
6. **Sonidos** - Efectos de sonido al trabajar
7. **Recursos agotables** - Árboles/minas que se agotan temporalmente
8. **Herramientas con durabilidad** - Se desgastan con el uso

---

## 📚 Referencias

- Cliente Godot: `clientes/ArgentumOnlineGodot/`
- Servidor VB6: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/`
- Protocolo AO: Basado en Argentum Online 0.13.3

---

**Documento creado el:** 21 de octubre, 2025  
**Autor:** Sistema de IA colaborativo  
**Estado:** ✅ COMPLETADO Y VERIFICADO

---

## Referencia rápida: WORK_SYSTEM_PROTOCOL.md

> Documento fuente archivado en [`archive/superseded/WORK_SYSTEM_PROTOCOL.md`](../archive/superseded/WORK_SYSTEM_PROTOCOL.md).

**Fecha:** 21 de octubre, 2025  
**Versión:** 0.6.0-alpha  
**Estado:** ✅ COMPLETAMENTE FUNCIONAL

## Resumen

Este documento describe el protocolo completo para el sistema de trabajo con herramientas en Argentum Online, incluyendo pesca, tala y minería. El protocolo fue descubierto mediante análisis del cliente Godot y el servidor VB6 original.

---

## Flujo Completo del Jugador

```
1. Equipar herramienta (caña/hacha/pico)
   ↓
2. Presionar tecla U en el slot de la herramienta
   ↓
3. Servidor envía MULTI_MESSAGE.WorkRequestTarget
   ↓
4. Cliente cambia cursor a modo trabajo
   ↓
5. Jugador hace click en recurso (agua/árbol/mina)
   ↓
6. Cliente envía WORK_LEFT_CLICK con coordenadas
   ↓
7. Servidor valida recurso y herramienta
   ↓
8. Servidor agrega item al inventario
   ↓
9. Servidor envía CHANGE_INVENTORY_SLOT para actualizar UI
   ↓
10. Cliente muestra item en inventario automáticamente
```

---

## 📡 Protocolo de Red

### 1. Cliente → Servidor: USE_ITEM (Presionar U)

**PacketID:** `30` (ClientPacketID.USE_ITEM)

**Formato:**
```
Byte 0: PacketID = 30
Byte 1: Slot del inventario (1-based)
```

**Cuándo se envía:**
- Al presionar tecla U en un slot del inventario
- El slot debe estar seleccionado visualmente en el cliente

**Comportamiento del servidor:**
- Si el slot contiene una herramienta (IDs: 561, 562, 563)
- Verifica en `EquipmentRepository` que la herramienta esté equipada
- Si **está equipada** → Envía `WorkRequestTarget` (skill 9/12/13) para cambiar el cursor
- Si **NO está equipada** → Envía mensaje de consola: "Debes tener equipada la herramienta para trabajar"
- Si la herramienta no tiene comportamiento (no está equipada) loguea `Item sin comportamiento definido`
- Verifica que el tile clickeado esté a **distancia 1** del jugador; en caso contrario envía
  "Debes estar a un tile de distancia para trabajar" y no entrega recursos

---

### 2. Servidor → Cliente: MULTI_MESSAGE.WorkRequestTarget

**PacketID:** `104` (ServerPacketID.MULTI_MESSAGE)

**Formato:**
```
Byte 0: PacketID = 104 (MULTI_MESSAGE)
Byte 1: Message Index = 17 (WorkRequestTarget)
Byte 2: Skill Type (ver tabla abajo)
```

**⚠️ IMPORTANTE - Descubrimientos Clave:**

1. **NO usar packet 46 directamente** - WorkRequestTarget debe ir dentro de MULTI_MESSAGE
2. **Índice del mensaje es 17** (no 18) - Basado en `enum Messages` del cliente Godot
3. **Skills correctos:**
   - `9` = Talar (no 1)
   - `12` = Pesca (no 3)
   - `13` = Minería (no 2)

**Tabla de Skills (según cliente Godot):**
```gdscript
enum Skill {
    None = 0,
    Magia = 1,
    Robar = 2,
    // ...
    Talar = 9,          ← Hacha
    // ...
    Pesca = 12,         ← Caña
    Mineria = 13,       ← Pico
    // ...
}
```

**Mapeo de Herramientas a Skills:**
```python
work_tools = {
    561: 9,   # Hacha de Leñador → Talar (Skill.Talar)
    562: 13,  # Piquete de Minero → Minería (Skill.Mineria)
    563: 12,  # Caña de pescar → Pesca (Skill.Pesca)
}
```

**Efecto en el cliente:**
```gdscript
Enums.Messages.WorkRequestTarget:
    _gameContext.usingSkill = p.arg1  # Guarda el skill activo
    _gameInput.ShowConsoleMessage(...)  # Muestra mensaje
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE  # Mouse visible
```

---

### 3. Cliente → Servidor: WORK_LEFT_CLICK

**PacketID:** `33` (ClientPacketID.WORK_LEFT_CLICK)

**Formato:**
```
Byte 0: PacketID = 33
Byte 1: X (coordenada del click)
Byte 2: Y (coordenada del click)
Byte 3: Skill Type (9, 12 o 13)
```

**Cuándo se envía:**
- Cuando el jugador hace click en el mapa estando en modo trabajo
- El cliente envía las coordenadas exactas del click

**⚠️ Diferencia con WORK (packet 28):**
- `WORK` (28): Usa dirección del jugador (heading)
- `WORK_LEFT_CLICK` (33): Usa coordenadas del click ← **El cliente Godot usa este**

---

### 4. Servidor → Cliente: CONSOLE_MSG (Confirmación)

**PacketID:** `24` (ServerPacketID.CONSOLE_MSG)

**Mensajes:**
```python
# Éxito
"Has obtenido {cantidad} {recurso}"
# Ejemplos:
"Has obtenido 2 Pescado"
"Has obtenido 5 Leña"
"Has obtenido 3 Mineral de Hierro"

# Error
"No hay nada para trabajar en esa posición"
"Necesitas una herramienta (hacha, pico o caña de pescar)"
```

---

### 5. Servidor → Cliente: CHANGE_INVENTORY_SLOT

**PacketID:** `47` (ServerPacketID.CHANGE_INVENTORY_SLOT)

**Formato:**
```python
struct.pack(
    "<BBHH",
    47,                    # PacketID
    slot,                  # Slot del inventario (1-20)
    item.item_id,          # ID del item
    len(item.name) * 2,    # Longitud del nombre (UTF-16)
)
# ... + nombre (UTF-16LE)
# ... + cantidad, equipped, grh_id, etc.
```

**⚠️ CRÍTICO:**
- **SIEMPRE enviar este packet después de agregar items**
- Sin este packet, el cliente NO actualiza la UI del inventario
- El jugador no verá el item hasta cerrar/abrir el inventario

**Implementación:**
```python
# Después de add_item()
slots = await self.inventory_repo.add_item(user_id, item_id=68, quantity=2)
if slots:
    slot = slots[0][0]  # Obtener slot donde se agregó
    await self._update_inventory_ui(user_id, item_id, slot)
```

---

## 🛠️ Validaciones del Servidor

### 1. Validar Herramienta Equipada

```python
# En TaskInventoryClick (cuando presiona U)
if item_id in work_tools:
    if is_equipped:
        skill_type = work_tools[item_id]
        await self.message_sender.send_work_request_target(skill_type)
    else:
        await self.message_sender.send_console_msg(
            "Debes tener equipada la herramienta para trabajar."
        )
```

### 2. Validar Herramienta en Inventario

```python
# En TaskWorkLeftClick (cuando hace click en modo trabajo)
has_hacha = any(slot.item_id == 561 for slot in inventory.values())
has_pico = any(slot.item_id == 562 for slot in inventory.values())
has_cana = any(slot.item_id == 563 for slot in inventory.values())
```

### 3. Validar Recurso en Coordenadas

```python
# Verificar si hay recurso en las coordenadas exactas del click
if skill_type == SKILL_TALAR:
    if self.map_resources.has_tree(map_id, target_x, target_y):
        # Otorgar leña
        
if skill_type == SKILL_PESCA:
    if self.map_resources.has_water(map_id, target_x, target_y):
        # Otorgar pescado
        
if skill_type == SKILL_MINERIA:
    if self.map_resources.has_mine(map_id, target_x, target_y):
        # Otorgar mineral
```

---

## 📊 Recursos y Recompensas

| Skill | Tool ID | Tool Name | Recurso | Item ID | Cantidad |
|-------|---------|-----------|---------|---------|----------|
| 9 (Talar) | 561 | Hacha de Leñador | Leña | 58 | 5 |
| 12 (Pesca) | 563 | Caña de pescar | Pescado | 68 | 2 |
| 13 (Minería) | 562 | Piquete de Minero | Mineral de Hierro | 70 | 3 |

---

## 🐛 Errores Comunes y Soluciones

### Error 1: Cliente crashea con "GetCharacterName in base Nil"

**Causa:** Índice de mensaje incorrecto (18 en vez de 17)

**Solución:**
```python
WORK_REQUEST_TARGET_MSG = 17  # No 18!
```

### Error 2: Cliente crashea con "Out of bounds get index '3'"

**Causa:** Skill type incorrecto (usando 1, 2, 3 en vez de 9, 12, 13)

**Solución:**
```python
work_tools = {
    561: 9,   # Talar (no 1)
    562: 13,  # Minería (no 2)
    563: 12,  # Pesca (no 3)
}
```

### Error 3: El cursor no cambia a modo trabajo

**Causa:** Enviando packet 46 directamente en vez de MULTI_MESSAGE

**Solución:**
```python
# ❌ MAL
packet = struct.pack("<BB", 46, skill_type)

# ✅ BIEN
packet = struct.pack("<BBB", 104, 17, skill_type)
#                      ^    ^   ^
#                      |    |   skill_type
#                      |    WorkRequestTarget index
#                      MULTI_MESSAGE
```

### Error 4: Inventario no se actualiza después de pescar/talar

**Causa:** No enviar CHANGE_INVENTORY_SLOT después de add_item

**Solución:**
```python
slots = await self.inventory_repo.add_item(user_id, item_id, quantity)
if slots:
    slot = slots[0][0]
    # ✅ CRÍTICO: Actualizar UI del cliente
    await self._update_inventory_ui(user_id, item_id, slot)
```

---

## 📁 Archivos Implementados

### Nuevos Archivos

1. **`src/task_work_left_click.py`** (237 líneas)
   - Handler principal de trabajo con coordenadas
   - Validación de herramientas y recursos
   - Actualización de inventario

2. **`src/message_work_sender.py`** (49 líneas)
   - Envío de MULTI_MESSAGE.WorkRequestTarget
   - Constantes de skills

### Archivos Modificados

1. **`src/packet_id.py`**
   - `WORK_LEFT_CLICK = 33`
   - `MULTI_MESSAGE = 104`

2. **`src/task_inventory_click.py`**
   - Detección de herramientas equipadas
   - Envío de WorkRequestTarget

3. **`src/message_sender.py`**
   - Integración de WorkMessageSender

4. **`src/packet_handlers.py`**
   - Mapeo de WORK_LEFT_CLICK → TaskWorkLeftClick

5. **`src/task_factory.py`**
   - Factory para TaskWorkLeftClick con dependencias

---

## 🔬 Cómo Descubrimos el Protocolo

### 1. Análisis del Cliente Godot

**Archivo:** `clientes/ArgentumOnlineGodot/engine/autoload/game_protocol.gd`

```gdscript
static func WriteWorkLeftClick(x:int, y:int, skill:int) -> void:
    _writer.put_u8(Enums.ClientPacketID.WorkLeftClick)  # 33
    _writer.put_u8(x)
    _writer.put_u8(y)
    _writer.put_u8(skill)
```

**Descubrimiento:** Cliente usa WORK_LEFT_CLICK (33), no WORK (28)

---

### 2. Análisis del Servidor VB6

**Archivo:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/InvUsuario.bas`

```vb
' Lo tiene equipado?
If .Invent.WeaponEqpObjIndex = ObjIndex Then
    Call WriteMultiMessage(UserIndex, eMessages.WorkRequestTarget, eSkill.Pesca)
Else
    Call WriteConsoleMsg(UserIndex, "Debes tener equipada la herramienta...")
End If
```

**Descubrimiento:** VB6 usa `WriteMultiMessage`, no packet separado

---

### 3. Análisis de Enums del Cliente

**Archivo:** `clientes/ArgentumOnlineGodot/common/enums/enums.gd`

```gdscript
enum Messages {
    DontSeeAnything,      // 0
    NPCSwing,             // 1
    // ...
    UserHittedUser,       // 16
    WorkRequestTarget,    // 17 ← ÍNDICE CORRECTO
    HaveKilledUser,       // 18
    // ...
}

enum Skill {
    None = 0,
    Magia = 1,
    Robar = 2,
    // ...
    Talar = 9,      ← SKILL CORRECTO
    // ...
    Pesca = 12,     ← SKILL CORRECTO
    Mineria = 13,   ← SKILL CORRECTO
}
```

**Descubrimiento:** Índices y valores correctos de enums

---

### 4. Análisis del Handler de Mensajes

**Archivo:** `clientes/ArgentumOnlineGodot/network/commands/MultiMessage.gd`

```gdscript
Enums.Messages.WorkRequestTarget:
    arg1 = reader.get_u8()  # Lee skill_type como 1 byte
```

**Descubrimiento:** Formato exacto del mensaje

---

## 🎯 Tests

**Archivo:** Tests manuales realizados

1. ✅ Equipar caña → Presionar U → Cursor cambia a modo pesca
2. ✅ Click en agua → Obtiene 2 pescados
3. ✅ Inventario se actualiza automáticamente
4. ✅ Click sin agua → Mensaje de error
5. ✅ Presionar U sin equipar → Mensaje de error
6. ✅ Talar árbol → Obtiene 5 leña
7. ✅ Minar → Obtiene 3 mineral de hierro

---

## 📝 Notas de Implementación

### Orden de Envío de Packets

```python
# 1. Mensaje de consola
await self.message_sender.console.send_console_msg(f"Has obtenido {qty} {name}")

# 2. Actualizar inventario en Redis
slots = await self.inventory_repo.add_item(user_id, item_id, quantity)

# 3. CRÍTICO: Actualizar UI del cliente
await self.message_sender.send_change_inventory_slot(...)
```

### MapResourcesService

```python
# Cargado UNA SOLA VEZ al inicio del servidor
# NO instanciar en cada task (causaría lag)
# Lee *_blocked.json y detecta agua/árboles/minas + tiles bloqueados
map_resources_service = MapResourcesService()  # En ServiceInitializer
```

### Constantes Importantes

```python
# IDs de Herramientas
HACHA_LENADOR = 561
PIQUETE_MINERO = 562
CANA_PESCAR = 563

# Skills (enum Skill del cliente)
SKILL_TALAR = 9
SKILL_PESCA = 12
SKILL_MINERIA = 13

# IDs de Recursos
LENA = 58
PESCADO = 68
MINERAL_HIERRO = 70

# Mensaje WorkRequestTarget
WORK_REQUEST_TARGET_MSG = 17  # En MULTI_MESSAGE
```

---

## 🚀 Próximas Mejoras Sugeridas

1. **Cooldown entre trabajos** - Evitar spam de clicks
2. **Experiencia de skills** - Subir nivel de Talar/Pesca/Minería
3. **Fallos aleatorios** - No siempre obtener recurso
4. **Consumo de stamina** - Cada acción consume energía
5. **Animaciones** - Mostrar animación de trabajo en el cliente
6. **Sonidos** - Efectos de sonido al trabajar
7. **Recursos agotables** - Árboles/minas que se agotan temporalmente
8. **Herramientas con durabilidad** - Se desgastan con el uso

---

## 📚 Referencias

- Cliente Godot: `clientes/ArgentumOnlineGodot/`
- Servidor VB6: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/`
- Protocolo AO: Basado en Argentum Online 0.13.3

---

**Documento creado el:** 21 de octubre, 2025  
**Autor:** Sistema de IA colaborativo  
**Estado:** ✅ COMPLETADO Y VERIFICADO

## Referencia rápida: WORK_SYSTEM_QUICK_REF.md

> Documento fuente archivado en [`archive/superseded/WORK_SYSTEM_QUICK_REF.md`](../archive/superseded/WORK_SYSTEM_QUICK_REF.md).

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

