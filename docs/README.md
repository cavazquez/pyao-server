# Documentación (PyAO Server)

Índice de la documentación interna. Presentación del proyecto: [**README.md**](../README.md).

> **Última reorganización:** 2026-05 — docs agrupadas por tipo en subcarpetas.

## Entrada rápida

| Documento | Contenido |
|-----------|-----------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo contribuir, estilo, PRs |
| [CLAUDE.md](CLAUDE.md) | Reglas de desarrollo para asistentes IA |
| [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) | Arquitectura del servidor (primera lectura) |
| [development/ESTADO_ACTUAL.md](development/ESTADO_ACTUAL.md) | Estado y roadmap interno |
| [guides/REDIS.md](guides/REDIS.md) | Docker Redis, operación |
| [todo/README.md](todo/README.md) | TODOs y roadmaps |

## Guías ([guides/](guides/README.md))

Setup, protocolo, datos y herramientas.

- [CONFIGURATION.md](guides/CONFIGURATION.md) — Configuración del servidor
- [CLI.md](guides/CLI.md) — Línea de comandos
- [REDIS.md](guides/REDIS.md) — Redis en desarrollo
- [LOGGING.md](guides/LOGGING.md) — Logging (guías + features)
- [LOGIN_FLOW.md](guides/LOGIN_FLOW.md) — Flujo de login
- [ACCOUNT_CREATION.md](guides/ACCOUNT_CREATION.md) — Creación de cuentas
- [DATA_DIRECTORY.md](guides/DATA_DIRECTORY.md) — Árbol `data/`
- [DATA_ITEMS.md](guides/DATA_ITEMS.md) — Convenciones de items
- [TOOLS_DIRECTORY.md](guides/TOOLS_DIRECTORY.md) — Herramientas en `tools/`
- [HOW_TO_SET_GM.md](guides/HOW_TO_SET_GM.md) — Asignar GM
- [WORK_SYSTEM.md](guides/WORK_SYSTEM.md) — Trabajo (talar, minería, pesca)

## Arquitectura ([architecture/](architecture/README.md))

- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) — Visión general y diagramas
- [ARCHITECTURE_PROJECT.md](architecture/ARCHITECTURE_PROJECT.md) — Ampliación detallada
- [SERVICES_ARCHITECTURE.md](architecture/SERVICES_ARCHITECTURE.md) — Capa de servicios
- [REDIS_DATA.md](architecture/REDIS_DATA.md) — Claves Redis e integración
- [COMMAND_PATTERN_ANALYSIS.md](architecture/COMMAND_PATTERN_ANALYSIS.md) — Patrón command

## Sistemas de juego ([systems/](systems/README.md))

- [COMBAT_SYSTEM.md](systems/COMBAT_SYSTEM.md) — Combate
- [MAGIC_SYSTEM.md](systems/MAGIC_SYSTEM.md) — Hechizos y magia
- [NPC_SYSTEM.md](systems/NPC_SYSTEM.md) — NPCs, spawns, IA
- [COMMERCE_SYSTEM.md](systems/COMMERCE_SYSTEM.md) — Comercio con mercaderes
- [BANK_SYSTEM.md](systems/BANK_SYSTEM.md) — Banco
- [PLAYER_TRADE_SYSTEM.md](systems/PLAYER_TRADE_SYSTEM.md) — Comercio entre jugadores
- [ITEMS_SYSTEM.md](systems/ITEMS_SYSTEM.md) — Ítems e inventario
- [LOOT_SYSTEM.md](systems/LOOT_SYSTEM.md) — Botín
- [CLAN_SYSTEM.md](systems/CLAN_SYSTEM.md) — Clanes/guilds
- [PARTY_SYSTEM.md](systems/PARTY_SYSTEM.md) — Parties/grupos
- [GAME_TICK_SYSTEM.md](systems/GAME_TICK_SYSTEM.md) — Tick (hambre, sed, meditación)
- [MAP_TRANSITIONS_SYSTEM.md](systems/MAP_TRANSITIONS_SYSTEM.md) — Transiciones entre mapas
- [PATHFINDING_ASTAR.md](systems/PATHFINDING_ASTAR.md) — Pathfinding A*
- [CLASSES_AND_RACES.md](systems/CLASSES_AND_RACES.md) — Clases y razas
- Ver carpeta `systems/` para el resto (movimiento, FX de NPC, etc.)

## Desarrollo ([development/](development/README.md))

- [ESTADO_ACTUAL.md](development/ESTADO_ACTUAL.md) — Estado del proyecto
- [REFACTORING.md](development/REFACTORING.md) — Oportunidades de refactor + handlers
- [TESTING.md](development/TESTING.md) — Cobertura y tests
- [TECH_IMPROVEMENTS_BACKLOG.md](development/TECH_IMPROVEMENTS_BACKLOG.md) — Backlog técnico
- [TOOLS_ANALYSIS.md](development/TOOLS_ANALYSIS.md) — Análisis de herramientas
- [PERFORMANCE_METRICS.md](development/PERFORMANCE_METRICS.md) — Métricas

## Análisis ([analysis/](analysis/README.md))

- [AUDITORIA.md](analysis/AUDITORIA.md) — Auditoría puntual
- [ANALISIS_CLIENTE_VB6_2026.md](analysis/ANALISIS_CLIENTE_VB6_2026.md) — Cliente VB6
- [DATA_ANALYSIS.md](analysis/DATA_ANALYSIS.md) — Datos
- [MAP_ORPHANS_ANALYSIS.md](analysis/MAP_ORPHANS_ANALYSIS.md) — Mapas huérfanos

## Planificación

- [todo/README.md](todo/README.md) — Índice de TODOs
- [todo/TODO_CONSOLIDADO.md](todo/TODO_CONSOLIDADO.md) — Backlog consolidado
- [todo/ROADMAP_VERSIONES.md](todo/ROADMAP_VERSIONES.md) — Roadmap por versiones

## Histórico

- [archive/README.md](archive/README.md) — Refactors completados y docs reemplazados
