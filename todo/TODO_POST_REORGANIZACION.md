# TODO: Post-Reorganización - Próximos Pasos

**Fecha:** 21 de octubre, 2025  
**Estado:** Reorganización completa ✅ - Listo para próximas mejoras  
**Prioridad:** Media-Baja (mejoras incrementales)

---

## 🎯 Contexto

Proyecto completamente reorganizado en 6 fases:
- ✅ 130 archivos movidos (65 src + 65 tests)
- ✅ 287 imports actualizados automáticamente
- ✅ Estructura profesional implementada
- ✅ 990 tests pasando (100%)

Con esta base sólida, ahora podemos crecer de forma organizada.

---

## 📋 Próximos Pasos Sugeridos

### 1. Ampliar Cobertura de Tests

**Prioridad:** Alta  
**Esfuerzo:** Medio  
**Beneficio:** Alta confianza en refactorings futuros

**Tareas:**
- [ ] Agregar tests para `tasks/work/` (actualmente 0 tests)
  - test_task_work.py
  - test_task_work_left_click.py
- [ ] Agregar tests para `tasks/admin/` (actualmente 0 tests)
  - test_task_gm_commands.py
- [ ] Agregar tests para `services/map/` (actualmente 0 tests)
  - test_map_resources_service.py
  - test_map_transition_service.py
  - test_player_map_service.py
  - test_pathfinding_service.py
- [ ] Aumentar cobertura de integration tests
  - Tests de flujos completos (login → spawn → combat → loot)
  - Tests de edge cases

**Ubicación:** `tests/tasks/work/`, `tests/tasks/admin/`, `tests/services/map/`

---

### 2. Documentar APIs por Módulo

**Prioridad:** Media  
**Esfuerzo:** Medio  
**Beneficio:** Onboarding más rápido, mejor mantenibilidad

**Tareas:**
- [ ] Generar docs automáticos con Sphinx o MkDocs
- [ ] Documentar API de cada módulo principal:
  - `src/tasks/` - Handlers de packets
  - `src/services/` - Lógica de negocio
  - `src/repositories/` - Acceso a datos
  - `src/messaging/` - Comunicación con cliente
- [ ] Crear diagramas de arquitectura (usar Mermaid)
- [ ] Documentar flujos de datos principales

**Ubicación:** `docs/api/`

**Herramientas sugeridas:**
- Sphinx con autodoc
- MkDocs con mkdocstrings
- Mermaid para diagramas

---

### 3. Mejorar CI/CD con Tests por Categoría

**Prioridad:** Media  
**Esfuerzo:** Bajo  
**Beneficio:** Feedback más rápido en PRs

**Tareas:**
- [ ] Configurar pytest para ejecutar tests por categoría:
  ```bash
  pytest tests/unit/           # Tests rápidos
  pytest tests/tasks/          # Tests de handlers
  pytest tests/integration/    # Tests completos
  ```
- [ ] Crear jobs de CI separados:
  - Quick checks (unit + linting) - 30s
  - Full tests (todos) - 2min
- [ ] Implementar test paralelo por categoría
- [ ] Agregar badges de cobertura por módulo

**Ubicación:** `.github/workflows/`

---

### 4. Implementar Metrics y Coverage por Componente

**Prioridad:** Media  
**Esfuerzo:** Bajo  
**Beneficio:** Visibilidad de calidad por módulo

**Tareas:**
- [ ] Configurar coverage.py para reportes por módulo
- [ ] Generar reports HTML con coverage por carpeta
- [ ] Agregar métricas de:
  - Cobertura por módulo (tasks, services, repos)
  - Complejidad ciclomática por módulo
  - Líneas de código por categoría
- [ ] Crear dashboard de métricas (opcional)

**Herramientas:**
- coverage.py
- radon (complejidad)
- pygount (líneas de código)

---

### 5. Crear Plantillas para Nuevos Componentes

**Prioridad:** Baja  
**Esfuerzo:** Bajo  
**Beneficio:** Consistencia al agregar código

**Tareas:**
- [ ] Crear template de Task con su test
- [ ] Crear template de Service con su test
- [ ] Crear template de Repository con su test
- [ ] Documentar convenciones de naming
- [ ] Crear script `new_component.py` para generar boilerplate

**Ubicación:** `scripts/templates/`

**Ejemplo de uso:**
```bash
uv run python scripts/new_component.py task trade --category commerce
# Genera: src/tasks/commerce/task_trade.py
#         tests/tasks/commerce/test_task_trade.py
```

---

### 6. Refactorizar Archivos Core Restantes

**Prioridad:** Baja  
**Esfuerzo:** Medio  
**Beneficio:** Completar la organización

**Archivos a revisar en src/ (~73 archivos restantes):**
- [ ] Agrupar effects (effect_*.py) en `src/effects/`
- [ ] Agrupar utils en `src/utils/`
- [ ] Revisar si packet_*.py deben ir a `src/network/`
- [ ] Agrupar catalogs/loaders en categoría apropiada

**No urgente:** El código funciona bien como está.

---

### 7. Optimizar Imports con __init__.py

**Prioridad:** Baja  
**Esfuerzo:** Bajo  
**Beneficio:** Imports más limpios

**Tareas:**
- [ ] Agregar re-exports en `__init__.py` de cada módulo
- [ ] Permitir imports cortos:
  ```python
  # Antes
  from src.tasks.player.task_login import TaskLogin
  
  # Después
  from src.tasks.player import TaskLogin
  ```
- [ ] Implementar en:
  - `src/tasks/__init__.py`
  - `src/services/__init__.py`
  - `src/repositories/__init__.py`
  - `src/models/__init__.py`

---

### 8. Documentar Convenciones del Proyecto

**Prioridad:** Media  
**Esfuerzo:** Bajo  
**Beneficio:** Consistencia para contribuidores

**Tareas:**
- [ ] Crear `CONTRIBUTING.md` con:
  - Estructura del proyecto explicada
  - Convenciones de naming
  - Cómo agregar nuevos componentes
  - Dónde poner cada tipo de código
- [ ] Crear `ARCHITECTURE.md` con:
  - Diagrama de capas
  - Flujo de datos
  - Responsabilidades de cada módulo
- [ ] Actualizar README.md con nueva estructura

**Ubicación:** Raíz del proyecto

---

## 🎯 Quick Wins (Hazlos Primero)

Si quieres mejoras rápidas con alto impacto:

1. **Tests para work system** (1-2 horas)
   - Ya tienes el código, solo falta test coverage
   - Alta prioridad porque es funcionalidad nueva

2. **Plantillas de componentes** (30 min)
   - Automatiza la creación de nuevos componentes
   - Mantiene consistencia

3. **Documentar convenciones** (1 hora)
   - CONTRIBUTING.md básico
   - Explica la estructura a futuros devs

---

## 📊 Priorización Sugerida

| Tarea | Prioridad | Esfuerzo | Beneficio | Orden |
|-------|-----------|----------|-----------|-------|
| Tests work/admin | Alta | Medio | Alto | 1 |
| Convenciones docs | Media | Bajo | Alto | 2 |
| Plantillas componentes | Media | Bajo | Medio | 3 |
| CI/CD categorías | Media | Bajo | Medio | 4 |
| API docs | Media | Medio | Medio | 5 |
| Metrics/Coverage | Media | Bajo | Bajo | 6 |
| Optimizar imports | Baja | Bajo | Bajo | 7 |
| Refactor core files | Baja | Medio | Bajo | 8 |

---

## ✅ Checklist de Mantenimiento

Para mantener la organización:

- [ ] Nuevos tasks van a `src/tasks/<categoría>/`
- [ ] Nuevos services van a `src/services/<dominio>/`
- [ ] Nuevos repos van a `src/repositories/`
- [ ] Nuevos tests espejan la estructura de `src/`
- [ ] Actualizar `__init__.py` cuando agregues archivos
- [ ] Mantener imports organizados
- [ ] Documentar decisiones arquitectónicas importantes

---

## 📝 Notas

- **No urgente:** El proyecto ya funciona perfectamente
- **Incremental:** Implementa estos cambios de a poco
- **Opcional:** Elige los que más valor agreguen a tu proyecto
- **Automatización:** Los scripts ya creados son reutilizables

---

**Última actualización:** 21 de octubre, 2025  
**Estado:** Lista de mejoras post-reorganización
