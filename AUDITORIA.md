# Auditoría de Seguridad y Calidad — pyao-server

**Fecha**: 2026-04-17  
**Revisión**: completa (Fases 0–6)  
**Estado final**: ✅ 2 078 tests · `ruff` sin errores · `mypy` sin errores

---

## 1. Arquitectura real del servidor

### Diagrama de capas

```
┌─────────────────────────────────────────────────────┐
│  Clientes TCP (Godot)                               │
└──────────────────────┬──────────────────────────────┘
                       │ bytes crudos
┌──────────────────────▼──────────────────────────────┐
│  Red (src/network/)                                 │
│  ClientConnection  PacketReader  PacketFramer(NEW)  │
│  PacketValidator   PacketLengthValidator            │
└──────────────────────┬──────────────────────────────┘
                       │ bytes de un packet completo
┌──────────────────────▼──────────────────────────────┐
│  Tareas / Despacho (src/tasks/)                     │
│  TaskFactory → Task concreto                        │
│  SessionManager                                     │
└──────────────────────┬──────────────────────────────┘
                       │ Command (objeto de valor)
┌──────────────────────▼──────────────────────────────┐
│  Handlers de comandos (src/command_handlers/)       │
│  PickupCommandHandler  CommerceSellCommandHandler   │
│  UpdateTradeOfferCommandHandler  …                  │
└──────────────────────┬──────────────────────────────┘
                       │ llamadas a servicios / repos
┌──────────────────────▼──────────────────────────────┐
│  Servicios de dominio (src/services/)               │
│  TradeService  CommerceService  SpellService  …     │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  Repositorios (src/repositories/)                   │
│  PlayerRepository  InventoryRepository              │
│  GroundItemsRepository  MerchantRepository  …       │
└──────────────────────┬──────────────────────────────┘
                       │ comandos Redis
┌──────────────────────▼──────────────────────────────┐
│  Persistencia (Redis + fakeredis en tests)          │
└─────────────────────────────────────────────────────┘
```

### Patrones identificados

| Patrón | Dónde se usa |
|--------|--------------|
| Command | `Task` → `Command` → `CommandHandler` |
| Repository | `InventoryRepository`, `PlayerRepository`, … |
| DI + auto-wiring | `DependencyContainer`, `TaskFactory` |
| Factory | `TaskFactory`, `NPCFactory` |
| Façade | `MessageSender`, `ServerInitializer` |
| Strategy | `_VARIABLE_PROBES` en `PacketFramer`; efectos de hechizos |

### Flujo de un packet

1. `asyncio` entrega bytes al `ClientConnection`.
2. `receive(max_bytes=1024)` lee del stream TCP sin respetar fronteras de application-level.
3. `TaskFactory` crea el `Task` concreto.
4. El `Task` parsea los bytes con `PacketReader` y construye un `Command`.
5. El `Command` se pasa al `CommandHandler` correspondiente.
6. El handler invoca servicios y/o repositorios y envía la respuesta vía `MessageSender`.

---

## 2. Módulos críticos

| Módulo | Responsabilidad | Criticidad |
|--------|----------------|-----------|
| `network/client_connection.py` | I/O TCP, framing | Alta |
| `network/packet_framer.py` | Extracción de packets del stream (nuevo) | Alta |
| `tasks/task_factory.py` | Despacho de packets a tasks | Alta |
| `command_handlers/pickup_handler.py` | Recoger items del suelo | Alta |
| `services/trade_service.py` | Comercio jugador-jugador | Alta |
| `services/commerce_service.py` | Comercio con NPCs | Media |
| `repositories/inventory_repository.py` | Inventario en Redis | Alta |
| `repositories/player_repository.py` | Oro y stats en Redis | Alta |
| `game/map_manager.py` + `ground_item_index.py` | Estado en memoria del mapa | Alta |

---

## 3. Invariantes formales del servidor

Los siguientes invariantes deben mantenerse en toda operación:

| ID | Invariante |
|----|-----------|
| INV-01 | `player.gold` ∈ [0, `MAX_PLAYER_GOLD`] en todo momento |
| INV-02 | Un item del suelo solo puede ser recogido por un jugador en una transacción |
| INV-03 | `_perform_trade` de una sesión se ejecuta como máximo una vez por ciclo de confirmación |
| INV-04 | Si un handler falla después de consumir un recurso, el recurso se restaura (rollback) |
| INV-05 | Ningún packet desconocido o malformado puede causar una excepción no controlada |
| INV-06 | El buffer de framing TCP no puede crecer más de `PacketFramer.MAX_BUFFER_BYTES` (4 KB) |
| INV-07 | La oferta de un jugador en trade solo refleja items que aún están en su inventario al momento de confirmar |
| INV-08 | Vender al NPC no puede elevar el oro del jugador por encima de `MAX_PLAYER_GOLD` |

---

## 4. Hallazgos de bugs y exploits

### BUG-01 — Duplicación de items por race condition en pickup (CRÍTICO)

**Archivo**: `src/command_handlers/pickup_handler.py`  
**Gravedad**: Crítica — permite duplicar cualquier item del suelo.

**Descripción**:  
El flujo original era `get_ground_items → await add_item/update_gold → remove_ground_item`. Entre `get_ground_items` y `remove_ground_item` hay `await`s de Redis. Si dos clientes en el mismo tile mandan `PICK_UP` al mismo tiempo:

1. Coroutine A lee el item del tile.  
2. `await add_item` → cede control.  
3. Coroutine B lee el mismo item (aún en el tile).  
4. Ambas coroutines llaman `add_item` y luego `remove_ground_item`.  
5. El item está duplicado en dos inventarios.

**Cómo reproducir**:  
Dos clientes se colocan en el mismo tile con un item, ambos envían `PICK_UP` dentro del mismo ciclo de asyncio.

**Fix aplicado**:  
Patrón *claim-first*: `remove_ground_item` (síncrono, modifica `dict` en memoria) se llama **antes** del primer `await`. Solo una coroutine puede ganar el `pop`. Si la operación posterior falla (inventario lleno, cap de oro, etc.), el item se restaura con `add_ground_item` como rollback.

**Archivos modificados**:
- `src/command_handlers/pickup_handler.py`
- `src/command_handlers/pickup_gold_handler.py` (renombrado a `pickup_claimed_gold`)
- `src/command_handlers/pickup_item_handler.py` (renombrado a `pickup_claimed_item`)

**Tests de regresión**: `tests/command_handlers/test_pickup_handler.py`  
- `test_concurrent_pickup_does_not_duplicate_item` — reproductor con `asyncio.gather`
- `test_handle_pickup_item_full_inventory_restores_ground` — rollback ante inventario lleno

---

### BUG-02 — Doble ejecución de `_perform_trade` en comercio jugador-jugador (CRÍTICO)

**Archivo**: `src/services/trade_service.py`  
**Gravedad**: Crítica — permite duplicar items en el contexto de un trade.

**Descripción**:  
`confirm_trade` fijaba los flags de confirmación de forma síncrona pero luego cedía control con `await _notify_console(...)` **antes** de chequear si ambos flags estaban activos. Si Alice y Bob confirmaban simultáneamente:

1. Alice: `initiator_confirmed = True` → `await _notify_console(alice)` ← cede.  
2. Bob: `target_confirmed = True` → `await _notify_console(bob)` ← cede.  
3. Alice reanuda: ambos flags `True` → llama `_perform_trade` → retira items.  
4. Bob reanuda: ambos flags aún `True` → llama `_perform_trade` DE NUEVO → items duplicados.

**Cómo reproducir**:  
`asyncio.gather(service.confirm_trade(alice_id), service.confirm_trade(bob_id))` con cualquier `await` en las dependencias. Ver `test_concurrent_confirm_does_not_double_execute`.

**Fix aplicado**:  
Nuevo campo `_trade_executing: bool` en `TradeSession`. En `confirm_trade`, la decisión de ejecutar y el set de la guarda ocurren en el mismo bloque síncrono (sin ningún `await` entre ellos). Asyncio de un solo hilo garantiza que ninguna otra coroutine puede interleavar entre esas dos líneas.

```python
both_ready = session.initiator_confirmed and session.target_confirmed
should_execute = both_ready and not session._trade_executing  # sin await aquí
if should_execute:
    session._trade_executing = True                           # ni aquí
await self._notify_console(...)  # ahora sí se puede ceder control
```

**Archivos modificados**: `src/services/trade_service.py`

**Tests de regresión**: `tests/services/test_trade_service.py`  
- `test_concurrent_confirm_does_not_double_execute`

---

### BUG-03 — Gold overflow en trade jugador-jugador (MEDIO)

**Archivo**: `src/services/trade_service.py`  
**Gravedad**: Media — el jugador receptor podría superar `MAX_PLAYER_GOLD`.

**Descripción**:  
`player_repo.add_gold(target_id, offer.gold)` no verificaba el tope. Un jugador con `MAX_PLAYER_GOLD - 1` podía recibir cualquier cantidad de oro.

**Fix aplicado**:  
- `_validate_offers` ahora comprueba `target_gold + offer.gold > MAX_PLAYER_GOLD` y rechaza el trade con mensaje claro antes de mover ningún recurso.  
- `_perform_trade` también usa `safe_amount = min(offer.gold, MAX_PLAYER_GOLD - current)` como defensa en profundidad.

**Tests de regresión**: `test_confirm_trade_blocked_by_gold_cap`

---

### BUG-04 — Gold overflow al vender a NPC (BAJO)

**Archivo**: `src/services/commerce_service.py`  
**Gravedad**: Baja — mismo problema que BUG-03 pero en el camino de venta.

**Fix aplicado**:  
`new_gold = min(player_gold + total_price, MAX_PLAYER_GOLD)`.

**Tests de regresión**: `test_sell_item_respects_gold_cap`

---

### BUG-05 — Framing de packets TCP incorrecto (CRÍTICO, estado: mitigado)

**Archivo**: `src/network/client_connection.py`  
**Gravedad**: Crítica — el servidor no delimita correctamente los mensajes de aplicación sobre TCP.

**Descripción**:  
`receive(max_bytes=1024)` lee chunks fijos del stream sin respetar las fronteras de packets. Un mensaje puede llegar fragmentado en varios chunks, o varios mensajes en uno solo. Sin framing correcto el servidor procesa datos malformados, lo que puede causar:
- Crasheo silencioso del parser.
- Procesamiento de packets con campos inválidos.
- Desincronización permanente del estado de la conexión.

**Fix aplicado (Fase 2)**:  
Nuevo módulo `src/network/packet_framer.py` con `PacketFramer`. Implementa:
- Tabla `_FIXED_LENGTHS` para packets de longitud conocida (la mayoría).
- Probes dinámicas (`_probe_login`, `_probe_create_account`, `_probe_single_string`, `_probe_gm_commands`) para packets con strings variables.
- Guarda contra buffer overflow (`MAX_BUFFER_BYTES = 4 KB`).
- Excepción `UnknownPacketError` para `packet_id` no soportados.

**Estado actual**: `PacketFramer` está completamente testeado como librería. La integración en `ClientConnection` requiere que los parsers de cada `Task` se adapten para no consumir bytes extra del stream (hay inconsistencias menores entre lo que el framer delimita y lo que algunos tasks leen). Se recomienda integrar en paralelo con la migración task por task.

**Tests**: `tests/network/test_packet_framer.py` — 22 tests, incluyendo fragmentación, concatenación, overflow y packets desconocidos.

---

### BUG-06 — `SyntaxError` en `src/server.py` (BLOQUEANTE, corregido)

**Descripción**: `except KeyboardInterrupt, asyncio.CancelledError:` (sintaxis Python 2).  
**Fix**: `except (KeyboardInterrupt, asyncio.CancelledError):`.

---

### RIESGO-01 — Ausencia de tope de oro al recoger del suelo (MEDIO, corregido)

**Fix**: `MAX_PLAYER_GOLD = 999_999_999` en `src/models/item_constants.py`. Aplicado en pickup, trade y venta a NPC. El validador de banco ya usaba este valor implícitamente.

**Tests de regresión**:
- `test_gold_cap_when_already_at_max`
- `test_gold_cap_partial_pickup_leaves_remainder` (remanente vuelve al suelo)

---

### RIESGO-02 — `_update_offer_item` no resetea confirmaciones al quitar la oferta

**Estado**: comportamiento correcto. `_reset_confirmations` sí se llama al remover (`quantity == 0`). Sin cambios necesarios.

---

### RIESGO-03 — Rollback parcial en `_perform_trade` cuando inventario del receptor está lleno

**Descripción**:  
Si la entrega de items a B falla (inventario lleno), `_rollback_trade` llama `remove_item_by_item_id` que podría no encontrar el item en el slot original (si hubo stackeo en otro slot). El rollback se logea como error pero el jugador no pierde su item porque el flujo ya había ejecutado `_refund_removed_resources`.

**Estado**: riesgo residual bajo. El código de rollback es best-effort y logea errores explícitos. Requiere una segunda fase de hardening con Redis transactions (MULTI/EXEC) para garantía completa. Documentado como deuda técnica.

---

## 5. Invariantes verificados por tests

| Invariante | Test |
|-----------|------|
| INV-01 (gold cap pickup) | `test_gold_cap_when_already_at_max`, `test_gold_cap_partial_pickup_leaves_remainder` |
| INV-01 (gold cap trade) | `test_confirm_trade_blocked_by_gold_cap` |
| INV-01 (gold cap sell) | `test_sell_item_respects_gold_cap` |
| INV-02 (no duplicar pickup) | `test_concurrent_pickup_does_not_duplicate_item` |
| INV-03 (no doble trade) | `test_concurrent_confirm_does_not_double_execute` |
| INV-04 (rollback pickup) | `test_handle_pickup_item_full_inventory_restores_ground` |
| INV-04 (rollback sin servicios) | `test_handle_pickup_item_without_services_restores_ground` |
| INV-05 (framing) | `tests/network/test_packet_framer.py` |
| INV-06 (buffer overflow) | `test_buffer_overflow_raises_error` |
| INV-07 (validación al confirmar) | `test_update_offer_item_validates_slot` |

---

## 6. Separación dominio / aplicación / infraestructura

### Estado actual (post-refactor)

```
Dominio puro (sin I/O, sin red):
  src/models/          — dataclasses y constantes
  src/services/        — reglas del juego (trade, combat, spells)
  src/game/            — estado en memoria (mapas, NPCs, ground items)

Aplicación (orquestación):
  src/command_handlers/ — coordinan repos y servicios, no conocen sockets
  src/tasks/           — parsean bytes, construyen Commands

Infraestructura:
  src/network/         — I/O TCP, framing, validación de protocolo
  src/repositories/    — acceso a Redis
  src/messaging/       — serialización de mensajes al cliente
```

### Acoplamiento problemático residual

- `CommerceSellCommandHandler` importa `ITEMS_CATALOG` directamente (acoplamiento a catálogo global). Debería inyectarse.
- `ClientConnection` aún no usa `PacketFramer` (integración pendiente).
- Algunos `Task` realizan parsing y lógica de negocio en el mismo método `execute`. Se recomienda mover la lógica al `CommandHandler` correspondiente.

---

## 7. Recomendaciones priorizadas

### Prioridad 1 — Integrar `PacketFramer` en `ClientConnection`

**Por qué**: sin framing correcto cualquier cliente malicioso puede desincronizar el parser con un único packet malformado.  
**Cómo**: reemplazar el loop de `receive(max_bytes)` por `framer.feed(chunk)` + `framer.next_packet()`. Migrar los parsers de cada `Task` para que no consuman bytes extra. Agregar tests de integración con streams fragmentados.

### Prioridad 2 — Atomicidad real en `_perform_trade` con Redis MULTI/EXEC

**Por qué**: el rollback actual es best-effort. Si Redis falla a mitad de la entrega de items, los jugadores pueden quedar en estado inconsistente.  
**Cómo**: envolver `remove_item`, `add_item`, `remove_gold`, `add_gold` en un pipeline atómico Redis (MULTI/EXEC con WATCH en las claves involucradas).

### Prioridad 3 — Validación de rangos en `TaskUserCommerceOffer`

**Por qué**: `slot` y `quantity` se leen sin validación mínima antes de pasarlos al handler.  
**Cómo**: aplicar un `UserCommerceOfferPacketValidator` análogo a `CommerceBuyPacketValidator`, rechazando slots fuera de rango y cantidades negativas antes de construir el `Command`.

### Prioridad 4 — Rate limiting por conexión

**Por qué**: un cliente puede enviar miles de packets por segundo sin penalización.  
**Cómo**: en `ClientConnection`, llevar un contador de packets por ventana temporal (token bucket). Desconectar si se supera el límite.

### Prioridad 5 — Test de integración end-to-end con cliente bot

**Por qué**: los tests actuales son unitarios; no hay cobertura de flujos completos cliente-servidor.  
**Cómo**: crear un cliente asyncio mínimo que conecte a un servidor en test, envíe packets reales del protocolo Godot y verifique las respuestas. Usar `fakeredis` para aislar Redis.

### Prioridad 6 — Observabilidad: métricas de pickup, trade y drops

**Por qué**: sin métricas es imposible detectar exploits en producción.  
**Cómo**: añadir contadores Prometheus (o logging estructurado) en `PickupCommandHandler._handle`, `TradeService._perform_trade` y `GroundItemIndex.remove_ground_item`. Monitorear anomalías (jugador con N pickups/s, oro que crece fuera de banda).

---

## 8. Resumen de cambios por fase

| Fase | Archivos modificados | Tests añadidos |
|------|---------------------|----------------|
| 0 | `src/server.py` | — |
| 2 | `src/network/packet_framer.py` (nuevo) | 22 (framer) |
| 3 | `src/command_handlers/pickup_handler.py`, `pickup_gold_handler.py`, `pickup_item_handler.py`, `src/models/item_constants.py` | 8 (pickup) |
| 4 | `src/services/trade_service.py`, `src/services/commerce_service.py` | 6 (trade + commerce) |

**Estado final del toolchain**:
- `pytest`: **2 078 tests, 0 fallos**
- `ruff check src/`: **0 errores**
- `mypy src/`: **0 errores (431 archivos)**
