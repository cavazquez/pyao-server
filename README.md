# PyAO Server

<p align="center">
  <img src="assets/icon.png" alt="Icono de PyAO Server" width="160" height="160">
</p>

<p align="center">
  <a href="https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml"><img src="https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI del servidor"></a>
  <a href="https://github.com/cavazquez/pyao-server/actions/workflows/release.yml"><img src="https://github.com/cavazquez/pyao-server/actions/workflows/release.yml/badge.svg" alt="Workflow de Release"></a>
  <a href="https://github.com/cavazquez/pyao-server/releases"><img src="https://img.shields.io/github/v/release/cavazquez/pyao-server?include_prereleases&amp;sort=date&amp;label=release" alt="Última release, incluidas versiones de prueba"></a>
  <a href="https://github.com/cavazquez/pyao-server/releases"><img src="https://img.shields.io/github/downloads/cavazquez/pyao-server/total" alt="Descargas de GitHub Releases"></a>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/docs-referencia-007ec6?logo=readthedocs&amp;logoColor=white" alt="Documentación del servidor"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.14%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.14 o superior"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/cavazquez/pyao-server" alt="Licencia Apache 2.0"></a>
</p>

<p align="center">
  <a href="https://snapcraft.io/pyao"><img src="https://img.shields.io/snapcraft/v/pyao/latest/edge?arch=amd64&amp;label=snap%20edge&amp;logo=snapcraft" alt="Versión de pyao en Snap latest/edge para amd64"></a>
  <a href="https://github.com/cavazquez/pyao-server/issues/363"><img src="https://img.shields.io/badge/homebrew-pendiente-lightgrey?logo=homebrew" alt="Homebrew pendiente: issue 363"></a>
  <a href="https://github.com/cavazquez/pyao-server/issues/364"><img src="https://img.shields.io/badge/apt-pendiente-lightgrey?logo=debian" alt="APT pendiente: issue 364"></a>
  <a href="https://github.com/cavazquez/pyao-server/issues/366"><img src="https://img.shields.io/badge/Microsoft%20Store-pendiente-lightgrey" alt="Microsoft Store pendiente de evaluación: issue 366"></a>
  <a href="https://github.com/cavazquez/pyao-server/issues/365"><img src="https://img.shields.io/badge/winget-pendiente-lightgrey" alt="WinGet pendiente: issue 365"></a>
</p>

<p align="center">
  <a href="https://codecov.io/gh/cavazquez/pyao-server"><img src="https://codecov.io/gh/cavazquez/pyao-server/branch/main/graph/badge.svg" alt="Cobertura de tests"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://deepwiki.com/cavazquez/pyao-server"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="https://github.com/cavazquez/pyao-server">Proyecto</a> ·
  <a href="docs/README.md">Documentación</a> ·
  <a href="https://github.com/cavazquez/pyao-server/releases">Releases</a>
</p>

Los canales marcados como pendientes enlazan sus issues de implementación.

Servidor de Argentum Online implementado en Python 3.14+ con asyncio.

Descarga de pruebas vigente: **[servidor 1.0.0rc3](https://github.com/cavazquez/pyao-server/releases/tag/v1.0.0rc3)** y **[cliente de la misma versión](https://github.com/cavazquez/ArgentumOnlineGodot/releases/tag/v1.0.0rc3)**. GitHub excluye las prereleases de `/releases/latest`, que todavía muestra una versión estable antigua.

Los PR ejecutan validaciones, pruebas y controles de dependencias sin construir
distribuciones. Compilar y publicar son operaciones manuales separadas; ver
[CI y releases](docs/development/CI_RELEASES.md).

> Implementación moderna y eficiente del servidor de Argentum Online.

Índice de toda la documentación interna: **[docs/README.md](docs/README.md)**.

**Próximo objetivo:** [alcance de la 1.0 de servidor y cliente](docs/development/ALCANCE_1_0.md), definido en el [issue #123](https://github.com/cavazquez/pyao-server/issues/123). Allí están los requisitos, el orden de los issues y las pruebas para aprobar una versión conjunta.

## 🛠️ Tecnologías

- ![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white) - Lenguaje de programación
- ![Redis](https://img.shields.io/badge/Redis-8.2+-DC382D?logo=redis&logoColor=white) - Base de datos en memoria para configuración y estado
- ![uv](https://img.shields.io/badge/uv-package_manager-6B4FBB?logo=python&logoColor=white) - Gestor de paquetes y entornos
- ![Ruff](https://img.shields.io/badge/Ruff-linter_&_formatter-D7FF64?logo=ruff&logoColor=black) - Linter y formatter ultra-rápido
- ![mypy](https://img.shields.io/badge/mypy-type_checker-blue?logo=python&logoColor=white) - Type checker estático
- ![pytest](https://img.shields.io/badge/pytest-testing-0A9EDC?logo=pytest&logoColor=white) - Framework de testing
- ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?logo=github-actions&logoColor=white) - Integración continua

Los command handlers se crean por petición: cada instancia y sus subhandlers conservan el emisor y la sesión de esa conexión durante todos sus `await`. `HandlerRegistry` comparte servicios, pero no almacena handlers mutables entre jugadores.

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
uv sync --locked --dev
```

### Configurar Redis (Obligatorio)

```bash
# Opción 1: Docker Compose (recomendado)
# Generar sólo la primera vez; reutilizar el archivo existente en reinicios.
uv run --locked python -m src.operations.redis_secret --output .local/redis-password
export PYAO_REDIS_PASSWORD_FILE="$PWD/.local/redis-password"
docker compose up -d --build redis  # Redis autenticado + persistencia
docker compose --profile tools up -d  # + Redis Insight GUI (puerto 5540)

```

**Interfaz Gráfica:** Redis Insight está incluido en Docker Compose (activar con `--profile tools`). Conectar al host interno `redis`, puerto `6379`, usuario `default` y la credencial del archivo privado. Ambos puertos se publican sólo en loopback.

Ver [docs/guides/REDIS.md](docs/guides/REDIS.md) para documentación completa de Redis.

### Ejecutar el servidor

```bash
uv run pyao-server

# Para habilitar TLS/SSL (usa certificados en certs/server.{crt,key} por defecto)
uv run pyao-server --ssl --ssl-cert certs/server.crt --ssl-key certs/server.key
```

La configuración efectiva de CLI y Redis debe quedar comprobada mediante [#87](https://github.com/cavazquez/pyao-server/issues/87) y [#88](https://github.com/cavazquez/pyao-server/issues/88). El [alcance de la 1.0](docs/development/ALCANCE_1_0.md) incluye las pruebas de arranque, persistencia y restauración.

**Nota:** Redis es obligatorio. El servidor no iniciará sin una conexión activa a Redis.
El cliente verifica certificado y hostname por TLS; sus pruebas rechazan certificados vencidos, de otro nombre o sin confianza y nunca retroceden automáticamente a TCP.

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
./scripts/checks.sh

# Modo rápido (solo tests, sin mypy)
./scripts/checks.sh -q

# Con cobertura de código
./scripts/checks.sh -c

# Ver todas las opciones
./scripts/checks.sh -h

# Solo tests específicos
uv run pytest tests/tasks/clan/ -v

# Tests con cobertura
uv run pytest -v --cov=src --cov-report=term-missing

# Solo linter
uv run ruff check .

# Solo type checker
uv run mypy .
```

### Pre-commit Hooks

El proyecto incluye hooks de pre-commit que ejecutan `ruff` y `mypy` automáticamente antes de cada commit:

```bash
# Instalar hooks (una sola vez)
uv run pre-commit install

# Ejecutar manualmente sobre todos los archivos
uv run pre-commit run --all-files
```

Los tests en CI se ejecutan en paralelo con `pytest-xdist` (`-n auto`).

## 🏗️ Arquitectura

El servidor utiliza una **arquitectura modular** con patrones de diseño modernos:

- **Strategy Pattern** - SpellEffects, HandlerRegistry (efectos y handlers como clases)
- **Factory Pattern + Auto-wiring** - TaskFactory con resolución automática de dependencias por introspección de constructores
- **Registry Pattern** - HandlerRegistry con configuración declarativa
- **Dependency Injection** - DependencyContainer centralizado con auto-wiring en TaskFactory
- **Facade Pattern** - ServerInitializer para inicialización
- **Repository Pattern** - Abstracción de acceso a datos
- **Observabilidad** - Logs de login con mensajes destacados y colores por nivel (TTY) para intento/éxito/spawns ocupados
- **Logs coloreados** - Usa `LOG_COLOR=1` para forzar color aun sin TTY; `NO_COLOR=1` para desactivar
- **Índices especializados** - MapManager delega en PlayerIndex, NpcIndex, GroundItemIndex, TileOccupation, DoorState, ExitIndex

`GroundItemIndex` ordena el envío inicial de objetos del suelo con sus cargas,
commits y notificaciones en la misma exclusión por mapa. El login utiliza la
apariencia del primer stack visible y libera esa exclusión incluso si se cancela.

Ver **[ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)** para documentación completa de la arquitectura.

### Estado y validación

Las versiones observadas y los bloqueos están en [ESTADO_ACTUAL.md](docs/development/ESTADO_ACTUAL.md). Los resultados de lint, tipos, pruebas y cobertura se registran con fecha y revisión; las cifras históricas no acreditan el candidato actual.

`PacketValidator` valida campos de los mensajes. La reconstrucción de mensajes TCP se sigue por separado en [servidor #95](https://github.com/cavazquez/pyao-server/issues/95), [#96](https://github.com/cavazquez/pyao-server/issues/96) y [cliente #4](https://github.com/cavazquez/ArgentumOnlineGodot/issues/4). Las fixtures compartidas de [#94](https://github.com/cavazquez/pyao-server/issues/94) determinan la compatibilidad de ambos proyectos.

## 📦 Estructura del Proyecto

```text
pyao-server/
├── src/
│   ├── runtime_paths.py      # Recursos del wheel y estado editable independientes del cwd
│   ├── core/                 # Inicialización y dependencias
│   ├── network/              # Protocolo y conexiones
│   ├── tasks/                # Parsing y despacho
│   ├── command_handlers/     # Ejecución de comandos
│   ├── services/             # Reglas y commits de juego
│   │   ├── skill_training.py # Entrenamiento natural, topes y XP general en el commit de la acción
│   │   ├── player_progression.py # Crecimiento y puntos por nivel con watermark persistente
│   │   ├── skill_action_service.py # Acciones compartidas por comandos clásicos y RPC negociado
│   │   ├── gathering.py, crafting.py, meditation.py # Recolección, recetas y recuperación
│   │   ├── personal_skills.py, navigation.py # Robo, ocultamiento, fogatas, doma y barcos
│   │   ├── combat/           # PvP, planes físicos, magia e invocaciones con recibos
│   │   ├── map/map_workshops.py # Talleres reales de .inf, terreno y gráficos para el cliente
│   │   └── player/lifecycle.py # Generaciones vitales y liquidación de muertes
│   ├── repositories/         # Persistencia
│   ├── operations/           # Redis, smoke y distribution: validación y ensamblado de releases
│   ├── models/               # Entidades y loaders de ciudades, reglas y recetas a Redis
│   └── messaging/            # Respuestas al cliente
├── tests/                    # Pruebas unitarias e integración
├── data/                     # Dataset propio versionado; skills.toml y crafting/*.toml
│   └── validation/redis_upgrade.toml # Fixture descartable de actualización/recuperación
├── config/                   # Configuración de ejemplo
├── docs/
│   ├── development/
│   │   ├── ALCANCE_1_0.md    # Requisitos, issues y pruebas de servidor/cliente
│   │   └── ESTADO_ACTUAL.md  # Versiones y bloqueos observados
│   ├── todo/                # Acceso al roadmap y backlog
│   ├── guides/              # Configuración y operación; SNAP.md para publicación instalada
│   ├── architecture/        # Diseño
│   ├── systems/             # Sistemas de juego
│   └── archive/             # Histórico
├── tools/                    # Herramientas de datos
├── scripts/
│   ├── checks.sh            # Verificaciones del proyecto
│   ├── build_snap.py        # Build Snap limpio, uv fijado y procedencia
│   └── smoke_installed_snap.py # TLS y reinicio del paquete instalado con Redis descartable
├── snap/                    # Receta core26 amd64/arm64 y wrapper sin catálogos obsoletos
├── .github/workflows/        # CI, releases y server-snap.yml con instalación real
├── pyproject.toml            # Metadatos, dependencias y herramientas
├── uv.lock                   # Lock de dependencias
└── README.md
```

### Arquitectura

El servidor sigue una **arquitectura en capas** con separación de responsabilidades:

`DataInitializer` carga las seis ciudades de `data/world/cities.toml` en Redis
antes de abrir el listener. El alta consulta ese catálogo y aplica el home
elegido sólo si el personaje todavía no tiene posición. Los logins posteriores
conservan su ubicación. Las doce clases del protocolo están declaradas en
`data/classes/definitions.toml`; las ocho que usaban atributos neutros mantienen
ese perfil, sus IDs y el balance existente de `data/classes/balance.toml`.
`NPCCatalog` adapta los campos anidados de los TOML regenerados al contrato de
spawn/invocación, conservando nombre, apariencia, HP y flags del catálogo propio.

#### Capa de Red
- **`ArgentumServer`**: Maneja conexiones TCP y el ciclo de vida del servidor
- **`ClientConnection`**: Gestiona la conexión TCP (send/receive, close, wait_closed)
- **`MessageSender`**: Envía mensajes específicos del juego al cliente

#### Capa de Datos (Repositorios)
- **`PlayerRepository`**: Gestión de datos de jugadores (posición, stats, hambre/sed, atributos)
- **`NPCRepository`**: Gestión de NPCs en Redis (crear, obtener, actualizar, eliminar)
- **`AccountRepository`**: Gestión de cuentas (crear, obtener, verificar password)
- **`RedisClient`**: Cliente Redis de bajo nivel, con pool async limitado y espera con timeout (conexión, configuración, sesiones)
- **`RedisConfig`**: Configuración y constantes de Redis

#### Capa de Servicios
- **`PlayerMapService`**: ✅ **NUEVO** - Centraliza lógica de spawn y transiciones de mapa
  - `spawn_in_map()`: Aparición inicial del jugador (login)
  - `transition_to_map()`: Cambio de mapa (transiciones, teletransporte)
  - `teleport_in_same_map()`: Teletransporte dentro del mismo mapa (comandos GM)
  - Elimina ~450 líneas de código duplicado en 3 archivos
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

**Paquetes documentados con validación de campos:**
- Con parámetros: LOGIN, CREATE_ACCOUNT, WALK, ATTACK, CAST_SPELL, DROP, TALK, DOUBLE_CLICK, LEFT_CLICK, EQUIP_ITEM, USE_ITEM, COMMERCE_BUY/SELL, BANK_DEPOSIT/EXTRACT, CHANGE_HEADING, GM_COMMANDS
- Sin parámetros: THROW_DICES, REQUEST_ATTRIBUTES, PICK_UP, COMMERCE_END, BANK_END, REQUEST_POSITION_UPDATE, MEDITATE, REQUEST_STATS, INFORMATION, REQUEST_MOTD, UPTIME, ONLINE, QUIT, PING, AYUDA

**Ejemplo de uso:**
```python
# En TaskFactory.create_task()
validation_result = validator.validate_packet_by_id(ClientPacketID.WALK)
assert validation_result is not None
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

Las 22 habilidades separan nivel, XP acumulada y porcentaje de entrenamiento.
Las 18 habilidades clásicas entrenables conceden 50 XP por éxito y 20 por fallo
válido, respetan el tope natural por nivel y requieren haber asignado los diez
puntos iniciales y no sufrir hambre/sed. Mejorar una habilidad concede 50 XP
general. Liderazgo, Navegación, Robustez y Agilidad se asignan manualmente.
Los puntos de nivel mejoran habilidades; los cinco atributos proceden de la
creación, raza y clase, además de sus modificadores temporales.

Se conservan las doce clases y su política propia de equipamiento. Robustez
reduce hasta un 10% el daño físico y Agilidad (habilidad) agrega hasta diez puntos
porcentuales de evasión; el atributo Agilidad y los críticos propios conservan
su función. Los requisitos de Liderazgo vienen de `data/skills.toml`: Carisma
por Liderazgo para parties, y Liderazgo mínimo para crear clanes. Las reglas de
navegación consideran barco, clase y Pesca experta del Trabajador.

Recolección, fabricación, comercio y combate confirman costes, resultado y
entrenamiento en la misma transacción Redis. Los reintentos conservan identidad
y recibo. El cliente negocia acciones mediante capacidad 256, pedido 251 y
respuesta 255; los comandos clásicos comparten el servicio y la cadencia.
Las recetas usan IDs reales: 26 armas, 61 armaduras y 34 recetas propias de
carpintería, más fundición de los tres minerales. Materiales apilables admiten
hasta 10.000 por stack para poder pagar los costes del catálogo. El cliente
permite consultar recetas, cantidades, materiales y rechazos del servidor.

Los 11 yunques y 9 fraguas originales se importan de los objetos `.inf`, mediante
`tools/extraction/extract_map_workshops.py`, a `data/world/map_workshops.toml`.
Se añaden después de cargar la caché de mapas para reparar instalaciones
existentes; el login y las transiciones envían su gráfico y bloqueo al cliente.
Las reglas, diferencias propias y validación están en
[MECANICAS_AO.md](docs/development/MECANICAS_AO.md).

La actualización requiere [migrar Redis a esquema v4](docs/guides/REDIS.md#esquema-y-migraciones)
con backup verificado. No publicar un cliente actualizado sin el servidor
correspondiente y la misma versión.

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

Ver **[documentación completa del sistema de tick](docs/systems/GAME_TICK_SYSTEM.md)** para crear efectos personalizados.

## ⚙️ Configuración

El servidor utiliza un sistema de configuración centralizado en `src/config.py` que permite sobrescribir valores mediante variables de entorno.

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto (ver `.env.example` para referencia):

```bash
# Servidor
SERVER_HOST=0.0.0.0
SERVER_PORT=7666
SERVER_MAX_CONNECTIONS=1000

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Gameplay
GAME_MAX_INVENTORY_SLOTS=20
GAME_MAX_BANK_SLOTS=40
GAME_MAX_PARTY_MEMBERS=6
GAME_RESPAWN_TIME_SECONDS=180
GAME_MAX_LEVEL=50

# Hambre y Sed
HUNGER_THIRST_ENABLED=true
HUNGER_THIRST_INTERVAL_SED=180
HUNGER_THIRST_REDUCCION_AGUA=10

# Reducción de Oro
GOLD_DECAY_ENABLED=true
GOLD_DECAY_PERCENTAGE=1.0
GOLD_DECAY_INTERVAL_SECONDS=60.0
```

### Uso en Código

```python
from src.config import config

# Acceder a configuraciones
print(config.server.host)  # "0.0.0.0"
print(config.redis.port)  # 6379
print(config.game.max_level)  # 50
print(config.hunger_thirst.enabled)  # True
```

**Beneficios:**
- ✅ Sin dependencias externas (solo stdlib)
- ✅ Type hints completos para mypy
- ✅ Inmutable (dataclasses frozen)
- ✅ Valores por defecto sensatos
- ✅ Fácil de testear y mockear

## 🎮 Cliente compatible

El cliente objetivo es **[cavazquez/ArgentumOnlineGodot](https://github.com/cavazquez/ArgentumOnlineGodot)**, derivado del [port de brian-christopher](https://github.com/brian-christopher/ArgentumOnlineGodot) de Argentum Online 0.13.3.

La compatibilidad conjunta se comprueba mediante el [alcance de la 1.0](docs/development/ALCANCE_1_0.md), el contrato de [servidor #94](https://github.com/cavazquez/pyao-server/issues/94) y el recorrido de [cliente #60](https://github.com/cavazquez/ArgentumOnlineGodot/issues/60). El motor y los templates exactos se fijan en [cliente #10](https://github.com/cavazquez/ArgentumOnlineGodot/issues/10); no se asume compatibilidad con cualquier versión posterior de Godot.

## 📚 Documentación

Índice completo: **[docs/README.md](docs/README.md)**.

| Enlace | Contenido |
|--------|-----------|
| [Arquitectura](docs/architecture/ARCHITECTURE.md) | Diseño del servidor y patrones |
| [Contribuir](docs/CONTRIBUTING.md) | Guía de desarrollo y PRs |
| [Redis](docs/guides/REDIS.md) | Setup y operación de Redis |
| [Estado actual](docs/development/ESTADO_ACTUAL.md) | Versiones observadas y bloqueos conocidos |
| [TODOs](docs/todo/README.md) | Backlog y planificación |

Documentación histórica (refactors completados, snapshots pre-fusión): [docs/archive/](docs/archive/README.md).

## 📝 Desarrollo

El proyecto sigue estrictas reglas de calidad de código:
- **Ruff**: Todas las reglas habilitadas (modo estricto)
- **mypy**: Type checking estricto
- **pytest**: pruebas con ejecución paralela (`pytest-xdist`); resultados del candidato en la evidencia de release
- **Pre-commit**: Hooks automáticos de ruff y mypy antes de cada commit
- **Docker Compose**: Entorno local estandarizado con Redis y Redis Insight

```bash
# Setup inicial
uv sync --locked --dev                # Instalar dependencias
uv run pre-commit install    # Instalar hooks
docker compose up -d         # Levantar Redis con el secreto preparado en Inicio Rápido

# Flujo de desarrollo
./scripts/checks.sh               # Verificar todo antes de commit
```

Ver [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) para guía completa y [docs/CLAUDE.md](docs/CLAUDE.md) para reglas de desarrollo.

## 📄 Licencia

Apache License 2.0 - ver [LICENSE](LICENSE) para más detalles.

La release conserva los nombres originales del wheel y sdist. `uv run --group build python -m src.operations.distribution validate --platform ubuntu-24.04` instala el wheel sin dependencias en un entorno nuevo, después de instalar el runtime fijado por `uv.lock`; comprueba metadata, entry point y `--help` fuera del checkout. El ensamblador exige esos manifiestos y hashes y guarda los builds por OS en ZIP independientes.

El wheel incluye el dataset TOML, configuración por defecto y archive de mapas bajo `src/runtime_data`. Los mapas se extraen en caché por SHA256 bajo el estado del operador; no se modifica el paquete. En Linux instalado el estado usa `$XDG_STATE_HOME/pyao-server` (por defecto `~/.local/state/pyao-server`); en Windows `%LOCALAPPDATA%/PyAO`; Snap conserva `$SNAP_USER_COMMON`. El checkout usa sus recursos versionados con rutas absolutas.

`pyao-server --config-file /ruta/server.toml --state-dir /ruta/estado` elige archivos editables. `--data-dir` y `--maps-dir` seleccionan datasets externos; sus equivalentes son `PYAO_CONFIG_FILE`, `PYAO_STATE_DIR`, `PYAO_DATA_DIR` y `PYAO_MAPS_DIR`. `pyao-server --check-resources` valida el conjunto efectivo sin Redis; el arranque también rechaza referencias inválidas. La validación de distribución ejecuta esta comprobación desde el wheel instalado, en una carpeta temporal, en cada OS de la matriz de release.

El cierre por SIGTERM/SIGINT deja de aceptar conexiones, despierta lectores ociosos y concede `server.shutdown_drain_seconds` a los handlers activos. Luego cancela los restantes, drena o descarta salida acotada, libera sesiones/mascotas y cierra trades y tareas de muerte antes de Redis. `server.shutdown_timeout_seconds` limita el cierre completo (20 s por defecto, 5 s de drenaje). `stop()` es compartido e idempotente. Un commit de resultado incierto conserva su recibo/journal y su identificador; el cierre no aplica compensaciones que puedan duplicar recursos.

El candidato de la versión 1.0 se identifica como `1.0.0rc1` tanto en servidor como en cliente. Usar la misma versión en ambos; el servidor la informa con `pyao-server --version` y los paquetes Snap la muestran en `snap list`. Los commits exactos y SHA256 se conservan como procedencia, sin reemplazar ese número común.

El [Snap del servidor `pyao`](docs/guides/SNAP.md) incluye Python 3.14, instala las dependencias con uv desde el lock y usa recursos del wheel actual. CI prueba el paquete instalado con TLS y Redis descartable en amd64 y arm64. La publicación en `latest/edge` y la migración explícita de partidas se verifican por separado.
