# Reglas de Desarrollo - PyAO Server

## Filosofía General
- **Desarrollo incremental**: Avanzar paso a paso, NO implementar múltiples features a la vez
- **Confirmación antes de avanzar**: Siempre preguntar qué hacer siguiente, no asumir
- **Simplicidad primero**: Implementar lo mínimo necesario que funcione antes de agregar complejidad

## Estructura del Proyecto
- Usar `pyproject.toml` para dependencias (proyecto manejado con `uv`)
- NO crear `requirements.txt`
- Python >= 3.14
- Usar `ruff` para linting y formatting
- Todo el código fuente debe estar en `src/`

## Protocolo de Red
- Basado en el cliente Argentum Online Godot: https://github.com/brian-christopher/ArgentumOnlineGodot
- Usar little-endian para todos los números multi-byte
- Strings en formato: `uint16 (longitud) + UTF-16LE bytes`
- Cada paquete comienza con un byte identificador (PacketID)

## Convenciones de Código
- Type hints en todas las funciones
- Docstrings en español para clases y funciones públicas
- Nombres de variables y funciones en inglés (snake_case)
- Nombres de clases en inglés (PascalCase)
- Usar dataclasses para estructuras de datos cuando sea apropiado

## Logging
- Implementar logging configurable para paquetes entrantes/salientes
- Formato: `[INCOMING/OUTGOING] PacketName | params`

## Testing
- Preguntar antes de crear tests
- Priorizar tests de integración para el protocolo de red

## NO Hacer Sin Confirmar
- NO crear múltiples archivos/módulos de una vez
- NO implementar features completas sin discutir el diseño primero
- NO asumir estructura de base de datos o persistencia
- NO agregar dependencias externas sin consultar

## Workflow
1. Discutir qué implementar
2. Mostrar el plan específico
3. Implementar solo esa parte
4. Confirmar que funciona
5. Preguntar qué sigue

## Pre-commit
- **OBLIGATORIO**: Antes de cada commit, ejecutar `./run_tests.sh` y verificar que todo pase
- El script incluye: ruff linter, ruff formatter, mypy type checker, y pytest
- NO hacer commit si algún check falla

## CI/CD
- GitHub Actions corre automáticamente los mismos checks que `run_tests.sh` en cada push
- Los checks deben pasar para poder mergear PRs
