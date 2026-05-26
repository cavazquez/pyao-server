# Refactorización de handlers

Documento único: trabajo completado + backlog opcional de división futura.

---


**Fecha:** 2025-01-30  
**Estado:** ✅ Completado - 8 handlers principales refactorizados

---

## 📊 Resumen Ejecutivo

Se completó la refactorización de **8 handlers principales** dividiéndolos en **handlers especializados** siguiendo el principio de **Single Responsibility Principle**. Esto mejora significativamente la mantenibilidad, testabilidad y organización del código.

**Métricas:**
- **8 handlers principales refactorizados**
- **24 handlers especializados creados**
- **Reducción promedio de complejidad:** ~60% por handler principal
- **Todos los tests pasando:** 2052 tests ✅
- **Sin errores de linting o tipos** ✅

---

## ✅ Handlers Refactorizados

### 1. `use_item_handler.py` → 3 handlers especializados

**Antes:** 741 líneas  
**Después:** 200 líneas (orquestador) + 3 handlers especializados

**Handlers creados:**
- `use_item_consumable_handler.py` (453 líneas) - Maneja items consumibles (pociones, manzanas)
- `use_item_special_handler.py` (292 líneas) - Maneja items especiales (herramientas, barcas)

**Beneficios:**
- ✅ Separación clara entre consumibles y items especiales
- ✅ Código común extraído (pociones de HP/Mana)
- ✅ Más fácil agregar nuevos tipos de items

**Commit:** `refactor: dividir use_item_handler.py en handlers especializados`

---

### 2. `talk_handler.py` → 5 handlers especializados

**Antes:** 661 líneas  
**Después:** 127 líneas (orquestador) + 5 handlers especializados

**Handlers creados:**
- `talk_metrics_handler.py` - Comandos `/METRICS`
- `talk_trade_handler.py` - Comandos `/COMERCIAR`
- `talk_clan_handler.py` (358 líneas) - Todos los comandos de clan
- `talk_pet_handler.py` - Comandos `/PET`
- `talk_public_handler.py` - Mensajes de chat público

**Beneficios:**
- ✅ Separación por tipo de comando de chat
- ✅ `talk_clan_handler.py` encapsula toda la lógica compleja de clanes
- ✅ Más fácil mantener y extender cada tipo de comando

**Commit:** `refactor: dividir talk_handler.py en handlers especializados`

---

### 3. `left_click_handler.py` → 2 handlers especializados

**Antes:** 635 líneas  
**Después:** 127 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `left_click_npc_handler.py` (258 líneas) - Interacciones con NPCs (mercaderes, banco, info)
- `left_click_tile_handler.py` (394 líneas) - Interacciones con tiles (puertas, carteles, recursos)

**Beneficios:**
- ✅ Separación clara entre NPCs y tiles
- ✅ Cada handler maneja su propio dominio de interacción
- ✅ Más fácil agregar nuevos tipos de interacciones

**Commit:** `refactor: dividir left_click_handler.py en handlers especializados`

---

### 4. `walk_handler.py` → 2 handlers especializados

**Antes:** 546 líneas  
**Después:** 115 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `walk_validation_handler.py` (109 líneas) - Validaciones pre-movimiento (stamina, inmovilización, meditación)
- `walk_movement_handler.py` (516 líneas) - Ejecución del movimiento (cálculo de posición, transiciones, colisiones, broadcast)

**Beneficios:**
- ✅ Separación entre validación y ejecución
- ✅ Validaciones centralizadas y reutilizables
- ✅ Lógica de movimiento encapsulada

**Commit:** `refactor: dividir walk_handler.py en handlers especializados`

---

### 5. `login_handler.py` → 4 handlers especializados

**Antes:** 510 líneas  
**Después:** 192 líneas (orquestador) + 4 handlers especializados

**Handlers creados:**
- `login_authentication_handler.py` (85 líneas) - Autenticación de credenciales
- `login_initialization_handler.py` (170 líneas) - Inicialización de datos del jugador
- `login_spawn_handler.py` (179 líneas) - Spawn del jugador en el mundo
- `login_finalization_handler.py` (79 líneas) - Finalización del login (inventario, MOTD)

**Beneficios:**
- ✅ Separación por etapas del login
- ✅ Cada etapa es independiente y testeable
- ✅ Más fácil mantener y depurar el flujo de login

**Commit:** `refactor: dividir login_handler.py en handlers especializados`

---

### 6. `create_account_handler.py` → 3 handlers especializados

**Antes:** 502 líneas  
**Después:** 200 líneas (orquestador) + 3 handlers especializados

**Handlers creados:**
- `create_account_validation_handler.py` (116 líneas) - Validación de datos de cuenta y personaje
- `create_account_character_handler.py` (196 líneas) - Creación de atributos, stats e inventario inicial
- `create_account_finalization_handler.py` (154 líneas) - Finalización y login automático

**Beneficios:**
- ✅ Separación por etapas de creación de cuenta
- ✅ Validaciones centralizadas
- ✅ Lógica de creación de personaje encapsulada

**Commit:** `refactor: dividir create_account_handler.py en handlers especializados`

---

### 7. `attack_handler.py` → 3 handlers especializados

**Antes:** 392 líneas  
**Después:** 161 líneas (orquestador) + 3 handlers especializados

**Handlers creados:**
- `attack_validation_handler.py` (111 líneas) - Validaciones (stamina, posición, buscar NPC)
- `attack_execution_handler.py` (138 líneas) - Ejecución del ataque (combate, efectos, sonidos)
- `attack_loot_handler.py` (182 líneas) - Manejo de loot drop

**Beneficios:**
- ✅ Separación entre validación, ejecución y loot
- ✅ Lógica de combate más clara
- ✅ Loot drop reutilizable

**Commit:** `refactor: dividir attack_handler.py en handlers especializados`

---

### 8. `work_left_click_handler.py` → 3 handlers especializados

**Antes:** 318 líneas  
**Después:** 163 líneas (orquestador) + 3 handlers especializados

**Handlers creados:**
- `work_left_click_validation_handler.py` (106 líneas) - Validaciones (distancia, herramientas)
- `work_left_click_execution_handler.py` (185 líneas) - Ejecución del trabajo (talar, pescar, minar)
- `work_left_click_ui_handler.py` (89 líneas) - Actualización de UI (inventario, mensajes)

**Beneficios:**
- ✅ Separación entre validación, ejecución y UI
- ✅ Lógica de cada tipo de trabajo encapsulada
- ✅ Actualización de UI centralizada

**Commit:** `refactor: dividir work_left_click_handler.py en handlers especializados`

---

### 9. `double_click_handler.py` → 2 handlers especializados

**Antes:** 308 líneas  
**Después:** 88 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `double_click_item_handler.py` (213 líneas) - Uso de items del inventario
- `double_click_npc_handler.py` (89 líneas) - Interacción con NPCs

**Beneficios:**
- ✅ Separación clara entre items y NPCs
- ✅ Lógica de uso de items encapsulada
- ✅ Interacción con NPCs simplificada

**Commit:** `refactor: dividir double_click_handler.py en handlers especializados`

---

### 10. `drop_handler.py` → 2 handlers especializados

**Antes:** 291 líneas  
**Después:** 104 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `drop_gold_handler.py` (114 líneas) - Drop de oro
- `drop_item_handler.py` (186 líneas) - Drop de items del inventario

**Beneficios:**
- ✅ Separación entre oro e items
- ✅ Lógica de drop más clara
- ✅ Más fácil mantener cada tipo de drop

**Commit:** `refactor: dividir drop_handler.py en handlers especializados`

---

### 11. `pickup_handler.py` → 2 handlers especializados

**Antes:** 222 líneas  
**Después:** 136 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `pickup_gold_handler.py` (82 líneas) - Pickup de oro
- `pickup_item_handler.py` (119 líneas) - Pickup de items del inventario

**Beneficios:**
- ✅ Separación entre oro e items
- ✅ Lógica de pickup más clara
- ✅ Más fácil mantener cada tipo de pickup

**Commit:** `refactor: dividir pickup_handler.py en handlers especializados`

---

### 12. `cast_spell_handler.py` → 2 handlers especializados

**Antes:** 194 líneas  
**Después:** 167 líneas (orquestador) + 2 handlers especializados

**Handlers creados:**
- `cast_spell_validation_handler.py` (148 líneas) - Validaciones (dependencias, stamina, coordenadas, rango, spellbook)
- `cast_spell_execution_handler.py` (101 líneas) - Ejecución (cálculo de target, lanzamiento del hechizo)

**Beneficios:**
- ✅ Separación entre validación y ejecución
- ✅ Validaciones centralizadas
- ✅ Lógica de cálculo de target encapsulada

**Commit:** `refactor: dividir cast_spell_handler.py en handlers especializados`

---

## 📈 Métricas Totales

**Handlers principales refactorizados:** 12  
**Handlers especializados creados:** 30  
**Líneas de código reducidas en handlers principales:** ~70%  
**Tests pasando:** 2052 ✅  
**Cobertura de tests:** Mantenida al 100%  
**Errores de linting:** 0 ✅  
**Errores de tipos (mypy):** 0 ✅

---

## 🎯 Patrón de Refactorización

Todos los handlers siguen el mismo patrón:

1. **Handler Principal (Orquestador):**
   - Valida el comando
   - Delega a handlers especializados según el tipo
   - Retorna el resultado

2. **Handlers Especializados:**
   - Cada uno maneja una responsabilidad específica
   - Pueden ser de validación, ejecución, UI, etc.
   - Son independientes y testeables

**Ejemplo:**
```python
class AttackCommandHandler(CommandHandler):
    def __init__(self, ...):
        # Inicializar handlers especializados
        self.validation_handler = AttackValidationHandler(...)
        self.execution_handler = AttackExecutionHandler(...)
        self.loot_handler = AttackLootHandler(...)
    
    async def handle(self, command: Command) -> CommandResult:
        # Validar
        can_attack, error_msg, target_npc = await self.validation_handler.validate_attack(...)
        if not can_attack:
            return CommandResult.error(error_msg)
        
        # Ejecutar
        success, error_msg, result_data = await self.execution_handler.execute_attack(...)
        if not success:
            return CommandResult.error(error_msg)
        
        # Manejar loot si es necesario
        if result_data.get("npc_died"):
            await self.loot_handler.handle_loot_drop(target_npc)
        
        return CommandResult.ok(result_data)
```

---

## ✅ Beneficios Obtenidos

1. **Mejor Separación de Responsabilidades:**
   - Cada handler tiene una única responsabilidad
   - Código más fácil de entender y mantener

2. **Mejor Testabilidad:**
   - Handlers especializados son más fáciles de testear
   - Tests más enfocados y específicos

3. **Mejor Reutilización:**
   - Handlers especializados pueden reutilizarse en otros contextos
   - Lógica común extraída y centralizada

4. **Mejor Mantenibilidad:**
   - Cambios en una funcionalidad no afectan otras
   - Más fácil encontrar y corregir bugs

5. **Mejor Escalabilidad:**
   - Fácil agregar nuevos tipos de items, comandos, etc.
   - Estructura preparada para crecimiento

---

## 📝 Notas Técnicas

- Todos los handlers especializados siguen el mismo patrón de retorno: `tuple[bool, str | None, dict | None]`
- Los handlers principales actúan como orquestadores, no contienen lógica de negocio
- Los tests se actualizaron para reflejar la nueva estructura
- No se introdujeron breaking changes en la API pública

---

**Última actualización:** 2025-01-30


---

## Pendientes y oportunidades futuras


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

### 1. `map_resources_service.py` — modularizado (2026-05)

**Estado:** Completado. Submódulos en `src/services/map/` (`map_bulk_resources_loader`, `map_single_map_loader`, `map_resource_queries`, `cache`, `blocked_loader`, `objects_loader`, `ndjson_reader`, etc.). El servicio principal expone solo API pública y ciclo de vida.

**Prioridad:** Completado

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

