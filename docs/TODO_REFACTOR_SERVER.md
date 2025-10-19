# TODO: Refactorizar server.py

## 📋 Contexto

`server.py` actualmente tiene **679 líneas** con toda la lógica de inicialización del servidor. El método `start()` tiene más de 200 líneas inicializando servicios, repositorios, efectos, etc.

## 🎯 Objetivo

Separar la inicialización del servidor en componentes más pequeños y manejables, siguiendo el principio de Single Responsibility.

## 🏗️ Arquitectura Propuesta

```
src/
├── server.py                    # Servidor principal (simplificado)
├── server_initializer.py        # Orquestador de inicialización
├── dependency_container.py      # Contenedor de dependencias
└── initializers/
    ├── __init__.py
    ├── redis_initializer.py     # Inicialización de Redis
    ├── repository_initializer.py # Inicialización de repositorios
    ├── service_initializer.py   # Inicialización de servicios
    ├── game_tick_initializer.py # Inicialización del game tick
    └── npc_initializer.py       # Inicialización de NPCs
```

## 📦 Componentes

### 1. DependencyContainer
Contenedor simple para todas las dependencias del servidor.

```python
@dataclass
class DependencyContainer:
    """Contenedor de todas las dependencias del servidor."""
    
    # Infraestructura
    redis_client: RedisClient
    
    # Repositorios
    player_repo: PlayerRepository
    account_repo: AccountRepository
    inventory_repo: InventoryRepository
    equipment_repo: EquipmentRepository
    merchant_repo: MerchantRepository
    bank_repo: BankRepository
    npc_repo: NPCRepository
    spellbook_repo: SpellbookRepository
    ground_items_repo: GroundItemsRepository
    server_repo: ServerRepository
    
    # Servicios
    combat_service: CombatService
    commerce_service: CommerceService
    spell_service: SpellService
    npc_service: NPCService
    npc_ai_service: NPCAIService
    npc_respawn_service: NPCRespawnService
    loot_table_service: LootTableService
    broadcast_service: MultiplayerBroadcastService
    
    # Managers
    map_manager: MapManager
    game_tick: GameTick
    
    # Catálogos
    npc_catalog: NPCCatalog
    spell_catalog: SpellCatalog
```

### 2. RedisInitializer
Inicializa Redis y carga datos iniciales.

```python
class RedisInitializer:
    """Inicializa Redis y datos iniciales."""
    
    async def initialize(self) -> RedisClient:
        """Conecta a Redis y carga datos iniciales."""
        redis_client = RedisClient()
        await redis_client.connect()
        
        # Cargar datos iniciales
        data_initializer = DataInitializer(redis_client)
        await data_initializer.initialize_all()
        
        return redis_client
```

### 3. RepositoryInitializer
Inicializa todos los repositorios.

```python
class RepositoryInitializer:
    """Inicializa todos los repositorios."""
    
    def initialize(self, redis_client: RedisClient) -> dict[str, Any]:
        """Crea todas las instancias de repositorios."""
        return {
            "player_repo": PlayerRepository(redis_client),
            "account_repo": AccountRepository(redis_client),
            "inventory_repo": InventoryRepository(redis_client),
            # ... etc
        }
```

### 4. ServiceInitializer
Inicializa todos los servicios.

```python
class ServiceInitializer:
    """Inicializa todos los servicios."""
    
    def initialize(
        self,
        repositories: dict[str, Any],
        managers: dict[str, Any],
        catalogs: dict[str, Any],
    ) -> dict[str, Any]:
        """Crea todas las instancias de servicios."""
        return {
            "combat_service": CombatService(
                repositories["player_repo"],
                repositories["npc_repo"],
                repositories["equipment_repo"],
                repositories["inventory_repo"],
            ),
            # ... etc
        }
```

### 5. GameTickInitializer
Inicializa el game tick y sus efectos.

```python
class GameTickInitializer:
    """Inicializa el sistema de game tick."""
    
    def initialize(
        self,
        services: dict[str, Any],
        managers: dict[str, Any],
        repositories: dict[str, Any],
    ) -> GameTick:
        """Crea el game tick y agrega todos los efectos."""
        game_tick = GameTick()
        
        # Agregar efectos
        game_tick.add_effect(HungerThirstEffect(...))
        game_tick.add_effect(GoldDecayEffect(...))
        game_tick.add_effect(MeditationEffect(...))
        game_tick.add_effect(NPCMovementEffect(...))
        game_tick.add_effect(NPCAIEffect(...))
        
        return game_tick
```

### 6. NPCInitializer
Inicializa NPCs y spawns.

```python
class NPCInitializer:
    """Inicializa NPCs y spawns."""
    
    async def initialize(
        self,
        npc_service: NPCService,
        map_manager: MapManager,
    ) -> None:
        """Carga y spawnea todos los NPCs."""
        await npc_service.load_and_spawn_npcs()
        logger.info("NPCs spawneados: %d", len(map_manager.get_all_npcs()))
```

### 7. ServerInitializer (Orquestador)
Orquesta toda la inicialización.

```python
class ServerInitializer:
    """Orquesta la inicialización completa del servidor."""
    
    async def initialize(self) -> DependencyContainer:
        """Inicializa todos los componentes del servidor."""
        logger.info("=== Iniciando servidor ===")
        
        # 1. Redis
        redis_initializer = RedisInitializer()
        redis_client = await redis_initializer.initialize()
        
        # 2. Repositorios
        repo_initializer = RepositoryInitializer()
        repositories = repo_initializer.initialize(redis_client)
        
        # 3. Catálogos
        catalogs = self._initialize_catalogs()
        
        # 4. Managers
        managers = self._initialize_managers(repositories)
        
        # 5. Servicios
        service_initializer = ServiceInitializer()
        services = service_initializer.initialize(repositories, managers, catalogs)
        
        # 6. Game Tick
        tick_initializer = GameTickInitializer()
        game_tick = tick_initializer.initialize(services, managers, repositories)
        
        # 7. NPCs
        npc_initializer = NPCInitializer()
        await npc_initializer.initialize(services["npc_service"], managers["map_manager"])
        
        # 8. Crear contenedor
        container = DependencyContainer(
            redis_client=redis_client,
            **repositories,
            **services,
            **managers,
            game_tick=game_tick,
            **catalogs,
        )
        
        logger.info("=== Servidor inicializado ===")
        return container
```

### 8. Server (Simplificado)
El servidor principal queda mucho más simple.

```python
class Server:
    """Servidor TCP para Argentum Online."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 7666) -> None:
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.container: DependencyContainer | None = None
    
    async def start(self) -> None:
        """Inicia el servidor."""
        try:
            # Inicializar todos los componentes
            initializer = ServerInitializer()
            self.container = await initializer.initialize()
            
            # Iniciar game tick
            self.container.game_tick.start()
            
            # Iniciar servidor TCP
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port,
            )
            
            logger.info("Servidor escuchando en %s:%d", self.host, self.port)
            
            async with self.server:
                await self.server.serve_forever()
                
        except redis.ConnectionError as e:
            logger.error("No se pudo conectar a Redis: %s", e)
            sys.exit(1)
    
    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja una conexión de cliente."""
        # Inyectar dependencias del container
        # ... (lógica existente)
```

## ✅ Ventajas

1. **Separación de responsabilidades** - Cada initializer tiene una función clara
2. **Testeable** - Cada initializer se puede testear independientemente
3. **Legible** - `server.py` pasa de 679 a ~150 líneas
4. **Mantenible** - Fácil agregar/modificar inicializaciones
5. **Dependency Injection** - Container centraliza todas las dependencias
6. **Orden claro** - Secuencia de inicialización explícita

## 📝 Checklist

- [ ] Crear `src/dependency_container.py`
- [ ] Crear carpeta `src/initializers/`
- [ ] Crear `redis_initializer.py`
- [ ] Crear `repository_initializer.py`
- [ ] Crear `service_initializer.py`
- [ ] Crear `game_tick_initializer.py`
- [ ] Crear `npc_initializer.py`
- [ ] Crear `server_initializer.py`
- [ ] Refactorizar `server.py` para usar initializers
- [ ] Ejecutar tests (deben pasar)
- [ ] Actualizar README.md

## ⚠️ Consideraciones

- **Orden de inicialización** - Respetar dependencias entre componentes
- **Error handling** - Cada initializer debe manejar sus errores
- **Logging** - Logging claro de cada paso de inicialización
- **Tests** - Crear tests para cada initializer
- **Backward compatibility** - El servidor debe funcionar igual

## 🎓 Patrón: Dependency Injection

Esta refactorización implementa el patrón de **Dependency Injection Container**:
1. Todas las dependencias en un contenedor
2. Initializers crean e inyectan dependencias
3. Componentes reciben dependencias del container
4. Fácil mockear para tests

## 📊 Comparación

**Antes:**
```
server.py (679 líneas)
├── start() (200+ líneas)
│   ├── Inicializar Redis
│   ├── Inicializar 10 repositorios
│   ├── Inicializar 8 servicios
│   ├── Inicializar managers
│   ├── Inicializar game tick
│   ├── Agregar 5 efectos
│   └── Spawnear NPCs
└── handle_client() (100+ líneas)
```

**Después:**
```
server.py (150 líneas)
├── start() (30 líneas)
│   └── ServerInitializer.initialize()
└── handle_client() (100+ líneas)

server_initializer.py (100 líneas)
initializers/ (7 archivos, ~50 líneas cada uno)
dependency_container.py (50 líneas)
```

## 🚀 Ejecución

El servidor se inicia igual que antes:
```python
server = Server(host="0.0.0.0", port=7666)
await server.start()
```

Pero internamente está mucho mejor organizado.
