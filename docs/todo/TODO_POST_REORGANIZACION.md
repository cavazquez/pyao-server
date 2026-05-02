# TODO: Post-reorganización (seguimiento)

**Última revisión:** 2026-05-02  
**Contexto:** La reorganización por fases del árbol `src/` / `tests/` ya está hecha. Este documento **no** es roadmap de features: para eso usar **`ROADMAP_VERSIONES.md`** y **`TODO_CONSOLIDADO.md`**.

---

## Estado frente al checklist original

| Bloque original | Estado 2026 | Notas |
|-----------------|-------------|--------|
| **1. Cobertura tests** (work, admin, map) | Parcialmente cubierto | Existen `tests/tasks/work/test_task_work*.py`, `tests/tasks/admin/test_gm_commands.py`, `tests/services/map/test_*`. Revisar huecos con `pytest --cov`, no con listas fijas de 2025. |
| **2. APIs por módulo** (Sphinx/MkDocs) | Pendiente / opcional | Índice humano: [`docs/README.md`](../README.md). API auto-gen sigue siendo mejora futura. |
| **3. CI por categoría** | Parcial | `pytest -n auto` + job único en CI; categorías por carpeta siguen siendo opcional. |
| **4. Métricas por componente** | Opcional | Codecov global; informes por carpeta no automatizados en CI. |
| **5. Plantillas nuevos componentes** | Pendiente | `scripts/templates/` aún no existe. |
| **6. Refactor core** (effects/, utils/) | Backlog bajo | Solo si hay dolor real de imports o navegación. |
| **7. Re-exports `__init__.py`** | Pendiente | Convención actual: imports explícitos desde módulos. |
| **8. Convenciones y README** | **Hecho** | [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`ARCHITECTURE_PROJECT.md`](../ARCHITECTURE_PROJECT.md), README raíz e índice [`docs/README.md`](../README.md). |
| **Enlaces Markdown en CI** | **Hecho** | Workflow comprueba `README.md`, `Claude.md`, `docs/README.md`. |

---

## Checklist de mantenimiento (sigue vigente)

- [ ] Nuevas tasks bajo `src/tasks/<categoría>/`
- [ ] Nuevos servicios bajo `src/services/<dominio>/`
- [ ] Repos bajo `src/repositories/`
- [ ] Tests espejando estructura de `src/`
- [ ] Decisiones grandes: una línea en `docs/` o en `TODO_CONSOLIDADO.md`

---

## Quick wins todavía útiles

1. Revisar cobertura de módulos críticos con melón real (`commerce`, combate, Redis) según `docs/COVERAGE_ANALYSIS.md` si está actualizado.
2. Si se añade mucha documentación nueva: mantener el índice en **`docs/README.md`**.

---

**Nota:** No buscar **`TODO_GENERAL.md`** ni **`TODO_REFACTORING.md`** — fueron retirados. Metadocumentación antigua: **`docs/archive/REVISION_TODOS_DOCS.md`**. Roadmap actualizado: **`ROADMAP_VERSIONES.md`**.
