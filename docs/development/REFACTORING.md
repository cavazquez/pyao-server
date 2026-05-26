> **Última consolidación:** 2026-05-26

# Oportunidades de Refactorización

Documento único de estado: qué está hecho, qué queda pendiente y dónde está el detalle histórico.

**Histórico archivado:** [`archive/superseded/REFACTORING_OPPORTUNITIES.md`](../archive/superseded/REFACTORING_OPPORTUNITIES.md), [`archive/superseded/HANDLER_REFACTORING.md`](../archive/superseded/HANDLER_REFACTORING.md)

---

## Resumen ejecutivo

| Área | Estado | Prioridad |
|------|--------|-----------|
| `stats.get()` en servicios | ✅ 0 usos en `src/` | — |
| `attributes.get()` vía repositorio | ✅ migrado | — |
| Archivos grandes (map, clan, player_repo, packet_validator, message_sender) | ✅ modularizados | — |
| Handlers monolíticos (12 splits) | ✅ completados | — |
| `party_service.py`, `npc_death_service.py`, `use_item_handler.py` | ⏳ pendientes | Media |
| Helper `send_update_user_stats_from_repo` | ⏳ pendiente | Baja |
| Reorganización de directorios `tasks/` | ⏳ propuesta | Baja |

---

## Completado

### Acceso tipado a stats y attributes

- **`stats.get()`:** 0 usos en `src/`. Servicios y handlers usan métodos de `PlayerRepository` (`get_current_hp`, `get_level`, `get_player_stats`, etc.).
- **`attributes.get()`:** migrado a helpers del repositorio. Queda un `.get()` en `class_service.py` solo sobre `dice_attributes` (dict opcional de entrada), no sobre datos de Redis.

### Archivos grandes modularizados (2026-05)

| Archivo | Resultado |
|---------|-----------|
| `map_resources_service.py` | Submódulos en `src/services/map/`; fachada ~140 líneas |
| `player_repository.py` | Mixins en `src/repositories/player_mixins/` |
| `clan_service.py` | Mixins en `src/services/clan/` |
| `packet_validator.py` | Fachada delgada; validadores en `src/network/validators/` |
| `message_sender.py` | Sub-senders en `src/messaging/senders/` |

### Refactors arquitectónicos previos

- `task_factory.py` → `HandlerRegistry` (-66% líneas)
- `spell_service.py` → `spell_effects/` (-75% líneas)
- `msg.py`, `server.py` → módulos especializados

### Handlers divididos (Command Pattern)

1. `use_item_handler` → consumable + special
2. `talk_handler` → metrics, trade, clan, pet, public
3. `left_click_handler` → npc + tile
4. `walk_handler` → validation + movement
5. `login_handler` → auth, init, spawn, finalization
6. `create_account_handler` → validation, character, finalization
7. `attack_handler` → validation, execution, loot
8. `work_left_click_handler` → validation, execution, ui
9. `double_click_handler` → item + npc
10. `drop_handler` → gold + item
11. `pickup_handler` → gold + item
12. `cast_spell_handler` → validation + execution

Detalle línea a línea de cada split: ver [`archive/superseded/HANDLER_REFACTORING.md`](../archive/superseded/HANDLER_REFACTORING.md).

---

## Pendiente

### Prioridad media — servicios grandes

| Archivo | ~Líneas | Propuesta |
|---------|---------|-----------|
| `party_service.py` | ~707 | management / membership / experience |
| `npc_death_service.py` | ~630 | death handler / exp distribution / level up |
| `use_item_handler.py` | ~741 | consumable / weapon / special (parcialmente hecho) |

Solo re-dividir handlers ya partidos (`walk_movement_handler`, `use_item_consumable_handler`, etc.) si vuelven a crecer o hay duplicación clara.

### Prioridad baja

**Helper `send_update_user_stats`:** ~17 call sites repiten el mismo patrón de obtener stats del repo y enviar al cliente. Un método `send_update_user_stats_from_repo(user_id)` en `MessageSender` reduciría boilerplate.

**Reorganización `tasks/`:** propuesta en [`archive/PROPOSED_CODE_ORGANIZATION.md`](../archive/PROPOSED_CODE_ORGANIZATION.md). Alto esfuerzo (imports masivos); no urgente.

---

## Referencia rápida — mapeo stats → repositorio

```python
# Antes
stats = await player_repo.get_stats(user_id)
hp = stats.get("min_hp", 0)

# Después
hp = await player_repo.get_current_hp(user_id)
# o
stats = await player_repo.get_player_stats(user_id)  # PlayerStats tipado
```

---

## Métricas (2026-05-26)

- Refactors mayores completados: **8** (stats, map, clan, player_repo, packet_validator, message_sender, task_factory, spell_service)
- Handlers divididos: **12**
- Servicios grandes pendientes: **3**
- Esfuerzo restante estimado: **8–12 h** (solo items de prioridad media)

---

**Última actualización:** 2026-05-26
