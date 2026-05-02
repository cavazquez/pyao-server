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
- **Coverage objetivo**: Mantener cobertura global > 45%
- **Branch coverage**: Priorizar tests que cubran todas las ramas (if/else, try/except)
- Usar `pytest --cov=src --cov-report=term-missing --cov-report=html` para ver cobertura detallada
- Archivo HTML de cobertura se genera en `htmlcov/index.html`

### Estrategia de Testing
1. **Tests unitarios**: Para repositorios y servicios (mocks de Redis)
2. **Tests de integración**: Para tasks y protocolo de red
3. **Tests de casos límite**: Validaciones, errores, datos inválidos
4. **Tests de rollback**: Transacciones que fallan deben revertirse
5. **Tests de aislamiento**: Múltiples usuarios no deben interferir entre sí

### Cobertura por Módulo
- **Repositorios**: Objetivo 90-100% (lógica crítica de datos)
- **Tasks**: Objetivo 80-95% (handlers de protocolo)
- **Servicios**: Objetivo 70-90% (lógica de negocio)
- **Efectos/Ticks**: Objetivo 60-80% (lógica de juego)

### Mejorando Branch Coverage
Para maximizar la cobertura de ramas, asegurar tests para:

**Validaciones:**
- ✅ Valores válidos (happy path)
- ✅ Valores inválidos (0, negativos, None, vacíos)
- ✅ Valores límite (min, max, fuera de rango)

**Manejo de Errores:**
- ✅ Operación exitosa
- ✅ Operación fallida (return False, None, exception)
- ✅ Dependencias no disponibles (None)
- ✅ Rollback en transacciones

**Estados del Sistema:**
- ✅ Usuario logueado vs no logueado
- ✅ Recursos disponibles vs no disponibles
- ✅ Slots vacíos vs ocupados
- ✅ Cantidad suficiente vs insuficiente

**Casos Especiales:**
- ✅ Packets malformados (tamaño incorrecto)
- ✅ Múltiples usuarios (aislamiento)
- ✅ Persistencia (datos sobreviven reconexión)
- ✅ Apilamiento de items del mismo tipo

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
5. **Verificar coverage**: Ejecutar `pytest --cov=src --cov-report=term` y verificar que:
   - La cobertura global se mantenga o mejore
   - Los nuevos módulos tengan cobertura adecuada según su tipo
   - Se cubran las ramas principales (if/else, try/except)
6. **Ejecutar tests nuevamente**: Correr `./run_tests.sh` hasta que no haya ningún error ni warning
7. **Actualizar README.md**: Si se agregaron/eliminaron archivos o cambió la arquitectura
8. **Commit y Push**: Solo cuando todo esté limpio y funcionando

## Pre-commit
- **OBLIGATORIO**: Antes de cada commit, ejecutar `./run_tests.sh` y verificar que todo pase
- El script incluye: ruff linter, ruff formatter, mypy type checker, y pytest
- NO hacer commit si algún check falla

## CI/CD
- GitHub Actions corre automáticamente los mismos checks que `run_tests.sh` en cada push
- Los checks deben pasar para poder mergear PRs
