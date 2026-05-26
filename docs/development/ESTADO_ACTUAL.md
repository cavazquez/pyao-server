# Estado Actual del Proyecto - PyAO Server

**Fecha:** 2026-05-26  
**Versión en pyproject.toml:** 0.9.4-alpha  
**Versión real completada:** 0.9.4-alpha (Refactor Arquitectura + modularización 2026-05)

---

## ✅ Sistemas Completados

### Versión 0.6.x (COMPLETADA)
- ✅ 0.6.0-alpha - IA de NPCs y Sistema de Trabajo
- ✅ 0.6.1-alpha - Tests faltantes
- ✅ 0.6.2-alpha - Refactor MapTransitionService
- ✅ 0.6.3-alpha - Validación de longitud de packets
- ✅ 0.6.4-alpha - Configuration Management

### Versión 0.7.0-alpha - Sistema de Clases ✅ COMPLETADO
**Estado:** Completado según `todo/TODO_CLASS_SYSTEM.md`
- ✅ Modelo CharacterClass
- ✅ ClassService con métodos de consulta
- ✅ Integración en creación de personaje
- ✅ 26 tests pasando

### Versión 0.8.0-alpha - Sistema de Parties ✅ COMPLETADO
**Estado:** Completado según `docs/systems/PARTY_SYSTEM.md`
- ✅ Modelos de datos (Party, PartyMember, PartyInvitation)
- ✅ Persistencia en Redis
- ✅ Lógica de negocio completa
- ✅ 7 handlers de packets
- ✅ Experiencia compartida automática
- ✅ Loot compartido
- ✅ Sincronización de level up
- ✅ 60 tests pasando

### Versión 0.9.0-alpha - Sistema de Clanes/Guilds ✅ COMPLETADO
**Estado:** Completado según `docs/systems/CLAN_SYSTEM.md`
- ✅ Modelos de datos (Clan, ClanMember, ClanInvitation)
- ✅ Persistencia en Redis
- ✅ Lógica de negocio completa
- ✅ 10 comandos implementados vía chat
- ✅ Sistema de rangos jerárquicos (MEMBER, OFFICER, VICE_LEADER, LEADER)
- ✅ Chat interno del clan (`/CLAN mensaje`)
- ✅ Gestión completa de miembros (invitar, expulsar, promover, degradar)
- ✅ Transferencia de liderazgo
- ✅ Tests básicos del servicio

### Versión 0.9.1-alpha - Mejoras del Sistema de Clanes ✅ COMPLETADO
- ✅ Notificaciones completas para todos los eventos
- ✅ Broadcast automático a todos los miembros del clan
- ✅ Tests ampliados (11 → 24 tests)
- ✅ Documentación completa (`docs/systems/CLAN_SYSTEM.md`)

### Versión 0.9.1-alpha - Sistema de Pociones ✅ COMPLETADO
- ✅ 6 tipos de pociones funcionando (HP, Mana, buffs, veneno, invisibilidad)
- ✅ Modificadores temporales con duración configurable
- ✅ Integración completa con inventario

### Versión 0.9.1-alpha - Mejoras de NPCs ✅ COMPLETADO
- ✅ Extracción de NPCs desde mapas VB6 (1,604 NPCs en 99 mapas)
- ✅ Sistema de mascotas/invocación (`/PET`)
- ✅ Scripts de extracción y limpieza de spawns

### Versión 0.9.2-alpha - Random Spawns y Sonidos ✅ COMPLETADO
- ✅ `RandomSpawnService` con límites multijugador y cooldowns
- ✅ Sonidos de NPCs (ataque, daño, muerte)
- ✅ Hechizo Mimetismo

### Versión 0.9.3-alpha - Refactor Stats y Tests ✅ COMPLETADO
- ✅ Dataclasses `PlayerStats` y `PlayerAttributes`
- ✅ Métodos tipados en `PlayerRepository`
- ✅ Ampliación de tests (clan tasks, cast spell handler)
- ✅ `scripts/checks.sh` con opciones CLI

### Versión 0.9.4-alpha - Refactor Arquitectura ✅ COMPLETADO
- ✅ `TaskFactory` → `HandlerRegistry` (-66%)
- ✅ `SpellService` → `spell_effects/` (-75%)

### Refactors adicionales (2026-05) ✅ COMPLETADO
- ✅ **`stats.get()`:** 0 usos en `src/` (migración completa)
- ✅ **`attributes.get()`:** migrado a helpers de `PlayerRepository`
- ✅ **`map_resources_service.py`:** submódulos en `src/services/map/`
- ✅ **`player_repository.py`:** mixins en `src/repositories/player_mixins/`
- ✅ **`clan_service.py`:** mixins en `src/services/clan/`
- ✅ **`packet_validator.py`:** fachada delgada (~274 líneas)
- ✅ **`message_sender.py`:** commerce/navigate en `InventoryMessageSender`
- ✅ **Documentación:** reorganización en subcarpetas (`guides/`, `systems/`, `development/`, etc.)

---

## 📋 Próximos Pasos (Según Prioridad)

### 🔴 ALTA PRIORIDAD - Próxima Versión (0.10.0-alpha)

#### Targeting por Click para Hechizos
**Esfuerzo:** ~1 semana  
**Nota:** Servidor ya acepta coordenadas en `CAST_SPELL`; el trabajo principal es en el cliente Godot.

**Features:**
- [ ] Click para seleccionar target en hechizos
- [ ] Cursor visual en modo targeting
- [ ] Cliente envía `CAST_SPELL` con coordenadas (x, y)
- [ ] Validación de rango antes de lanzar
- [ ] Cancelar targeting (ESC o click derecho)

**Archivos cliente Godot:**
- `ui/hub/spell_list_panel.gd`
- `screens/game_screen.gd`
- `engine/autoload/game_protocol.gd`

---

### 🟡 MEDIA PRIORIDAD - Refactoring restante

Ver [`REFACTORING.md`](REFACTORING.md) para detalle.

- [ ] `party_service.py` (~707 líneas) — split por dominio
- [ ] `npc_death_service.py` (~630 líneas) — death / exp / level up
- [ ] `use_item_handler.py` — handlers especializados adicionales si crece

**Ya completado (no repetir):**
- [x] `packet_validator.py`, `map_resources_service`, `player_repository`, `clan_service`, `message_sender`
- [x] `MapManager` ya delega en índices especializados (afinado futuro, no split inicial)

---

### 🟡 MEDIA PRIORIDAD - Clanes avanzados

- [ ] Almacén/depósito del clan
- [ ] Alianzas entre clanes
- [ ] Guerras de clanes
- [ ] Edificio del clan con NPCs

---

### 🟡 MEDIA PRIORIDAD - Calidad

#### Cobertura de tests
**Objetivo:** 80%+

**Progreso reciente:**
- [x] `tests/command_handlers/test_bank_item_handlers.py` — deposit/extract (éxito, vacío, rollback, inventario lleno)
- [x] `tests/services/test_commerce_service.py` — suite existente amplia

**Pendiente revisar:**
- [ ] Ramas sin cubrir en `commerce_service.py` (ejecutar `pytest --cov=src/services/commerce_service.py`)

#### Antipatrón stats/attributes
- [x] `stats.get()` — 0 usos en `src/`
- [x] `attributes.get()` — migrado (solo `.get()` residual en dict local de dados en `class_service.py`)

---

### 🟢 BAJA PRIORIDAD

- Helper `send_update_user_stats_from_repo` en `MessageSender`
- Reorganización de `tasks/` en subcarpetas (propuesta archivada)
- Roadmap 0.11+ (hechizos avanzados, facciones, quests, etc.)

---

## 📊 Resumen de Estado

### Versiones
- **Versión actual:** 0.9.4-alpha ✅
- **Próxima versión:** 0.10.0-alpha (Targeting por Click)

### Tests
- **Total:** 2154 tests
- **Pasando:** 100% ✅
- **Cobertura:** ~75% (objetivo 80%+)

### Calidad
- **Linting:** 0 errores ✅
- **Type checking:** 0 errores ✅
- **Documentación:** reorganizada en `docs/` con índice en `docs/README.md`

### Observabilidad
- Logs de login con mensajes destacados y colores por nivel (TTY)
- `LOG_COLOR=1` fuerza color; `NO_COLOR=1` lo desactiva

---

## 🎯 Recomendación Inmediata

1. **v0.10.0-alpha** — targeting por click (cliente Godot)
2. **Cobertura** — medir gaps en `commerce_service` tras suite de banco
3. **Refactor opcional** — `party_service` o `npc_death_service` si hay tiempo

---

**Última actualización:** 2026-05-26  
**Estado:** ✅ 0.9.4-alpha + refactors mayo 2026 completados; docs al día
