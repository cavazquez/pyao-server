# TODO: Refactorizar msg.py

## 📋 Contexto

`msg.py` actualmente tiene **642 líneas** con todas las funciones `build_*_response()` que construyen paquetes de red. Similar a como refactorizamos `MessageSender` en componentes, deberíamos organizar `msg.py` por categorías.

## 🎯 Objetivo

Dividir `msg.py` en módulos especializados por tipo de mensaje, manteniendo retrocompatibilidad.

## 📁 Estructura Propuesta

```
src/msg/
├── __init__.py              # Re-exporta todas las funciones
├── map_messages.py          # Mensajes de mapa
├── console_messages.py      # Mensajes de consola
├── audio_messages.py        # Mensajes de audio
├── character_messages.py    # Mensajes de personajes
├── inventory_messages.py    # Mensajes de inventario/banco/comercio
├── player_stats_messages.py # Mensajes de stats del jugador
├── session_messages.py      # Mensajes de sesión/login
└── visual_effects_messages.py # Mensajes de efectos visuales
```

## 📦 Distribución de Funciones

### map_messages.py (5 funciones)
```python
def build_change_map_response(map_id: int, version: int) -> bytes
def build_pos_update_response(x: int, y: int) -> bytes
def build_object_create_response(x: int, y: int, grh_index: int) -> bytes
def build_object_delete_response(x: int, y: int) -> bytes
def build_block_position_response(x: int, y: int, blocked: bool) -> bytes
```

### console_messages.py (3 funciones)
```python
def build_console_msg_response(message: str, font_color: int) -> bytes
def build_multiline_console_msg_response(message: str, font_color: int) -> bytes
def build_error_msg_response(message: str) -> bytes
```

### audio_messages.py (2 funciones)
```python
def build_play_midi_response(midi_id: int) -> bytes
def build_play_wave_response(wave_id: int, x: int, y: int) -> bytes
```

### character_messages.py (4 funciones)
```python
def build_character_create_response(...) -> bytes
def build_character_change_response(...) -> bytes
def build_character_remove_response(char_index: int) -> bytes
def build_character_move_response(char_index: int, x: int, y: int) -> bytes
```

### inventory_messages.py (9 funciones)
```python
def build_change_inventory_slot_response(...) -> bytes
def build_change_bank_slot_response(...) -> bytes
def build_change_npc_inventory_slot_response(...) -> bytes
def build_change_spell_slot_response(...) -> bytes
def build_commerce_init_response(...) -> bytes
# ... etc
```

### player_stats_messages.py (6 funciones)
```python
def build_update_hp_response(hp: int) -> bytes
def build_update_mana_response(mana: int) -> bytes
def build_update_sta_response(sta: int) -> bytes
def build_update_exp_response(exp: int) -> bytes
def build_update_hunger_and_thirst_response(...) -> bytes
def build_update_user_stats_response(...) -> bytes
```

### session_messages.py (4 funciones)
```python
def build_dice_roll_response(...) -> bytes
def build_attributes_response(...) -> bytes
def build_logged_response(user_class: int) -> bytes
def build_user_char_index_in_server_response(char_index: int) -> bytes
```

### visual_effects_messages.py (2 funciones)
```python
def build_create_fx_response(char_index: int, fx_id: int, loops: int) -> bytes
def build_create_fx_at_position_response(x: int, y: int, fx_id: int, loops: int) -> bytes
```

## 🔄 Migración

### Paso 1: Crear estructura de carpeta
```bash
mkdir src/msg
touch src/msg/__init__.py
```

### Paso 2: Crear módulos especializados
Mover funciones de `msg.py` a sus respectivos módulos.

### Paso 3: Re-exportar en __init__.py
```python
# src/msg/__init__.py
from src.msg.map_messages import *
from src.msg.console_messages import *
from src.msg.audio_messages import *
# ... etc

__all__ = [
    "build_change_map_response",
    "build_console_msg_response",
    # ... todas las funciones
]
```

### Paso 4: Actualizar imports
Los componentes ya importan desde `src.msg`, por lo que seguirán funcionando:
```python
# Esto sigue funcionando sin cambios
from src.msg import build_console_msg_response
```

## ✅ Ventajas

1. **Organización clara** - Funciones agrupadas por categoría
2. **Archivos más pequeños** - ~80 líneas por archivo vs 642 en uno
3. **Fácil de encontrar** - Saber dónde buscar cada función
4. **Retrocompatible** - Los imports existentes siguen funcionando
5. **Escalable** - Fácil agregar nuevas funciones
6. **Testeable** - Tests por módulo

## 📝 Checklist

- [ ] Crear carpeta `src/msg/`
- [ ] Crear `map_messages.py`
- [ ] Crear `console_messages.py`
- [ ] Crear `audio_messages.py`
- [ ] Crear `character_messages.py`
- [ ] Crear `inventory_messages.py`
- [ ] Crear `player_stats_messages.py`
- [ ] Crear `session_messages.py`
- [ ] Crear `visual_effects_messages.py`
- [ ] Crear `__init__.py` con re-exports
- [ ] Ejecutar tests (deben pasar sin cambios)
- [ ] Eliminar `msg.py` viejo
- [ ] Actualizar README.md

## ⚠️ Consideraciones

- **NO cambiar firmas de funciones** - Mantener compatibilidad
- **Mover PacketBuilder también** - Considerar moverlo a `src/msg/packet_builder.py`
- **Tests existentes** - Deben seguir pasando sin modificaciones
- **Imports relativos** - Usar imports absolutos en los módulos

## 🎓 Patrón Similar a MessageSender

Esta refactorización sigue el mismo patrón que usamos con `MessageSender`:
1. Identificar responsabilidades
2. Crear módulos especializados
3. Mantener interfaz pública
4. Retrocompatibilidad 100%
