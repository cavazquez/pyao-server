# PyAO Server

[![CI](https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml/badge.svg)](https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml)
[![Release](https://github.com/cavazquez/pyao-server/actions/workflows/release.yml/badge.svg)](https://github.com/cavazquez/pyao-server/actions/workflows/release.yml)
[![codecov](https://codecov.io/gh/cavazquez/pyao-server/branch/main/graph/badge.svg)](https://codecov.io/gh/cavazquez/pyao-server)
[![Downloads](https://img.shields.io/github/downloads/cavazquez/pyao-server/total.svg)](https://github.com/cavazquez/pyao-server/releases)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/cavazquez/pyao-server)

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

# Para habilitar TLS/SSL (usa certificados en certs/server.{crt,key} por defecto)
uv run pyao-server --ssl --ssl-cert certs/server.crt --ssl-key certs/server.key
```

El servidor cargará automáticamente la configuración desde Redis (host, puerto, etc.) y almacenará el estado del juego.

**Nota:** Redis es obligatorio. El servidor no iniciará sin una conexión activa a Redis.
**Nuevo:** El login de Godot incluye un checkbox "Usar conexión SSL" que recuerda la preferencia del usuario.

### 🎒 Inventario inicial

Al crear un personaje nuevo se entregan automáticamente:

- 5 Pociones Rojas y 5 Pociones Azules
- 10 Manzanas y 10 Aguas
- 1 Daga y la Armadura de Aprendiz (ID 1073)
- Herramientas de trabajo: Hacha de Leñador (ID 561), Piquete Minero (ID 562) y Caña de Pescar (ID 563)

Las herramientas permiten entrar al modo de trabajo (tecla **U**) para talar, minar y pescar desde el inicio.

## 🧪 Testing

```bash
# Ejecutar todos los checks (linter, formatter, type checker, tests)
./run_tests.sh

# Solo tests
uv run pytest -v

# Tests con cobertura
uv run pytest -v --cov=src --cov-report=term-missing

# Tests de seguridad (SSL)
uv run pytest tests/security/test_ssl_manager.py

# Solo linter
uv run ruff check .

# Solo type checker
uv run mypy .
```

## 🏗️ Arquitectura

El servidor utiliza una **arquitectura modular** con patrones de diseño modernos:

- **Factory Pattern** - TaskFactory para creación de tasks
- **Dependency Injection** - DependencyContainer centralizado
- **Facade Pattern** - ServerInitializer para inicialización
- **Repository Pattern** - Abstracción de acceso a datos
- **Strategy Pattern** - Dictionary-based task creation

Ver **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** para documentación completa de la arquitectura.

### Estadísticas del Código

- **server.py:** 685 → 194 líneas (-72% reducción) ✅
- **msg.py:** 763 líneas → 8 módulos especializados ✅
- **PacketValidator:** 16 tasks migradas (100% de las que leen datos) ✅
- **NPCFactory:** 16 factory methods (14 NPCs) ✅ **NUEVO**
- **Tests:** 990 tests pasando (100%) ✅
- **Calidad:** 0 errores de linting, 0 errores de mypy ✅

### Sistema de Validación de Packets

**PacketValidator** - Sistema centralizado de validación y parsing de packets:

- ✅ **16 tasks migradas** (100% de las que leen datos del packet)
- ✅ **8 métodos de validación** (slot, quantity, coordinates, strings, etc.)
- ✅ **Reducción de código** del 40-70% en tasks migradas
- ✅ **Type safety completo** con mypy
- ✅ **Mensajes de error descriptivos** para debugging

Ver **[PACKET_VALIDATOR_MIGRATION.md](docs/PACKET_VALIDATOR_MIGRATION.md)** para documentación completa.

## 📦 Estructura del Proyecto

```
pyao-server/
├── src/                         # Código fuente (refactorizado ✅)
│   ├── __init__.py              # Inicialización del paquete
│   ├── run_server.py            # Entry point del servidor
│   ├── server.py                # Servidor TCP principal (194 líneas, -72%)
│   ├── client_connection.py     # Gestión de conexiones TCP
│   │
│   ├── # MessageSender (Patrón Facade) ✅ REFACTORIZADO
│   ├── message_sender.py        # Facade que delega a componentes
│   ├── message_map_sender.py    # Mensajes de mapa (5 métodos)
│   ├── message_console_sender.py # Mensajes de consola (3 métodos)
│   ├── message_audio_sender.py  # Mensajes de audio (12 métodos)
│   ├── message_visual_effects_sender.py # Efectos visuales (6 métodos)
│   ├── message_player_stats_sender.py # Stats del jugador (6 métodos)
│   │   ├── message_character_sender.py # Envío de personajes/NPCs
│   │   ├── message_npc_sender.py     # Envío especializado de NPCs ✅ NUEVO (4 métodos)
│   ├── message_inventory_sender.py # Inventario/Banco/Comercio (9 métodos)
│   ├── message_session_sender.py # Sesión/Login (4 métodos)
│   │
│   ├── # Arquitectura (Initializers & Containers) ✅ REFACTORIZADO
│   ├── dependency_container.py  # Contenedor de dependencias (24 deps)
│   ├── task_factory.py          # Factory para crear tasks (25 tipos)
│   ├── server_initializer.py    # Orquestador principal
│   ├── redis_initializer.py     # Inicialización de Redis
│   ├── repository_initializer.py # Creación de repositorios (10)
│   ├── service_initializer.py   # Creación de servicios (8)
│   ├── game_tick_initializer.py # Configuración de GameTick
│   │
│   ├── # Data Loaders (Inicialización de Datos) ✅ NUEVO
│   ├── base_data_loader.py      # Clase base abstracta para loaders
│   ├── merchant_data_loader.py  # Carga inventarios de mercaderes
│   ├── data_initializer.py      # Orquestador de loaders
│   │
│   ├── # Servicios (Lógica Reutilizable)
│   ├── player_service.py        # Gestión de jugadores
│   ├── player_map_service.py    # Spawn y transiciones de mapa ✅ NUEVO
│   ├── npc_service.py           # Gestión de NPCs
│   ├── npc_factory.py           # Factory methods para crear NPCs ✅ NUEVO
│   ├── npc_ai_service.py        # IA de NPCs hostiles
│   ├── npc_respawn_service.py   # Respawn de NPCs
│   ├── combat_service.py        # Sistema de combate
│   ├── commerce_service.py      # Sistema de comercio
│   ├── spell_service.py         # Sistema de hechizos
│   ├── loot_table_service.py    # Sistema de loot
│   ├── authentication_service.py # Autenticación
│   ├── session_manager.py       # Gestión de sesiones
│   ├── multiplayer_broadcast_service.py # Broadcast multijugador
│   ├── password_utils.py        # Utilidades de contraseñas
│   │
│   ├── # Servicios de Juego ✅ NUEVO
│   ├── game/
│   │   ├── __init__.py          # Paquete de servicios de juego
│   │   ├── balance_service.py   # Balance de clases y razas (extraído de cliente)
│   │   ├── crafting_service.py  # Sistema de crafting herrería (extraído de cliente)
│   │   ├── npc_service.py       # Sistema completo de gestión de NPCs (336 NPCs)
│   │   ├── npc_spawn_service.py # Spawning de NPCs en mapas con visión dinámica
│   │   └── npc_world_manager.py # Gestor de NPCs en el mundo (combate, movimiento)
│   │
│   ├── # Repositorios (Capa de Datos)
│   ├── player_repository.py     # Datos de jugadores
│   ├── npc_repository.py        # NPCs en Redis
│   ├── account_repository.py    # Cuentas de usuario
│   ├── server_repository.py     # Configuración del servidor
│   ├── inventory_repository.py  # Inventarios de jugadores
│   ├── equipment_repository.py  # Equipamiento de jugadores
│   ├── merchant_repository.py   # Inventarios de mercaderes
│   ├── bank_repository.py       # Bóvedas bancarias
│   ├── spellbook_repository.py  # Libros de hechizos
│   ├── ground_items_repository.py # Items en el suelo
│   ├── redis_client.py          # Cliente Redis (bajo nivel)
│   ├── redis_config.py          # Configuración y keys de Redis
│   │
│   ├── # Tasks (Lógica de Negocio por Packet)
│   ├── task.py                  # Clase base abstracta
│   ├── task_login.py            # Login
│   ├── task_account.py          # Creación de cuentas
│   ├── task_attributes.py       # Solicitud de atributos
│   ├── task_dice.py             # Tirada de dados
│   ├── task_talk.py             # Chat
│   ├── task_walk.py             # Movimiento
│   ├── task_attack.py           # Ataque
│   ├── task_cast_spell.py       # Lanzar hechizo
│   ├── task_meditate.py         # Meditación
│   ├── task_drop.py             # Tirar item
│   ├── task_pickup.py           # Recoger item
│   ├── task_equip_item.py       # Equipar item
│   ├── task_left_click.py       # Click en NPC
│   ├── task_double_click.py     # Doble click
│   ├── task_commerce_buy.py     # Comprar item
│   ├── task_commerce_sell.py    # Vender item
│   ├── task_commerce_end.py     # Cerrar comercio
│   ├── task_bank_deposit.py     # Depositar en banco
│   ├── task_bank_extract.py     # Extraer del banco
│   ├── task_bank_end.py         # Cerrar banco
│   ├── task_change_heading.py   # Cambio de dirección
│   ├── task_motd.py             # MOTD
│   ├── task_inventory_click.py  # Click en inventario
│   ├── task_null.py             # Packets desconocidos
│   │
│   ├── # Protocolo y Validación ✅ REFACTORIZADO
│   ├── packet_id.py             # IDs de paquetes (enums)
│   ├── packet_handlers.py       # Mapeo packet ID → handler
│   ├── packet_builder.py        # Constructor de paquetes
│   ├── packet_reader.py         # Lectura estructurada de packets
│   ├── packet_validator.py      # Validación de packets (32 validadores) ✅ NUEVO
│   ├── task_factory.py          # Factory con pre-validación automática ✅ MEJORADO
│   ├── msg.py                   # Construcción de mensajes (642 líneas → refactorizar)
│   │
│   ├── # Sistema de Juego
│   ├── map_manager.py           # Gestor de mapas/jugadores/NPCs
│   ├── map_manager_spatial.py   # Índices espaciales
│   ├── game_tick.py             # Sistema de tick (efectos periódicos)
│   ├── effect_hunger_thirst.py  # Efecto de hambre y sed
│   ├── effect_gold_decay.py     # Efecto de decaimiento de oro
│   ├── effect_npc_movement.py   # Efecto de movimiento de NPCs
│   ├── meditation_effect.py     # Efecto de meditación
│   ├── npc_ai_effect.py         # Efecto de IA de NPCs
│   ├── items_catalog.py         # Catálogo de items (1049 items)
│   ├── item_catalog.py          # Clase ItemCatalog
│   ├── item.py                  # Modelo de Item
│   ├── npc_catalog.py           # Catálogo de NPCs
│   ├── npc.py                   # Modelo de NPC
│   ├── spell_catalog.py         # Catálogo de hechizos
│   └── inventory_stacking_strategy.py # Estrategia de stacking
│
├── data/                        # Datos del juego
│   ├── npcs_hostiles.toml       # NPCs hostiles (Goblin, Lobo, etc.)
│   ├── npcs_amigables.toml      # NPCs amigables (Comerciante, Banquero, etc.)
│   ├── map_npcs.toml            # Spawns de NPCs en mapas
│   ├── merchant_inventories.toml # Inventarios de mercaderes
│   ├── items.toml               # Catálogo de items (1049 items)
│   ├── loot_tables.toml         # Tablas de loot de NPCs
│   ├── classes_balance.toml     # Balance de clases y razas (extraído de cliente) ✅ NUEVO
│   ├── weapons_crafting.toml    # Recetas de armas (extraído de cliente) ✅ NUEVO
│   ├── armor_crafting.toml      # Recetas de armaduras (extraído de cliente) ✅ NUEVO
│   └── crafting_materials.toml  # Materiales base para crafting ✅ NUEVO
│
├── map_data/                    # Datos de mapas (generados desde clientes VB6/Godot)
│   ├── 001_metadata.json        # Metadatos del mapa (nombre, clima, tamaño)
│   ├── 001_ground.json          # Tiles de capa base (100x100)
│   ├── 001_upper.json           # Sprites de la capa superior
│   ├── 001_graphics.json        # Sprites adicionales/efectos
│   ├── 001_flags.json           # Flags originales del mapa (desde VB6)
│   ├── 001_triggers.json        # Triggers detectados (zonas seguras, portales, etc.)
│   ├── 001_blocked.json         # Tiles bloqueados y recursos detectados
│   └── ...                      # Archivos XXX_*.json por cada capa del mapa
│
├── tools/                       # Scripts utilitarios
│   ├── compress_map_data.py     # Comprime map_data en archives/map_data.xz (LZMA)
│   ├── decompress_map_data.py   # Restaura map_data desde archives/map_data.xz
│   │
│   └── extract_client_data/     # Extracción de datos del cliente ✅ NUEVO
│       ├── extract_balance_data.py   # Extrae Balance.dat → TOML
│       ├── extract_crafting_data.py  # Extrae ArmasHerrero/ArmadurasHerrero → TOML
│       ├── extract_npcs_data.py      # Extrae NPCs.dat → TOML (336 NPCs) ✅ NUEVO
│       ├── extract_map_objects.py    # Extrae objetos de mapas .map → JSON consolidado
│       ├── optimize_map_data.py      # Optimiza metadata/blocked → JSON compacto
│       └── reoptimize_metadata.py    # Formato mejorado: 1 mapa por línea
│
├── tests/                       # Tests unitarios (1113 tests) ✅
│   ├── __init__.py              # Inicialización del paquete de tests
│   │
│   ├── # Tests de Arquitectura (13 tests) ✅ NUEVO
│   ├── test_dependency_container.py # Tests de DependencyContainer (1 test)
│   ├── test_task_factory.py     # Tests de TaskFactory (6 tests)
│   ├── test_repository_initializer.py # Tests de RepositoryInitializer (2 tests)
│   ├── test_service_initializer.py # Tests de ServiceInitializer (1 test)
│   ├── test_game_tick_initializer.py # Tests de GameTickInitializer (3 tests)
│   │
│   ├── # Tests de Data Loaders (21 tests) ✅ NUEVO
│   ├── test_merchant_data_loader.py # Tests de MerchantDataLoader (11 tests)
│   ├── test_data_initializer.py  # Tests de DataInitializer (10 tests)
│   │
│   ├── # Tests de Servicios (76 tests)
│   ├── test_player_service.py      # Tests de PlayerService (7 tests)
│   ├── test_authentication_service.py # Tests de AuthenticationService (4 tests)
│   ├── test_session_manager.py     # Tests de SessionManager (13 tests)
│   ├── test_balance_service.py     # Tests de BalanceService (7 tests)
│   ├── test_crafting_service.py    # Tests de CraftingService (8 tests)
│   ├── test_npc_service.py         # Tests de NPCService (11 tests) ✅ NUEVO
│   ├── test_npc_spawn_service.py   # Tests de NPCSpawnService (15 tests) ✅ NUEVO
│   ├── test_npc_world_manager.py   # Tests de NPCWorldManager (25 tests) ✅ NUEVO
│   ├── test_npc_message_sender.py  # Tests de NPCMessageSender (16 tests) ✅ NUEVO
│   │
│   ├── # Tests de MessageSender Components (75 tests) ✅ REFACTORIZADO
│   ├── test_message_sender.py      # Tests de MessageSender
│   ├── test_message_map_sender.py  # Tests de MapMessageSender (9 tests)
│   ├── test_message_console_sender.py # Tests de ConsoleMessageSender (9 tests)
│   ├── test_message_audio_sender.py # Tests de AudioMessageSender (15 tests)
│   ├── test_message_visual_effects_sender.py # Tests de VisualEffectsMessageSender (9 tests)
│   ├── test_message_player_stats_sender.py # Tests de PlayerStatsMessageSender (8 tests)
│   ├── test_message_character_sender.py # Tests de CharacterMessageSender (8 tests)
│   ├── test_message_inventory_sender.py # Tests de InventoryMessageSender (11 tests)
│   ├── test_message_session_sender.py # Tests de SessionMessageSender (6 tests)
│   │
│   ├── # Tests de Protocolo (15 tests) ✅ NUEVO
│   ├── test_packet_reader.py       # Tests de PacketReader (15 tests)
│   │
│   ├── # Tests de Tasks
│   ├── test_account_creation.py    # Tests de creación de cuentas
│   ├── test_task_change_heading.py # Tests de cambio de dirección
│   ├── test_task_dice.py           # Tests de TaskDice
│   ├── test_task_null.py           # Tests de TaskNull
│   ├── test_task_talk.py           # Tests de TaskTalk
│   ├── test_map_manager.py         # Tests de MapManager
│   ├── test_packet_builder.py      # Tests de PacketBuilder
│   ├── test_msg.py                 # Tests de mensajes y packets
│   └── test_redis_client.py        # Tests de Redis
│
├── redis/                       # Configuración de Redis
│   ├── Dockerfile               # Imagen Docker de Redis 8
│   └── README.md                # Documentación de Redis
│
├── docs/                        # Documentación
│   ├── ARCHITECTURE.md          # Arquitectura completa del servidor ⭐ NUEVO
│   ├── LOGIN_FLOW.md            # Flujo de login
│   ├── ACCOUNT_CREATION.md      # Creación de cuentas
│   ├── NPC_SYSTEM.md            # Sistema de NPCs
│   ├── COMMERCE_SYSTEM.md       # Sistema de comercio con mercaderes
│   ├── GAME_TICK_SYSTEM.md      # Sistema de tick y efectos periódicos
│   ├── MESSAGE_SENDER_USAGE.md  # Guía de uso de MessageSender
│   ├── REFACTOR_MSG_COMPLETED.md # Refactorización de msg.py ✅ COMPLETADO
│   ├── REFACTOR_SERVER_COMPLETED.md # Refactorización de server.py ✅ COMPLETADO
│   ├── TODO_PACKET_VALIDATOR.md # TODO: Sistema de validación de packets ⭐ NUEVO
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
- **`NPCRepository`**: Gestión de NPCs en Redis (crear, obtener, actualizar, eliminar)
- **`AccountRepository`**: Gestión de cuentas (crear, obtener, verificar password)
- **`RedisClient`**: Cliente Redis de bajo nivel (conexión, configuración, sesiones)
- **`RedisConfig`**: Configuración y constantes de Redis

#### Capa de Servicios
- **`PlayerMapService`**: ✅ **NUEVO** - Centraliza lógica de spawn y transiciones de mapa
  - `spawn_in_map()`: Aparición inicial del jugador (login)
  - `transition_to_map()`: Cambio de mapa (transiciones, teletransporte)
  - Elimina ~400 líneas de código duplicado en 3 archivos
  - Encapsula secuencia de 12 pasos para cambios de mapa
- **`CombatService`**: Sistema de combate jugador vs NPC
- **`CommerceService`**: Sistema de comercio con NPCs
- **`SpellService`**: Sistema de hechizos y magia
- **`NPCService`**: Gestión de NPCs (spawn, respawn, movimiento)
- **`AuthenticationService`**: Autenticación de usuarios

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

#### Sistema de Validación de Packets ✅ NUEVO
El servidor implementa un **sistema de validación en dos capas** (defensa en profundidad) para todos los packets del cliente:

**Capa 1: Pre-validación en TaskFactory**
- **`PacketValidator`**: 32 métodos `validate_*()` para cada tipo de packet
- **`ValidationResult`**: Dataclass que encapsula el resultado de validación
- **Fail-fast**: Valida ANTES de crear la task
- **Logging automático**: Registra todas las validaciones (✓ exitosas, ✗ fallidas)
- **Envío de errores**: Notifica al cliente inmediatamente si hay error
- **Performance**: Evita crear tasks innecesarias para packets inválidos

**Capa 2: Validación en Tasks**
- Validación defensiva dentro de cada task
- Segunda capa de seguridad
- Permite tests unitarios directos de tasks

**Packets con Validación (32/32 = 100% cobertura):**
- Con parámetros: LOGIN, CREATE_ACCOUNT, WALK, ATTACK, CAST_SPELL, DROP, TALK, DOUBLE_CLICK, LEFT_CLICK, EQUIP_ITEM, USE_ITEM, COMMERCE_BUY/SELL, BANK_DEPOSIT/EXTRACT, CHANGE_HEADING, GM_COMMANDS
- Sin parámetros: THROW_DICES, REQUEST_ATTRIBUTES, PICK_UP, COMMERCE_END, BANK_END, REQUEST_POSITION_UPDATE, MEDITATE, REQUEST_STATS, INFORMATION, REQUEST_MOTD, UPTIME, ONLINE, QUIT, PING, AYUDA

**Ejemplo de uso:**
```python
# En TaskFactory.create_task()
validation_result = validator.validate_walk_packet()
validation_result.log_validation("WALK", 6, "127.0.0.1:12345")

if not validation_result.success:
    await message_sender.send_console_msg(validation_result.error_message)
    return TaskNull(data, message_sender)

# Logs generados automáticamente:
# [127.0.0.1:12345] ✓ Packet WALK (ID:6) validado correctamente: {'heading': 1}
# [127.0.0.1:12345] ✗ Packet WALK (ID:6) inválido: Dirección inválida: 5 (debe ser 1-4)
```

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
player:{user_id}:hunger_thirst  # Hambre y sed (max/min water/hunger, flags, counters)
player:{user_id}:stats          # Atributos (STR, AGI, INT, CHA, CON)
player:{user_id}:character      # Datos del personaje (race, gender, job, head, home)
player:{user_id}:inventory      # Inventario del jugador

# NPCs (gestionadas por NPCRepository)
npc:instance:{instance_id}      # Datos de una instancia de NPC (hash)
npc:map:{map_id}                # Índice de NPCs en un mapa (set)
```

### Sistema de Tick del Juego

El servidor implementa un **sistema de tick genérico y configurable** que aplica efectos periódicos a todos los jugadores conectados. **Todas las constantes se almacenan en Redis** y pueden modificarse sin reiniciar el servidor.

#### Efectos Implementados

**1. Hambre y Sed** (basado en General.bas:1369-1422 del servidor original VB6)
- **Intervalo de Sed**: Configurable (default: 4 segundos)
- **Intervalo de Hambre**: Configurable (default: 6 segundos)
- **Reducción de Agua**: Configurable (default: 10 puntos)
- **Reducción de Hambre**: Configurable (default: 10 puntos)
- **Flags de Estado**: Cuando agua o comida llegan a 0, se activa un flag
- **Notificación**: Los cambios se envían mediante UPDATE_HUNGER_AND_THIRST

**2. Reducción de Oro**
- **Intervalo**: Configurable (default: 60 segundos)
- **Reducción**: Configurable (default: 1% del oro actual)
- **Notificación**: El jugador recibe un mensaje en consola y actualización de stats

#### Configuración en Redis

Todas las constantes se almacenan en Redis y pueden modificarse en tiempo real:

```bash
# Hambre y Sed
redis-cli SET config:effects:hunger_thirst:enabled 1
redis-cli SET config:effects:hunger_thirst:interval_sed 180
redis-cli SET config:effects:hunger_thirst:interval_hambre 180
redis-cli SET config:effects:hunger_thirst:reduccion_agua 10
redis-cli SET config:effects:hunger_thirst:reduccion_hambre 10

# Reducción de Oro
redis-cli SET config:effects:gold_decay:enabled 1
redis-cli SET config:effects:gold_decay:percentage 1.0
redis-cli SET config:effects:gold_decay:interval_seconds 60.0

# Dados (valores mínimo y máximo para atributos)
redis-cli SET server:dice:min_value 6
redis-cli SET server:dice:max_value 18
```

**Ejemplos de Configuración:**

```bash
# Hambre/sed más agresiva (cada 30 segundos, -20 puntos)
redis-cli SET config:effects:hunger_thirst:interval_sed 30
redis-cli SET config:effects:hunger_thirst:reduccion_agua 20

# Oro más suave (0.5% cada 2 minutos)
redis-cli SET config:effects:gold_decay:percentage 0.5
redis-cli SET config:effects:gold_decay:interval_seconds 120.0

# Desactivar un efecto
redis-cli SET config:effects:gold_decay:enabled 0

# Dados más difíciles (8-16 en lugar de 6-18)
redis-cli SET server:dice:min_value 8
redis-cli SET server:dice:max_value 16
```

Los cambios se aplican **inmediatamente** en el próximo tick (no requiere reiniciar el servidor).

**Ejemplo de Salida del Servidor:**
```
INFO - Configuración de efecto inicializada: config:effects:hunger_thirst:enabled = 1
INFO - Configuración de efecto inicializada: config:effects:gold_decay:percentage = 1.0
INFO - Efecto de hambre/sed habilitado
INFO - Efecto de reducción de oro habilitado
INFO - Sistema de tick iniciado (intervalo: 1.0s, efectos: 2)
INFO - user_id 1: oro reducido de 1000 a 990 (-10, 1.0%)
INFO - user_id 2 tiene sed (agua = 0)
```

Ver **[documentación completa del sistema de tick](docs/GAME_TICK_SYSTEM.md)** para crear efectos personalizados.

## 🎮 Cliente Compatible

Este servidor implementa el **protocolo estándar de Argentum Online Godot** y es 100% compatible con:

- **[ArgentumOnlineGodot](https://github.com/brian-christopher/ArgentumOnlineGodot)** (brian-christopher)
- Basado en Argentum Online 0.13.3
- Requiere Godot 4.4.1+

## 📚 Documentación

### Arquitectura ⭐
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Arquitectura completa del servidor, patrones de diseño y componentes **NUEVO**
- **[Refactorización Server](docs/REFACTOR_SERVER_COMPLETED.md)**: Refactorización completada de server.py ✅
- **[Refactorización MSG](docs/REFACTOR_MSG_COMPLETED.md)**: Refactorización completada de msg.py ✅

### Protocolo y Flujos
- **[Flujo de Login](docs/LOGIN_FLOW.md)**: Protocolo estándar de login y mensajes post-login
- **[Creación de Cuentas](docs/ACCOUNT_CREATION.md)**: Protocolo y validaciones para crear cuentas

### Sistema de Juego
- **[Sistema de NPCs](docs/NPC_SYSTEM.md)**: NPCs, spawns, catálogos y protocolo
- **[Sistema de Comercio](docs/COMMERCE_SYSTEM.md)**: Compra/venta con mercaderes, protocolo completo
- **[Sistema de Tick del Juego](docs/GAME_TICK_SYSTEM.md)**: Sistema genérico de efectos periódicos

### Sistemas Completados ✅
- **[NPC Factory](docs/NPC_FACTORY_COMPLETED.md)**: Sistema de factory methods para crear NPCs con FX ✅ **COMPLETADO**
- **[Sistema de Validación](docs/PACKET_VALIDATOR_MIGRATION.md)**: PacketValidator centralizado ✅ **COMPLETADO**

### TODOs y Mejoras Futuras
- **[TODO: Refactoring](docs/TODO_REFACTORING.md)**: Mejoras de arquitectura pendientes

### Arquitectura y Diseño
- **[Arquitectura de Servicios](docs/SERVICES_ARCHITECTURE.md)**: Servicios reutilizables y patrones de diseño
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
