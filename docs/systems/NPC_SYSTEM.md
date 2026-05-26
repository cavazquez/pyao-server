> **Última consolidación:** 2026-05

# Sistema de NPCs en Argentum Online

## 📋 Visión General

Los NPCs (Non-Player Characters) en Argentum Online son entidades controladas por el servidor que aparecen en el mapa junto con los jugadores. Comparten el mismo sistema de renderizado que los jugadores pero tienen comportamientos controlados por IA del servidor.

## 🎭 Tipos de NPCs

### 1. NPCs Estáticos
- **Comerciantes** - Venden y compran items
- **Banqueros** - Gestionan el banco del jugador
- **Entrenadores** - Suben skills
- **Quest Givers** - Dan misiones

### 2. NPCs Móviles
- **Monstruos** - Enemigos hostiles
- **Guardias** - Protegen ciudades
- **Animales** - Fauna del juego
- **Mascotas** - NPCs que siguen al jugador

## 📦 Protocolo de NPCs

### CHARACTER_CREATE (Packet ID: 29)

Los NPCs usan el **mismo paquete** que los jugadores para aparecer en el mapa.

**Estructura del paquete**:
```
Byte 0: PacketID (29 = CHARACTER_CREATE)
Byte 1-2: CharIndex (ID único del personaje/NPC en el mapa)
Byte 3-4: Body (ID del cuerpo/sprite)
Byte 5-6: Head (ID de la cabeza)
Byte 7: Heading (dirección: 1=Norte, 2=Este, 3=Sur, 4=Oeste)
Byte 8-9: X (posición X en el mapa)
Byte 10-11: Y (posición Y en el mapa)
Byte 12-13: FX (efecto visual al aparecer, opcional)
Byte 14-15: Loops (repeticiones del efecto, -1 = una vez)
String: Name (nombre del personaje/NPC)
```

### Diferencias entre Jugador y NPC

| Aspecto | Jugador | NPC |
|---------|---------|-----|
| **CharIndex** | 1-10000 (típico) | 10001+ (típico) |
| **Nombre** | Nombre del jugador | Nombre del NPC |
| **Body** | Cuerpo de jugador | Cuerpo de NPC/monstruo |
| **Movimiento** | Controlado por cliente | Controlado por servidor |
| **IA** | Ninguna | IA del servidor |

## 🔄 Ciclo de Vida de un NPC

### 1. Spawn (Aparición)

```python
# Cuando un jugador entra al mapa, el servidor envía:
# 1. CHARACTER_CREATE de todos los NPCs en el mapa
# 2. CHARACTER_CREATE de todos los jugadores en el mapa

for npc in map_npcs:
    await message_sender.send_character_create(
        char_index=npc.char_index,  # 10001+
        body=npc.body_id,            # ID del sprite del NPC
        head=npc.head_id,            # Cabeza del NPC (0 si no tiene)
        heading=npc.heading,
        x=npc.x,
        y=npc.y,
        name=npc.name,               # "Goblin", "Comerciante", etc.
    )
```

### 2. Movimiento

```python
# Cuando un NPC se mueve, el servidor envía:
# CHARACTER_MOVE (Packet ID: 32)

await message_sender.send_character_move(
    char_index=npc.char_index,
    x=new_x,
    y=new_y,
    heading=new_heading,
)
```

### 3. Cambio de Dirección

```python
# Cuando un NPC cambia de dirección sin moverse:
# CHARACTER_CHANGE (Packet ID: 31)

await message_sender.send_character_change(
    char_index=npc.char_index,
    body=npc.body_id,
    head=npc.head_id,
    heading=new_heading,
    weapon=npc.weapon_id,
    shield=npc.shield_id,
    helmet=npc.helmet_id,
)
```

### 4. Desaparición

```python
# Cuando un NPC muere o desaparece:
# CHARACTER_REMOVE (Packet ID: 32)

await message_sender.send_character_remove(
    char_index=npc.char_index,
)
```

## 🎨 Renderizado en el Cliente

El cliente **no distingue** entre jugadores y NPCs en el renderizado:

```vb
' VB6 - Cliente
' charlist() contiene TANTO jugadores como NPCs

For i = 1 To LastChar
    If charlist(i).Active Then
        ' Renderizar personaje (jugador o NPC)
        Call DrawChar(i, charlist(i).Pos.x, charlist(i).Pos.y)
    End If
Next i
```

## 🤖 IA del Servidor ✅ IMPLEMENTADO

### Sistema de Movimiento de NPCs

El servidor implementa un sistema de IA básica para NPCs hostiles que incluye:

1. **Detección de Jugadores**
   - Rango de detección: 10 tiles (distancia Manhattan)
   - Solo NPCs hostiles detectan jugadores (Goblin ID=1, Lobo ID=7)

2. **Persecución**
   - NPCs hostiles persiguen al jugador más cercano
   - Se mueven un tile por turno hacia el objetivo
   - Priorizan movimiento horizontal sobre vertical

3. **Movimiento Aleatorio**
   - Cuando no hay jugadores cerca, se mueven aleatoriamente
   - Limitado a un radio de 5 tiles desde su posición de spawn

4. **NPCs Estáticos**
   - Comerciantes, Banqueros, Entrenadores, Herreros no se mueven
   - Permanecen en su posición inicial

### Implementación Actual

```python
# src/effect_npc_movement.py
class NPCMovementEffect(TickEffect):
    """Efecto que hace que los NPCs se muevan aleatoriamente."""
    
    async def _move_npc_with_ai(self, npc, player_repo):
        # Obtener jugadores en el mapa
        player_ids = self.npc_service.map_manager.get_players_in_map(npc.map_id)
        
        # Encontrar jugador más cercano
        closest_player = None
        min_distance = float("inf")
        
        for user_id in player_ids:
            position = await player_repo.get_position(user_id)
            distance = abs(npc.x - position["x"]) + abs(npc.y - position["y"])
            
            if distance < min_distance and distance <= 10:
                min_distance = distance
                closest_player = (position["x"], position["y"])
        
        # Perseguir o moverse aleatoriamente
        if closest_player:
            await self._move_towards_target(npc, *closest_player)
        else:
            await self._move_npc_randomly(npc)
```

### Configuración

- **Intervalo de movimiento**: 5 segundos
- **Rango de detección**: 10 tiles
- **NPCs hostiles**: Goblin (ID=1), Lobo (ID=7)
- **GameTick**: 0.5 segundos

### Broadcast de Movimiento

Cuando un NPC se mueve, el servidor envía `CHARACTER_MOVE` a todos los jugadores en el mapa:

```python
# src/npc_service.py
async def move_npc(self, npc, new_x, new_y, new_heading):
    # Actualizar en Redis
    await self.npc_repository.update_npc_position(...)
    
    # Actualizar en memoria
    npc.x = new_x
    npc.y = new_y
    npc.heading = new_heading
    
    # Broadcast a jugadores cercanos
    await self.broadcast_service.broadcast_character_move(
        npc.map_id, npc.char_index, new_x, new_y, new_heading, old_x, old_y
    )
```

## 📊 Estructura de Datos del NPC

```python
@dataclass
class NPC:
    # Identificación
    npc_id: int              # ID único del NPC en el mundo
    char_index: int          # CharIndex en el mapa (10001+)
    name: str                # Nombre del NPC
    
    # Posición
    map_id: int
    x: int
    y: int
    heading: int             # 1=Norte, 2=Este, 3=Sur, 4=Oeste
    
    # Apariencia
    body_id: int             # ID del sprite del cuerpo
    head_id: int             # ID del sprite de la cabeza (0 si no tiene)
    
    # Stats
    hp: int
    max_hp: int
    level: int
    
    # Comportamiento
    is_hostile: bool         # ¿Ataca a jugadores?
    is_attackable: bool      # ¿Puede ser atacado?
    movement_type: str       # "static", "patrol", "random"
    respawn_time: int        # Segundos para respawn
    
    # Loot
    gold_min: int
    gold_max: int
    items: list[tuple[int, float]]  # [(item_id, drop_chance)]
```

## 🗺️ NPCs en el Mapa

### Spawn Inicial

```python
# Al cargar el mapa, el servidor:
# 1. Lee los NPCs del archivo de mapa
# 2. Crea instancias de NPC
# 3. Los agrega al MapManager

map_manager.spawn_npc(
    npc_id=1,
    name="Goblin",
    map_id=1,
    x=50,
    y=50,
    body_id=500,  # ID del sprite de goblin
    head_id=0,
    is_hostile=True,
)
```

### Sistema de Spawns ✅ IMPLEMENTADO

Los NPCs se configuran en `data/map_npcs.toml` con dos tipos de spawns:

#### 1. Spawn Points Fijos
NPCs que aparecen en posiciones exactas cuando se carga el mapa:

```toml
[[map_npcs.1.spawn_points]]
npc_id = 504
x = 49
y = 50
direction = 3
```

- Se procesan durante la inicialización del servidor
- Siempre aparecen en la misma posición
- Se crean al iniciar el servidor

#### 2. Random Spawns (Spawns Aleatorios)
NPCs que aparecen dinámicamente en áreas definidas:

```toml
[[map_npcs.1.random_spawns]]
npc_type = "hostile"
count = 5
area = {x1 = 70, y1 = 70, x2 = 90, y2 = 90}
```

- Se manejan dinámicamente cuando un jugador entra al mapa
- No se procesan durante la inicialización
- Se usan para generar NPCs aleatorios en zonas específicas
- El servicio `NPCSpawnService` maneja estos spawns

### Extracción de NPCs desde Mapas VB6 ✅ IMPLEMENTADO

Se creó un sistema para extraer todos los NPCs desde los archivos de mapas originales del VB6:

#### Herramientas de Extracción

1. **`tools/extraction/extract_npcs_from_maps.py`**
   - Extrae NPCs desde archivos `.Inf` del servidor VB6
   - Lee todos los mapas (`Mapa*.Inf`) y detecta NPCs en tiles
   - Genera `data/map_npcs.toml` con spawn_points
   - Preserva spawns aleatorios existentes
   - **Resultado**: 1,604 NPCs en 99 mapas

2. **`tools/extraction/clean_duplicate_npc_spawns.py`**
   - Limpia spawns duplicados en la misma posición
   - Mantiene solo el primer NPC definido por tile
   - Evita errores de tiles ocupados

#### Estadísticas Actuales

- **Total de NPCs spawneados**: 1,604 NPCs
- **Mapas con NPCs**: 99 mapas
- **NPCs únicos en catálogo**: 336 NPCs (147 hostiles, 189 amigables)

### Cuando un Jugador Entra al Mapa

```python
# El servidor envía CHARACTER_CREATE de:
# 1. Todos los jugadores en el mapa
# 2. Todos los NPCs en el mapa

async def notify_player_enter_map(player_id, map_id):
    # Enviar jugadores existentes
    for player in map_manager.get_players(map_id):
        await send_character_create(player)
    
    # Enviar NPCs del mapa
    for npc in map_manager.get_npcs(map_id):
        await send_character_create(npc)
```

## 🎯 Interacción con NPCs

### Click en NPC

```python
# Cliente envía: LEFT_CLICK (Packet ID: 8)
# Servidor responde según el tipo de NPC:

if npc.is_merchant:
    # Abrir ventana de comercio
    await send_commerce_init(npc_id, npc_items)

elif npc.is_banker:
    # Abrir ventana de banco
    await send_bank_init(player_items)

elif npc.is_trainer:
    # Mostrar opciones de entrenamiento
    await send_trainer_options(npc_id)

elif npc.is_hostile:
    # Atacar al NPC
    await attack_npc(player_id, npc_id)
```

## ✅ Implementación Actual en PyAO

### NPCService (Implementado)
```python
# src/npc_service.py
class NPCService:
    async def initialize_world_npcs(self, spawns_path: str):
        """Inicializa todos los NPCs del mundo desde map_npcs.toml."""
    
    async def spawn_npc(self, npc_id, map_id, x, y, heading):
        """Crea un NPC en el mapa."""
    
    async def move_npc(self, npc, new_x, new_y, new_heading):
        """Mueve un NPC y hace broadcast a jugadores."""
    
    async def remove_npc(self, npc):
        """Elimina un NPC del mundo."""
```

### NPCMovementEffect (Implementado)
```python
# src/effect_npc_movement.py
class NPCMovementEffect(TickEffect):
    """Efecto de IA que mueve NPCs hostiles."""
    
    async def apply(self, user_id, player_repo, message_sender):
        """Ejecuta la IA de movimiento cada 5 segundos."""
```

### MultiplayerBroadcastService (Implementado)
```python
# src/multiplayer_broadcast_service.py
async def broadcast_character_move(
    self, map_id, char_index, new_x, new_y, new_heading, old_x, old_y
):
    """Envía CHARACTER_MOVE a todos los jugadores en el mapa."""
```

## 🔮 Próximas Fases

### Fase 3: Sistema de Combate (Pendiente)
```python
class CombatService:
    async def npc_attack(self, npc_id, target_id):
        """NPC ataca a un jugador."""
    
    async def calculate_damage(self, attacker, defender):
        """Calcula daño de un ataque."""
    
    async def apply_damage(self, target_id, damage):
        """Aplica daño a un objetivo."""
```

### Fase 4: Sistema de Loot (Pendiente)
```python
class LootService:
    async def drop_loot(self, npc_id, position):
        """Genera loot cuando un NPC muere."""
    
    async def give_experience(self, player_id, npc_level):
        """Otorga experiencia al jugador."""
```

## 📝 Notas Importantes

1. **CharIndex Único**: Cada personaje (jugador o NPC) en el mapa debe tener un CharIndex único.

2. **Rango de CharIndex**:
   - Jugadores: 1-10000 (convención)
   - NPCs: 10001+ (convención)

3. **Mismo Protocolo**: NPCs y jugadores usan los mismos paquetes (CHARACTER_CREATE, CHARACTER_MOVE, etc.)

4. **IA del Servidor**: El cliente solo renderiza, toda la lógica está en el servidor.

5. **Optimización**: No enviar NPCs fuera del rango de visión del jugador.

## 🚀 Estado Actual y Próximos Pasos

### ✅ Completado
1. **NPCRepository** - Almacenar NPCs en Redis
2. **NPCService** - Gestión de NPCs (spawn, despawn, move)
3. **NPCCatalog** - Catálogo de NPCs desde `data/npcs.toml` (336 NPCs)
4. **NPCMovementEffect** - IA básica de movimiento y persecución
5. **MultiplayerBroadcastService** - Broadcast de movimiento a jugadores
6. **Extracción de NPCs desde Mapas** - 1,604 NPCs en 99 mapas desde archivos VB6
7. **Sistema de Spawns** - Spawns fijos (spawn_points) y aleatorios (random_spawns)
8. **Sistema de Mascotas** - Comando `/PET`, seguimiento automático, limpieza al desconectar
9. **Random Spawns Dinámicos** - Sistema completo de spawns aleatorios con límites por área ✅ **NUEVO**
10. **Sonidos de NPCs** - Sistema completo de sonidos (ataque, daño, muerte) ✅ **NUEVO**

### 🔄 En Progreso
- **Tests** - 11 tests de movimiento y broadcast de NPCs

### 📋 Pendiente
1. **CombatService** - Sistema de combate NPC vs Jugador
2. **LootService** - Sistema de drops y experiencia
3. **NPCDialogService** - Sistema de diálogos con NPCs
4. **QuestService** - Sistema de misiones
5. **IA Avanzada** - Pathfinding, comportamientos complejos

## 📄 Archivos de Configuración

### Cliente Original: localindex.dat

El cliente original tiene un archivo **`localindex.dat`** que contiene información de texto.

**Ubicación**: `C:\AO20\init\localindex.dat`

**Contenido**:
- `[HECHIZO1]`, `[HECHIZO2]`, etc. - Información de hechizos
- `[OBJ1]`, `[OBJ2]`, etc. - Información de objetos
- `[NPC1]`, `[NPC2]`, etc. - **Información de NPCs**

### PyAO Server: Archivos TOML Separados ⭐

PyAO Server usa archivos **TOML separados** en lugar de un solo `.dat`:

**Ubicación**: `data/`

**Archivos**:
- `data/npcs.toml` - Catálogo de NPCs
- `data/hechizos.toml` - Catálogo de hechizos
- `data/objetos.toml` - Catálogo de objetos

**Formato de NPC en npcs.toml**:
```toml
[[npc]]
id = 1
nombre = "Goblin"
descripcion = "Un goblin salvaje que ataca a los viajeros."
body_id = 500
head_id = 0
es_hostil = true
es_atacable = true
nivel = 5
hp_max = 100
oro_min = 10
oro_max = 50

[[npc]]
id = 2
nombre = "Comerciante"
descripcion = "Un comerciante amigable que vende pociones."
body_id = 501
head_id = 1
es_hostil = false
es_atacable = false
nivel = 0
hp_max = 0
oro_min = 0
oro_max = 0
```

### ¿Cómo se Usa?

1. **Servidor**: Solo envía el **NPC ID** y datos mínimos (body, head, posición)
2. **Cliente**: Lee el nombre y descripción del `localindex.dat` usando el NPC ID
3. **Beneficio**: Ahorra ancho de banda (no enviar nombres/descripciones cada vez)

### Ventajas de TOML sobre .dat

1. **Formato Moderno** - Más legible y mantenible
2. **Separación** - Un archivo por tipo de dato
3. **Versionable** - Fácil de trackear en Git
4. **Tipado** - Estructura clara con tipos
5. **Comentarios** - Se pueden agregar comentarios
6. **Validación** - Fácil de validar con schemas
7. **Extensible** - Fácil agregar nuevos campos

### Carga de Catálogos

```python
import tomllib

# Cargar catálogo de NPCs
with open("data/npcs.toml", "rb") as f:
    data = tomllib.load(f)
    npcs = {npc["id"]: npc for npc in data["npc"]}

# Obtener NPC por ID
goblin = npcs[1]
print(f"{goblin['nombre']}: {goblin['descripcion']}")
```

### Implicaciones para PyAO Server

**Opción 1: Usar localindex.dat (Compatible)**
```python
# El servidor solo envía el NPC ID
await message_sender.send_character_create(
    char_index=10001,
    body=500,      # ID del sprite
    head=0,
    heading=3,
    x=50,
    y=50,
    name="",       # Vacío! El cliente lo lee de localindex.dat
)

# El cliente busca en localindex.dat:
# [NPC500] -> NOMBRE=Goblin
```

**Opción 2: Enviar Nombre Completo (Más Simple)**
```python
# El servidor envía el nombre completo
await message_sender.send_character_create(
    char_index=10001,
    body=500,
    head=0,
    heading=3,
    x=50,
    y=50,
    name="Goblin",  # Nombre completo
)

# Más simple pero usa más ancho de banda
```

**Recomendación**: Empezar con **Opción 2** (más simple) y luego optimizar con **Opción 1** si es necesario.

## 🔊 Sistema de Sonidos de NPCs ✅ COMPLETADO

Los NPCs pueden reproducir sonidos en diferentes situaciones:

### Sonidos Implementados

| Campo | Descripción | Cuándo se Reproduce |
|-------|-------------|---------------------|
| `snd1` | Sonido de ataque | Cuando el NPC ataca a un jugador |
| `snd2` | Sonido de daño | Cuando el NPC recibe daño |
| `snd3` | Sonido de muerte | Cuando el NPC muere |

### Configuración

Los sonidos se configuran en el catálogo de NPCs (`data/npcs_complete.toml`):

```toml
[[npc]]
id = 1
nombre = "Goblin"
# ...
[appearance]
sounds = [10, 11, 12]  # [snd1, snd2, snd3]
```

### Implementación

1. **Ataque (snd1)**: Reproducido por `NPCService` cuando el NPC ataca
2. **Daño (snd2)**: Reproducido por `AttackCommandHandler` cuando el NPC recibe daño
3. **Muerte (snd3)**: Reproducido por `NPCDeathService` cuando el NPC muere

**Protocolo:** Todos los sonidos usan el paquete `PLAY_WAVE` (Packet ID: 51)

**Ejemplo:**
```python
# Cuando un NPC ataca
if npc.snd1 > 0:
    await broadcast_service.broadcast_play_wave(
        map_id=npc.map_id, wave_id=npc.snd1, x=npc.x, y=npc.y
    )
```

### NPCs con Sonidos

Muchos NPCs del catálogo tienen sonidos configurados:
- Goblin: Sonidos de gruñido y muerte
- Lobo: Aullidos y sonidos de ataque
- Araña: Sonidos de veneno y muerte
- Y más...

Ver `data/npcs_complete.toml` para la lista completa de NPCs con sonidos.

## 📚 Referencias

- [LOGIN_FLOW.md](guides/LOGIN_FLOW.md) - Flujo de login (usa CHARACTER_CREATE)
- [SERVICES_ARCHITECTURE.md](architecture/SERVICES_ARCHITECTURE.md) - Arquitectura de servicios
- Cliente VB6 - `charlist()` maneja jugadores y NPCs
- [localindex.dat](https://github.com/ao-org/Recursos/blob/master/init/localindex.dat) - Archivo de índice del cliente
- [Creador de Índices](https://github.com/ao-org/argentum-online-creador-indices) - Programa que genera localindex.dat

---

## Arquitectura interna: NPC_ARCHITECTURE.md

> Documento fuente archivado en [`archive/superseded/NPC_ARCHITECTURE.md`](../archive/superseded/NPC_ARCHITECTURE.md).

## Descripción General

El sistema de NPCs está diseñado con una **arquitectura de capas** que separa:
- **Configuración** (archivos TOML)
- **Factory** (creación de instancias)
- **Service** (lógica de negocio)
- **Repository** (persistencia en Redis)

---

## 📊 Flujo de Datos

```
data/npcs_hostiles.toml
         ↓
    NPCCatalog (lee TOML)
         ↓
    NPCService (lógica)
         ↓
    NPCFactory.create_hostile(parámetros del TOML)
         ↓
    NPC (instancia)
         ↓
    NPCRepository (persiste en Redis)
```

---

## 🔧 Componentes

### 1. **NPCCatalog**
**Ubicación:** `src/npc_catalog.py`

**Responsabilidad:** Leer y parsear archivos TOML

```python
catalog = NPCCatalog("data/npcs_hostiles.toml")
npc_data = catalog.get_npc_data(npc_id=1)  # Devuelve dict con todos los parámetros
```

**Formato TOML:**
```toml
[[npc]]
id = 1
nombre = "Goblin"
body_id = 14
hp_max = 110
nivel = 5
ataque = 8
cooldown_ataque = 2.5
rango_agresion = 6
# ... más parámetros
```

---

### 2. **NPCFactory**
**Ubicación:** `src/npc_factory.py`

**Responsabilidad:** Crear instancias de NPCs con parámetros configurables

```python
# Método genérico (usado por NPCService)
npc = NPCFactory.create_hostile(
    npc_id=1,
    name="Goblin",
    body_id=14,
    hp=110,
    level=5,
    x=50, y=50,
    map_id=1,
    char_index=10001,
    attack_damage=8,
    attack_cooldown=2.5,
    aggro_range=6,
    fx=5,
    fx_loop=0
)

# Métodos helper (conveniencia)
npc = NPCFactory.create_goblin(x=50, y=50, map_id=1, char_index=10001)
```

**Ventajas:**
- ✅ **100% configurable desde TOML**
- ✅ Factory no tiene lógica de negocio
- ✅ Fácil agregar nuevos NPCs sin cambiar código
- ✅ Métodos helper opcionales para conveniencia

---

### 3. **NPCService**
**Ubicación:** `src/npc_service.py`

**Responsabilidad:** Coordinar la creación y spawneo de NPCs

**Flujo en `spawn_npc()`:**

```python
async def spawn_npc(self, npc_id: int, map_id: int, x: int, y: int) -> NPC | None:
    # 1. Obtener datos del catálogo (TOML)
    npc_data = self.npc_catalog.get_npc_data(npc_id)
    
    # 2. Asignar CharIndex único
    char_index = self._next_char_index
    self._next_char_index += 1
    
    # 3. Crear instancia via Repository (usa TOML data)
    npc = await self.npc_repository.create_npc_instance(
        npc_id=npc_id,
        char_index=char_index,
        map_id=map_id,
        x=x, y=y,
        name=npc_data.get("nombre"),
        body_id=npc_data.get("body_id"),
        hp=npc_data.get("hp_max"),
        # ... TODOS los parámetros del TOML
        attack_damage=npc_data.get("ataque", 10),
        attack_cooldown=npc_data.get("cooldown_ataque", 3.0),
        aggro_range=npc_data.get("rango_agresion", 8)
    )
    
    # 4. Agregar al mapa
    self.map_manager.add_npc(map_id, npc)
    
    # 5. Broadcast a jugadores
    await self.broadcast_service.broadcast_character_create(...)
    
    # 6. Enviar FX si tiene aura
    if npc.fx_loop > 0:
        await self.broadcast_service.broadcast_create_fx(...)
    
    return npc
```

**El NPCService YA hace lo que pediste:**
- ✅ Lee parámetros del TOML
- ✅ Usa factory genérico
- ✅ No tiene lógica hardcodeada
- ✅ Totalmente configurable

---

### 4. **NPCRepository**
**Ubicación:** `src/npc_repository.py`

**Responsabilidad:** Persistencia en Redis

```python
# Crear y persistir
npc = await npc_repo.create_npc_instance(
    npc_id=1,
    char_index=10001,
    # ... todos los parámetros
)

# Recuperar de Redis
npc = await npc_repo.get_npc_by_instance_id("uuid-123")

# Actualizar
await npc_repo.update_npc(npc)

# Eliminar
await npc_repo.remove_npc("uuid-123")
```

---

## 🎯 Ejemplo Completo: Agregar un NPC Nuevo

### 1. Agregar al TOML

```toml
[[npc]]
id = 25
nombre = "Troll de Hielo"
descripcion = "Un troll gigante de las montañas heladas."
body_id = 180
head_id = 0
es_hostil = true
es_atacable = true
nivel = 30
hp_max = 3000
oro_min = 200
oro_max = 800
respawn_time = 180
respawn_time_max = 360
ataque = 80
cooldown_ataque = 4.0
rango_agresion = 12
```

### 2. Spawnear el NPC

```python
# En map_npcs.toml
[[spawn]]
map_id = 5
npc_id = 25  # <-- Nuevo Troll
x = 50
y = 50
heading = 3
```

### 3. ¡Listo!

**NO necesitas:**
- ❌ Modificar código Python
- ❌ Crear método en Factory
- ❌ Tocar NPCService
- ❌ Escribir tests específicos

**El sistema automáticamente:**
- ✅ Lee el TOML
- ✅ Crea la instancia
- ✅ Spawnea el NPC
- ✅ Persiste en Redis
- ✅ Envía al cliente

---

## 📈 Ventajas de esta Arquitectura

### Separación de Responsabilidades
- **NPCCatalog**: Solo lee archivos
- **NPCFactory**: Solo crea instancias
- **NPCService**: Solo orquesta
- **NPCRepository**: Solo persiste

### Configurabilidad
- Todos los stats en TOML
- Sin código hardcodeado
- Fácil balanceo

### Escalabilidad
- Agregar 100 NPCs = 100 entradas en TOML
- Sin cambios en código
- Sin riesgo de bugs

### Mantenibilidad
- Un solo lugar para cambiar stats
- Cambios sin deployar código
- Hot-reload posible en futuro

---

## 🧪 Testing

El sistema está diseñado para testing fácil:

```python
# Test con datos mock
npc_data = {
    "nombre": "Test NPC",
    "body_id": 1,
    "hp_max": 100,
    # ...
}

npc = NPCFactory.create_hostile(
    **npc_data,
    x=50, y=50,
    map_id=1,
    char_index=10001
)

assert npc.name == "Test NPC"
assert npc.hp == 100
```

---

## 📊 Catálogo Actual

**24 NPCs hostiles configurados:**
- Murciélago (id=16)
- Serpiente (id=9)
- Lobo (id=7)
- Goblin (id=1)
- Esqueleto (id=11)
- Escorpión (id=17)
- Zombie (id=12)
- Araña Gigante (id=8)
- Bandido (id=18)
- Oso Pardo (id=19)
- Orco (id=4)
- Tigre Salvaje (id=20)
- Licántropo (id=21)
- Golem (id=23)
- Ogro (id=14)
- Liche (id=22)
- Elemental de Fuego (id=24)
- Demonio (id=15)
- Dragón Rojo (id=10)
- Gran Dragón Rojo (id=13) - BOSS

**Todos con:**
- Body IDs correctos del VB6
- Stats balanceados
- Configuración completa

---

## 🔄 Próximas Mejoras

### Hot-Reload de Configuración
```python
# Recargar TOML sin reiniciar servidor
await npc_service.reload_catalog()
```

### Validación de TOML
```python
# Validar al cargar
NPCCatalog.validate("data/npcs_hostiles.toml")
```

### NPCs por Loot Table
```toml
[[npc]]
id = 25
# ...
loot_table = "boss_dragon"  # Referencia a loot_tables.toml
```

---

**Última actualización:** 2025-10-21  
**Autor:** Equipo PyAO  
**Estado:** ✅ Producción

