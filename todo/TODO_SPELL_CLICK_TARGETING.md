# TODO: Sistema de Click para Target de Hechizos

**Fecha:** 21 de octubre, 2025  
**Prioridad:** Media  
**Estado:** 📋 Pendiente de Implementación

---

## 📝 Descripción

Implementar un sistema de "click para seleccionar target" en hechizos, similar al sistema de trabajo (pesca, tala, minería) que ya está funcionando.

---

## 🎯 Objetivo

Permitir que el jugador haga click en el objetivo específico donde quiere lanzar el hechizo, en lugar de usar solamente su dirección (heading).

---

## 📊 Estado Actual

### Cliente Godot

**Archivo:** `ui/hub/spell_list_panel.gd` (líneas 27-28)

```gdscript
func _on_btn_cast_pressed() -> void:
    GameProtocol.WriteCastSpell(slot + 1)     # CAST_SPELL (25) - Solo slot (2 bytes)
    GameProtocol.WriteWork(Enums.Skill.Magia) # WORK (28) con skill=1 (Magia)
```

**Comportamiento:**
1. Jugador selecciona hechizo de la lista
2. Presiona botón "Cast"
3. Hechizo se lanza hacia donde está mirando (heading)

### Servidor

**Archivo:** `src/task_cast_spell.py`

El servidor **YA soporta dos formatos**:

1. **Formato antiguo (2 bytes):** `PacketID + Slot`
   - Usa heading del jugador
   - **← Esto es lo que usa el cliente actual**

2. **Formato nuevo (6 bytes):** `PacketID + Slot + X + Y`
   - Usa coordenadas exactas
   - **← YA IMPLEMENTADO pero no usado**

```python
# Líneas 102-108
has_target_coords = len(self.data) >= PACKET_SIZE_WITH_COORDS

if has_target_coords:
    target_x = reader.read_int16()
    target_y = reader.read_int16()
    # Lanza al target específico
```

---

## 🔄 Comparación con Sistema de Trabajo

| Aspecto | Sistema de Trabajo ✅ | Sistema de Hechizos ⏳ |
|---------|----------------------|----------------------|
| **Paso 1** | Equipar herramienta | Seleccionar hechizo |
| **Paso 2** | Presionar U → WORK_REQUEST_TARGET | Presionar "Cast" → ¿SPELL_REQUEST_TARGET? |
| **Paso 3** | Cursor cambia a modo trabajo | Cursor cambia a modo hechizo |
| **Paso 4** | Click en target → WORK_LEFT_CLICK(x,y) | Click en target → CAST_SPELL(x,y) |
| **Servidor** | TaskWorkLeftClick procesa | TaskCastSpell **ya soporta** |

---

## 📋 Implementación Propuesta

### Opción 1: Sistema Completo (Similar a Trabajo)

#### Cliente Godot

**1. Crear mensaje SpellRequestTarget en MULTI_MESSAGE**

Verificar si existe en `enum Messages` del cliente:
- Buscar índice correcto en `common/enums/enums.gd`
- Similar a `WorkRequestTarget` (índice 17)

**2. Modificar spell_list_panel.gd**

```gdscript
func _on_btn_cast_pressed() -> void:
    var slot = get_selected_slot()
    if slot == -1 || _item_list.get_item_text(slot) == "(None)": 
        return
    
    # Opción A: Enviar solo slot, esperar SpellRequestTarget del servidor
    GameProtocol.WriteCastSpell(slot + 1)
    
    # Opción B: Directamente activar modo targeting
    _gameContext.castingSpell = true
    _gameContext.castingSpellSlot = slot + 1
```

**3. Modificar game_screen.gd para manejar clicks**

```gdscript
# Cuando SpellRequestTarget llega del servidor
Enums.Messages.SpellRequestTarget:
    _gameContext.castingSpell = true
    _gameContext.castingSpellSlot = p.arg1
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
    
# Cuando usuario hace click en el mapa
if _gameContext.castingSpell:
    var spell_slot = _gameContext.castingSpellSlot
    var target_x = clicked_tile_x
    var target_y = clicked_tile_y
    GameProtocol.WriteCastSpellWithTarget(spell_slot, target_x, target_y)
    _gameContext.castingSpell = false
```

**4. Agregar WriteCastSpellWithTarget en game_protocol.gd**

```gdscript
static func WriteCastSpellWithTarget(slot:int, x:int, y:int) -> void:
    _log_outgoing_packet("CastSpellWithTarget", "slot: " + str(slot) + ", x: " + str(x) + ", y: " + str(y))
    _writer.put_u8(Enums.ClientPacketID.CastSpell)  # 25
    _writer.put_u8(slot)
    _writer.put_16(x)
    _writer.put_16(y)
```

#### Servidor

**1. Crear SpellRequestTarget en MULTI_MESSAGE**

```python
# src/message_work_sender.py (o crear message_spell_sender.py)
SPELL_REQUEST_TARGET_MSG = ???  # Buscar índice correcto

async def send_spell_request_target(self, spell_slot: int) -> None:
    packet = struct.pack(
        "<BBB",
        ServerPacketID.MULTI_MESSAGE,
        SPELL_REQUEST_TARGET_MSG,
        spell_slot,
    )
    await self.connection.send(packet)
```

**2. Modificar task_cast_spell.py**

```python
# Si packet es de 2 bytes (solo slot), enviar SpellRequestTarget
if len(self.data) == PACKET_SIZE_WITHOUT_COORDS:
    await self.message_sender.send_spell_request_target(slot)
    return  # Esperar que cliente envíe CAST_SPELL con coordenadas
```

---

### Opción 2: Simplificada (Sin SpellRequestTarget)

#### Cliente Godot

Modificar directamente el botón Cast para activar modo targeting sin round-trip al servidor:

```gdscript
func _on_btn_cast_pressed() -> void:
    var slot = get_selected_slot()
    if slot == -1: return
    
    # Activar modo targeting directamente
    _gameContext.castingSpell = true
    _gameContext.castingSpellSlot = slot + 1
    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
    
# En game_screen.gd, cuando hace click:
if _gameContext.castingSpell:
    GameProtocol.WriteCastSpellWithTarget(slot, x, y)
```

**Ventajas:** Más simple, menos latencia  
**Desventajas:** No valida en servidor antes de activar modo targeting

---

## 🔍 Investigación Necesaria

1. **Verificar enums del cliente:**
   - ¿Existe `SpellRequestTarget` en `enum Messages`?
   - Si no existe, ¿se puede agregar o usar mensaje existente?

2. **Verificar protocolo VB6:**
   - Buscar en `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/`
   - ¿Cómo manejaba el servidor original el targeting de hechizos?

3. **Revisar UI del cliente:**
   - ¿Hay algún modo de targeting ya implementado?
   - ¿Cómo se muestra visualmente cuando estás en modo targeting?

---

## ✅ Ventajas de Implementarlo

1. **Precisión:** Lanzar hechizos a tiles específicos, no solo en la dirección
2. **UX Mejorada:** Más intuitivo clickear el objetivo
3. **Consistencia:** Mismo patrón que trabajo (pesca, tala, minería)
4. **Rango Visual:** Jugador ve exactamente dónde caerá el hechizo
5. **Hechizos de Área:** Más útil para hechizos AoE (área de efecto)

---

## ⚠️ Consideraciones

1. **Compatibilidad:** ¿Mantener formato antiguo (heading) como fallback?
2. **Rango:** Validar que target esté dentro del rango del hechizo (ya implementado)
3. **Cursor:** Cambiar cursor visualmente cuando está en modo targeting
4. **Cancelar:** Permitir cancelar el targeting (ESC o click derecho)
5. **Mana:** No consumir mana hasta que se confirme el target

---

## 📁 Archivos a Modificar

### Cliente Godot (si existe localmente)

- `ui/hub/spell_list_panel.gd` - Lógica del botón Cast
- `screens/game_screen.gd` - Handler de clicks en modo targeting
- `engine/autoload/game_protocol.gd` - WriteCastSpellWithTarget
- `common/enums/enums.gd` - Verificar enums

### Servidor Python

- `src/message_work_sender.py` - O crear `message_spell_sender.py`
- `src/message_sender.py` - Integrar send_spell_request_target
- `src/task_cast_spell.py` - Modificar para enviar SpellRequestTarget
- `src/packet_id.py` - Verificar MULTI_MESSAGE activo

---

## 🎯 Criterios de Éxito

- [ ] Jugador puede clickear target específico para hechizos
- [ ] Cursor cambia visualmente al modo targeting
- [ ] Servidor valida rango antes de lanzar
- [ ] Funciona con todos los tipos de hechizos
- [ ] Se puede cancelar el targeting
- [ ] Formato antiguo (heading) sigue funcionando como fallback
- [ ] Logs claros de debugging
- [ ] Documentación actualizada

---

## 📚 Referencias

- **Sistema de Trabajo:** `docs/WORK_SYSTEM_PROTOCOL.md`
- **TaskCastSpell:** `src/task_cast_spell.py` (líneas 102-115)
- **Cliente Godot:** `clientes/ArgentumOnlineGodot/ui/hub/spell_list_panel.gd`
- **Protocolo MULTI_MESSAGE:** Ya documentado en sistema de trabajo

---

## 🚀 Próximos Pasos

1. Verificar si `SpellRequestTarget` existe en enums del cliente
2. Revisar código VB6 para ver implementación original
3. Decidir entre Opción 1 (completa) u Opción 2 (simplificada)
4. Implementar en cliente Godot (si tienes acceso)
5. Modificar servidor según sea necesario
6. Testing exhaustivo
7. Documentar protocolo similar a `WORK_SYSTEM_PROTOCOL.md`

---

**Nota:** El servidor **ya está preparado** para recibir coordenadas en CAST_SPELL. Solo falta modificar el cliente para enviarlas.
