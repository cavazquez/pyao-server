# Refactorización de Handlers - Pendiente

**Fecha:** 2025-01-30  
**Estado:** 📋 Pendiente

---

## 📊 Resumen

Este documento lista los handlers y archivos relacionados que aún podrían beneficiarse de refactorización adicional, pero que no son críticos en este momento.

---

## 🔍 Handlers que Podrían Refactorizarse Más

Los siguientes handlers ya fueron creados como parte de refactorizaciones anteriores, pero podrían dividirse más si crecen o si se identifica duplicación:

### 1. `walk_movement_handler.py` (516 líneas)

**Estado:** Ya fue creado en refactorización de `walk_handler.py`  
**Posible división futura:**
- `walk_position_calculator.py` - Cálculo de nuevas posiciones
- `walk_map_transition_handler.py` - Manejo de transiciones de mapa
- `walk_collision_handler.py` - Validación de colisiones
- `walk_broadcast_handler.py` - Broadcast de movimiento

**Prioridad:** 🟢 Baja (solo si crece significativamente)

---

### 2. `use_item_consumable_handler.py` (453 líneas)

**Estado:** Ya fue creado en refactorización de `use_item_handler.py`  
**Posible división futura:**
- `use_item_potion_handler.py` - Manejo de pociones (HP, Mana, atributos)
- `use_item_food_handler.py` - Manejo de comida (manzanas, etc.)

**Prioridad:** 🟢 Baja (solo si se agregan muchos tipos nuevos de consumibles)

---

### 3. `left_click_tile_handler.py` (394 líneas)

**Estado:** Ya fue creado en refactorización de `left_click_handler.py`  
**Posible división futura:**
- `left_click_door_handler.py` - Manejo de puertas
- `left_click_sign_handler.py` - Manejo de carteles
- `left_click_resource_handler.py` - Manejo de recursos del mapa

**Prioridad:** 🟢 Baja (solo si se agregan muchos tipos nuevos de interacciones con tiles)

---

### 4. `talk_clan_handler.py` (358 líneas)

**Estado:** Ya fue creado en refactorización de `talk_handler.py`  
**Posible división futura:**
- `talk_clan_management_handler.py` - Crear, eliminar, modificar clanes
- `talk_clan_membership_handler.py` - Invitar, aceptar, rechazar, expulsar
- `talk_clan_leadership_handler.py` - Promover, degradar, transferir liderazgo
- `talk_clan_messaging_handler.py` - Mensajes de clan

**Prioridad:** 🟡 Media (si el sistema de clanes se expande significativamente)

---

### 5. `use_item_special_handler.py` (292 líneas)

**Estado:** Ya fue creado en refactorización de `use_item_handler.py`  
**Posible división futura:**
- `use_item_tool_handler.py` - Manejo de herramientas de trabajo
- `use_item_boat_handler.py` - Manejo de barcas

**Prioridad:** 🟢 Baja (solo si se agregan muchos tipos nuevos de items especiales)

---

### 6. `left_click_npc_handler.py` (258 líneas)

**Estado:** Ya fue creado en refactorización de `left_click_handler.py`  
**Posible división futura:**
- `left_click_merchant_handler.py` - Abrir ventana de comercio
- `left_click_banker_handler.py` - Abrir ventana de banco
- `left_click_npc_info_handler.py` - Mostrar información de NPC

**Prioridad:** 🟢 Baja (solo si se agregan muchos tipos nuevos de NPCs interactivos)

---

## 📋 Otros Archivos Grandes Pendientes

### 1. `map_resources_service.py` (1094 líneas)

**Problema:** Muy grande, múltiples responsabilidades  
**Solución propuesta:** Dividir en:
- `map_resources_loader.py` - Carga de datos
- `map_resources_cache.py` - Sistema de caché
- `map_resources_validator.py` - Validación

**Esfuerzo:** Alto (4-6 horas)  
**Beneficio:** Alto  
**Prioridad:** 🟡 Media

---

### 2. `player_repository.py` (1013 líneas)

**Problema:** Muchos métodos, podría dividirse por dominio  
**Solución propuesta:** Mantener como está (Repository Pattern típico) o dividir en:
- `player_stats_repository.py` - Stats y atributos
- `player_position_repository.py` - Posición y heading
- `player_status_repository.py` - Estados (poison, blind, etc.)

**Esfuerzo:** Alto (4-6 horas)  
**Beneficio:** Medio (puede complicar el código)  
**Prioridad:** 🟢 Baja (solo si se vuelve difícil de mantener)

---

### 3. `clan_service.py` (882 líneas)

**Problema:** Mucha lógica de negocio  
**Solución propuesta:** Dividir en:
- `clan_management_service.py` - Crear, eliminar, modificar
- `clan_membership_service.py` - Invitar, aceptar, expulsar
- `clan_leadership_service.py` - Promover, degradar, transferir

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto  
**Prioridad:** 🟡 Media

---

### 4. `party_service.py` (726 líneas)

**Problema:** Mucha lógica de negocio  
**Solución propuesta:** Dividir en:
- `party_management_service.py` - Crear, disolver
- `party_membership_service.py` - Unirse, salir, expulsar
- `party_experience_service.py` - Distribución de EXP

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto  
**Prioridad:** 🟡 Media

---

### 5. `npc_death_service.py` (638 líneas)

**Problema:** Mucha lógica de muerte y experiencia  
**Solución propuesta:** Dividir en:
- `npc_death_handler.py` - Manejo de muerte
- `experience_distribution_service.py` - Distribución de EXP
- `level_up_service.py` - Manejo de level up

**Esfuerzo:** Medio (3-4 horas)  
**Beneficio:** Medio-Alto  
**Prioridad:** 🟡 Media

---

## 🎯 Recomendaciones

### Prioridad Alta
Ninguna en este momento. Los handlers principales ya fueron refactorizados.

### Prioridad Media
1. **`clan_service.py`** - Si el sistema de clanes se expande
2. **`party_service.py`** - Si el sistema de parties se expande
3. **`npc_death_service.py`** - Si se agregan más características de muerte/experiencia
4. **`map_resources_service.py`** - Si se vuelve difícil de mantener

### Prioridad Baja
1. Handlers especializados que ya fueron creados (solo si crecen significativamente)
2. **`player_repository.py`** - Solo si se vuelve difícil de mantener

---

## 📝 Notas

- Los handlers especializados creados en refactorizaciones anteriores están bien organizados y no requieren refactorización adicional a menos que crezcan significativamente
- La prioridad es mantener el código funcionando y agregar nuevas características
- Las refactorizaciones futuras deben justificarse por necesidad real, no solo por tamaño

---

**Última actualización:** 2025-01-30

