# Sistema de Clanes - Documentación

## Overview

El sistema de clanes (guilds) permite a los jugadores crear y gestionar organizaciones permanentes con hasta 50 miembros. Está basado en el sistema del servidor VB6 original de Argentum Online, pero implementado con arquitectura moderna en Python con Redis.

## ⚠️ Limitación del Cliente

**El servidor envía correctamente el packet `CLAN_DETAILS` (ID 80) durante el login para habilitar el botón de clanes en el cliente, pero el cliente Godot actualmente NO procesa este packet.**

- ✅ El servidor envía el packet correctamente cuando está habilitado (ver [`docs/CLAN_BUTTON.md`](CLAN_BUTTON.md))
- ❌ El cliente Godot no tiene implementado el manejo del packet 80
- 📝 **Solución**: El cliente necesita implementar el handler para el packet 80 que habilite el botón de clanes en la UI

**Nota**: Los comandos de clan (`/CREARCLAN`, `/INVITARCLAN`, `/CLAN`, etc.) funcionan correctamente desde la consola, pero el botón visual en la UI no se habilita porque el cliente no procesa el packet 80.

## Características

### ✅ Implementadas
- **Creación de clanes**: Líder puede crear clan con requisitos mínimos (nivel 13+)
- **Invitaciones**: Sistema de invitaciones con expiración (60 segundos)
- **Gestión de miembros**: Unirse, abandonar, expulsar miembros
- **Sistema de rangos**: 4 niveles jerárquicos (MEMBER, OFFICER, VICE_LEADER, LEADER)
- **Promoción/Degradación**: Vice líderes+ pueden cambiar rangos de miembros
- **Transferencia de liderazgo**: El líder puede ceder el liderazgo a otro miembro
- **Chat de clan**: Mensajes privados entre todos los miembros del clan
- **Notificaciones**: Todos los miembros reciben notificaciones de eventos importantes
- **Validaciones**: Nivel mínimo, estado (vivo/muerto), permisos por rango
- **Persistencia**: Todos los datos guardados en Redis

### 🔄 Funcionalidades Futuras
- **Almacén del clan**: Depósito compartido de items y oro
- **Alianzas y guerras**: Relaciones diplomáticas entre clanes
- **Edificio del clan**: Zona propia con NPCs del clan
- **Sistema de código**: Reglas y descripciones extendidas

## Arquitectura

### Modelos de Datos

#### Clan
```python
@dataclass
class Clan:
    clan_id: int
    name: str
    description: str
    leader_id: int
    leader_username: str
    created_at: float
    website: str = ""
    members: Dict[int, ClanMember]
    alliances: List[int] = field(default_factory=list)
    wars: List[int] = field(default_factory=list)
```

#### ClanMember
```python
@dataclass
class ClanMember:
    user_id: int
    username: str
    level: int
    rank: ClanRank  # MEMBER, OFFICER, VICE_LEADER, LEADER
    joined_at: float
    is_online: bool
    last_seen: float
    contribution: int  # Puntos de contribución al clan
```

#### ClanInvitation
```python
@dataclass
class ClanInvitation:
    clan_id: int
    clan_name: str
    inviter_id: int
    inviter_username: str
    target_id: int
    target_username: str
    created_at: float
    expires_at: float  # 60 segundos desde creación
```

#### ClanRank (Enum)
```python
class ClanRank(IntEnum):
    MEMBER = 1          # Miembro regular (permisos básicos)
    OFFICER = 2         # Oficial (puede invitar/expulsar)
    VICE_LEADER = 3     # Vice líder (puede promover/degradar)
    LEADER = 4          # Líder (control total)
```

### Constantes del Sistema

- **MAX_CLAN_MEMBERS**: 50 miembros máximo por clan
- **MIN_LEVEL_TO_CREATE**: 13 nivel mínimo para crear un clan
- **MIN_LEVEL_TO_JOIN**: 1 nivel mínimo para unirse a un clan
- **INVITATION_TIMEOUT_SECONDS**: 60 segundos de expiración de invitaciones
- **MAX_CLAN_NAME_LENGTH**: 30 caracteres máximo para el nombre
- **MAX_CLAN_DESCRIPTION_LENGTH**: 200 caracteres máximo para la descripción

### Repositorio (Redis)

#### Keys utilizadas:
- `clan:next_id` - ID autoincremental para nuevos clanes
- `clan:{id}` - Metadata del clan (hash)
- `clan:{id}:members` - Miembros del clan (hash)
- `clan:index` - Set con todos los IDs de clanes activos
- `user:{id}:clan` - Referencia al clan del usuario
- `clan_invitations:{target_id}` - Invitaciones pendientes por usuario (hash)

#### Operaciones principales:
- **CRUD completo** de clanes y miembros
- **Invitaciones** con expiración automática
- **Consultas eficientes** por usuario o clan
- **Transacciones** para mantener consistencia

### Servicio de Negocio (ClanService)

Centraliza toda la lógica de negocio del sistema:

#### Validaciones:
- **Nivel mínimo**: 13 para crear clan, 1 para unirse
- **Estado del personaje**: No puede estar muerto
- **Clan existente**: No puede crear/clan si ya pertenece a uno
- **Nombre único**: No puede haber dos clanes con el mismo nombre
- **Permisos**: Validación de rangos para cada operación

#### Métodos principales:

##### Gestión de Clanes
- `can_create_clan()` - Validar requisitos para crear clan
- `create_clan()` - Crear nuevo clan
- `get_user_clan()` - Obtener clan del usuario

##### Invitaciones
- `invite_to_clan()` - Enviar invitación a un jugador
- `accept_invitation()` - Aceptar invitación pendiente
- `reject_invitation()` - Rechazar invitación pendiente

##### Gestión de Miembros
- `leave_clan()` - Abandonar el clan (no disponible para líder)
- `kick_member()` - Expulsar miembro (requiere OFFICER+)
- `promote_member()` - Promover rango (requiere VICE_LEADER+)
- `demote_member()` - Degradar rango (requiere VICE_LEADER+)
- `transfer_leadership()` - Transferir liderazgo (requiere LEADER)

##### Comunicación
- `send_clan_message()` - Enviar mensaje a todos los miembros

### Sistema de Permisos

Los permisos están determinados por el rango del miembro:

| Rango | Invitar | Expulsar | Promover/Degradar | Transferir Liderazgo | Gestionar Clan |
|-------|---------|----------|-------------------|---------------------|----------------|
| MEMBER | ❌ | ❌ | ❌ | ❌ | ❌ |
| OFFICER | ✅ | ✅ | ❌ | ❌ | ❌ |
| VICE_LEADER | ✅ | ✅ | ✅ | ❌ | ❌ |
| LEADER | ✅ | ✅ | ✅ | ✅ | ✅ |

## Comandos Disponibles

### Creación y Gestión
- `/CREARCLAN <nombre> [descripción]` - Crear un clan (nivel 13+)
- `/INVITARCLAN <usuario>` - Invitar jugador a tu clan
- `/ACEPTARCLAN` - Aceptar invitación a clan
- `/RECHAZARCLAN` - Rechazar invitación a clan
- `/SALIRCLAN` - Abandonar tu clan

### Gestión de Miembros
- `/EXPULSARCLAN <usuario>` - Expulsar miembro (solo oficiales+)
- `/PROMOVERCLAN <usuario>` - Promover miembro (solo vice líder+)
- `/DEGRADARCLAN <usuario>` - Degradar miembro (solo vice líder+)
- `/TRANSFERIRLIDERAZGO <usuario>` - Transferir liderazgo (solo líder)

### Comunicación
- `/CLAN <mensaje>` - Enviar mensaje a todos los miembros del clan

## Flujos de Trabajo

### Crear un Clan

1. El jugador debe ser nivel 13 o superior
2. El jugador no debe pertenecer a ningún clan
3. El jugador debe estar vivo
4. El nombre del clan no debe existir ya
5. Se crea el clan con el jugador como líder (rango LEADER)

**Ejemplo:**
```
/CREARCLAN LosGuerreros Un clan de guerreros valientes
```

### Invitar a un Miembro

1. El inviter debe ser OFICIAL o superior
2. El clan no debe estar lleno (máximo 50 miembros)
3. El objetivo no debe pertenecer a ningún clan
4. El objetivo debe estar conectado y vivo
5. El objetivo debe ser nivel 1 o superior
6. Se crea una invitación que expira en 60 segundos

**Ejemplo:**
```
/INVITARCLAN Jugador123
```

### Aceptar Invitación

1. El jugador debe tener una invitación pendiente
2. La invitación no debe haber expirado
3. El clan no debe estar lleno
4. El jugador se une como MEMBER

**Ejemplo:**
```
/ACEPTARCLAN
```

### Abandonar Clan

1. El jugador debe ser miembro del clan
2. El líder no puede abandonar (debe transferir liderazgo primero)
3. Se notifica a todos los miembros restantes
4. Se elimina la referencia del jugador al clan

**Ejemplo:**
```
/SALIRCLAN
```

### Promover Miembro

1. El promotor debe ser VICE_LEADER o superior
2. El objetivo debe ser miembro del clan
3. El objetivo no puede ser el líder (rango máximo)
4. Se aumenta el rango en uno (MEMBER → OFFICER → VICE_LEADER)
5. Se notifica a todos los miembros del clan

**Ejemplo:**
```
/PROMOVERCLAN MiembroActivo
```

### Transferir Liderazgo

1. Solo el líder actual puede transferir
2. El nuevo líder debe ser miembro del clan
3. El líder actual pasa a ser VICE_LEADER
4. El nuevo miembro pasa a ser LEADER
5. Se notifica a todos los miembros del clan

**Ejemplo:**
```
/TRANSFERIRLIDERAZGO ViceLiderConfiable
```

### Chat de Clan

1. El jugador debe pertenecer a un clan
2. El mensaje se envía a todos los miembros del clan (incluyendo el emisor)
3. Formato: `[Clan] <username>: <mensaje>`
4. Color: Verde (FONTTYPE_PARTY)

**Ejemplo:**
```
/CLAN ¡Nos encontramos en la entrada del mapa 1!
```

## Notificaciones

El sistema envía notificaciones automáticas a todos los miembros del clan en los siguientes eventos:

### Cuando alguien se une al clan
- **Al nuevo miembro**: "Te has unido al clan '{nombre}'"
- **A los demás miembros**: "{username} se ha unido al clan '{nombre}'"

### Cuando alguien abandona el clan
- **Al que abandona**: "Has abandonado el clan '{nombre}'"
- **A los demás miembros**: "{username} ha abandonado el clan '{nombre}'"

### Cuando se expulsa a un miembro
- **Al expulsado**: "Has sido expulsado del clan '{nombre}'" (color rojo)
- **Al expulsador**: "Has expulsado a '{username}' del clan '{nombre}'"
- **A los demás miembros**: "{username} ha sido expulsado del clan '{nombre}'"

### Cuando se promueve/degradan miembros
- **Al promovido/degradado**: "Has sido promovido/degradado a {rango} en el clan '{nombre}'"
- **Al promotor/degradador**: "Has promovido/degradado a '{username}' a {rango}"
- **A los demás miembros**: "{username} ha sido promovido/degradado a {rango} en el clan '{nombre}'"

### Cuando se transfiere el liderazgo
- **Al líder anterior**: "Has transferido el liderazgo del clan '{nombre}' a '{username}'"
- **Al nuevo líder**: "¡Has sido nombrado líder del clan '{nombre}'!"
- **A los demás miembros**: "{old_leader} ha transferido el liderazgo del clan '{nombre}' a {new_leader}"

Todas las notificaciones usan el color verde (FONTTYPE_PARTY = 7), excepto los mensajes de expulsión que usan rojo (FONTTYPE_FIGHT = 1).

## Persistencia

### Redis Keys

El sistema utiliza las siguientes keys en Redis:

- **`clan:next_id`**: ID autoincremental para nuevos clanes (tipo: string/int)
- **`clan:{id}`**: Hash con metadata del clan:
  - `name`: Nombre del clan
  - `description`: Descripción
  - `leader_id`: ID del líder
  - `leader_username`: Nombre del líder
  - `created_at`: Timestamp de creación
  - `website`: Sitio web (opcional)
- **`clan:{id}:members`**: Hash con miembros del clan (key: user_id, value: JSON de ClanMember)
- **`clan:index`**: Set con todos los IDs de clanes activos
- **`user:{id}:clan`**: Referencia al clan del usuario (tipo: string/int con clan_id)
- **`clan_invitations:{target_id}`**: Hash con invitación pendiente (tipo: JSON de ClanInvitation)

### Persistencia de Invitaciones

Las invitaciones expiran automáticamente después de 60 segundos. El sistema verifica la expiración cada vez que se intenta aceptar una invitación.

## Ejemplos de Uso

### Ejemplo 1: Crear y gestionar un clan pequeño

```
# Líder crea el clan
/CREARCLAN LosValientes Un clan para jugadores activos

# Líder invita a dos miembros
/INVITARCLAN Jugador1
/INVITARCLAN Jugador2

# Los jugadores aceptan (desde sus clientes)
/ACEPTARCLAN  # Jugador1
/ACEPTARCLAN  # Jugador2

# Líder promueve a Jugador1 a Oficial
/PROMOVERCLAN Jugador1

# Oficial invita a otro miembro
/INVITARCLAN Jugador3  # Jugador1 (ahora oficial) puede invitar

# Líder comunica a todos
/CLAN Reunión mañana a las 20:00 en el mapa 1
```

### Ejemplo 2: Reorganización del clan

```
# Líder quiere dejar el liderazgo
/TRANSFERIRLIDERAZGO Jugador2

# Jugador2 ahora es líder, puede promover miembros
/PROMOVERCLAN Jugador1  # Ahora Jugador1 es Vice Líder

# Vice Líder puede gestionar miembros
/PROMOVERCLAN Jugador3  # Jugador3 ahora es Oficial
/DEGRADARCLAN Jugador4  # Jugador4 degradado de Oficial a Miembro
```

### Ejemplo 3: Gestión de problemas

```
# Oficial expulsa a un miembro problemático
/EXPULSARCLAN MiembroProblematico

# Todos los miembros reciben notificación
# El expulsado recibe mensaje en rojo
```

## Limitaciones Conocidas

1. **Botón de UI no se habilita**: El cliente Godot no procesa el packet `CLAN_DETAILS` (80), por lo que el botón visual de clanes no se habilita aunque el sistema funcione completamente.

2. **Sin almacén del clan**: El sistema de depósito compartido aún no está implementado.

3. **Sin alianzas/guerras**: Las relaciones diplomáticas entre clanes están definidas en el modelo pero no tienen funcionalidad activa.

4. **Sin edificio del clan**: No hay zona propia para los clanes con NPCs especiales.

## Próximos Pasos

1. **Habilitar botón en cliente**: Implementar handler para packet 80 en el cliente Godot
2. **Almacén del clan**: Sistema de depósito compartido de items y oro
3. **Alianzas y guerras**: Comandos y lógica para relaciones entre clanes
4. **Edificio del clan**: Zona dedicada con NPCs del clan

## Referencias

- **Estado de implementación**: `docs/CLAN_SYSTEM_IMPLEMENTATION_STATUS.md`
- **Guía de pruebas**: `docs/TESTING_CLAN_SYSTEM.md`
- **Botón de clan / packet GuildDetails**: [`docs/CLAN_BUTTON.md`](CLAN_BUTTON.md)
- **Código fuente**: `src/services/clan_service.py`
- **Modelos**: `src/models/clan.py`
- **Repositorio**: `src/repositories/clan_repository.py`

