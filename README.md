# PyAO Server

[![CI](https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml/badge.svg)](https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml)
[![Release](https://github.com/cavazquez/pyao-server/actions/workflows/release.yml/badge.svg)](https://github.com/cavazquez/pyao-server/actions/workflows/release.yml)
[![codecov](https://codecov.io/gh/cavazquez/pyao-server/branch/main/graph/badge.svg)](https://codecov.io/gh/cavazquez/pyao-server)
[![Downloads](https://img.shields.io/github/downloads/cavazquez/pyao-server/total.svg)](https://github.com/cavazquez/pyao-server/releases)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Servidor de Argentum Online implementado en Python 3.14+ con asyncio.

> Implementación moderna y eficiente del servidor de Argentum Online.

## 🛠️ Tecnologías

- ![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white) - Lenguaje de programación
- ![Redis](https://img.shields.io/badge/Redis-8.2+-DC382D?logo=redis&logoColor=white) - Base de datos en memoria para configuración y estado
- ![uv](https://img.shields.io/badge/uv-package_manager-6B4FBB?logo=python&logoColor=white) - Gestor de paquetes y entornos
- ![Ruff](https://img.shields.io/badge/Ruff-linter_&_formatter-D7FF64?logo=ruff&logoColor=black) - Linter y formatter ultra-rápido
- ![mypy](https://img.shields.io/badge/mypy-type_checker-blue?logo=python&logoColor=white) - Type checker estático
- ![pytest](https://img.shields.io/badge/pytest-testing-0A9EDC?logo=pytest&logoColor=white) - Framework de testing
- ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?logo=github-actions&logoColor=white) - Integración continua

## 🚀 Inicio Rápido

### Requisitos

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (gestor de paquetes)
- Redis 8.2+ (obligatorio, para configuración y estado distribuido)
- Docker (recomendado, para ejecutar Redis)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/cavazquez/pyao-server.git
cd pyao-server

# Instalar dependencias
uv sync --dev
```

### Configurar Redis (Obligatorio)

```bash
# Opción 1: Usar el Dockerfile incluido (recomendado)
docker build -t pyao-redis ./redis
docker run -d --name pyao-redis -p 6379:6379 pyao-redis

# Opción 2: Usar imagen oficial de Docker
docker run -d --name pyao-redis -p 6379:6379 redis:8-alpine

# Opción 3: Instalar localmente (Ubuntu/Debian)
sudo apt-get install redis-server
redis-server
```

**Interfaz Gráfica (Recomendado):** Para gestionar Redis visualmente, instala [Redis Insight](https://redis.io/insight/) (disponible en Snap, Flatpak, Docker y AppImage).

Ver [redis/README.md](redis/README.md) para documentación completa de Redis y Redis Insight.

### Ejecutar el servidor

```bash
uv run pyao-server
```

El servidor cargará automáticamente la configuración desde Redis (host, puerto, etc.) y almacenará el estado del juego.

**Nota:** Redis es obligatorio. El servidor no iniciará sin una conexión activa a Redis.

## 🧪 Testing

```bash
# Ejecutar todos los checks (linter, formatter, type checker, tests)
./run_tests.sh

# Solo tests
uv run pytest -v

# Tests con cobertura
uv run pytest -v --cov=src --cov-report=term-missing

# Solo linter
uv run ruff check .

# Solo type checker
uv run mypy .
```

## 📦 Estructura del Proyecto

```
pyao-server/
├── src/                         # Código fuente
│   ├── __init__.py              # Inicialización del paquete
│   ├── run_server.py            # Entry point del servidor
│   ├── server.py                # Servidor TCP principal (ArgentumServer)
│   ├── client_connection.py     # Gestión de conexiones TCP (send/receive)
│   ├── message_sender.py        # Envío de mensajes específicos del juego
│   │
│   ├── # Capa de Datos (Repositorios)
│   ├── player_repository.py     # Repositorio de datos de jugadores
│   ├── account_repository.py    # Repositorio de cuentas de usuario
│   ├── redis_client.py          # Cliente Redis (bajo nivel)
│   ├── redis_config.py          # Configuración y constantes de Redis
│   │
│   ├── # Lógica de Negocio (Tasks)
│   ├── task.py                  # Sistema de tareas base (clase abstracta)
│   ├── task_login.py            # Tarea de login
│   ├── task_account.py          # Tarea de creación de cuentas
│   ├── task_attributes.py       # Tarea de solicitud de atributos
│   ├── task_dice.py             # Tarea de tirada de dados
│   ├── task_talk.py             # Tarea de chat
│   ├── task_walk.py             # Tarea de movimiento
│   ├── task_change_heading.py   # Tarea de cambio de dirección
│   ├── task_null.py             # Tarea para packets desconocidos
│   │
│   ├── # Protocolo
│   ├── packet_id.py             # Definición de IDs de paquetes (enums)
│   ├── packet_handlers.py       # Mapeo de packet IDs a handlers
│   ├── packet_builder.py        # Constructor de paquetes de bytes
│   └── msg.py                   # Construcción de mensajes del servidor
│
├── tests/                       # Tests unitarios (131 tests)
│   ├── __init__.py              # Inicialización del paquete de tests
│   ├── test_client_connection.py   # Tests de ClientConnection
│   ├── test_message_sender.py      # Tests de MessageSender
│   ├── test_account_creation.py    # Tests de creación de cuentas
│   ├── test_task_change_heading.py # Tests de cambio de dirección (6 tests)
│   ├── test_task_dice.py           # Tests de TaskDice (1 test)
│   ├── test_task_null.py           # Tests de TaskNull (1 test)
│   ├── test_task_talk.py           # Tests de TaskTalk (9 tests)
│   ├── test_map_manager.py         # Tests de MapManager (19 tests)
│   ├── test_packet_builder.py      # Tests de PacketBuilder
│   ├── test_msg.py                 # Tests de mensajes y packets
│   └── test_redis_client.py        # Tests de Redis
│
├── redis/                       # Configuración de Redis
│   ├── Dockerfile               # Imagen Docker de Redis 8
│   └── README.md                # Documentación de Redis
│
├── docs/                        # Documentación
│   ├── LOGIN_FLOW.md            # Flujo de login
│   ├── ACCOUNT_CREATION.md      # Creación de cuentas
│   ├── redis_architecture.md    # Arquitectura de Redis
│   ├── REDIS_INTEGRATION.md     # Integración con Redis
│   ├── REFACTOR_REPOSITORIES.md # Refactorización de repositorios
│   └── COVERAGE_ANALYSIS.md     # Análisis de cobertura de tests
│
├── .github/                     # GitHub Actions workflows (CI/CD)
│   └── workflows/
│       ├── ci.yml               # Integración continua
│       └── release.yml          # Releases automáticos
│
├── pyproject.toml               # Configuración del proyecto y dependencias
├── uv.lock                      # Lock file de dependencias
├── run_tests.sh                 # Script para ejecutar todos los checks
├── Claude.md                    # Reglas de desarrollo
├── README.md                    # Este archivo
└── LICENSE                      # Licencia Apache 2.0
```

### Arquitectura

El servidor sigue una **arquitectura en capas** con separación de responsabilidades:

#### Capa de Red
- **`ArgentumServer`**: Maneja conexiones TCP y el ciclo de vida del servidor
- **`ClientConnection`**: Gestiona la conexión TCP (send/receive, close, wait_closed)
- **`MessageSender`**: Envía mensajes específicos del juego al cliente

#### Capa de Datos (Repositorios)
- **`PlayerRepository`**: Gestión de datos de jugadores (posición, stats, hambre/sed, atributos)
- **`AccountRepository`**: Gestión de cuentas (crear, obtener, verificar password)
- **`RedisClient`**: Cliente Redis de bajo nivel (conexión, configuración, sesiones)
- **`RedisConfig`**: Configuración y constantes de Redis

#### Capa de Lógica de Negocio (Tasks)
- **`Task`**: Clase base abstracta para procesamiento de paquetes
- **`TaskLogin`**: Procesa login de usuarios
- **`TaskCreateAccount`**: Procesa creación de cuentas
- **`TaskRequestAttributes`**: Procesa solicitud de atributos
- **`TaskDice`**: Procesa tirada de dados
- **`TaskTalk`**: Procesa mensajes de chat
- **`TaskWalk`**: Procesa movimiento del personaje
- **`TaskChangeHeading`**: Procesa cambio de dirección sin moverse
- **`TaskNull`**: Maneja packets desconocidos

#### Capa de Protocolo
- **`PacketBuilder`**: Construye paquetes de bytes con validación
- **`msg.py`**: Funciones para construir mensajes específicos del protocolo
- **`packet_id.py`**: Enums de IDs de paquetes
- **`packet_handlers.py`**: Mapeo de packet IDs a handlers

```
┌─────────────────────────────────────────┐
│         Capa de Red                     │
│  ArgentumServer → ClientConnection      │
│         ↓                                │
│    MessageSender                         │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼────────┐ ┌──▼────────────────┐
│ Capa de Datos  │ │ Lógica Negocio    │
│ PlayerRepo     │ │ Tasks             │
│ AccountRepo    │ │ (Login, Create,   │
│ RedisClient    │ │  Attributes, etc) │
└────────────────┘ └───────────────────┘
```

### Integración con Redis

Redis se utiliza para:

- **Configuración del servidor**: Host, puerto, límites de conexiones
- **Cuentas de usuario**: Almacenamiento de cuentas, autenticación
- **Estado del juego**: Sesiones de jugadores, posiciones, inventarios
- **Métricas en tiempo real**: Contador de conexiones activas, estadísticas

Estructura de claves en Redis:

```
# Configuración (gestionada por RedisClient)
config:server:host              # Host del servidor
config:server:port              # Puerto del servidor
config:server:max_connections   # Límite de conexiones

# Sesiones (gestionadas por RedisClient)
server:connections:count        # Contador de conexiones activas
session:{user_id}:active        # Sesión activa del jugador
session:{user_id}:last_seen     # Último acceso del jugador

# Cuentas (gestionadas por AccountRepository)
accounts:counter                # Contador autoincremental de user_id
account:{username}:data         # Datos de la cuenta (hash)
account:username:{username}     # Mapeo username -> user_id

# Jugadores (gestionadas por PlayerRepository)
player:{user_id}:position       # Posición del jugador (x, y, map, heading)
player:{user_id}:user_stats     # Estadísticas (HP, mana, stamina, gold, level, exp)
player:{user_id}:hunger_thirst  # Hambre y sed (max/min water/hunger)
player:{user_id}:stats          # Atributos (STR, AGI, INT, CHA, CON)
player:{user_id}:character      # Datos del personaje (race, gender, job, head, home)
player:{user_id}:inventory      # Inventario del jugador
```

## 🎮 Cliente Compatible

Este servidor implementa el **protocolo estándar de Argentum Online Godot** y es 100% compatible con:

- **[ArgentumOnlineGodot](https://github.com/brian-christopher/ArgentumOnlineGodot)** (brian-christopher)
- Basado en Argentum Online 0.13.3
- Requiere Godot 4.4.1+

## 📚 Documentación

### Protocolo y Flujos
- **[Flujo de Login](docs/LOGIN_FLOW.md)**: Protocolo estándar de login y mensajes post-login
- **[Creación de Cuentas](docs/ACCOUNT_CREATION.md)**: Protocolo y validaciones para crear cuentas

### Arquitectura y Diseño
- **[Arquitectura Redis](docs/redis_architecture.md)**: Estructura de datos y claves en Redis
- **[Integración Redis](docs/REDIS_INTEGRATION.md)**: Guía de integración con Redis
- **[Refactorización de Repositorios](docs/REFACTOR_REPOSITORIES.md)**: Separación de responsabilidades

### Calidad y Testing
- **[Análisis de Cobertura](docs/COVERAGE_ANALYSIS.md)**: Análisis detallado de cobertura de tests

## 📝 Desarrollo

El proyecto sigue estrictas reglas de calidad de código:
- **Ruff**: Todas las reglas habilitadas (modo estricto)
- **mypy**: Type checking estricto
- **pytest**: Tests obligatorios antes de commits

Ver [Claude.md](Claude.md) para las reglas completas de desarrollo.

## 📄 Licencia

Apache License 2.0 - ver [LICENSE](LICENSE) para más detalles.