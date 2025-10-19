# Arquitectura del Servidor PyAO

## 📋 Visión General

PyAO Server es un servidor de juego MMORPG implementado en Python con arquitectura modular, siguiendo principios SOLID y patrones de diseño modernos.

## 🏗️ Arquitectura Principal

```
┌─────────────────────────────────────────────────────────────┐
│                     ArgentumServer                          │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │ DependencyContainer  │  │     TaskFactory          │   │
│  │  (24 dependencies)   │  │  (25 task types)         │   │
│  └──────────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │      ServerInitializer              │
        │      (Orchestrator Pattern)         │
        └─────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────────────┐
        │                 │                         │
        ▼                 ▼                         ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│   Redis      │  │ Repository   │  │    Service       │
│ Initializer  │  │ Initializer  │  │  Initializer     │
└──────────────┘  └──────────────┘  └──────────────────┘
        │                 │                         │
        ▼                 ▼                         ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ RedisClient  │  │ 10 Repos     │  │  8 Services      │
│ DataInit     │  │ PlayerRepo   │  │  CombatService   │
│ Config       │  │ AccountRepo  │  │  NPCService      │
└──────────────┘  │ etc...       │  │  etc...          │
                  └──────────────┘  └──────────────────┘
```

## 📦 Componentes Principales

### 1. DependencyContainer
**Archivo:** `src/dependency_container.py`

Contenedor centralizado de todas las dependencias del servidor usando el patrón Dependency Injection.

**Responsabilidades:**
- Almacenar referencias a todos los servicios y repositorios
- Facilitar inyección de dependencias
- Proporcionar acceso type-safe a componentes

**Dependencias (24 total):**
- 1 Cliente de infraestructura (RedisClient)
- 10 Repositorios (Player, Account, Inventory, etc.)
- 8 Servicios (Combat, Commerce, Spell, NPC, etc.)
- 2 Managers (MapManager, GameTick)
- 3 Catálogos (NPC, Spell, Item)

### 2. TaskFactory
**Archivo:** `src/task_factory.py`

Factory para crear instancias de Tasks con sus dependencias inyectadas.

**Patrón:** Factory Pattern + Strategy Pattern

**Características:**
- Dictionary-based task creation (O(1) lookup)
- 25 tipos de tasks soportados
- Inyección automática de dependencias
- Fallback a TaskNull para packets desconocidos

**Ejemplo de uso:**
```python
factory = TaskFactory(deps)
task = factory.create_task(data, message_sender, session_data)
await task.execute()
```

### 3. ServerInitializer
**Archivo:** `src/server_initializer.py`

Orquestador principal que coordina la inicialización de todos los componentes.

**Patrón:** Facade Pattern + Builder Pattern

**Flujo de inicialización:**
1. Redis + Datos iniciales
2. Repositorios (10)
3. MapManager + Ground Items
4. Servicios (8)
5. GameTick + Efectos
6. DependencyContainer

**Método principal:**
```python
@staticmethod
async def initialize_all() -> tuple[DependencyContainer, str, int]:
    # Retorna: (container, host, port)
```

## 🔧 Initializers Especializados

### RedisInitializer
**Archivo:** `src/redis_initializer.py`

- Conecta a Redis
- Carga datos iniciales (items, NPCs, merchants)
- Configura valores por defecto (dados, MOTD, efectos)
- Resetea contadores de sesión

### RepositoryInitializer
**Archivo:** `src/repository_initializer.py`

Crea los 10 repositorios:
- PlayerRepository
- AccountRepository
- InventoryRepository
- EquipmentRepository
- MerchantRepository
- BankRepository
- NPCRepository
- SpellbookRepository
- GroundItemsRepository
- ServerRepository

### ServiceInitializer
**Archivo:** `src/service_initializer.py`

Crea los 8 servicios + 3 catálogos:
- CombatService
- CommerceService
- SpellService
- NPCService
- NPCAIService
- NPCRespawnService
- LootTableService
- MultiplayerBroadcastService
- NPCCatalog, SpellCatalog, ItemCatalog

### GameTickInitializer
**Archivo:** `src/game_tick_initializer.py`

Configura el sistema de tick del juego con efectos:
- HungerThirstEffect (configurable)
- GoldDecayEffect (configurable)
- MeditationEffect (siempre activo)
- NPCMovementEffect
- NPCAIEffect

## 📨 Sistema de Mensajes

### MessageSender (Refactorizado)
**Archivos:** `src/message_*_sender.py`

Sistema modular de envío de mensajes dividido en 7 componentes:

1. **ConsoleMessageSender** - Mensajes de consola
2. **AudioMessageSender** - Música y sonidos
3. **VisualEffectsMessageSender** - Efectos visuales
4. **PlayerStatsMessageSender** - Stats del jugador
5. **CharacterMessageSender** - Personajes en el mapa
6. **InventoryMessageSender** - Inventario, banco, comercio
7. **MapMessageSender** - Cambios de mapa y objetos

### Módulos msg_*
**Archivos:** `src/msg_*.py`

8 módulos especializados para construir packets:
- msg_session.py
- msg_map.py
- msg_console.py
- msg_audio.py
- msg_visual_effects.py
- msg_character.py
- msg_player_stats.py
- msg_inventory.py

## 🎮 Sistema de Tasks

### Flujo de Procesamiento de Packets

```
Cliente → Packet → ArgentumServer.handle_client()
                          │
                          ▼
                   create_task(data)
                          │
                          ▼
                    TaskFactory
                          │
                          ▼
                  Dictionary Lookup
                          │
                          ▼
                   Task Instance
                          │
                          ▼
                   task.execute()
```

### Tipos de Tasks (25)

**Sesión:**
- TaskLogin, TaskCreateAccount, TaskQuit

**Movimiento:**
- TaskWalk, TaskChangeHeading, TaskRequestPositionUpdate

**Combate:**
- TaskAttack, TaskCastSpell

**Inventario:**
- TaskPickup, TaskDrop, TaskInventoryClick, TaskEquipItem

**Comercio:**
- TaskCommerceBuy, TaskCommerceSell, TaskCommerceEnd

**Banco:**
- TaskBankDeposit, TaskBankExtract, TaskBankEnd

**Interacción:**
- TaskLeftClick, TaskDoubleClick, TaskTalk

**Información:**
- TaskRequestStats, TaskOnline, TaskMotd, TaskInformation, TaskUptime

**Otros:**
- TaskDice, TaskMeditate, TaskRequestAttributes

## 🗄️ Capa de Datos

### Redis como Base de Datos

**Estructuras principales:**
```
player:{user_id}:*          # Datos del jugador
account:{username}:*        # Datos de cuenta
inventory:{user_id}:*       # Inventario
bank:{user_id}:vault        # Bóveda bancaria
merchant:{npc_id}:*         # Inventario de mercaderes
npc:{npc_id}:*             # Datos de NPCs
session:{user_id}:*         # Datos de sesión
server:*                    # Configuración global
```

## 🎯 Patrones de Diseño Implementados

### 1. Factory Pattern
- **TaskFactory** - Creación de tasks
- **NPCFactory** (pendiente) - Creación de NPCs

### 2. Dependency Injection
- **DependencyContainer** - Inyección de dependencias
- Todas las tasks reciben dependencias via constructor

### 3. Facade Pattern
- **ServerInitializer** - Simplifica inicialización compleja
- **MessageSender** - Simplifica envío de mensajes

### 4. Strategy Pattern
- **Dictionary-based task creation** - Selección dinámica de estrategia

### 5. Builder Pattern
- **Initializers** - Construcción paso a paso de componentes

### 6. Repository Pattern
- **Todos los *Repository** - Abstracción de acceso a datos

## 📊 Principios SOLID

### Single Responsibility
- Cada initializer tiene una responsabilidad única
- TaskFactory solo crea tasks
- Cada repository maneja un tipo de dato

### Open/Closed
- Agregar nuevos tasks: solo modificar TaskFactory
- Agregar nuevos servicios: solo modificar ServiceInitializer

### Liskov Substitution
- Todos los tasks implementan interfaz Task
- Todos los repositorios usan RedisClient

### Interface Segregation
- Interfaces específicas para cada componente
- No hay interfaces monolíticas

### Dependency Inversion
- Dependencias inyectadas via constructor
- No hay dependencias hard-coded

## 📈 Métricas de Calidad

### Cobertura de Tests
- **767 tests** pasando (100%)
- Tests unitarios para componentes clave
- Tests de integración para flujos completos

### Complejidad
- **server.py:** 685 → 194 líneas (-72%)
- **create_task():** 215 → 3 líneas (-99%)
- **Complejidad ciclomática:** Reducida dramáticamente

### Mantenibilidad
- Código modular y organizado
- Responsabilidades claras
- Fácil de extender

## 🚀 Flujo de Inicio del Servidor

```python
# 1. Crear servidor
server = ArgentumServer()

# 2. Iniciar (internamente usa ServerInitializer)
await server.start()
    ├── ServerInitializer.initialize_all()
    │   ├── RedisInitializer.initialize()
    │   ├── RepositoryInitializer.initialize_all()
    │   ├── ServiceInitializer.initialize_all()
    │   ├── GameTickInitializer.initialize()
    │   └── DependencyContainer(...)
    ├── TaskFactory(deps)
    └── game_tick.start()

# 3. Escuchar conexiones
await server.serve_forever()
```

## 📝 Convenciones de Código

### Naming
- **Classes:** PascalCase (TaskFactory, PlayerRepository)
- **Functions:** snake_case (initialize_all, create_task)
- **Constants:** UPPER_SNAKE_CASE (CLIENT_PACKET_ID)
- **Private:** _leading_underscore (_initialize_dice_config)

### Type Hints
- Todas las funciones tienen type hints
- Uso de TYPE_CHECKING para imports circulares
- dict[str, Any] para diccionarios genéricos

### Async/Await
- Métodos I/O son async
- Uso consistente de await
- AsyncMock en tests

## 🔮 Próximas Mejoras

### Corto Plazo
- [ ] Implementar PacketReader
- [ ] Implementar NPC Factory
- [ ] Mejorar tests de integración

### Mediano Plazo
- [ ] Sistema de quests
- [ ] Sistema de guilds
- [ ] Optimizaciones de rendimiento

### Largo Plazo
- [ ] Migración a PostgreSQL para datos persistentes
- [ ] Sistema de sharding para escalabilidad
- [ ] Métricas y monitoring

---

**Última actualización:** 2025-01-19  
**Versión:** 1.0.0  
**Estado:** Production Ready ✅
