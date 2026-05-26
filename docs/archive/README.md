# Archivo de documentación

Material **histórico** o **reemplazado** por docs consolidadas. No enlazar desde el índice principal salvo consulta puntual.

## Completados (`completed/`)

Refactors y migraciones ya aplicados en el código.

| Documento | Descripción |
|-----------|-------------|
| [REFACTOR_SERVER_COMPLETED.md](completed/REFACTOR_SERVER_COMPLETED.md) | Refactor de `server.py` |
| [REFACTOR_MSG_COMPLETED.md](completed/REFACTOR_MSG_COMPLETED.md) | Refactor de `msg.py` |
| [REFACTOR_REPOSITORIES.md](completed/REFACTOR_REPOSITORIES.md) | Separación de repositorios |
| [NPC_FACTORY_COMPLETED.md](completed/NPC_FACTORY_COMPLETED.md) | Factory de NPCs con FX |
| [PACKET_VALIDATOR_MIGRATION.md](completed/PACKET_VALIDATOR_MIGRATION.md) | Migración a PacketValidator centralizado |
| [MAP_TRANSITION_REFACTORING.md](completed/MAP_TRANSITION_REFACTORING.md) | Refactor MapTransitionService |

## Reemplazados (`superseded/`)

Copias pre-fusión; la fuente de verdad está en [`../systems/`](../systems/), [`../guides/`](../guides/), [`../development/`](../development/) o [`../architecture/`](../architecture/).

| Documento | Reemplazado por |
|-----------|-----------------|
| `CLAN_SYSTEM_IMPLEMENTATION_STATUS.md`, `CLAN_BUTTON.md`, `TESTING_CLAN_SYSTEM.md` | [systems/CLAN_SYSTEM.md](../systems/CLAN_SYSTEM.md) |
| `PARTY_SYSTEM_IMPLEMENTATION_STATUS.md` | [systems/PARTY_SYSTEM.md](../systems/PARTY_SYSTEM.md) |
| `NPC_ARCHITECTURE.md` | [systems/NPC_SYSTEM.md](../systems/NPC_SYSTEM.md) |
| `SPELL_ADVANCED_IMPLEMENTATION_PLAN.md` | [systems/MAGIC_SYSTEM.md](../systems/MAGIC_SYSTEM.md) |
| `MAP_TRANSITIONS_EXPANSION.md` | [systems/MAP_TRANSITIONS_SYSTEM.md](../systems/MAP_TRANSITIONS_SYSTEM.md) |
| `WORK_SYSTEM_PROTOCOL.md`, `WORK_SYSTEM_QUICK_REF.md` | [guides/WORK_SYSTEM.md](../guides/WORK_SYSTEM.md) |
| `REDIS_ARCHITECTURE.md`, `REDIS_INTEGRATION.md` | [architecture/REDIS_DATA.md](../architecture/REDIS_DATA.md) |
| `REFACTORING_OPPORTUNITIES.md`, `HANDLER_REFACTORING.md` | [development/REFACTORING.md](../development/REFACTORING.md) |
| `COVERAGE_ANALYSIS.md`, `REDUNDANT_TESTS.md`, `TEST_COVERAGE_NPC_*.md` | [development/TESTING.md](../development/TESTING.md) |
| `LOGGING_GUIDELINES.md`, `LOGGING_FEATURES.md` | [guides/LOGGING.md](../guides/LOGGING.md) |

## Raíz `archive/` (legacy)

| Documento | Motivo |
|-----------|--------|
| [REVISION_TODOS_DOCS.md](REVISION_TODOS_DOCS.md) | Meta-revisión 2025 |
| [ANALISIS_PROYECTO.md](ANALISIS_PROYECTO.md) | Snapshot de análisis |
| [PROPOSED_CODE_ORGANIZATION.md](PROPOSED_CODE_ORGANIZATION.md) | Propuesta pre-reorganización |

Índice activo: [`../README.md`](../README.md).
