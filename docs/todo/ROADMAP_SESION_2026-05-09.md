# Roadmap - Sesión 2026-05-09

Estado actual del proyecto tras la sesión de refactoring y análisis.

---

## ✅ Completado hoy

| # | Tema | Commit |
|---|------|--------|
| 1 | Refactor `PacketReaderMixin` (889→613 líneas) | `fb679e5` |
| 2 | Encapsular `MessageSender` (address, disconnect, is_ssl_enabled) | `3165841` |
| 3 | Wrappers en `RedisClient` (hget, hset, hgetall, etc.) | `db4bd5e` |
| 4 | Eliminar fugas Redis en handlers (active_merchant) | `db4bd5e` |
| 5 | `redis_initializer` usa `ServerRepository` | `56582ac` |
| 6 | `server.py` usa `redis.asyncio` | `56582ac` |
| 7 | Mover `run_tests.sh` → `scripts/checks.sh` | `2ad7297` |
| 8 | Fix 130 errores mypy | `f104c23` |
| 9 | Aumentar mana inicial a 50000 × int | `5ece0b6` |
| 10 | `ParalysisEffect` ahora inmoviliza jugadores | `44e76ec` |

---

## 🔴 Pendientes — Cliente Godot

### 1. Targeting de hechizos con cursor
**Doc:** `docs/todo/TODO_SPELL_CLICK_TARGETING.md`
**Estado:** Servidor listo, cliente NO implementa

- El servidor ya acepta `CAST_SPELL` con coordenadas (7 bytes)
- El cliente Godot **solo envía slot** (2 bytes) — nunca coordenadas
- Ningún fork (`jonathanhecl`, `cavazquez`, `Comunidad-Winter`) lo tiene
- Ver detalles en `TODO_SPELL_CLICK_TARGETING.md` (2 opciones de implementación)

### 2. Fork `jonathanhecl` más avanzado
**Repo:** `github.com/jonathanhecl/ArgentumOnlineGodot`
**Estado:** Evaluar merge/tomar features

Features extra vs el cliente original:
- `spell_macro_system.gd` — macros de hechizos
- `hotkey_config.gd` — configuración de hotkeys
- 30+ comandos de clanes completos
- `WriteMoveItem`, `WriteSafeToggle`, `WriteMoveBank`
- `WritePetStand/Follow/Release`
- `WriteResuscitate`, `WriteHeal`
- `WriteCraftBlacksmith/Carpenter`
- `WriteWorkLeftClick`, `WriteInvisible`, `WriteHiding`
- `WriteNavigateToggle`

### 3. Otros TODOs del cliente
**Doc:** `docs/todo/TODO_CLIENTE.md`
- Mostrar posición en GUI
- Indicador visual de ground items
- Feedback de acciones (sonido/animación)
- Panel de inventario con drag & drop
- Minimapa, panel de stats, chat mejorado

---

## 🟡 Pendientes — Servidor

### 4. Spell effects incompletos
**Archivo:** `src/services/player/spell_effects/status.py`

| Efecto | NPC | Jugador | Fix |
|--------|-----|---------|-----|
| `ParalysisEffect` | 10s ✅ | 30s ✅ (hecho hoy) | Listo |
| `ImmobilizeEffect` | ❌ | 30s ✅ | Debería afectar NPCs también |
| `BlindEffect` | ❌ | 10s ✅ | Debería afectar NPCs |
| `DumbEffect` | ❌ | 30s ✅ | Debería afectar NPCs |
| `PoisonEffect` | ✅ | ✅ | Listo |
| `CurePoisonEffect` | ✅ | ✅ | Listo |
| `RemoveParalysisEffect` | ✅ | ✅ | Listo |
| `RemoveDumbEffect` | ❌ | ✅ | Debería afectar NPCs |

### 5. Status effect packets al cliente
**Doc:** `docs/ANALISIS_CLIENTE_VB6_2026.md` (sección 1.1)

El servidor tiene los efectos server-side pero podría no estar enviando todos los packets visuales al cliente:

| Packet | ID | Estado |
|--------|----|--------|
| `BLIND` | 56 | Verificar si se envía al aplicar ceguera |
| `BLIND_NO_MORE` | 69 | Verificar si se envía al curar |
| `DUMB` | 57 | Verificar si se envía al aturdir |
| `DUMB_NO_MORE` | 70 | Verificar si se envía al curar |
| `SET_INVISIBLE` | 66 | Verificar |
| `PARALIZE_OK` | 82 | ✅ Se envía (ImmobilizeEffect + ParalysisEffect) |

### 6. `Inmovilizar` vs `Paralizar` — diferencia semántica
**Archivo:** `data/spells.toml`

| Spell | ID | Flag | Mana | Efecto VB6 |
|-------|----|------|------|-----------|
| Paralizar | 9 | `paralyzes = true` | 450 | No moverse NI actuar |
| Inmovilizar | 24 | `immobilizes = true` | 300 | No moverse (sí atacar/castear) |

Actualmente ambos solo inmovilizan. Para ser fiel al VB6, `Paralizar` debería también aplicar `dumb_until` (no castear).

### 7. PRs sin mergear en el cliente original
**Repo:** `brian-christopher/ArgentumOnlineGodot` — 10 PRs abiertos, 0 mergeados

| # | Título | Autor |
|---|--------|-------|
| 20 | fix: manejar timeout y reintentos | cavazquez |
| 19 | fix: username en /PARTY | cavazquez |
| 18 | feat: SSL opcional | cavazquez |
| 17 | feat: coordenadas en HUD | cavazquez |
| 16 | feat: mensaje al meditar con maná lleno | cavazquez |
| 15 | Soporte UTF-8 | cavazquez |
| 14 | Fix: emoji ojo en contraseña | cavazquez |
| 13 | *.import al .gitignore | cavazquez |
| 12 | Drag & Drop + mejor UI de guild | jonathanhecl |
| 11 | Sistema PING/PONG | cavazquez |

---

## 🔵 Refactoring pendiente

### 8. Archivos grandes por reducir
| Archivo | Líneas | Sugerencia |
|---------|--------|-----------|
| `clan_service.py` | 882 | Separar en membership/rank/creation services |
| `message_sender.py` | 850 | Delegar más a sub-senders |
| `player_repository.py` | 944 | Extraer mixins (stats, attributes, skills) |

### 9. `merchant_data_loader.py`
Usa `self.redis_client` directamente en vez de `MerchantRepository`. Agregar métodos `clear_inventory(npc_id)` y `set_items(npc_id, items)` al repo.

### 10. `redis_initializer.py`
Ya mejorado pero aún usa `redis_client.set("server:connections:count", "0")` directo — mover a `ServerRepository`.

---

## 📊 Orden sugerido

| Prioridad | Tema | Esfuerzo | Impacto |
|-----------|------|----------|---------|
| 🔴 1 | Cliente: targeting de hechizos | Alto | Alto |
| 🔴 2 | Evaluar merge del fork `jonathanhecl` | Medio | Alto |
| 🟡 3 | PRs sin mergear — considerar fork propio | Bajo | Medio |
| 🟡 4 | Spell effects en NPCs (blind, dumb, immobilize) | Bajo | Medio |
| 🟡 5 | Diferencia semántica Paralizar vs Inmovilizar | Bajo | Bajo |
| 🟡 6 | Status effect packets visuales al cliente | Bajo | Medio |
| 🔵 7 | Refactor `clan_service.py` | Alto | Medio |
| 🔵 8 | Refactor `player_repository.py` | Medio | Medio |
| 🔵 9 | `merchant_data_loader` → `MerchantRepository` | Bajo | Bajo |

---

## 📁 Archivos de referencia

| Documento | Contenido |
|-----------|-----------|
| `docs/todo/TODO_SPELL_CLICK_TARGETING.md` | Detalle completo del targeting de hechizos |
| `docs/todo/TODO_CLIENTE.md` | TODOs del cliente Godot |
| `docs/ANALISIS_CLIENTE_VB6_2026.md` | Análisis cruzado VB6 vs Godot vs PyAO |
| `docs/SPELL_ADVANCED_IMPLEMENTATION_PLAN.md` | Plan de spell effects |
| `docs/todo/ROADMAP_VERSIONES.md` | Roadmap de versiones |
| `docs/todo/TODO_CONSOLIDADO.md` | TODOs consolidados |
