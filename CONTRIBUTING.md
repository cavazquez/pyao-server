# Guía de Contribución - PyAO Server

Bienvenido al proyecto PyAO Server. Esta guía te ayudará a entender la estructura del proyecto y cómo contribuir de manera efectiva.

## 📋 Tabla de Contenidos

1. [Estructura del Proyecto](#estructura-del-proyecto)
2. [Convenciones de Naming](#convenciones-de-naming)
3. [Cómo Agregar Nuevos Componentes](#cómo-agregar-nuevos-componentes)
4. [Proceso de Desarrollo](#proceso-de-desarrollo)
5. [Estándares de Código](#estándares-de-código)

---

## 🏗️ Estructura del Proyecto

El proyecto sigue una arquitectura en capas bien definida:

```
src/
├── tasks/              # Handlers de packets (Command Pattern)
│   ├── player/        # Tasks de jugador (login, walk, attack, etc.)
│   ├── inventory/     # Tasks de inventario (equip, drop, use, etc.)
│   ├── commerce/      # Tasks de comercio (buy, sell, end)
│   ├── banking/       # Tasks de banco (deposit, extract, end)
│   ├── spells/        # Tasks de hechizos (cast, move, info)
│   ├── interaction/   # Tasks de interacción (pickup, talk, left_click)
│   ├── work/          # Tasks de trabajo (work, work_left_click)
│   └── admin/         # Tasks de administración (gm_commands)
│
├── commands/          # Comandos (Command Pattern - objetos de comando)
│   └── [mismo orden que tasks/]
│
├── command_handlers/  # Handlers de comandos (lógica de ejecución)
│   └── [mismo orden que tasks/]
│
├── services/          # Lógica de negocio reutilizable
│   ├── combat/        # Servicios de combate
│   ├── game/          # Servicios de juego (NPCs, clases, crafting)
│   ├── map/           # Servicios de mapas (transiciones, recursos, pathfinding)
│   ├── npc/           # Servicios de NPCs (IA, muerte, respawn, loot)
│   └── player/        # Servicios de jugador (auth, equipment, spells)
│
├── repositories/      # Acceso a datos (Redis)
│   └── [repositorios especializados por entidad]
│
├── models/            # Modelos de datos (dataclasses)
│   └── [NPC, Item, Party, CharacterClass, etc.]
│
├── network/           # Protocolo de red
│   ├── packet_*.py    # Validación, lectura, construcción
│   └── msg_*.py       # Construcción de mensajes específicos
│
├── messaging/         # Envío de mensajes al cliente
│   ├── message_sender.py  # Facade principal
│   └── senders/       # Senders especializados por dominio
│
├── game/              # Componentes del juego
│   └── map_manager.py # Gestor de mapas, jugadores, NPCs
│
├── effects/           # Efectos del sistema de tick
│   └── [hunger_thirst, npc_movement, meditation, etc.]
│
└── utils/             # Utilidades generales
    └── [sounds, visual_effects, level_calculator, etc.]
```

### Tests

Los tests espejan la estructura de `src/`:

```
tests/
├── tasks/             # Tests de tasks (misma estructura que src/tasks/)
├── services/          # Tests de services (misma estructura que src/services/)
├── repositories/      # Tests de repositories
├── models/            # Tests de models
├── network/           # Tests de network
├── integration/       # Tests de integración end-to-end
└── unit/              # Tests unitarios de componentes específicos
```

---

## 📝 Convenciones de Naming

### Archivos y Módulos

- **Tasks**: `task_<accion>.py` (ej: `task_login.py`, `task_attack.py`)
- **Commands**: `<accion>_command.py` (ej: `login_command.py`, `attack_command.py`)
- **Handlers**: `<accion>_handler.py` (ej: `login_handler.py`, `attack_handler.py`)
- **Services**: `<dominio>_service.py` (ej: `commerce_service.py`, `npc_service.py`)
- **Repositories**: `<entidad>_repository.py` (ej: `player_repository.py`, `npc_repository.py`)
- **Models**: `<entidad>.py` (ej: `npc.py`, `item.py`, `party.py`)
- **Tests**: `test_<nombre>.py` (ej: `test_task_login.py`, `test_commerce_service.py`)

### Clases

- **Tasks**: `Task<Accion>` (ej: `TaskLogin`, `TaskAttack`)
- **Commands**: `<Accion>Command` (ej: `LoginCommand`, `AttackCommand`)
- **Handlers**: `<Accion>CommandHandler` (ej: `LoginCommandHandler`, `AttackCommandHandler`)
- **Services**: `<Dominio>Service` (ej: `CommerceService`, `NPCService`)
- **Repositories**: `<Entidad>Repository` (ej: `PlayerRepository`, `NPCRepository`)
- **Models**: `<Entidad>` (ej: `NPC`, `Item`, `Party`)

### Métodos y Variables

- **Métodos públicos**: `snake_case` (ej: `buy_item()`, `spawn_npc()`)
- **Métodos privados**: `_snake_case` (ej: `_parse_packet()`, `_validate_item()`)
- **Variables**: `snake_case` (ej: `user_id`, `item_id`)
- **Constantes**: `UPPER_SNAKE_CASE` (ej: `MAX_PARTY_MEMBERS`, `VISIBLE_RANGE`)

---

## ➕ Cómo Agregar Nuevos Componentes

### 1. Agregar un Nuevo Task

**Paso 1:** Crear el Task en la categoría apropiada

```python
# src/tasks/<categoria>/task_<accion>.py
from src.tasks.task import Task

class Task<Accion>(Task):
    """Descripción del task."""
    
    def __init__(self, data: bytes, message_sender: MessageSender, ...):
        super().__init__(data, message_sender)
        # Inicializar dependencias
    
    def _parse_packet(self) -> ...:
        """Parsea el packet."""
        # Implementar parsing
    
    async def execute(self) -> None:
        """Ejecuta la lógica del task."""
        # Implementar lógica
```

**Paso 2:** Crear el Command correspondiente

```python
# src/commands/<accion>_command.py
from src.commands.base import BaseCommand

class <Accion>Command(BaseCommand):
    """Comando para <acción>."""
    
    def __init__(self, ...):
        # Parámetros del comando
```

**Paso 3:** Crear el Handler

```python
# src/command_handlers/<accion>_handler.py
from src.command_handlers.base import BaseCommandHandler

class <Accion>CommandHandler(BaseCommandHandler):
    """Handler para <acción>."""
    
    async def handle(self, command: <Accion>Command) -> None:
        """Maneja el comando."""
        # Implementar lógica
```

**Paso 4:** Registrar en TaskFactory

```python
# src/tasks/task_factory.py - Solo agregar al diccionario _task_classes:
PacketID.<PACKET_ID>: Task<Accion>,
```

> **Nota:** TaskFactory usa **auto-wiring** - resuelve automáticamente las dependencias
> del constructor del Task por introspección. No es necesario agregar imports ni mapeos
> manuales de dependencias. Los parámetros se resuelven en este orden:
> 1. Parámetros fijos: `data`, `message_sender`, `session_data`
> 2. Handlers: parámetros que terminan en `_handler` (via HandlerRegistry)
> 3. Datos pre-validados: parámetros que coinciden con claves de `parsed_data`
> 4. Dependencias del contenedor: atributos de `DependencyContainer`

**Paso 5:** Crear tests

```python
# tests/tasks/<categoria>/test_task_<accion>.py
import pytest
from src.tasks.<categoria>.task_<accion> import Task<Accion>

class TestTask<Accion>:
    """Tests para Task<Accion>."""
    
    @pytest.mark.asyncio
    async def test_<escenario>(self):
        """Test <escenario>."""
        # Implementar test
```

### 2. Agregar un Nuevo Service

**Paso 1:** Crear el Service en la categoría apropiada

```python
# src/services/<dominio>/<servicio>_service.py
class <Servicio>Service:
    """Descripción del servicio."""
    
    def __init__(self, ...):
        """Inicializa el servicio."""
        # Inicializar dependencias
    
    async def <metodo_principal>(self, ...) -> ...:
        """Descripción del método."""
        # Implementar lógica
```

**Paso 2:** Registrar en ServiceInitializer

```python
# src/core/service_initializer.py
from src.services.<dominio>.<servicio>_service import <Servicio>Service

# En initialize_services():
service = <Servicio>Service(...)
container.register_<servicio>_service(service)
```

**Paso 3:** Crear tests

```python
# tests/services/<dominio>/test_<servicio>_service.py
import pytest
from src.services.<dominio>.<servicio>_service import <Servicio>Service

class Test<Servicio>Service:
    """Tests para <Servicio>Service."""
    
    @pytest.mark.asyncio
    async def test_<escenario>(self):
        """Test <escenario>."""
        # Implementar test
```

### 3. Agregar un Nuevo Repository

**Paso 1:** Crear el Repository

```python
# src/repositories/<entidad>_repository.py
from src.repositories.base_repository import BaseRepository

class <Entidad>Repository(BaseRepository):
    """Repositorio para <entidad>."""
    
    def __init__(self, redis_client: RedisClient):
        super().__init__(redis_client)
        # Inicializar
    
    async def get_<entidad>(self, id: int) -> dict | None:
        """Obtiene <entidad> por ID."""
        # Implementar
```

**Paso 2:** Registrar en RepositoryInitializer

```python
# src/core/repository_initializer.py
from src.repositories.<entidad>_repository import <Entidad>Repository

# En initialize_repositories():
repo = <Entidad>Repository(redis_client)
container.register_<entidad>_repository(repo)
```

**Paso 3:** Crear tests

```python
# tests/repositories/test_<entidad>_repository.py
import pytest
from src.repositories.<entidad>_repository import <Entidad>Repository

class Test<Entidad>Repository:
    """Tests para <Entidad>Repository."""
    
    @pytest.mark.asyncio
    async def test_<escenario>(self, redis_client):
        """Test <escenario>."""
        # Implementar test
```

### 4. Agregar un Nuevo Model

**Paso 1:** Crear el Model

```python
# src/models/<entidad>.py
from dataclasses import dataclass

@dataclass
class <Entidad>:
    """Modelo de <entidad>."""
    
    id: int
    name: str
    # Otros campos
```

**Paso 2:** Crear tests

```python
# tests/models/test_<entidad>.py
import pytest
from src.models.<entidad> import <Entidad>

def test_<entidad>_creation():
    """Test creación de <entidad>."""
    # Implementar test
```

---

## 🔄 Proceso de Desarrollo

### 1. Antes de Empezar

1. **Asegúrate de tener el entorno configurado:**
   ```bash
   uv sync --dev
   ```

2. **Instala los pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```

3. **Levanta Redis con Docker Compose:**
   ```bash
   docker compose up -d                      # Redis
   docker compose --profile tools up -d      # Redis + Redis Insight GUI
   ```

4. **Ejecuta los tests para verificar que todo funciona:**
   ```bash
   ./run_tests.sh
   ```

### 2. Durante el Desarrollo

1. **Crea una rama para tu feature:**
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```

2. **Escribe código siguiendo las convenciones:**
   - Usa type hints en todos los métodos
   - Documenta con docstrings
   - Sigue el patrón de arquitectura existente

3. **Escribe tests:**
   - Crea tests para cada nueva funcionalidad
   - Asegúrate de cubrir casos edge
   - Usa mocks para dependencias externas

4. **Verifica calidad de código:**
   ```bash
   ./run_tests.sh  # Ejecuta linter, formatter, type checker y tests
   ```

### 3. Antes de Hacer Commit

Los pre-commit hooks ejecutan automáticamente `ruff` y `mypy` al hacer commit. Además:

1. **Verifica que todos los checks pasen:**
   ```bash
   ./run_tests.sh
   ```

2. **Asegúrate de que la cobertura no baje:**
   ```bash
   uv run pytest --cov=src --cov-report=term-missing
   ```

3. **Ejecuta pre-commit manualmente (opcional):**
   ```bash
   uv run pre-commit run --all-files
   ```

4. **Revisa tus cambios:**
   ```bash
   git diff
   git status
   ```

### 4. Hacer Commit y Push

1. **Haz commit con mensaje descriptivo:**
   ```bash
   git add -A
   git commit -m "feat: Agregar nueva funcionalidad X"
   ```

2. **Push a tu rama:**
   ```bash
   git push origin feature/nueva-funcionalidad
   ```

3. **Crea un Pull Request** en GitHub

---

## 📏 Estándares de Código

### Type Hints

**Siempre** usa type hints en:
- Parámetros de funciones/métodos
- Valores de retorno
- Variables de clase
- Variables locales (cuando no es obvio)

```python
async def buy_item(
    self,
    user_id: int,
    item_id: int,
    quantity: int,
) -> tuple[bool, str]:
    """Compra un item."""
    # ...
```

### Docstrings

**Siempre** documenta:
- Clases con descripción
- Métodos públicos con descripción y parámetros
- Métodos privados con descripción (opcional pero recomendado)

```python
class CommerceService:
    """Gestiona transacciones de compra/venta con mercaderes."""

    async def buy_item(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
    ) -> tuple[bool, str]:
        """Compra un item de un mercader.

        Args:
            user_id: ID del jugador.
            item_id: ID del item a comprar.
            quantity: Cantidad a comprar.

        Returns:
            Tupla (éxito, mensaje).
        """
        # ...
```

### Imports

**Orden de imports:**
1. Standard library
2. Third-party packages
3. Local imports (src/)

```python
import logging
from typing import TYPE_CHECKING

import pytest

from src.models.npc import NPC
from src.services.npc.npc_service import NPCService

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
```

### Tests

**Convenciones de tests:**
- Usa `pytest.mark.asyncio` para tests asíncronos
- Usa fixtures para setup común
- Nombra tests descriptivamente: `test_<escenario>_<resultado_esperado>`
- Agrupa tests relacionados en clases

```python
@pytest.mark.asyncio
class TestCommerceService:
    """Tests para CommerceService."""

    async def test_buy_item_success(self):
        """Test compra exitosa."""
        # ...

    async def test_buy_item_insufficient_gold(self):
        """Test compra sin oro suficiente."""
        # ...
```

---

## 🎯 Dónde Poner Cada Tipo de Código

### Lógica de Negocio

- **Por dominio específico**: `src/services/<dominio>/`
- **Reutilizable entre múltiples tasks**: `src/services/`
- **Específica de un packet**: En el Task o Handler correspondiente

### Acceso a Datos

- **Siempre** usa Repositories: `src/repositories/`
- **Nunca** accedas directamente a Redis desde Services o Tasks
- **Usa** el patrón Repository para abstraer Redis

### Manejo de Packets

- **Parsing**: En el Task (`_parse_packet()`)
- **Validación**: Usa `PacketValidator` antes de crear el Task
- **Construcción de respuestas**: Usa `MessageSender` o builders en `src/network/msg_*.py`

### Modelos de Datos

- **Entidades del juego**: `src/models/`
- **Usa dataclasses** para modelos inmutables
- **Documenta** cada campo del modelo

---

## 🚫 Qué NO Hacer

1. **NO** mezcles lógica de negocio en Tasks
   - ✅ Usa Services para lógica reutilizable
   - ❌ NO pongas lógica compleja directamente en Tasks

2. **NO** accedas directamente a Redis
   - ✅ Usa Repositories
   - ❌ NO uses `redis_client` directamente en Services

3. **NO** crees dependencias circulares
   - ✅ Usa `TYPE_CHECKING` para imports de tipo
   - ❌ NO importes módulos que te importan

4. **NO** ignores los linters
   - ✅ Resuelve todos los warnings de `ruff` y `mypy`
   - ❌ NO uses `# noqa` a menos que sea absolutamente necesario

5. **NO** commits sin tests
   - ✅ Escribe tests para nueva funcionalidad
   - ❌ NO hagas commits de código sin tests

---

## 📚 Recursos Adicionales

- **Arquitectura**: Ver `ARCHITECTURE.md` para diagramas y flujos
- **Documentación de Servicios**: Ver `docs/SERVICES_ARCHITECTURE.md`
- **Roadmap**: Ver `todo/ROADMAP_VERSIONES.md`
- **TODOs**: Ver `todo/TODO_CONSOLIDADO.md`

---

## ❓ Preguntas Frecuentes

### ¿Dónde va la lógica de validación?

- **Validación de packets**: `PacketValidator` (antes de crear el Task)
- **Validación de negocio**: En el Service correspondiente
- **Validación de datos**: En el Repository (validación de existencia, etc.)

### ¿Cómo manejo errores?

- **Errores de protocolo**: Retorna `None` o lanza excepciones específicas
- **Errores de negocio**: Retorna tuplas `(bool, str)` con éxito y mensaje
- **Errores críticos**: Lanza excepciones y loguea con `logger.exception()`

### ¿Cómo agrego un nuevo packet ID?

1. Agrega el ID en `src/network/packet_id.py`
2. Crea el Task correspondiente
3. Regístralo en `TaskFactory`
4. Crea el Command y Handler
5. Escribe tests

---

**Última actualización:** 2026-02-08  
**Mantenedor:** Equipo PyAO Server

