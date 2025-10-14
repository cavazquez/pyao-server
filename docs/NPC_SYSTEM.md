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
# CHARACTER_MOVE (Packet ID: 30)

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

## 🤖 IA del Servidor (No Implementado Aún)

### Comportamientos Típicos

1. **Patrullaje**
   - El NPC se mueve en un área definida
   - Puede seguir un path predefinido

2. **Agresión**
   - Detecta jugadores cercanos
   - Persigue y ataca

3. **Huida**
   - Si la vida es baja, huye
   - Busca aliados

4. **Respawn**
   - Después de morir, reaparece en un tiempo
   - Puede tener un punto de spawn fijo

### Ejemplo de IA Básica

```python
class NPCBehavior:
    async def update(self, npc, delta_time):
        if npc.is_hostile:
            # Buscar jugadores cercanos
            target = self.find_nearest_player(npc)
            
            if target:
                # Perseguir
                await self.move_towards(npc, target)
                
                # Atacar si está en rango
                if self.is_in_range(npc, target):
                    await self.attack(npc, target)
        else:
            # Patrullar
            await self.patrol(npc)
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

## 🔮 Implementación Futura en PyAO

### Fase 1: NPCs Estáticos
```python
class NPCService:
    async def spawn_npc(self, map_id, npc_data):
        """Crea un NPC en el mapa."""
    
    async def send_npcs_to_player(self, player_id, map_id):
        """Envía todos los NPCs del mapa al jugador."""
```

### Fase 2: NPCs con IA
```python
class NPCAIService:
    async def update_npc_behavior(self, npc_id, delta_time):
        """Actualiza el comportamiento del NPC."""
    
    async def npc_attack(self, npc_id, target_id):
        """NPC ataca a un objetivo."""
```

### Fase 3: Sistema de Combate
```python
class CombatService:
    async def calculate_damage(self, attacker, defender):
        """Calcula daño de un ataque."""
    
    async def apply_damage(self, target_id, damage):
        """Aplica daño a un objetivo."""
```

## 📝 Notas Importantes

1. **CharIndex Único**: Cada personaje (jugador o NPC) en el mapa debe tener un CharIndex único.

2. **Rango de CharIndex**:
   - Jugadores: 1-10000 (convención)
   - NPCs: 10001+ (convención)

3. **Mismo Protocolo**: NPCs y jugadores usan los mismos paquetes (CHARACTER_CREATE, CHARACTER_MOVE, etc.)

4. **IA del Servidor**: El cliente solo renderiza, toda la lógica está en el servidor.

5. **Optimización**: No enviar NPCs fuera del rango de visión del jugador.

## 🚀 Próximos Pasos

1. **NPCRepository** - Almacenar NPCs en Redis
2. **NPCService** - Gestión de NPCs (spawn, despawn, move)
3. **NPCAIService** - Comportamientos de IA
4. **CombatService** - Sistema de combate
5. **LootService** - Sistema de drops

## 📄 Archivos de Configuración del Cliente

### localindex.dat

El cliente tiene un archivo **`localindex.dat`** que contiene información de texto para minimizar el uso de ancho de banda.

**Ubicación**: `C:\AO20\init\localindex.dat`

**Contenido**:
- `[HECHIZO1]`, `[HECHIZO2]`, etc. - Información de hechizos
- `[OBJ1]`, `[OBJ2]`, etc. - Información de objetos
- `[NPC1]`, `[NPC2]`, etc. - **Información de NPCs** (nombres, descripciones)

**Formato de NPC en localindex.dat**:
```ini
[NPC1]
NOMBRE=Goblin
DESC=Un goblin salvaje que ataca a los viajeros.

[NPC2]
NOMBRE=Comerciante
DESC=Un comerciante amigable que vende pociones.

[NPC3]
NOMBRE=Guardia Real
DESC=Un guardia que protege la ciudad.
```

### ¿Cómo se Usa?

1. **Servidor**: Solo envía el **NPC ID** y datos mínimos (body, head, posición)
2. **Cliente**: Lee el nombre y descripción del `localindex.dat` usando el NPC ID
3. **Beneficio**: Ahorra ancho de banda (no enviar nombres/descripciones cada vez)

### Generación del Archivo

El archivo se genera con el programa **`Creador_de_indices.exe`**:
- Lee los datos del servidor (NPCs.dat, Obj.dat, Hechizos.dat)
- Genera el `localindex.dat` para el cliente
- Repositorio: [argentum-online-creador-indices](https://github.com/ao-org/argentum-online-creador-indices)

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

## 📚 Referencias

- [LOGIN_FLOW.md](LOGIN_FLOW.md) - Flujo de login (usa CHARACTER_CREATE)
- [SERVICES_ARCHITECTURE.md](SERVICES_ARCHITECTURE.md) - Arquitectura de servicios
- Cliente VB6 - `charlist()` maneja jugadores y NPCs
- [localindex.dat](https://github.com/ao-org/Recursos/blob/master/init/localindex.dat) - Archivo de índice del cliente
- [Creador de Índices](https://github.com/ao-org/argentum-online-creador-indices) - Programa que genera localindex.dat
