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

## Gestión de Datos Iniciales
- **OBLIGATORIO**: Todo dato inicial debe estar en un archivo TOML en `data/`
- Los datos deben cargarse en Redis antes de iniciar el servidor (scripts de inicialización)
- Durante la ejecución, el servidor solo lee/escribe desde Redis
- Ejemplos: inventarios de mercaderes, configuración de NPCs, items, mapas, etc.

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

## Documentación
- **SIEMPRE actualizar la estructura del proyecto en README.md** cuando se agreguen/eliminen archivos
- Mantener sincronizada la sección "📦 Estructura del Proyecto" con los cambios
- Actualizar la sección "Arquitectura" si cambian las responsabilidades de las clases

## Workflow
1. **Proponer cambios**: Mostrar qué cambios se van a realizar y esperar confirmación del usuario
2. **Implementar**: Solo después de la aprobación, realizar los cambios en el código
3. **Ejecutar tests**: Correr `./run_tests.sh` y verificar que no haya errores ni warnings
4. **Generar tests**: Crear o actualizar los tests necesarios para los cambios realizados
5. **Ejecutar tests nuevamente**: Correr `./run_tests.sh` hasta que no haya ningún error ni warning
6. **Actualizar README.md**: Si se agregaron/eliminaron archivos o cambió la arquitectura
7. **Commit y Push**: Solo cuando todo esté limpio y funcionando

## Pre-commit
- **OBLIGATORIO**: Antes de cada commit, ejecutar `./run_tests.sh` y verificar que todo pase
- El script incluye: ruff linter, ruff formatter, mypy type checker, y pytest
- NO hacer commit si algún check falla

## CI/CD
- GitHub Actions corre automáticamente los mismos checks que `run_tests.sh` en cada push
- Los checks deben pasar para poder mergear PRs
