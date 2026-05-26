# Mejoras Arquitectónicas - Explicación Detallada

Este documento explica en detalle las 7 mejoras arquitectónicas propuestas para el servidor PyAO.

---

## 📋 Resumen Ejecutivo

**Total de mejoras:** 7  
**Prioridad Alta:** 2 mejoras  
**Prioridad Media:** 2 mejoras  
**Prioridad Baja:** 3 mejoras  
**Esfuerzo total estimado:** 40-50 horas

---

## 1. Service Container / Dependency Injection

### 🎯 Problema Actual

Actualmente, el proyecto **ya tiene** un `DependencyContainer` básico, pero las tasks se crean manualmente con todas sus dependencias en `TaskFactory`:

```python
# Código actual en task_factory.py
TaskTalk: lambda: TaskTalk(
    data,
    message_sender,
    self.deps.player_repo,
    self.deps.account_repo,
    self.deps.map_manager,
    session_data,
    self.deps.game_tick,
),
```

**Problemas:**
- ❌ Código repetitivo (30+ handlers con dependencias similares)
- ❌ Difícil mantener (agregar dependencia = modificar 30+ líneas)
- ❌ No escalable (más tasks = más código repetitivo)
- ❌ Difícil testear (mock de todas las dependencias manualmente)

### ✅ Solución Propuesta

Mejorar el `DependencyContainer` existente para que use **introspección automática** y determine qué dependencias necesita cada task:

```python
# Mejora propuesta
class DependencyContainer:
    def create_task_auto(
        self,
        task_class: type[Task],
        data: bytes,
        message_sender: MessageSender,
        session_data: dict,
    ) -> Task:
        """Crea una task inyectando automáticamente las dependencias."""
        import inspect
        
        # Obtener la firma del __init__ de la task
        sig = inspect.signature(task_class.__init__)
        
        # Construir kwargs con las dependencias disponibles
        kwargs = {
            "data": data,
            "message_sender": message_sender,
        }
        
        # Para cada parámetro del __init__, buscar en self.deps
        for param_name, param in sig.parameters.items():
            if param_name in ["data", "message_sender", "session_data"]:
                continue  # Ya los tenemos
            
            # Buscar en el container
            if hasattr(self, param_name):
                kwargs[param_name] = getattr(self, param_name)
            elif hasattr(self.deps, param_name):
                kwargs[param_name] = getattr(self.deps, param_name)
        
        # Agregar session_data si lo necesita
        if "session_data" in sig.parameters:
            kwargs["session_data"] = session_data
        
        return task_class(**kwargs)
```

**Uso simplificado:**

```python
# Antes (manual)
TaskTalk: lambda: TaskTalk(
    data, message_sender,
    self.deps.player_repo,
    self.deps.account_repo,
    self.deps.map_manager,
    session_data,
    self.deps.game_tick,
),

# Después (automático)
TaskTalk: lambda: self.deps.create_task_auto(
    TaskTalk, data, message_sender, session_data
),
```

**Beneficios:**
- ✅ Código 70% más corto
- ✅ Agregar dependencia = automático (no tocar 30+ handlers)
- ✅ Mejor testabilidad (mock del container una vez)
- ✅ Principio de inversión de dependencias (SOLID)

**Prioridad:** 🟢 Baja  
**Esfuerzo:** 4-6 horas  
**Complejidad:** Media  
**Cuándo:** Antes de v0.9.0 (clanes) para facilitar desarrollo

---

## 2. Event System / Message Bus

### 🎯 Problema Actual

Los eventos del juego están **acoplados directamente** entre componentes:

```python
# task_attack.py - Código actual
async def _handle_npc_death(self, npc: NPC) -> None:
    # Lógica de muerte
    await self._drop_loot(npc)
    await self.map_manager.remove_npc(npc.map_id, npc.x, npc.y)
    await self._broadcast_npc_death(npc)
    await self._give_experience(npc)
    # Si queremos agregar achievements, hay que modificar este código
    # Si queremos agregar quests, hay que modificar este código
    # Si queremos agregar estadísticas, hay que modificar este código
```

**Problemas:**
- ❌ **Acoplamiento fuerte**: Un cambio afecta múltiples lugares
- ❌ **Difícil extender**: Agregar funcionalidad = modificar código existente
- ❌ **Lógica dispersa**: Comportamientos relacionados en archivos diferentes
- ❌ **No escalable**: Más features = más acoplamiento

### ✅ Solución Propuesta: Event Bus

Crear un sistema de eventos **desacoplado** donde los componentes se comunican a través de eventos:

```python
# src/events/event_bus.py
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
    PARTY_CREATED = "party_created"
    PLAYER_JOINED_MAP = "player_joined_map"

@dataclass
class Event:
    """Evento del juego."""
    type: GameEvent
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

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
            try:
                await handler(event.data)
            except Exception as e:
                logger.error(f"Error en handler de {event.type}: {e}")
```

**Uso:**

```python
# task_attack.py - Versión con eventos (desacoplado)
async def _handle_npc_death(self, npc: NPC) -> None:
    # Solo publicar evento, no hacer nada más
    await self.event_bus.publish(Event(
        type=GameEvent.NPC_DIED,
        data={
            "npc": npc,
            "killer_id": self.user_id,
            "map_id": npc.map_id,
            "position": (npc.x, npc.y),
        },
    ))

# loot_handler.py - Handler de loot (separado)
class LootHandler:
    def __init__(self, loot_service, map_manager):
        self.loot_service = loot_service
        self.map_manager = map_manager
    
    async def on_npc_died(self, data: dict) -> None:
        """Maneja la muerte de NPCs para dropear loot."""
        npc = data["npc"]
        await self.loot_service.drop_loot(npc)

# achievement_handler.py - Handler de logros (separado)
class AchievementHandler:
    async def on_npc_died(self, data: dict) -> None:
        """Maneja la muerte de NPCs para achievements."""
        killer_id = data["killer_id"]
        npc = data["npc"]
        await self._check_kill_achievements(killer_id, npc)

# quest_handler.py - Handler de quests (separado)
class QuestHandler:
    async def on_npc_died(self, data: dict) -> None:
        """Maneja la muerte de NPCs para quests."""
        killer_id = data["killer_id"]
        npc = data["npc"]
        await self._update_quest_progress(killer_id, npc)

# Registro de handlers (en server initialization)
event_bus.subscribe(GameEvent.NPC_DIED, loot_handler.on_npc_died)
event_bus.subscribe(GameEvent.NPC_DIED, achievement_handler.on_npc_died)
event_bus.subscribe(GameEvent.NPC_DIED, quest_handler.on_npc_died)
# Agregar nuevos comportamientos = solo suscribir nuevos handlers
```

**Beneficios:**
- ✅ **Desacoplamiento total**: Componentes no se conocen entre sí
- ✅ **Fácil extender**: Agregar feature = crear handler + suscribir
- ✅ **Código modular**: Cada handler es independiente
- ✅ **Preparado para futuro**: Quests, achievements, estadísticas sin tocar código existente
- ✅ **Mejor testabilidad**: Testear handlers individualmente

**Prioridad:** 🟢 Baja  
**Esfuerzo:** 6-8 horas  
**Complejidad:** Media-Alta  
**Cuándo:** Antes de v0.13.0 (quests) o v0.17.0 (achievements)

---

## 3. Command Pattern para Tasks

### 🎯 Problema Actual

Las tasks tienen **lógica mezclada** de parsing, validación, negocio y comunicación:

```python
# task_attack.py - Código actual
class TaskAttack(Task):
    async def execute(self) -> None:
        # 1. Validar packet
        if len(self.data) < 3:
            return
        
        # 2. Parsear datos
        reader = PacketReader(self.data)
        x = reader.read_byte()
        y = reader.read_byte()
        
        # 3. Validar posición
        position = await self.player_repo.get_position(self.user_id)
        if not position:
            return
        
        # 4. Lógica de negocio (atacar NPC)
        npc = await self._find_npc_at(x, y)
        if not npc:
            return
        
        damage = await self._calculate_damage()
        await npc.take_damage(damage)
        
        # 5. Enviar mensajes
        await self.message_sender.send_attack_result(...)
        
        # TODO mezclado: parsing + negocio + comunicación
```

**Problemas:**
- ❌ **Responsabilidades mezcladas**: Parsing, validación, negocio, comunicación
- ❌ **Difícil reutilizar**: No puedes usar la lógica de ataque desde otro lugar
- ❌ **Difícil testear**: Tienes que mockear todo (packet, repos, services, messaging)
- ❌ **No hay undo/redo**: No puedes deshacer acciones

### ✅ Solución Propuesta: Command Pattern

Separar el **comando** (datos) del **handler** (lógica):

```python
# src/commands/attack_command.py
@dataclass
class AttackCommand:
    """Comando de ataque (solo datos)."""
    user_id: int
    target_x: int
    target_y: int
    timestamp: float = field(default_factory=time.time)

# src/command_handlers/attack_handler.py
class AttackCommandHandler:
    """Handler para comando de ataque (solo lógica de negocio)."""
    
    def __init__(
        self,
        player_repo: PlayerRepository,
        combat_service: CombatService,
        npc_service: NPCService,
        message_sender: MessageSender,
    ):
        self.player_repo = player_repo
        self.combat_service = combat_service
        self.npc_service = npc_service
        self.message_sender = message_sender
    
    async def handle(self, command: AttackCommand) -> AttackResult:
        """Ejecuta el comando de ataque (solo lógica de negocio)."""
        # Validar posición del jugador
        position = await self.player_repo.get_position(command.user_id)
        if not position:
            return AttackResult.error("Jugador no encontrado")
        
        # Buscar NPC en la posición
        npc = await self.npc_service.get_npc_at(
            position["map"], command.target_x, command.target_y
        )
        if not npc:
            return AttackResult.error("No hay NPC en esa posición")
        
        # Calcular daño
        damage = await self.combat_service.calculate_damage(
            command.user_id, npc
        )
        
        # Aplicar daño
        await npc.take_damage(damage)
        
        # Enviar resultado
        await self.message_sender.send_attack_result(damage, npc.hp)
        
        return AttackResult.success(damage, npc.hp)

# src/tasks/task_attack.py - Versión simplificada
class TaskAttack(Task):
    def __init__(self, ..., attack_handler: AttackCommandHandler):
        super().__init__(data, message_sender)
        self.attack_handler = attack_handler
    
    async def execute(self) -> None:
        # Solo parsing (responsabilidad única)
        reader = PacketReader(self.data)
        if len(self.data) < 3:
            return
        
        x = reader.read_byte()
        y = reader.read_byte()
        
        # Crear comando
        command = AttackCommand(
            user_id=self.user_id,
            target_x=x,
            target_y=y,
        )
        
        # Delegar a handler (separación de responsabilidades)
        result = await self.attack_handler.handle(command)
        
        if not result.success:
            await self.message_sender.send_error(result.error_message)
```

**Beneficios adicionales:**

```python
# Ahora puedes usar el handler desde otros lugares
# CLI admin
command = AttackCommand(user_id=1, target_x=50, target_y=50)
result = await attack_handler.handle(command)

# API REST (futuro)
@app.post("/api/attack")
async def attack_endpoint(data: AttackRequest):
    command = AttackCommand(**data.dict())
    result = await attack_handler.handle(command)
    return result

# Undo/Redo (futuro)
class UndoableAttackCommand(AttackCommand):
    async def undo(self) -> None:
        # Restaurar HP del NPC, etc.
        pass

# Cola de comandos (futuro)
command_queue.add(AttackCommand(...))
await command_queue.process()
```

**Beneficios:**
- ✅ **Separación de responsabilidades**: Parsing vs Negocio
- ✅ **Reutilizable**: Handler se puede usar desde CLI, API, tests
- ✅ **Mejor testabilidad**: Testear handler sin mockear packets
- ✅ **Preparado para undo/redo**: Comandos son objetos serializables
- ✅ **Cola de comandos**: Puedes encolar comandos para procesar después

**Prioridad:** 🟡 Media  
**Esfuerzo:** 8-10 horas  
**Complejidad:** Alta  
**Estado:** 🟡 **EN PROGRESO** - Ver `src/commands/` y `src/command_handlers/`

### 📊 Estado Actual (2025-01-XX)

**✅ Implementado:**
- Estructura base: `Command`, `CommandResult`, `CommandHandler`
- `AttackCommand` y `AttackCommandHandler` (TaskAttack refactorizado)
- Tests actualizados y pasando (23/23)

**⏳ Pendiente (7 tasks complejas):**
1. **TaskWalk** - Movimiento complejo (stamina, validaciones, broadcast, transiciones de mapa)
2. **TaskCastSpell** - Lógica de hechizos con validaciones múltiples
3. **TaskUseItem** - Múltiples casos especiales (herramientas, barca, manzanas)
4. **TaskPickup** - Recoger items con validaciones y party loot
5. **TaskDrop** - Soltar items con validaciones
6. **TaskCommerceBuy/Sell** - Lógica de comercio
7. **TaskBankDeposit/Extract** - Lógica bancaria

**📝 Notas:**
- Las tasks simples (TaskPing, TaskQuit, etc.) no requieren Command Pattern
- Priorizar por complejidad y frecuencia de uso
- Cada refactorización debe incluir tests actualizados

---

## 4. Repository Pattern Mejorado

### 🎯 Problema Actual

Los repositories mezclan **lógica de Redis** con **lógica de negocio**:

```python
# player_repository.py - Código actual
class PlayerRepository:
    async def update_hp(self, user_id: int, hp: int) -> None:
        # Lógica de Redis
        key = f"player:{user_id}:stats"
        await self.redis.hset(key, "hp", hp)
        
        # Lógica de negocio mezclada
        if hp <= 0:
            await self._handle_death(user_id)  # ¿Debería estar aquí?
        
        # Validación mezclada
        max_hp = await self.redis.hget(key, "max_hp")
        if hp > int(max_hp):
            hp = int(max_hp)  # ¿Debería estar aquí?
```

**Problemas:**
- ❌ **Responsabilidades mezcladas**: Data access + Domain logic
- ❌ **Difícil cambiar backend**: Si quieres PostgreSQL, hay que reescribir todo
- ❌ **Lógica de negocio en repositorio**: Debería estar en entidades de dominio
- ❌ **No hay validación centralizada**: Cada método valida diferente

### ✅ Solución Propuesta: Separar Data Access de Domain Logic

```python
# src/data_access/player_data_access.py
class PlayerDataAccess:
    """Acceso a datos de jugadores (solo Redis, sin lógica)."""
    
    async def get_raw(self, user_id: int) -> dict | None:
        """Obtiene datos raw de Redis (sin procesar)."""
        key = f"player:{user_id}:stats"
        return await self.redis.hgetall(key)
    
    async def save_raw(self, user_id: int, data: dict) -> None:
        """Guarda datos raw en Redis (sin validar)."""
        key = f"player:{user_id}:stats"
        await self.redis.hset(key, mapping=data)

# src/domain/player.py
@dataclass
class Player:
    """Entidad de dominio del jugador (lógica de negocio)."""
    user_id: int
    hp: int
    max_hp: int
    mana: int
    max_mana: int
    
    def take_damage(self, damage: int) -> None:
        """Lógica de negocio: recibir daño."""
        self.hp = max(0, self.hp - damage)
    
    def heal(self, amount: int) -> None:
        """Lógica de negocio: curarse."""
        self.hp = min(self.max_hp, self.hp + amount)
    
    def is_alive(self) -> bool:
        """Lógica de negocio: está vivo."""
        return self.hp > 0
    
    def is_dead(self) -> bool:
        """Lógica de negocio: está muerto."""
        return self.hp <= 0
    
    def to_dict(self) -> dict:
        """Serializa a dict para guardar en Redis."""
        return {
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mana": self.mana,
            "max_mana": self.max_mana,
        }
    
    @classmethod
    def from_dict(cls, user_id: int, data: dict) -> "Player":
        """Crea entidad desde dict de Redis."""
        return cls(
            user_id=user_id,
            hp=int(data.get("hp", 0)),
            max_hp=int(data.get("max_hp", 100)),
            mana=int(data.get("mana", 0)),
            max_mana=int(data.get("max_mana", 50)),
        )

# src/repositories/player_repository.py - Versión mejorada
class PlayerRepository:
    """Repository que combina data access y domain."""
    
    def __init__(self, data_access: PlayerDataAccess):
        self.data_access = data_access
    
    async def get_player(self, user_id: int) -> Player | None:
        """Obtiene entidad de dominio (con lógica de negocio)."""
        data = await self.data_access.get_raw(user_id)
        if not data:
            return None
        return Player.from_dict(user_id, data)
    
    async def save_player(self, player: Player) -> None:
        """Guarda entidad de dominio (con validación)."""
        await self.data_access.save_raw(player.user_id, player.to_dict())
    
    async def update_hp(self, user_id: int, new_hp: int) -> None:
        """Actualiza HP usando entidad de dominio."""
        player = await self.get_player(user_id)
        if not player:
            raise ValueError(f"Player {user_id} not found")
        
        # Usar lógica de dominio
        player.hp = new_hp
        if player.hp > player.max_hp:
            player.hp = player.max_hp  # Validación en dominio
        
        await self.save_player(player)
```

**Beneficios:**
- ✅ **Separación clara**: Data access vs Domain logic
- ✅ **Lógica de negocio en entidades**: Más fácil de entender y testear
- ✅ **Fácil cambiar backend**: Solo cambiar `PlayerDataAccess`, el resto igual
- ✅ **Mejor testabilidad**: Testear entidades sin Redis
- ✅ **Validación centralizada**: En las entidades de dominio

**Ejemplo de cambio de backend:**

```python
# Cambiar de Redis a PostgreSQL = solo cambiar data_access
class PlayerDataAccessPostgreSQL:
    async def get_raw(self, user_id: int) -> dict | None:
        async with self.db.execute(
            "SELECT * FROM players WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

# El resto del código NO cambia
# PlayerRepository sigue igual
# Player entity sigue igual
# Services siguen igual
```

**Prioridad:** 🟢 Baja  
**Esfuerzo:** 10-12 horas  
**Complejidad:** Alta  
**Cuándo:** Cuando tengas tiempo o quieras migrar a PostgreSQL

---

## 5. Configuration Management

### 🎯 Problema Actual

Configuración **dispersa** en múltiples archivos y hardcodeada:

```python
# Hardcoded en código
AGGRO_RANGE = 5
MAX_INVENTORY_SLOTS = 20
RESPAWN_TIME = 60

# En archivos TOML
# data/npcs.toml
[npc_1]
aggro_range = 5

# En Redis
await redis.set("config:npc:aggro_range", "5")
```

**Problemas:**
- ❌ **Configuración dispersa**: No sabes dónde está cada valor
- ❌ **Hardcoded**: Cambiar requiere modificar código
- ❌ **Sin validación**: Valores inválidos causan errores en runtime
- ❌ **Sin documentación**: No sabes qué valores son válidos

### ✅ Solución Propuesta: Centralizar con Pydantic

```python
# src/config/game_config.py
from pydantic import BaseSettings, Field, validator

class GameConfig(BaseSettings):
    """Configuración centralizada del juego."""
    
    # Combat
    base_attack_damage: int = Field(default=10, ge=1, le=100)
    critical_hit_chance: float = Field(default=0.1, ge=0.0, le=1.0)
    max_damage: int = Field(default=999, ge=1)
    
    # NPCs
    npc_aggro_range: int = Field(default=5, ge=1, le=20)
    npc_respawn_time: int = Field(default=60, ge=1, le=3600)
    max_npcs_per_map: int = Field(default=50, ge=1, le=200)
    
    # Inventory
    max_inventory_slots: int = Field(default=20, ge=1, le=100)
    max_bank_slots: int = Field(default=20, ge=1, le=100)
    
    # Experience
    base_exp_per_level: int = Field(default=100, ge=1)
    exp_multiplier: float = Field(default=1.5, ge=1.0, le=10.0)
    
    # Party
    max_party_members: int = Field(default=5, ge=2, le=10)
    party_exp_share_range: int = Field(default=18, ge=1, le=50)
    
    @validator("critical_hit_chance")
    def validate_crit_chance(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Critical hit chance must be between 0 and 1")
        return v
    
    class Config:
        env_prefix = "PYAO_"
        env_file = ".env"
        env_file_encoding = "utf-8"

# Uso
config = GameConfig()
aggro_range = config.npc_aggro_range  # Validado automáticamente
```

**Beneficios:**
- ✅ **Configuración centralizada**: Todo en un solo lugar
- ✅ **Validación automática**: Pydantic valida tipos y rangos
- ✅ **Variables de entorno**: Soporte para `.env` y variables de sistema
- ✅ **Documentación**: Los tipos y defaults documentan los valores válidos
- ✅ **Type-safe**: mypy puede verificar tipos

**Nota:** El proyecto **ya tiene** `ConfigManager` básico, pero se puede mejorar con Pydantic.

**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 horas  
**Complejidad:** Baja  
**Cuándo:** Próximamente, es fácil y útil

---

## 6. Sistema de Carga de Recursos

### 🎯 Problema Actual

Al iniciar, se cargan recursos desde TOML → Redis, luego solo se consulta Redis:

```python
# Al iniciar servidor
npcs = load_from_toml("data/npcs.toml")
await redis.set("npc:1", json.dumps(npcs[0]))
# Después solo se consulta Redis
```

**Problemas:**
- ❌ **No hay sincronización**: Cambios en TOML no se reflejan en Redis
- ❌ **Requiere reinicio**: Cambiar TOML = reiniciar servidor
- ❌ **No hay versionado**: No sabes qué versión de datos está en Redis
- ❌ **Inconsistencias posibles**: Redis puede tener datos viejos

### ✅ Solución Propuesta: Híbrido

**Opción A - Source of Truth en Archivos (Recomendado):**
- Archivos TOML son la fuente de verdad
- Redis solo como cache
- Recargar desde archivos periódicamente o con comando

**Opción B - Source of Truth en Redis:**
- Migración inicial desde archivos
- Después todo se edita en Redis
- Exportar a archivos para backup

**Opción C - Híbrido:**
- Archivos para configuración estática (NPCs, hechizos)
- Redis para estado dinámico (HP, posición, items)
- Sincronización clara entre ambos

**Implementación sugerida:**

```python
# src/resources/resource_loader.py
class ResourceLoader:
    """Carga recursos desde archivos TOML."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._cache: dict[str, Any] = {}
        self._versions: dict[str, int] = {}
    
    def load_npcs(self) -> list[dict]:
        """Carga NPCs desde TOML."""
        path = self.data_dir / "npcs.toml"
        mtime = path.stat().st_mtime
        
        # Verificar si cambió
        if path.as_posix() in self._versions:
            if self._versions[path.as_posix()] == mtime:
                return self._cache["npcs"]  # Cache hit
        
        # Cargar desde archivo
        with path.open("rb") as f:
            data = tomllib.load(f)
        
        # Actualizar cache
        self._cache["npcs"] = data["npc"]
        self._versions[path.as_posix()] = mtime
        
        return data["npc"]
    
    async def sync_to_redis(self, redis: RedisClient) -> None:
        """Sincroniza recursos a Redis."""
        npcs = self.load_npcs()
        for npc in npcs:
            await redis.set(f"npc:{npc['id']}", json.dumps(npc))
```

**Prioridad:** 🔴 Alta  
**Esfuerzo:** 4-6 horas  
**Complejidad:** Media  
**Cuándo:** Próximamente, afecta mantenibilidad

---

## 7. Inicialización de Objetos con Valores None

### 🎯 Problema Actual

El servidor se inicializa con muchos valores `None`:

```python
# server.py - Código actual
def __init__(self):
    self.redis_client: RedisClient | None = None
    self.player_repo: PlayerRepository | None = None
    self.account_repo: AccountRepository | None = None
    self.map_manager: MapManager | None = None
    # ... 15+ atributos más como None
```

**Problemas:**
- ❌ **Estado inválido**: Objetos no funcionales hasta `start()`
- ❌ **Type checking difícil**: Siempre verificar `None`
- ❌ **Fácil olvidar inicializar**: No hay garantía de orden
- ❌ **Difícil testear**: Estado inconsistente

### ✅ Solución Propuesta: Builder Pattern

```python
# src/core/server_builder.py
class ServerBuilder:
    """Builder para crear servidor completamente inicializado."""
    
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
        
        # 5. Server (completamente inicializado, sin None)
        return Server(
            redis=redis,
            repositories=repos,
            managers=managers,
            services=services,
        )

# server.py - Versión mejorada
class Server:
    def __init__(
        self,
        redis: RedisClient,  # No None!
        repositories: dict,
        managers: dict,
        services: dict,
    ):
        self.redis = redis
        self.player_repo = repositories["player_repo"]
        # ... siempre válidos, nunca None
```

**Beneficios:**
- ✅ **Estado siempre válido**: No hay `None` después de construcción
- ✅ **Type checking fácil**: No necesitas verificar `None`
- ✅ **Orden garantizado**: Builder asegura orden correcto
- ✅ **Mejor testabilidad**: Estado consistente siempre

**Prioridad:** 🔴 Alta  
**Esfuerzo:** 6-8 horas  
**Complejidad:** Media-Alta  
**Cuándo:** Próximamente, mejora calidad del código significativamente

---

## 📊 Resumen de Prioridades

### 🔴 Alta Prioridad (Hacer primero)
1. **Sistema de Carga de Recursos** (4-6h) - Afecta mantenibilidad
2. **Inicialización sin None** (6-8h) - Mejora calidad del código

### 🟡 Media Prioridad
1. **Configuration Management** (2-3h) - ✅ **IMPLEMENTADO**
2. **Command Pattern** (8-10h) - 🟡 **EN PROGRESO** (TaskAttack ✅, faltan 7 tasks complejas)

### 🟢 Baja Prioridad (Opcional)
1. **Service Container** (4-6h) - Útil pero no urgente
2. **Event System** (6-8h) - Para features futuras
3. **Repository Pattern Mejorado** (10-12h) - Refactoring grande

---

## 🚀 Roadmap Sugerido

### Fase 1: Mejoras Rápidas (1-2 semanas)
1. Configuration Management (2-3h)
2. Sistema de Carga de Recursos (4-6h)

### Fase 2: Mejoras de Calidad (2-3 semanas)
3. Inicialización sin None (6-8h)
4. Service Container (4-6h)

### Fase 3: Mejoras Arquitectónicas (3-4 semanas)
5. Command Pattern (8-10h) - 🟡 **EN PROGRESO**
   - ✅ TaskAttack implementado
   - ⏳ Pendientes: TaskWalk, TaskCastSpell, TaskUseItem, TaskPickup, TaskDrop, TaskCommerceBuy/Sell, TaskBankDeposit/Extract
6. Event System (6-8h)

### Fase 4: Refactoring Grande (Opcional)
7. Repository Pattern Mejorado (10-12h)

---

**Última actualización:** 2025-01-XX  
**Referencia:** `todo/TODO_ARQUITECTURA.md`

