# NPC Factory - IMPLEMENTADO ✅

**Fecha:** 21 de octubre, 2025  
**Versión:** 0.6.0-alpha  
**Estado:** ✅ Completado

---

## 📋 Resumen

Sistema de factory methods para crear NPCs con configuraciones predefinidas, eliminando duplicación de código y centralizando la creación de diferentes tipos de NPCs.

---

## 🏗️ Arquitectura

### Archivo Principal
- **`src/npc_factory.py`** (620 líneas)

### Estructura

```python
class NPCFactory:
    # Factory methods base
    create_hostile()    # Base para NPCs hostiles
    create_friendly()   # Base para NPCs amigables
    
    # NPCs hostiles específicos (11 total)
    create_goblin()
    create_lobo()
    create_orco()
    create_arana()
    create_serpiente()
    create_dragon_rojo()
    create_esqueleto()
    create_zombie()
    create_gran_dragon_rojo()
    create_ogro()
    create_demonio()
    create_murcielago()
    
    # NPCs amigables específicos (3 total)
    create_comerciante()
    create_banquero()
    create_guardia()
```

---

## 🎯 NPCs Implementados

### NPCs Hostiles (11)

| NPC | ID | Body ID | HP | Nivel | Daño | Cooldown | Aggro | FX | FX Loop |
|-----|----|---------|----|-------|------|----------|-------|-----|---------|
| **Murciélago** | 16 | 9 | 15 | 1 | 4 | 1.0s | 4 | 5 | - |
| **Serpiente** | 9 | 13 | 22 | 2 | 1 | 1.5s | 5 | 10 | - |
| **Lobo** | 7 | 10 | 80 | 3 | 6 | 2.0s | 7 | 5 | - |
| **Goblin** | 1 | 14 | 110 | 5 | 8 | 2.5s | 6 | 5 | - |
| **Esqueleto** | 11 | 12 | 50 | 5 | 8 | 3.0s | 7 | 5 | - |
| **Araña Gigante** | 8 | 42 | 150 | 8 | 12 | 2.5s | 8 | 10 | 15 |
| **Zombie** | 12 | 196 | 250 | 8 | 12 | 2.5s | 6 | 10 | - |
| **Orco** | 4 | 185 | 350 | 10 | 35 | 3.0s | 10 | 5 | - |
| **Ogro** | 14 | 76 | 2250 | 18 | 232 | 3.5s | 10 | 5 | - |
| **Demonio** | 15 | 83 | 5000 | 25 | 400 | 4.0s | 15 | 25 | 50 |
| **Dragón Rojo** | 10 | 41 | 5000 | 50 | 300 | 4.0s | 15 | 25 | 20 |
| **Gran Dragón Rojo** | 13 | 82 | 200000 | 100 | 5000 | 5.0s | 20 | 25 | 20 |

### NPCs Amigables (3)

| NPC | ID | Body ID | Función |
|-----|----|---------|----|
| **Comerciante** | 2 | 501 | Vende items (is_merchant=true) |
| **Guardia Real** | 3 | 502 | Protección (estático) |
| **Banquero** | 5 | 504 | Gestiona bóveda (is_banker=true) |

---

## 🎨 Sistema de Efectos Visuales (FX)

### FX al Morir (one-shot)
- **fx=5**: Sangre (muerte normal) - Usado por: Goblin, Lobo, Orco, Esqueleto, Ogro, Murciélago
- **fx=10**: Veneno - Usado por: Serpiente, Araña, Zombie
- **fx=25**: Explosión de fuego - Usado por: Dragón Rojo, Gran Dragón Rojo, Demonio

### FX Loop (aura continua)
- **fx_loop=15**: Aura venenosa - Usado por: Araña Gigante
- **fx_loop=20**: Aura de fuego - Usado por: Dragón Rojo, Gran Dragón Rojo
- **fx_loop=50**: Aura oscura - Usado por: Demonio

---

## 💻 Uso del Factory

### Ejemplo Básico

```python
from src.npc_factory import NPCFactory

# Crear NPCs hostiles
goblin = NPCFactory.create_goblin(x=50, y=50, map_id=1, char_index=10001)
dragon = NPCFactory.create_dragon_rojo(x=70, y=70, map_id=1, char_index=10002)

# Crear NPCs amigables
comerciante = NPCFactory.create_comerciante(x=30, y=30, map_id=1, char_index=10003)
banquero = NPCFactory.create_banquero(x=35, y=35, map_id=1, char_index=10004)

# Agregar al mapa
await map_manager.add_npc(goblin)
await map_manager.add_npc(dragon)
```

### Integración con NPCService

El `NPCService` ya usa el factory para cargar NPCs desde archivos TOML:

```python
# src/npc_service.py
npc = NPCFactory.create_hostile(
    npc_id=npc_id,
    name=npc_data.get("nombre", "NPC"),
    body_id=npc_data.get("body_id", 1),
    hp=npc_data.get("hp_max", 100),
    # ... otros parámetros desde TOML
)
```

---

## ✅ Ventajas Implementadas

1. **DRY (Don't Repeat Yourself)**
   - No duplicar código entre NPCs similares
   - Configuración centralizada

2. **Type-Safe**
   - Todos los métodos retornan `NPC` tipado
   - Parámetros explícitos con type hints

3. **Autodocumentado**
   - Nombres claros: `create_dragon_rojo()`, `create_murcielago()`
   - Docstrings descriptivos para cada método

4. **Fácil de Extender**
   - Agregar nuevo NPC = 1 factory method nuevo
   - Template claro con `create_hostile()` y `create_friendly()`

5. **Efectos Visuales Integrados**
   - FX de muerte y auras definidos por NPC
   - Configuración en el factory, no en múltiples lugares

6. **Consistencia**
   - Todos los NPCs usan el mismo sistema
   - Body IDs correctos desde AO VB6 0.13.3

---

## 🧪 Tests

**Archivo:** `tests/test_npc_factory.py`

**Tests implementados:** 17 tests
- Tests de creación para cada tipo de NPC
- Verificación de parámetros (body_id, hp, level, etc.)
- Tests de efectos visuales (fx, fx_loop)
- Tests de NPCs amigables (is_merchant, is_banker)

**Resultado:** ✅ 990 tests pasando (100%)

---

## 📊 Estadísticas

- **Líneas de código:** 620
- **Factory methods:** 16 total (11 hostiles + 3 amigables + 2 base)
- **NPCs cubiertos:** 14 tipos diferentes
- **Body IDs correctos:** ✅ 100% verificados con AO VB6 0.13.3
- **Tests:** 17 tests específicos
- **Linting:** ✅ 0 errores

---

## 📝 Configuración en TOML

Los NPCs se configuran en:
- **`data/npcs_hostiles.toml`** - NPCs hostiles (24 configurados)
- **`data/npcs_amigables.toml`** - NPCs amigables (4 configurados)

Los factory methods proveen valores por defecto robustos que coinciden con el TOML.

---

## 🔮 Próximos Pasos Sugeridos

### Opcional: Más NPCs

Agregar factory methods para NPCs adicionales del TOML:
- `create_escorpion()` (id=17)
- `create_bandido()` (id=18)
- `create_oso_pardo()` (id=19)
- `create_tigre_salvaje()` (id=20)
- `create_licantropo()` (id=21)
- `create_liche()` (id=22)
- `create_golem()` (id=23)
- `create_elemental_fuego()` (id=24)

### Mejoras Futuras

1. **Spawn Service**: Servicio para spawn automático por bioma
2. **FX Broadcast**: Envío automático de FX al spawn/muerte
3. **Factory Config**: Cargar factory methods desde TOML dinámicamente
4. **Variants**: Variantes de NPCs (Elite, Weak, etc.)

---

## 📚 Referencias

- **Body IDs verificados:** `/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Dat/NPCs.dat`
- **Configuración actual:** `data/npcs_hostiles.toml`, `data/npcs_amigables.toml`
- **Diseño original:** `todo/TODO_NPC_FACTORY.md`

---

**Última actualización:** 2025-10-21  
**Estado:** ✅ COMPLETADO  
**Tests:** ✅ 990 pasando (100%)  
**Linting:** ✅ 0 errores
