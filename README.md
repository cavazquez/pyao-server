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
- ![uv](https://img.shields.io/badge/uv-package_manager-6B4FBB?logo=python&logoColor=white) - Gestor de paquetes y entornos
- ![Ruff](https://img.shields.io/badge/Ruff-linter_&_formatter-D7FF64?logo=ruff&logoColor=black) - Linter y formatter ultra-rápido
- ![mypy](https://img.shields.io/badge/mypy-type_checker-blue?logo=python&logoColor=white) - Type checker estático
- ![pytest](https://img.shields.io/badge/pytest-testing-0A9EDC?logo=pytest&logoColor=white) - Framework de testing
- ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?logo=github-actions&logoColor=white) - Integración continua

## 🚀 Inicio Rápido

### Requisitos

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (gestor de paquetes)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/cavazquez/pyao-server.git
cd pyao-server

# Instalar dependencias
uv sync --dev
```

### Ejecutar el servidor

```bash
uv run pyao-server
```

El servidor escuchará en `0.0.0.0:7666` por defecto.

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
│   ├── client_connection.py     # Gestión de conexiones TCP
│   ├── message_sender.py        # Envío de mensajes específicos del juego
│   ├── task.py                  # Sistema de tareas (Task, TaskDice, TaskNull)
│   ├── packet_id.py             # Definición de IDs de paquetes (enums)
│   ├── packet_handlers.py       # Mapeo de packet IDs a handlers
│   ├── packet_builder.py        # Constructor de paquetes de bytes
│   └── msg.py                   # Construcción de mensajes del servidor
├── tests/                       # Tests unitarios (52 tests, 61% cobertura)
│   ├── __init__.py              # Inicialización del paquete de tests
│   ├── test_client_connection.py   # Tests de ClientConnection (6 tests)
│   ├── test_message_sender.py      # Tests de MessageSender (6 tests)
│   ├── test_task.py                # Tests de tareas (2 tests)
│   ├── test_packet_builder.py      # Tests de PacketBuilder (28 tests)
│   └── test_msg.py                 # Tests de mensajes (10 tests)
├── .github/                     # GitHub Actions workflows (CI/CD)
│   └── workflows/
│       ├── ci.yml               # Integración continua
│       └── release.yml          # Releases automáticos
├── pyproject.toml               # Configuración del proyecto y dependencias
├── uv.lock                      # Lock file de dependencias
├── run_tests.sh                 # Script para ejecutar todos los checks
├── Claude.md                    # Reglas de desarrollo
├── README.md                    # Este archivo
└── LICENSE                      # Licencia Apache 2.0
```

### Arquitectura

El servidor sigue una arquitectura de separación de responsabilidades:

- **`ArgentumServer`**: Maneja conexiones TCP y el ciclo de vida del servidor
- **`ClientConnection`**: Gestiona la conexión TCP básica (send, close, wait_closed)
- **`MessageSender`**: Envía mensajes específicos del juego al cliente
- **`Task`**: Procesa la lógica de negocio (tirada de dados, movimiento, etc.)
- **`PacketBuilder`**: Construye paquetes de bytes con validación (soporta bytes, int16, int32, strings)
- **`msg.py`**: Funciones para construir mensajes específicos del protocolo

## 🎮 Cliente Compatible

Este servidor es compatible con el cliente [ArgentumOnlineGodot](https://github.com/brian-christopher/ArgentumOnlineGodot).

## 📝 Desarrollo

El proyecto sigue estrictas reglas de calidad de código:
- **Ruff**: Todas las reglas habilitadas (modo estricto)
- **mypy**: Type checking estricto
- **pytest**: Tests obligatorios antes de commits

Ver [Claude.md](Claude.md) para las reglas completas de desarrollo.

## 📄 Licencia

Apache License 2.0 - ver [LICENSE](LICENSE) para más detalles.