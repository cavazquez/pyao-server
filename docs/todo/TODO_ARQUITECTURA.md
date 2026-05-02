# TODO: Mejoras de Arquitectura

**Estado:** 📝 Propuestas de diseño - Pendiente implementación  
**Prioridad:** Baja-Media  
**Versión objetivo:** 0.6.0+

---

## 🎯 Objetivo

Este documento describe mejoras arquitecturales propuestas para mejorar la mantenibilidad, escalabilidad y calidad del código del servidor PyAO.

---

## 1. Service Container / Dependency Injection

> **Estado (2026): implementado en otro diseño.** El código actual usa `DependencyContainer`, `TaskFactory` (inyección por introspección del `__init__`), `HandlerRegistry` para handlers nombrados y `src/network/packet_handlers.py` solo como `TASK_HANDLERS: dict[int, type[Task]]` (mapa packet → clase). Lo siguiente describe el problema **antes** de ese diseño; conservarlo como referencia histórica, no como backlog activo.

### Problema Actual

Las tasks se crean manualmente con todas sus dependencias en `packet_handlers.py`:

```python
# packet_handlers.py - Código actual
def create_task_handlers(
    redis_client: RedisClient,
    session_manager: SessionManager,
    map_manager: MapManager,
    # ... más de 15 parámetros
) -> dict[int, type[Task]]:
    return {
        PacketID.ATTACK: lambda data, user_id, connection: TaskAttack(
            data=data,
            user_id=user_id,
            connection=connection,
            redis_client=redis_client,
            session_manager=session_manager,
            map_manager=map_manager,
            player_repository=player_repository,
            # ... más dependencias
        ),
        # ... 30+ handlers
    }
```

**Problemas:**
- ❌ Código muy repetitivo
- ❌ Difícil de mantener (agregar dependencia = modificar 30+ líneas)
- ❌ No es escalable
- ❌ Difícil de testear (mock de todas las dependencias)

---

### Solución Propuesta: Service Container

Crear un contenedor de servicios que gestione las dependencias:

```python
# src/service_container.py
from dataclasses import dataclass
from typing import Any

@dataclass
class ServiceContainer:
    """Contenedor de servicios para dependency injection."""
    
    # Core services
    redis_client: RedisClient
    session_manager: SessionManager
    map_manager: MapManager
    
    # Repositories
    player_repository: PlayerRepository
    bank_repository: BankRepository
    merchant_repository: MerchantRepository
    npc_repository: NPCRepository
    
    # Services
    combat_service: CombatService
    equipment_service: EquipmentService
    npc_service: NPCService
    magic_service: MagicService
    
    def create_task(
        self,
        task_class: type[Task],
        data: bytes,
        user_id: int,
        connection: ClientConnection,
    ) -> Task:
        """Crea una task inyectando todas las dependencias necesarias."""
        # Introspección para determinar qué dependencias necesita la task
        return task_class(
            data=data,
            user_id=user_id,
            connection=connection,
            **self._get_task_dependencies(task_class),
        )
    
    def _get_task_dependencies(self, task_class: type[Task]) -> dict[str, Any]:
        """Obtiene las dependencias necesarias para una task."""
        # Usar inspect para determinar parámetros del __init__
        # y retornar solo las dependencias que necesita
        pass
```

**Uso simplificado:**

```python
# packet_handlers.py - Versión simplificada
def create_task_handlers(container: ServiceContainer) -> dict[int, type[Task]]:
    return {
        PacketID.ATTACK: lambda data, uid, conn: container.create_task(
            TaskAttack, data, uid, conn
        ),
        PacketID.WALK: lambda data, uid, conn: container.create_task(
            TaskWalk, data, uid, conn
        ),
        # ... mucho más simple
    }
```

**Beneficios:**
- ✅ Código mucho más limpio
- ✅ Fácil agregar nuevas dependencias
- ✅ Mejor testabilidad (mock del container)
- ✅ Principio de inversión de dependencias

**Prioridad:** Baja  
**Esfuerzo:** 4-6 horas  
**Complejidad:** Media-Alta

---

## 2. Event System / Message Bus

### Problema Actual

Los eventos del juego están acoplados directamente:

```python
# task_attack.py - Código actual
async def _handle_npc_death(self, npc: NPC) -> None:
    # Lógica de muerte
    await self._drop_loot(npc)
    await self.map_manager.remove_npc(npc.map_id, npc.x, npc.y)
    # Enviar a todos los jugadores cercanos
    await self._broadcast_npc_death(npc)
```

**Problemas:**
- ❌ Acoplamiento fuerte entre componentes
- ❌ Difícil agregar nuevos comportamientos (achievements, quests, etc.)
- ❌ Lógica dispersa en múltiples archivos

---

### Solución Propuesta: Event Bus

Crear un sistema de eventos desacoplado:

```python
# src/event_bus.py
from dataclasses import dataclass
from typing import Callable, Any
from enum import Enum

class GameEvent(Enum):
    """Eventos del juego."""
    NPC_DIED = "npc_died"
    PLAYER_LEVELED_UP = "player_leveled_up"
    ITEM_DROPPED = "item_dropped"
    PLAYER_ATTACKED = "player_attacked"
    SPELL_CAST = "spell_cast"

@dataclass
class Event:
    """Evento del juego."""
    type: GameEvent
    data: dict[str, Any]

class EventBus:
    """Bus de eventos para desacoplar lógica del juego."""
    
    def __init__(self):
        self._handlers: dict[GameEvent, list[Callable]] = {}
    
    def subscribe(self, event_type: GameEvent, handler: Callable) -> None:
        """Suscribe un handler a un evento."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: Event) -> None:
        """Publica un evento a todos los handlers suscritos."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            await handler(event.data)
```

**Uso:**

```python
# task_attack.py - Versión con eventos
async def _handle_npc_death(self, npc: NPC) -> None:
    # Publicar evento
    await self.event_bus.publish(Event(
        type=GameEvent.NPC_DIED,
        data={"npc": npc, "killer_id": self.user_id},
    ))

# loot_handler.py - Handler de loot
class LootHandler:
    async def on_npc_died(self, data: dict) -> None:
        npc = data["npc"]
        await self._drop_loot(npc)

# achievement_handler.py - Handler de logros
class AchievementHandler:
    async def on_npc_died(self, data: dict) -> None:
        killer_id = data["killer_id"]
        npc = data["npc"]
        await self._check_kill_achievements(killer_id, npc)

# Registro de handlers
event_bus.subscribe(GameEvent.NPC_DIED, loot_handler.on_npc_died)
event_bus.subscribe(GameEvent.NPC_DIED, achievement_handler.on_npc_died)
```

**Beneficios:**
- ✅ Desacoplamiento total
- ✅ Fácil agregar nuevos comportamientos
- ✅ Código más modular y testeable
- ✅ Preparado para sistemas futuros (quests, achievements)

**Prioridad:** Baja  
**Esfuerzo:** 6-8 horas  
**Complejidad:** Media-Alta

---

## 3. Command Pattern para Tasks

### Problema Actual

Las tasks tienen lógica mezclada de parsing y ejecución:

```python
class TaskAttack(Task):
    async def execute(self) -> None:
        # Validaciones
        # Parsing
        # Lógica de negocio
        # Envío de mensajes
        # Todo en un solo método
```

---

### Solución Propuesta: Separar Command de Handler

```python
# src/commands.py
@dataclass
class AttackCommand:
    """Comando de ataque."""
    user_id: int
    target_x: int
    target_y: int

# src/command_handlers.py
class AttackCommandHandler:
    """Handler para comando de ataque."""
    
    async def handle(self, command: AttackCommand) -> None:
        # Solo lógica de negocio, sin parsing
        pass

# src/task_attack.py
class TaskAttack(Task):
    async def execute(self) -> None:
        # Solo parsing
        reader = PacketReader(self.data)
        # ... parsear datos
        
        # Crear comando
        command = AttackCommand(
            user_id=self.user_id,
            target_x=x,
            target_y=y,
        )
        
        # Delegar a handler
        await self.attack_handler.handle(command)
```

**Beneficios:**
- ✅ Separación de responsabilidades
- ✅ Handlers reutilizables (CLI, API, etc.)
- ✅ Mejor testabilidad
- ✅ Código más limpio

**Prioridad:** Media  
**Esfuerzo:** 8-10 horas  
**Complejidad:** Alta  
**Estado:** ✅ **IMPLEMENTADO** - Ver `src/commands/` y `src/command_handlers/`

---

## 4. Repository Pattern Mejorado

### Problema Actual

Los repositories mezclan lógica de Redis con lógica de negocio:

```python
# player_repository.py - Código actual
class PlayerRepository:
    async def update_hp(self, user_id: int, hp: int) -> None:
        # Lógica de Redis + validaciones
        pass
```

---

### Solución Propuesta: Separar Data Access de Domain Logic

```python
# src/repositories/player_data_access.py
class PlayerDataAccess:
    """Acceso a datos de jugadores (solo Redis)."""
    
    async def get(self, user_id: int) -> dict | None:
        """Obtiene datos raw de Redis."""
        pass
    
    async def save(self, user_id: int, data: dict) -> None:
        """Guarda datos raw en Redis."""
        pass

# src/domain/player.py
@dataclass
class Player:
    """Entidad de dominio del jugador."""
    user_id: int
    hp: int
    max_hp: int
    
    def take_damage(self, damage: int) -> None:
        """Lógica de negocio: recibir daño."""
        self.hp = max(0, self.hp - damage)
    
    def is_alive(self) -> bool:
        """Lógica de negocio: está vivo."""
        return self.hp > 0

# src/repositories/player_repository.py
class PlayerRepository:
    """Repository que combina data access y domain."""
    
    def __init__(self, data_access: PlayerDataAccess):
        self.data_access = data_access
    
    async def get_player(self, user_id: int) -> Player | None:
        """Obtiene entidad de dominio."""
        data = await self.data_access.get(user_id)
        if not data:
            return None
        return Player(**data)
    
    async def save_player(self, player: Player) -> None:
        """Guarda entidad de dominio."""
        await self.data_access.save(player.user_id, asdict(player))
```

**Beneficios:**
- ✅ Separación clara de responsabilidades
- ✅ Lógica de negocio en entidades de dominio
- ✅ Fácil cambiar backend (Redis → PostgreSQL)
- ✅ Mejor testabilidad

**Prioridad:** Baja  
**Esfuerzo:** 10-12 horas  
**Complejidad:** Alta

---

## 5. Configuration Management

### Problema Actual

Configuración dispersa en múltiples archivos:

```python
# Hardcoded en código
AGGRO_RANGE = 5
MAX_INVENTORY_SLOTS = 20
RESPAWN_TIME = 60
```

---

### Solución Propuesta: Centralizar Configuración

```python
# config/game_config.py
from pydantic import BaseSettings

class GameConfig(BaseSettings):
    """Configuración del juego."""
    
    # Combat
    base_attack_damage: int = 10
    critical_hit_chance: float = 0.1
    
    # NPCs
    npc_aggro_range: int = 5
    npc_respawn_time: int = 60
    
    # Inventory
    max_inventory_slots: int = 20
    max_bank_slots: int = 20
    
    # Experience
    base_exp_per_level: int = 100
    exp_multiplier: float = 1.5
    
    class Config:
        env_prefix = "PYAO_"
        env_file = ".env"

# Uso
config = GameConfig()
aggro_range = config.npc_aggro_range
```

**Beneficios:**
- ✅ Configuración centralizada
- ✅ Fácil modificar sin cambiar código
- ✅ Validación con Pydantic
- ✅ Soporte para variables de entorno

**Prioridad:** Media  
**Esfuerzo:** 2-3 horas  
**Complejidad:** Baja

---

## 📊 Resumen de Prioridades

### Alta Prioridad
*Ninguna actualmente - enfocarse en completar features existentes*

### Media Prioridad
1. **Configuration Management** (2-3h) - ✅ **IMPLEMENTADO**
2. **Command Pattern** (8-10h) - ✅ **IMPLEMENTADO**

### Baja Prioridad
1. **Service Container** (4-6h) - Útil pero no urgente
2. **Event System** (6-8h) - Para features futuras
3. **Repository Pattern Mejorado** (10-12h) - Refactoring grande

---

## 🚀 Roadmap Sugerido

### Versión 0.5.0 (Actual)
- ✅ Completar PacketReader refactoring
- ✅ Sistemas core funcionando (combat, bank, commerce)

### Versión 0.6.0 (Próxima)
- 📝 Configuration Management
- 📝 NPC Factory Pattern
- 📝 Packet Validation

### Versión 0.7.0 (Futuro)
- 📝 Service Container
- ✅ Command Pattern - **COMPLETADO**
- 📝 Event System

### Versión 1.0.0 (Largo plazo)
- 📝 Repository Pattern Mejorado
- 📝 Full test coverage (>90%)
- 📝 Performance optimization

---

## 6. Sistema de Carga de Recursos

### Problema Actual

Apenas se inicia Redis se cargan los recursos desde los archivos TOML y maps, luego solo se consulta la base Redis. Este comportamiento debe ser revisado.

**Ubicación:** `src/server.py`, `src/npc_service.py`, `src/spell_catalog.py`

**Comportamiento Actual:**
- NPCs se cargan desde `npcs.toml` → Redis al iniciar
- Hechizos se cargan desde `spells.toml` al iniciar
- Mapas se cargan desde archivos `.map` al iniciar
- Después solo se consulta Redis

**Problemas:**
- No hay sincronización entre archivos y Redis
- Cambios en archivos requieren reiniciar servidor
- No hay versionado de datos
- Puede haber inconsistencias

**Soluciones Propuestas:**

1. **Opción A - Source of Truth en Archivos:**
   - Archivos TOML/maps son la fuente de verdad
   - Redis solo como cache
   - Recargar desde archivos periódicamente o con comando

2. **Opción B - Source of Truth en Redis:**
   - Migración inicial desde archivos
   - Después todo se edita en Redis
   - Exportar a archivos para backup

3. **Opción C - Híbrido (Recomendado):**
   - Archivos para configuración estática (NPCs, hechizos)
   - Redis para estado dinámico (HP, posición, items)
   - Sincronización clara entre ambos

**Tareas:**
- [ ] Documentar qué datos son estáticos vs dinámicos
- [ ] Implementar sistema de versionado para configs
- [ ] Agregar comando admin para recargar configs
- [ ] Separar repositorios de configuración vs estado

**Prioridad:** Alta  
**Esfuerzo:** 4-6 horas  
**Complejidad:** Media

---

## 7. Inicialización de Objetos con Valores None

### Problema Actual

Los objetos deberían crearse lo más completos posibles y funcionales. Analizar si se puede cambiar el orden y reducir la cantidad de None.

**Ubicación:** `src/server.py` - método `__init__` y `start()`

**Código Actual:**
```python
def __init__(self):
    self.redis_client: RedisClient | None = None
    self.player_repo: PlayerRepository | None = None
    self.account_repo: AccountRepository | None = None
    self.map_manager: MapManager | None = None
    # ... 15+ atributos más como None
```

**Problemas:**
- Objetos en estado inválido hasta que se llama `start()`
- Type checking requiere verificar None constantemente
- Fácil olvidar inicializar algo
- No hay garantía de orden de inicialización
- Difícil de testear

**Soluciones Propuestas:**

1. **Builder Pattern (Recomendado):**
   ```python
   class ServerBuilder:
       async def build(self) -> Server:
           redis = await self._init_redis()
           repos = await self._init_repositories(redis)
           services = await self._init_services(repos)
           return Server(redis, repos, services)
   ```

2. **Factory con Async:**
   ```python
   class ServerFactory:
       @staticmethod
       async def create() -> Server:
           # Inicializar todo en orden correcto
           # Retornar Server completamente funcional
   ```

3. **Lazy Initialization con Properties:**
   ```python
   @property
   def player_repo(self) -> PlayerRepository:
       if self._player_repo is None:
           raise RuntimeError("Server not started")
       return self._player_repo
   ```

4. **Separar Configuración de Runtime:**
   ```python
   class ServerConfig:
       # Solo configuración inmutable
       
   class ServerRuntime:
       # Estado mutable, siempre válido
   ```

**Ejemplo de Implementación:**
```python
class ServerBuilder:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
    
    async def build(self) -> Server:
        # 1. Redis (base de todo)
        redis = RedisClient()
        await redis.connect()
        
        # 2. Repositorios (dependen de Redis)
        repos = await self._build_repositories(redis)
        
        # 3. Managers (estado en memoria)
        managers = await self._build_managers(repos)
        
        # 4. Services (lógica de negocio)
        services = await self._build_services(repos, managers)
        
        # 5. Server (completamente inicializado)
        return Server(
            redis=redis,
            repositories=repos,
            managers=managers,
            services=services,
            host=self.host,
            port=self.port
        )
```

**Tareas:**
- [ ] Crear ServerBuilder class
- [ ] Separar ServerConfig (inmutable) de ServerRuntime (mutable)
- [ ] Eliminar todos los `| None` innecesarios
- [ ] Garantizar orden de inicialización correcto
- [ ] Agregar validación de dependencias
- [ ] Actualizar tests para usar builder

**Prioridad:** Alta  
**Esfuerzo:** 6-8 horas  
**Complejidad:** Media-Alta

---

## 📚 Referencias

- **Clean Architecture:** Robert C. Martin
- **Domain-Driven Design:** Eric Evans
- **Enterprise Integration Patterns:** Gregor Hohpe
- **Dependency Injection in Python:** Python Patterns
- **Builder Pattern:** Gang of Four Design Patterns

---

**Última actualización:** 2025-01-19  
**Autor:** Unificado de propuestas arquitecturales  
**Estado:** 📝 Documento de diseño - Pendiente implementación
