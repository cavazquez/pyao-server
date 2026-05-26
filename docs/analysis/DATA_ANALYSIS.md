# Análisis de Datos: PyAO Server vs VB6 Original

## Resumen Comparativo

| Dato | VB6 Original | PyAO Server | Estado |
|------|-------------|-------------|--------|
| NPCs | 336 | 336 | ✅ Completo |
| Items | 1049 | 1096 | ✅ Completo+ |
| Hechizos | 48 | 45 | ⚠️ Faltan 3 |
| Clases | ? | 11 | ✅ Definido |
| Merchants | ~80 | 80 | ✅ Completo (recién sincronizado) |

## Detalle de Archivos

### VB6 Original (`server/Dat/`)

| Archivo | Contenido | Líneas |
|---------|-----------|--------|
| `NPCs.dat` | 336 NPCs (todos los tipos) | 9,626 |
| `obj.dat` | 1,049 objetos | 12,670 |
| `Hechizos.dat` | 48 hechizos | 2,918 |
| `Balance.dat` | Modificadores de clases | 187 |
| `ArmasHerrero.dat` | Crafting de armas | 79 |
| `ArmadurasHerrero.dat` | Crafting de armaduras | 186 |
| `ObjCarpintero.dat` | Crafting de carpintero | 104 |
| `Invokar.dat` | NPCs invocables | 76 |
| `Ciudades.Dat` | Puntos de spawn | 11 |
| `Pretorianos.dat` | NPCs pretorianos | 43 |

### PyAO Server (`data/`)

#### NPCs
| Archivo | Contenido | Notas |
|---------|-----------|-------|
| `npcs_complete.toml` | 336 NPCs | Todos los NPCs del VB6 |
| `npcs_traders_extended.toml` | 80 comerciantes | Con inventarios |
| `npcs_hostiles_extended.toml` | NPCs hostiles | Con stats de combate |
| `npcs_amigables.toml` | NPCs pacíficos | Formato alternativo |
| `merchant_inventories.toml` | 80 merchants, 640 items | **Recién sincronizado** |
| `map_npcs.toml` | Spawns en mapas | 10,340 líneas |

#### Items
| Directorio | Archivos | Items |
|------------|----------|-------|
| `items/equipment/` | armors, weapons, shields, etc. | 363 |
| `items/consumables/` | food, potions, drinks, scrolls | 78 |
| `items/resources/` | minerals, wood, gems, flowers | 56 |
| `items/tools/` | keys, books, instruments | 84 |
| `items/world_objects/` | doors, trees, furniture | 472 |
| `items/misc/` | teleports, arrows, boats | 43 |
| **Total** | 30 archivos | **1,096 items** |

#### Hechizos
| Archivo | Contenido | Notas |
|---------|-----------|-------|
| `spells.toml` | 45 hechizos | **Del VB6, faltan 3** |
| `hechizos.toml` | 7 hechizos | Duplicado/alternativo, NO SE USA |

#### Otros
| Archivo | Contenido |
|---------|-----------|
| `classes.toml` | 11 clases de personaje |
| `classes_balance.toml` | Modificadores por clase |
| `armor_crafting.toml` | Crafting de armaduras |
| `weapons_crafting.toml` | Crafting de armas |
| `loot_tables.toml` | Tablas de loot |
| `map_doors.toml` | Puertas en mapas |

---

## Problemas Detectados

### 1. ⚠️ Hechizos Incompletos
**Problema**: Faltan 3 hechizos (48 en VB6 vs 45 en PyAO)

**Solución**: Verificar cuáles faltan y agregarlos a `spells.toml`

### 2. ⚠️ Archivo Duplicado `hechizos.toml`
**Problema**: Existen dos archivos de hechizos:
- `spells.toml` (45 hechizos, formato correcto, SE USA)
- `hechizos.toml` (7 hechizos, formato diferente, NO SE USA)

**Solución**: Eliminar `hechizos.toml` para evitar confusión

### 3. ✅ RESUELTO - Merchants sin inventario
**Problema anterior**: Solo 1 merchant tenía items configurados
**Solución aplicada**: Script `sync_merchant_inventories.py` generó 80 merchants con 640 items

### 4. ✅ RESUELTO - Archivos TOML con errores de formato
**Problema anterior**: `npcs_complete.toml` y `npcs_traders_extended.toml` tenían claves duplicadas
**Solución aplicada**: Regenerados desde NPCs.dat del VB6 original con formato TOML válido
- 336 NPCs correctamente parseados
- 147 hostiles, 80 comerciantes

### 5. ⚠️ Datos de crafting incompletos
**Problema**: Solo hay crafting de armas y armaduras

**Faltantes del VB6**:
- `ObjCarpintero.dat` → Carpintería (no migrado)

---

## Archivos Migrados de VB6

| VB6 Original | PyAO Equivalente | Estado |
|--------------|------------------|--------|
| `Invokar.dat` | `summon_list.toml` | ✅ Migrado - 20 NPCs invocables |
| `Ciudades.Dat` | `cities.toml` | ✅ Migrado - 7 ciudades con spawns |
| `ObjCarpintero.dat` | `carpentry_crafting.toml` | ✅ Migrado - 34 recetas |
| `Pretorianos.dat` | - | ⚠️ Pendiente (NPCs especiales de eventos) |
| `AreasStats.dat` | - | ⚠️ Pendiente (sistema de áreas)

---

## Recomendaciones

### Completado ✅
1. ✅ Eliminar `hechizos.toml` (duplicado) - HECHO
2. ✅ Corregir formato TOML en `npcs_*.toml` - HECHO (regenerados desde VB6)
3. ✅ Migrar `Invokar.dat` → `summon_list.toml` - HECHO
4. ✅ Migrar `Ciudades.Dat` → `cities.toml` - HECHO
5. ✅ Migrar `ObjCarpintero.dat` → `carpentry_crafting.toml` - HECHO

### A Futuro
6. ⬜ Migrar `Pretorianos.dat` (NPCs de eventos especiales)
7. ⬜ Crear sistema de áreas (`AreasStats.dat`)
8. ⬜ Integrar `cities.toml` con sistema de spawn
9. ⬜ Integrar `summon_list.toml` con sistema de invocación
10. ⬜ Integrar `carpentry_crafting.toml` con sistema de crafting

---

## Uso Actual de Catálogos

### ItemCatalog (`src/models/item_catalog.py`)
- **Fuente**: `data/items/**/*.toml` (1,096 items)
- **Usado por**: `DropCommandHandler`, `CombatService`, `CommerceService`, etc.

### SpellCatalog (`src/models/spell_catalog.py`)
- **Fuente**: `data/spells.toml` (45 hechizos)
- **Usado por**: `SpellService`, `CastSpellHandler`, `SpellInfoHandler`

### NPCService (`src/services/game/npc_service.py`)
- **Fuente**: `data/npcs_*.toml`
- **Usado por**: `MapManager`, `NPCFactory`, `NPCAIService`

### MerchantDataLoader (`src/models/merchant_data_loader.py`)
- **Fuente**: `data/merchant_inventories.toml` (80 merchants, 640 items)
- **Usado por**: `MerchantRepository`, `CommerceService`

