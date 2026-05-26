# Oportunidades de Refactorización

**Fecha:** 2025-01-30  
**Estado:** Análisis completo

---

## 📊 Resumen Ejecutivo

Se identificaron **5 áreas principales** de refactorización con diferentes niveles de prioridad y esfuerzo.

---

## 🔴 Prioridad Alta

### 1. Eliminar Acceso Directo a `stats.get()` en Servicios — ✅ Completado (2026-05)

**Estado:** 0 usos en `src/services/`; los servicios usan métodos tipados de `PlayerRepository` (`get_current_hp`, `get_level`, `get_player_stats`, etc.).

**Referencia histórica:** Ver métodos helper listados abajo. Completado también en `drop_handler.py` y `pickup_handler.py`.
- `stats.get("min_hp", 0)` → `await player_repo.get_current_hp(user_id)`
- `stats.get("max_hp", 100)` → `await player_repo.get_max_hp(user_id)`
- `stats.get("level", 1)` → `await player_repo.get_level(user_id)`
- `stats.get("gold", 0)` → `await player_repo.get_gold(user_id)`
- `stats.get("experience", 0)` → `(await player_repo.get_experience(user_id))[0]`
- `stats.get("min_mana", 0)` → `(await player_repo.get_mana(user_id))[0]`
- `stats.get("max_mana", 100)` → `(await player_repo.get_mana(user_id))[1]`

**Para múltiples stats:**
- `stats = await player_repo.get_player_stats(user_id)` → objeto tipado `PlayerStats`

**Esfuerzo:** Medio (2-3 horas)  
**Beneficio:** Alto (mejor type safety, menos bugs, más mantenible)

**Ejemplo de refactorización:**
```python
# Antes
stats = await self.player_repo.get_stats(user_id)
if not stats or stats.get("min_hp", 0) <= 0:
    return False
current_exp = stats.get("experience", 0)
level = stats.get("level", 1)

# Después
if not await self.player_repo.is_alive(user_id):
    return False
experience, _ = await self.player_repo.get_experience(user_id)
level = await self.player_repo.get_level(user_id)
```

**Referencia:** Ya completado en `drop_handler.py` y `pickup_handler.py` ✅

---

## 🟡 Prioridad Media

### 2. Eliminar Acceso Directo a `attributes.get()`

**Problema:**
- **22 usos** en 9 archivos
- Similar a stats, pero menos crítico

**Archivos afectados:**
1. `command_handlers/use_item_handler.py` - 4 usos
2. `services/combat/combat_service.py` - 3 usos
3. `services/player/spell_effects/buffs.py` - 4 usos
4. `command_handlers/login_handler.py` - 2 usos
5. `command_handlers/create_account_handler.py` - 2 usos
6. `services/game/class_service.py` - 2 usos
7. `effects/effect_attribute_modifiers.py` - 2 usos
8. `services/npc/npc_death_service.py` - 2 usos
9. `services/party_service.py` - 1 uso

**Solución:**
Agregar métodos helper a `PlayerRepository`:
- `attributes.get("strength", 10)` → `await player_repo.get_strength(user_id)`
- `attributes.get("agility", 10)` → `await player_repo.get_agility(user_id)`
- etc.

**Esfuerzo:** Bajo-Medio (1-2 horas)  
**Beneficio:** Medio

---

### 3. Dividir Archivos Grandes

**Archivos candidatos (>600 líneas):**

#### 3.1 `map_resources_service.py` — modularizado (2026-05)
**Estado:** Completado parcialmente. El monolito (~1100 líneas) se dividió en submódulos bajo `src/services/map/`:
- `map_bulk_resources_loader.py` — carga masiva NDJSON
- `map_single_map_loader.py` — carga por mapa (`parse_blocked_for_map`, `parse_objects_for_map`)
- `map_resource_queries.py` — consultas puras
- `cache.py` / `binary_cache.py` — caché JSON y MessagePack
- `blocked_loader.py` / `objects_loader.py` / `ndjson_reader.py` — parsing compartido
- `map_manual_doors.py` — puertas TOML

`MapResourcesService` (~140 líneas) conserva solo ciclo de vida y API pública.

**Esfuerzo restante:** Bajo (transiciones/pathfinding si se desea el mismo patrón)  
**Beneficio:** Alto (ya obtenido en mantenibilidad)

#### 3.2 `player_repository.py` — mixins por dominio (2026-05)
**Estado:** Completado. Mixins bajo `src/repositories/player_mixins/`:
- `_base.py` — helpers Redis
- `_position_mixin.py` — posición y heading
- `_stats_mixin.py` — stats, hambre/sed, flags de meditación/navegación
- `_attributes_mixin.py` — atributos y modificadores temporales
- `_status_mixin.py` — efectos de estado (veneno, ceguera, etc.)
- `_skills_mixin.py` — habilidades

`PlayerRepository` en la ruta original compone los mixins (~25 líneas).

#### 3.3 `clan_service.py` — split por dominio (2026-05)
**Estado:** Completado. Submódulos bajo `src/services/clan/`:
- `creation.py` — crear clan
- `membership.py` — invitar, aceptar, expulsar, abandonar
- `ranks.py` — promover, degradar, transferir liderazgo
- `messaging.py` — mensajes de clan
- `_helpers.py` — helpers compartidos y nombres de rango

`ClanService` compone mixins; `src/services/clan_service.py` re-exporta para compatibilidad.

#### 3.4 `packet_validator.py` — fachada delgada (2026-05)
**Estado:** Completado. Eliminados ~40 wrappers `validate_*_packet()`; producción y tests usan `validate_packet_by_id(ClientPacketID.X)`.

#### 3.5 `message_sender.py` — sin envíos inline (2026-05)
**Estado:** Completado. `send_navigate_toggle`, `send_user_commerce_init` y `send_user_commerce_end` delegan en `InventoryMessageSender`. Sub-senders en `messaging/senders/`.

#### 3.6 `use_item_handler.py` (741 líneas)
**Problema:** Mucha lógica de diferentes tipos de items  
**Solución:** Dividir en handlers especializados:
- `use_item_consumable_handler.py` - Pociones, comida
- `use_item_weapon_handler.py` - Armas
- `use_item_special_handler.py` - Items especiales

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto

#### 3.7 `party_service.py` (726 líneas)
**Problema:** Mucha lógica de negocio  
**Solución:** Similar a clan_service:
- `party_management_service.py` - Crear, disolver
- `party_membership_service.py` - Unirse, salir, expulsar
- `party_experience_service.py` - Distribución de EXP

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto

#### 3.8 `talk_handler.py` (661 líneas)
**Problema:** Mucha lógica de diferentes comandos de chat  
**Solución:** Dividir por tipo de comando:
- `talk_public_handler.py` - Chat público
- `talk_private_handler.py` - Mensajes privados
- `talk_guild_handler.py` - Chat de clan

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio

#### 3.9 `npc_death_service.py` (638 líneas)
**Problema:** Mucha lógica de muerte y experiencia  
**Solución:** Dividir en:
- `npc_death_handler.py` - Manejo de muerte
- `experience_distribution_service.py` - Distribución de EXP
- `level_up_service.py` - Manejo de level up

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto

---

## 🟢 Prioridad Baja

### 4. Extraer Helper para `send_update_user_stats`

**Problema:**
- 17 archivos llaman a `send_update_user_stats` con el mismo patrón
- Código repetido para obtener todos los stats

**Solución:**
Crear helper en `MessageSender`:
```python
async def send_update_user_stats_from_repo(self, user_id: int) -> None:
    """Envía UPDATE_USER_STATS obteniendo datos del repositorio."""
    stats = await self.player_repo.get_player_stats(user_id)
    if stats:
        await self.send_update_user_stats(
            max_hp=stats.max_hp,
            min_hp=stats.min_hp,
            # ... etc
        )
```

**Esfuerzo:** Bajo (1 hora)  
**Beneficio:** Bajo-Medio

---

### 5. Reorganización de Estructura de Directorios

**Problema:**
- Muchos archivos en `src/` (307 archivos)
- Difícil navegación

**Solución:**
Reorganizar tasks en subcarpetas (referencia histórica de layout: `docs/archive/PROPOSED_CODE_ORGANIZATION.md`):
- `tasks/player/` - Tasks de jugador
- `tasks/inventory/` - Tasks de inventario
- `tasks/commerce/` - Tasks de comercio
- etc.

**Esfuerzo:** Alto (6-8 horas)  
**Beneficio:** Medio (mejor organización, pero requiere actualizar muchos imports)

**Estado:** Propuesta documentada, no implementada

---

## 📋 Plan de Acción Recomendado

### Fase 1: Alta Prioridad (2-3 horas)
1. ✅ Refactorizar `drop_handler.py` y `pickup_handler.py` (COMPLETADO)
2. 🔄 Refactorizar servicios críticos:
   - `services/npc/npc_ai_service.py`
   - `services/combat/combat_service.py`
   - `services/npc/npc_death_service.py`

### Fase 2: Media Prioridad (4-6 horas)
3. Refactorizar servicios restantes con `stats.get()`
4. Refactorizar `attributes.get()`
5. Dividir `use_item_handler.py` (741 líneas)

### Fase 3: Baja Prioridad (opcional)
6. Dividir otros archivos grandes si es necesario
7. Extraer helper para `send_update_user_stats`
8. Reorganización de estructura (si se decide hacerlo)

---

## 📊 Métricas

- **Total de refactorizaciones identificadas:** 5 áreas principales
- **Archivos afectados por stats.get():** 8 archivos (100 usos)
- **Archivos afectados por attributes.get():** 9 archivos (22 usos)
- **Archivos grandes (>600 líneas):** 9 archivos
- **Esfuerzo total estimado:** 20-30 horas
- **Beneficio esperado:** Alto (mejor mantenibilidad, type safety, menos bugs)

---

## ✅ Refactorizaciones Completadas

### Handlers de Comandos (Command Pattern)
1. ✅ `use_item_handler.py` - Dividido en `use_item_consumable_handler.py` y `use_item_special_handler.py`
2. ✅ `talk_handler.py` - Dividido en 5 handlers especializados (metrics, trade, clan, pet, public)
3. ✅ `left_click_handler.py` - Dividido en `left_click_npc_handler.py` y `left_click_tile_handler.py`
4. ✅ `walk_handler.py` - Dividido en `walk_validation_handler.py` y `walk_movement_handler.py`
5. ✅ `login_handler.py` - Dividido en 4 handlers especializados (auth, init, spawn, finalization)
6. ✅ `create_account_handler.py` - Dividido en 3 handlers especializados (validation, character, finalization)
7. ✅ `attack_handler.py` - Dividido en 3 handlers especializados (validation, execution, loot)
8. ✅ `work_left_click_handler.py` - Dividido en 3 handlers especializados (validation, execution, ui)
9. ✅ `double_click_handler.py` - Dividido en `double_click_item_handler.py` y `double_click_npc_handler.py`
10. ✅ `drop_handler.py` - Dividido en `drop_gold_handler.py` y `drop_item_handler.py`
11. ✅ `pickup_handler.py` - Dividido en `pickup_gold_handler.py` y `pickup_item_handler.py`
12. ✅ `cast_spell_handler.py` - Dividido en `cast_spell_validation_handler.py` y `cast_spell_execution_handler.py`

**Ver [HANDLER_REFACTORING.md](development/REFACTORING.md) para detalles completos.**

### Otros Refactorizaciones
1. ✅ `drop_handler.py` - Reemplazado `stats.get()` con métodos helper
2. ✅ `pickup_handler.py` - Reemplazado `stats.get()` con métodos helper
3. ✅ `msg.py` - Dividido en 8 módulos especializados
4. ✅ `server.py` - Refactorizado en initializers
5. ✅ `task_factory.py` - Refactorizado con handler_registry
6. ✅ `spell_service.py` - Dividido en spell_effects/
7. ✅ `packet_validator.py` - Dividido en validators/
8. ✅ `message_sender.py` - Dividido en senders/

---

## 🔄 Refactorizaciones Pendientes

### Handlers que aún pueden refactorizarse

Los siguientes handlers son grandes pero aún no han sido refactorizados:

1. **`walk_movement_handler.py`** (516 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece
2. **`use_item_consumable_handler.py`** (453 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece
3. **`left_click_tile_handler.py`** (394 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece
4. **`talk_clan_handler.py`** (358 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece
5. **`use_item_special_handler.py`** (292 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece
6. **`left_click_npc_handler.py`** (258 líneas) - Ya fue creado en refactorización anterior, pero podría dividirse más si crece

**Nota:** Estos handlers ya fueron creados como parte de refactorizaciones anteriores. Solo deberían refactorizarse más si crecen significativamente o si se identifica duplicación de código.

### Otros archivos grandes pendientes

1. **`map_resources_service.py`** — Ver sección 3.1 (modularizado en submódulos `src/services/map/`)
2. **`player_repository.py`** (1013 líneas) - Ver sección 3.2
3. **`clan_service.py`** (882 líneas) - Ver sección 3.3
4. **`party_service.py`** (726 líneas) - Ver sección 3.7
5. **`npc_death_service.py`** (638 líneas) - Ver sección 3.9

---

**Última actualización:** 2025-01-30
