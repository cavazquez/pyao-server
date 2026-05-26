# Plan de Implementación - Sistema de Hechizos Avanzados

**Fecha:** 2025-01-31  
**Versión Objetivo:** v0.11.0-alpha  
**Estado:** 📋 Planificación

---

## 📊 Análisis del Estado Actual

### ✅ Lo que ya está implementado:

1. **Sistema básico de hechizos:**
   - 11 hechizos básicos (de 46 totales)
   - Casteo de hechizos (daño directo)
   - Validación de mana/stamina
   - Efectos visuales (FX)
   - Paralización de NPCs (básico)

2. **Tipos de hechizos soportados:**
   - Tipo 1: Daño/Curar HP básico
   - Tipo 2: Estados básicos (paralización)

### ❌ Lo que falta implementar:

1. **Efectos de estado faltantes:**
   - ❌ Envenenamiento (Envenena=1)
   - ❌ Inmovilización (Inmoviliza=1)
   - ❌ Ceguera (Ceguera=1)
   - ❌ Estupidez (Estupidez=1)
   - ❌ Remover estados (RemoverParalisis, RemoverEstupidez)
   - ❌ Invisibilidad (Invisibilidad=1)
   - ❌ Remover invisibilidad parcial

2. **Tipos de hechizos faltantes:**
   - ❌ Tipo 3: Invocación (Invoca=1)
   - ❌ Tipo 4: Materialización (Materializa=1)
   - ❌ Tipo 5: Metamorfosis (Mimetiza=1)

3. **Funcionalidades avanzadas:**
   - ❌ Hechizos de área (AOE)
   - ❌ Hechizos sobre terreno (Target=4)
   - ❌ Curación sobre otros jugadores
   - ❌ Resucitación (Revivir=1)
   - ❌ Sistema de runas y componentes
   - ❌ Escuelas de magia (Fuego, Agua, Tierra, Aire, etc.)

4. **Hechizos faltantes:**
   - Solo 11/46 hechizos implementados
   - Faltan 35 hechizos por importar

---

## 📋 Plan de Implementación por Fases

### Fase 1: Importar Todos los Hechizos (Prioridad Alta) ✅ COMPLETADO

**Objetivo:** Tener todos los 46 hechizos del VB6 en el servidor.

**Tareas:**
1. ✅ Crear script para extraer todos los hechizos de `Hechizos.dat`
2. ✅ Convertir a formato TOML
3. ✅ Agregar a `data/spells.toml`
4. ✅ Verificar que el catálogo los carga correctamente

**Archivos creados/modificados:**
- ✅ `tools/extraction/extract_all_spells.py` - Script de extracción
- ✅ `data/spells.toml` - Expandido de 11 a 46 hechizos (908 líneas)

**Resultados:**
- ✅ 46/46 hechizos importados correctamente
- ✅ Sin duplicados
- ✅ Todos los campos mapeados correctamente
- ✅ Efectos especiales identificados (envenenamiento, paralización, invocación, etc.)

**Criterio de éxito:** ✅ 46 hechizos cargados en el servidor.

---

### Fase 2: Efectos de Estado Completos (Prioridad Alta)

**Objetivo:** Implementar todos los efectos de estado del VB6.

#### 2.1 Envenenamiento

**Campos del hechizo:**
- `Envenena=1` - Activa envenenamiento

**Implementación:**
1. Agregar campo `poisoned_until: float` a modelo `Player`
2. Agregar método `update_player_poisoned_until()` en `PlayerRepository`
3. Crear efecto periódico `PoisonEffect` que reduzca HP cada tick
4. Aplicar envenenamiento en `SpellService` cuando `Envenena=1`
5. Chequear envenenamiento en `NPCAIService` para prevenir ataques (opcional)

**Archivos a crear/modificar:**
- `src/models/player.py` - Agregar campo
- `src/repositories/player_repository.py` - Método de actualización
- `src/effects/poison_effect.py` - Efecto periódico
- `src/services/player/spell_service.py` - Aplicar envenenamiento

---

#### 2.2 Inmovilización

**Campos del hechizo:**
- `Inmoviliza=1` - Activa inmovilización

**Implementación:**
1. Agregar campo `immobilized_until: float` a modelo `Player`
2. Agregar método `update_player_immobilized_until()` en `PlayerRepository`
3. Chequear inmovilización en `TaskWalk` para prevenir movimiento
4. Aplicar inmovilización en `SpellService` cuando `Inmoviliza=1`

**Archivos a crear/modificar:**
- `src/models/player.py` - Agregar campo
- `src/repositories/player_repository.py` - Método de actualización
- `src/tasks/player/task_walk.py` - Chequear antes de mover
- `src/services/player/spell_service.py` - Aplicar inmovilización

---

#### 2.3 Ceguera

**Campos del hechizo:**
- `Ceguera=1` - Activa ceguera

**Implementación:**
1. Agregar campo `blinded_until: float` a modelo `Player`
2. Agregar método `update_player_blinded_until()` en `PlayerRepository`
3. Efecto: Reducir rango de visión (opcional, puede ser solo visual)
4. Aplicar ceguera en `SpellService` cuando `Ceguera=1`

**Archivos a crear/modificar:**
- `src/models/player.py` - Agregar campo
- `src/repositories/player_repository.py` - Método de actualización
- `src/services/player/spell_service.py` - Aplicar ceguera

---

#### 2.4 Estupidez

**Campos del hechizo:**
- `Estupidez=1` - Activa estupidez

**Implementación:**
1. Agregar campo `dumb_until: float` a modelo `Player`
2. Agregar método `update_player_dumb_until()` en `PlayerRepository`
3. Efecto: Prevenir lanzar hechizos (chequear en `TaskCastSpell`)
4. Aplicar estupidez en `SpellService` cuando `Estupidez=1`

**Archivos a crear/modificar:**
- `src/models/player.py` - Agregar campo
- `src/repositories/player_repository.py` - Método de actualización
- `src/tasks/spells/task_cast_spell.py` - Chequear antes de lanzar
- `src/services/player/spell_service.py` - Aplicar estupidez

---

#### 2.5 Remover Estados

**Campos del hechizo:**
- `RemoverParalisis=1`
- `RemoverEstupidez=1`
- `CuraVeneno=1` (ya existe básico, mejorar)

**Implementación:**
1. Métodos helper en `SpellService` para remover cada estado
2. Llamarlos cuando el hechizo correspondiente se lance
3. Actualizar flags en Redis

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Métodos para remover estados

---

### Fase 3: Curación sobre Otros Jugadores (Prioridad Alta)

**Objetivo:** Permitir curar a otros jugadores (no solo NPCs).

**Campos del hechizo:**
- `SubeHP=1` - Cura HP
- `Target=3` - Usuario Y NPC (ya soportado)

**Implementación:**
1. Modificar `SpellService.cast_spell()` para buscar jugadores en la posición objetivo
2. Si hay jugador, aplicar curación en lugar de daño
3. Validar que no sea auto-curación si el hechizo no lo permite
4. Enviar mensajes tanto al caster como al target

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Buscar jugadores en target
- `src/repositories/player_repository.py` - Métodos para curar HP

---

### Fase 4: Hechizos de Área (AOE) (Prioridad Media)

**Objetivo:** Hechizos que afectan múltiples objetivos en un área.

**Nota:** El VB6 no tiene un campo explícito de "AOE", pero algunos hechizos afectan área (ej: Apocalipsis).

**Implementación:**
1. Agregar campo `area_radius: int` a hechizos en TOML
2. Modificar `SpellService.cast_spell()` para buscar todos los objetivos en radio
3. Aplicar efecto a cada objetivo encontrado
4. Validar rango máximo para cada objetivo

**Archivos a crear/modificar:**
- `data/spells.toml` - Agregar campo `area_radius`
- `src/services/player/spell_service.py` - Lógica de AOE

---

### Fase 5: Hechizos de Invocación (Prioridad Media)

**Objetivo:** Hechizos que invocan NPCs aliados.

**Campos del hechizo:**
- `Tipo=3` - Tipo invocación
- `Invoca=1` - Activa invocación
- `NumNpc=<ID>` - ID del NPC a invocar
- `Cant=<número>` - Cantidad de NPCs a invocar

**Implementación:**
1. Crear servicio `SummonService` para gestionar invocaciones
2. Agregar límite de mascotas por jugador (`MAX_PETS = 5`)
3. Modificar `SpellService` para detectar hechizos de invocación
4. Usar `NPCService` para spawnear NPCs aliados
5. Marcar NPCs como mascotas del jugador
6. Sistema de despawn automático tras tiempo límite

**Archivos a crear:**
- `src/services/summon_service.py`
- `src/repositories/summon_repository.py`
- `src/models/summon.py`

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Detectar tipo 3
- `src/models/npc.py` - Agregar campo `master_user_id`

---

### Fase 6: Hechizos de Materialización (Prioridad Baja)

**Objetivo:** Hechizos que crean items en el terreno.

**Campos del hechizo:**
- `Tipo=4` - Tipo materialización
- `Materializa=1` - Activa materialización
- `itemindex=<ID>` - ID del item a materializar
- `Target=4` - Terreno

**Implementación:**
1. Modificar `SpellService` para detectar tipo 4
2. Usar `MapManager` para agregar ground item
3. Validar que la posición esté disponible
4. Broadcast `OBJECT_CREATE` a jugadores cercanos

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Detectar tipo 4
- `src/game/map_manager.py` - Agregar ground item

---

### Fase 7: Resucitación (Prioridad Alta)

**Objetivo:** Hechizos que reviven jugadores muertos.

**Campos del hechizo:**
- `Revivir=1` - Activa resucitación
- `Target=1` - Usuario (solo sobre otros, no sobre uno mismo)

**Implementación:**
1. Verificar que el target esté muerto (HP = 0)
2. Revivir con HP parcial (50% o configurable)
3. Restaurar posición en último punto seguro
4. Enviar mensajes al caster y al revivido

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Lógica de resucitación
- `src/repositories/player_repository.py` - Métodos para revivir

---

### Fase 8: Invisibilidad (Prioridad Media)

**Objetivo:** Hechizos que hacen invisible al jugador.

**Campos del hechizo:**
- `Invisibilidad=1` - Activa invisibilidad

**Nota:** El sistema de invisibilidad es complejo y requiere:
- Flags en jugador
- Broadcast a otros jugadores para ocultar/mostrar
- Validación en NPCs para no detectar invisibles

**Implementación:**
1. Agregar campo `invisible_until: float` a modelo `Player`
2. Crear servicio `InvisibilityService` para gestionar visibilidad
3. Modificar broadcast de jugadores para omitir invisibles
4. Chequear invisibilidad en `NPCAIService`

**Archivos a crear:**
- `src/services/invisibility_service.py`
- `src/models/player.py` - Agregar campo

**Archivos a modificar:**
- `src/services/player/spell_service.py` - Aplicar invisibilidad
- `src/services/map/player_map_service.py` - Omitir invisibles en broadcast

---

## 🎯 Priorización Recomendada

### Sprint 1 (1-2 semanas) - Funcionalidades Core
1. ✅ Importar todos los 46 hechizos
2. ✅ Efectos de estado completos (envenenar, inmovilizar)
3. ✅ Curación sobre otros jugadores
4. ✅ Resucitación

### Sprint 2 (1 semana) - Efectos Avanzados
5. ✅ Ceguera y estupidez
6. ✅ Remover estados
7. ✅ Mejorar sistema de envenenamiento con efecto periódico

### Sprint 3 (2 semanas) - Features Avanzadas
8. ✅ Hechizos de invocación
9. ✅ Invisibilidad

### Sprint 4 (1 semana) - Polish
10. ✅ Hechizos de área (AOE)
11. ✅ Hechizos de materialización
12. ✅ Tests completos

---

## 📊 Métricas de Éxito

- [ ] 46/46 hechizos importados y cargados
- [ ] 100% de efectos de estado implementados
- [ ] Tests de todos los efectos de estado (100% cobertura)
- [ ] Documentación completa actualizada
- [ ] Compatibilidad con protocolo VB6 mantenida

---

## 🔗 Referencias

- **Hechizos.dat:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Dat/Hechizos.dat`
- **VB6 Code:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/modHechizos.bas`
- **Sistema Actual:** `src/services/player/spell_service.py`
- **Documentación:** `docs/systems/MAGIC_SYSTEM.md`

---

**Última actualización:** 2025-01-31  
**Estado:** 📋 Plan de implementación listo para ejecutar

