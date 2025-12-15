# Oportunidades de Refactorización

**Fecha:** 2025-01-30  
**Estado:** Análisis completo

---

## 📊 Resumen Ejecutivo

Se identificaron **5 áreas principales** de refactorización con diferentes niveles de prioridad y esfuerzo.

---

## 🔴 Prioridad Alta

### 1. Eliminar Acceso Directo a `stats.get()` en Servicios

**Problema:**
- **100 usos** de `stats.get()` en 8 archivos de servicios
- Duplicación de conocimiento del formato de datos
- Falta de type safety
- Propenso a errores de typos en keys

**Archivos afectados:**
1. `services/npc/npc_ai_service.py` - 21 usos
2. `services/combat/combat_service.py` - 26 usos
3. `services/npc/npc_death_service.py` - 26 usos
4. `services/player/player_death_service.py` - 13 usos
5. `services/party_service.py` - 5 usos
6. `services/player/spell_effects/healing.py` - 4 usos
7. `services/player/spell_effects/damage.py` - 3 usos
8. `services/player/spell_service.py` - 2 usos

**Solución:**
Reemplazar con métodos helper de `PlayerRepository`:
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

#### 3.1 `map_resources_service.py` (1094 líneas)
**Problema:** Muy grande, múltiples responsabilidades  
**Solución:** Dividir en:
- `map_resources_loader.py` - Carga de datos
- `map_resources_cache.py` - Sistema de caché
- `map_resources_validator.py` - Validación

**Esfuerzo:** Alto (4-6 horas)  
**Beneficio:** Alto

#### 3.2 `player_repository.py` (1013 líneas)
**Problema:** Muchos métodos, podría dividirse por dominio  
**Solución:** Mantener como está (Repository Pattern típico) o dividir en:
- `player_stats_repository.py` - Stats y atributos
- `player_position_repository.py` - Posición y heading
- `player_status_repository.py` - Estados (poison, blind, etc.)

**Esfuerzo:** Alto (4-6 horas)  
**Beneficio:** Medio (puede complicar el código)

#### 3.3 `clan_service.py` (882 líneas)
**Problema:** Mucha lógica de negocio  
**Solución:** Dividir en:
- `clan_management_service.py` - Crear, eliminar, modificar
- `clan_membership_service.py` - Invitar, aceptar, expulsar
- `clan_leadership_service.py` - Promover, degradar, transferir

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto

#### 3.4 `packet_validator.py` (865 líneas)
**Problema:** Muchos validadores en un solo archivo  
**Solución:** Ya está dividido en `network/validators/` ✅  
**Estado:** Ya refactorizado

#### 3.5 `message_sender.py` (766 líneas)
**Problema:** Facade muy grande  
**Solución:** Ya está dividido en `messaging/senders/` ✅  
**Estado:** Ya refactorizado

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
Reorganizar tasks en subcarpetas según `PROPOSED_CODE_ORGANIZATION.md`:
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

1. ✅ `drop_handler.py` - Reemplazado `stats.get()` con métodos helper
2. ✅ `pickup_handler.py` - Reemplazado `stats.get()` con métodos helper
3. ✅ `msg.py` - Dividido en 8 módulos especializados
4. ✅ `server.py` - Refactorizado en initializers
5. ✅ `task_factory.py` - Refactorizado con handler_registry
6. ✅ `spell_service.py` - Dividido en spell_effects/
7. ✅ `packet_validator.py` - Dividido en validators/
8. ✅ `message_sender.py` - Dividido en senders/

---

**Última actualización:** 2025-01-30
