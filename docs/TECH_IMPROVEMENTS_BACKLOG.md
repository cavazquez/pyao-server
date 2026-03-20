# Backlog de Mejoras Tecnicas (para retomar)

Este documento resume propuestas detectadas en una revision general del proyecto para retomarlas mas adelante.

## Objetivo

- Tener una lista priorizada de mejoras con impacto real.
- Dejar claro esfuerzo, riesgo y archivos/sistemas afectados.
- Facilitar dividir el trabajo en PRs chicos.

## Prioridad Alta (alto impacto)

### 1) Optimizar acceso de NPCs en Redis

- **Problema:** patron tipo `KEYS + N consultas` en flujo de obtencion global de NPCs.
- **Impacto esperado:** menor latencia y menor carga Redis en mapas con muchos NPCs.
- **Riesgo:** medio.
- **Esfuerzo:** 1-2 semanas.
- **Areas involucradas:** `src/repositories/npc_repository.py`, servicios que consumen listado de NPCs.
- **Siguiente paso sugerido:**
  - Reemplazar `KEYS` por `SCAN` o por indices (`SET`) por mapa/global.
  - Pasar lecturas a batch con `pipeline`/`HMGET`.
  - Medir before/after con escenarios de carga.

### 2) Resiliencia de Redis (retry/backoff/jitter/timeouts)

- **Problema:** falta capa comun de resiliencia para errores transitorios.
- **Impacto esperado:** menos errores intermitentes y mejor estabilidad.
- **Riesgo:** medio.
- **Esfuerzo:** 1-2 semanas.
- **Areas involucradas:** `src/utils/redis_client.py`, repositorios y servicios con operaciones criticas.
- **Siguiente paso sugerido:**
  - Crear wrapper de operaciones Redis con retry exponencial + jitter.
  - Definir timeouts por operacion.
  - Agregar metricas de retry/fallo.

### 3) Control de concurrencia en Game Tick

- **Problema:** posible explosion de tareas por tick (`effect x player`) y jitter del loop.
- **Impacto esperado:** mejor estabilidad del loop y menor presion sobre event loop.
- **Riesgo:** medio (puede afectar timings de gameplay si no se calibra).
- **Esfuerzo:** ~1 semana.
- **Areas involucradas:** `src/game/game_tick.py`.
- **Siguiente paso sugerido:**
  - Limitar concurrencia con semaforo o lotes.
  - Agregar presupuesto de tick y alertas cuando se excede.
  - Exponer metricas p95/p99 de duracion por tick.

## Prioridad Media (mantenibilidad y evolucion)

### 4) Reducir acoplamiento en inicializacion

- **Problema:** wiring muy centralizado en contenedor/initializer.
- **Impacto esperado:** mayor testabilidad y cambios mas seguros.
- **Riesgo:** medio.
- **Esfuerzo:** 1-2 semanas.
- **Areas involucradas:** `src/core/dependency_container.py`, `src/core/server_initializer.py`.
- **Siguiente paso sugerido:**
  - Partir inicializacion por dominios (player/combat/npc/social/map).
  - Exponer interfaces minimas por contexto.

### 5) Mejorar observabilidad (metricas accionables)

- **Problema:** hay logs, pero faltan metricas operativas sistematicas.
- **Impacto esperado:** menor MTTR y mejor tuning.
- **Riesgo:** bajo.
- **Esfuerzo:** ~1 semana.
- **Areas involucradas:** `src/logging_config.py`, `src/game/game_tick.py`, handlers/servicios.
- **Siguiente paso sugerido:**
  - Incorporar metricas (prometheus/otel).
  - Medir latencias por handler/packet, errores por modulo y retries Redis.

### 6) Estrategia de tests menos fragil

- **Problema:** mucho mock de implementacion interna en partes de la suite.
- **Impacto esperado:** mayor confianza frente a regresiones reales.
- **Riesgo:** bajo-medio.
- **Esfuerzo:** 1-2 semanas.
- **Areas involucradas:** `tests/services/*`, `tests/command_handlers/*`.
- **Siguiente paso sugerido:**
  - Agregar mas tests de integracion de flujos criticos.
  - Reducir mocks cuando sea viable.

## Quick Wins (1-2 dias)

- Actualizar documentacion de cobertura/estado para reflejar estado actual.
- Agregar alerta de tick fuera de presupuesto.
- Estandarizar contexto minimo de logs de error (`user_id`, `packet_id`, `map_id` cuando aplique).

## Propuesta de ejecucion en PRs (cuando se retome)

1. **PR 1 (ROI rapido):** optimizacion de listado de NPCs en Redis + benchmark simple.
2. **PR 2:** capa de resiliencia Redis + instrumentacion minima.
3. **PR 3:** control de concurrencia y metricas de Game Tick.

## Criterio de exito

- `run_tests.sh` verde.
- Sin regresion funcional en gameplay.
- Mejora medible en latencia/carga en escenarios con alta cantidad de NPCs.
- Trazabilidad de errores y tiempos en produccion/dev.

