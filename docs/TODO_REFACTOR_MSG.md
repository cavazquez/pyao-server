# TODO: Refactorizar msg.py

## 📋 Contexto

`msg.py` actualmente tiene **642 líneas** con todas las funciones `build_*_response()` que construyen paquetes de red. Estas funciones **solo se usan en los componentes de MessageSender**.

## 🎯 Objetivo

Dividir `msg.py` en módulos `msg_*.py` por categoría, luego cada componente importa solo lo que necesita. Finalmente eliminar `msg.py`.

## 📁 Estructura Propuesta

```
src/
├── msg_map.py                   # Funciones para mensajes de mapa
├── msg_console.py               # Funciones para mensajes de consola
├── msg_audio.py                 # Funciones para mensajes de audio
├── msg_character.py             # Funciones para mensajes de personajes
├── msg_inventory.py             # Funciones para mensajes de inventario
├── msg_player_stats.py          # Funciones para mensajes de stats
├── msg_session.py               # Funciones para mensajes de sesión
├── msg_visual_effects.py        # Funciones para efectos visuales
│
├── message_map_sender.py        # Importa de msg_map
├── message_console_sender.py    # Importa de msg_console
├── message_audio_sender.py      # Importa de msg_audio
└── ... (otros componentes)
```

## 📦 Distribución de Funciones por Módulo

### msg_map.py (5 funciones)
```python
def build_change_map_response(map_id: int, version: int) -> bytes
def build_pos_update_response(x: int, y: int) -> bytes
def build_object_create_response(x: int, y: int, grh_index: int) -> bytes
def build_object_delete_response(x: int, y: int) -> bytes
def build_block_position_response(x: int, y: int, blocked: bool) -> bytes
```

### msg_console.py (3 funciones)
```python
def build_console_msg_response(message: str, font_color: int) -> bytes
def build_multiline_console_msg_response(message: str, font_color: int) -> bytes
def build_error_msg_response(message: str) -> bytes
```

### msg_audio.py (2 funciones)
```python
def build_play_midi_response(midi_id: int) -> bytes
def build_play_wave_response(wave_id: int, x: int, y: int) -> bytes
```

### msg_character.py (4 funciones)
```python
def build_character_create_response(...) -> bytes
def build_character_change_response(...) -> bytes
def build_character_remove_response(char_index: int) -> bytes
def build_character_move_response(char_index: int, x: int, y: int) -> bytes
```

### msg_inventory.py (9 funciones)
```python
def build_change_inventory_slot_response(...) -> bytes
def build_change_bank_slot_response(...) -> bytes
def build_change_npc_inventory_slot_response(...) -> bytes
def build_change_spell_slot_response(...) -> bytes
def build_commerce_init_response(...) -> bytes
# ... etc
```

### msg_player_stats.py (6 funciones)
```python
def build_update_hp_response(hp: int) -> bytes
def build_update_mana_response(mana: int) -> bytes
def build_update_sta_response(sta: int) -> bytes
def build_update_exp_response(exp: int) -> bytes
def build_update_hunger_and_thirst_response(...) -> bytes
def build_update_user_stats_response(...) -> bytes
```

### msg_session.py (4 funciones)
```python
def build_dice_roll_response(...) -> bytes
def build_attributes_response(...) -> bytes
def build_logged_response(user_class: int) -> bytes
def build_user_char_index_in_server_response(char_index: int) -> bytes
```

### msg_visual_effects.py (2 funciones)
```python
def build_create_fx_response(char_index: int, fx_id: int, loops: int) -> bytes
def build_create_fx_at_position_response(x: int, y: int, fx_id: int, loops: int) -> bytes
```

## 🔄 Migración

### Paso 1: Crear módulos msg_*.py
Crear cada módulo `msg_*.py` y mover las funciones correspondientes de `msg.py`.

**Ejemplo - Crear msg_map.py:**
```python
# src/msg_map.py
"""Funciones para construir mensajes de mapa."""

from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID


def build_change_map_response(map_id: int, version: int) -> bytes:
    """Construye paquete ChangeMap."""
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHANGE_MAP)
    packet.add_int16(map_id)
    packet.add_int16(version)
    return packet.to_bytes()


def build_pos_update_response(x: int, y: int) -> bytes:
    """Construye paquete PosUpdate."""
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.POS_UPDATE)
    packet.add_byte(x)
    packet.add_byte(y)
    return packet.to_bytes()

# ... resto de funciones
```

### Paso 2: Actualizar imports en componentes
Cambiar imports de `src.msg` a `src.msg_*`:

```python
# src/message_map_sender.py

# Antes
from src.msg import (
    build_change_map_response,
    build_pos_update_response,
    # ...
)

# Después
from src.msg_map import (
    build_change_map_response,
    build_pos_update_response,
    # ...
)
```

### Paso 3: Verificar que todo funciona
```bash
uv run pytest --tb=short -q
uv run ruff check .
```

### Paso 4: Eliminar msg.py
Una vez que todos los componentes usen los nuevos módulos `msg_*.py`:
```bash
rm src/msg.py
```

## ✅ Ventajas

1. **Organización clara** - Funciones agrupadas por categoría en archivos `msg_*.py`
2. **Imports específicos** - Cada componente importa solo lo que necesita
3. **Sin subcarpetas** - Todo en `src/`, sin complejidad extra
4. **Archivos más pequeños** - ~80 líneas por archivo vs 642 en uno
5. **Fácil de encontrar** - Saber dónde buscar cada función
6. **Mantenible** - Fácil agregar nuevas funciones al módulo correcto

## 📝 Checklist

- [ ] Crear `src/msg_map.py` y mover funciones de mapa
- [ ] Crear `src/msg_console.py` y mover funciones de consola
- [ ] Crear `src/msg_audio.py` y mover funciones de audio
- [ ] Crear `src/msg_character.py` y mover funciones de personajes
- [ ] Crear `src/msg_inventory.py` y mover funciones de inventario
- [ ] Crear `src/msg_player_stats.py` y mover funciones de stats
- [ ] Crear `src/msg_session.py` y mover funciones de sesión
- [ ] Crear `src/msg_visual_effects.py` y mover funciones de efectos
- [ ] Actualizar imports en `message_map_sender.py` (de `msg` a `msg_map`)
- [ ] Actualizar imports en `message_console_sender.py` (de `msg` a `msg_console`)
- [ ] Actualizar imports en `message_audio_sender.py` (de `msg` a `msg_audio`)
- [ ] Actualizar imports en `message_character_sender.py` (de `msg` a `msg_character`)
- [ ] Actualizar imports en `message_inventory_sender.py` (de `msg` a `msg_inventory`)
- [ ] Actualizar imports en `message_player_stats_sender.py` (de `msg` a `msg_player_stats`)
- [ ] Actualizar imports en `message_session_sender.py` (de `msg` a `msg_session`)
- [ ] Actualizar imports en `message_visual_effects_sender.py` (de `msg` a `msg_visual_effects`)
- [ ] Ejecutar tests (deben pasar sin cambios)
- [ ] Ejecutar linter
- [ ] Eliminar `src/msg.py`
- [ ] Actualizar README.md

## ⚠️ Consideraciones

- **NO cambiar firmas de funciones** - Solo moverlas a nuevos archivos
- **Tests existentes** - Deben seguir pasando sin modificaciones
- **PacketBuilder** - Cada `msg_*.py` lo importa
- **Imports** - Cambiar `from src.msg import X` a `from src.msg_map import X`

## 🎓 Principio: Separación por Responsabilidad

Esta refactorización sigue el principio de **Single Responsibility**:
- Cada módulo `msg_*.py` tiene una responsabilidad clara
- Los componentes importan solo lo que necesitan
- No hay un archivo gigante con todo mezclado
- Fácil de mantener y extender
