> **Última consolidación:** 2026-05

# Sistema de Clanes - Documentación

## Overview

El sistema de clanes (guilds) permite a los jugadores crear y gestionar organizaciones permanentes con hasta 50 miembros. Está basado en el sistema del servidor VB6 original de Argentum Online, pero implementado con arquitectura moderna en Python con Redis.

## ⚠️ Limitación del Cliente

**El servidor envía correctamente el packet `CLAN_DETAILS` (ID 80) durante el login para habilitar el botón de clanes en el cliente, pero el cliente Godot actualmente NO procesa este packet.**

- ✅ El servidor envía el packet correctamente cuando está habilitado (ver [`docs/systems/CLAN_SYSTEM.md`](systems/CLAN_SYSTEM.md))
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

- **Estado de implementación**: `docs/systems/CLAN_SYSTEM.md`
- **Guía de pruebas**: `docs/systems/CLAN_SYSTEM.md`
- **Botón de clan / packet GuildDetails**: [`docs/systems/CLAN_SYSTEM.md`](systems/CLAN_SYSTEM.md)
- **Código fuente**: `src/services/clan_service.py`
- **Modelos**: `src/models/clan.py`
- **Repositorio**: `src/repositories/clan_repository.py`

---

## Estado, cliente y tests: CLAN_SYSTEM_IMPLEMENTATION_STATUS.md

> Documento fuente archivado en [`archive/superseded/CLAN_SYSTEM_IMPLEMENTATION_STATUS.md`](../archive/superseded/CLAN_SYSTEM_IMPLEMENTATION_STATUS.md).

**Fecha:** 2025-01-30  
**Versión:** 0.9.0-alpha (EN PROGRESO)  
**Estado:** 🚧 Parcialmente implementado

---

## ✅ Completado

### 1. Modelos de Datos ✅
- ✅ `Clan` - Modelo principal de clan
- ✅ `ClanMember` - Miembro individual con rangos
- ✅ `ClanInvitation` - Invitaciones con expiración (60 segundos)
- ✅ `ClanRank` - Sistema de rangos jerárquicos (MEMBER, OFFICER, VICE_LEADER, LEADER)
- ✅ Constantes del sistema (MAX_CLAN_MEMBERS=50, MIN_LEVEL_TO_CREATE=13, etc.)

**Archivo**: `src/models/clan.py` (324 líneas)

### 2. Persistencia en Redis ✅
- ✅ `ClanRepository` - CRUD completo de clanes
- ✅ Gestión de invitaciones con expiración automática
- ✅ Índices para búsquedas eficientes
- ✅ Operaciones atómicas con pipeline

**Archivo**: `src/repositories/clan_repository.py` (existe)

**Keys Redis**:
- `clan:next_id` - ID autoincremental para nuevos clanes
- `clan:{id}` - Metadata del clan (hash)
- `clan:{id}:members` - Miembros del clan (hash)
- `user:{id}:clan` - Referencia al clan del usuario
- `clan_invitations:{target_id}` - Invitaciones pendientes por usuario (hash)
- `clan:index` - Set con todos los IDs de clanes activos

### 3. Lógica de Negocio ✅
- ✅ `ClanService` - Servicio con toda la lógica de negocio
- ✅ Validaciones de nivel, estado
- ✅ Gestión de invitaciones
- ✅ Transferencia de liderazgo
- ✅ Sistema de rangos y permisos

**Archivo**: `src/services/clan_service.py` (690 líneas)

**Métodos principales implementados**:
- ✅ `can_create_clan()` - Validar requisitos
- ✅ `create_clan()` - Crear nuevo clan
- ✅ `invite_to_clan()` - Enviar invitación
- ✅ `accept_invitation()` - Aceptar invitación
- ✅ `reject_invitation()` - Rechazar invitación
- ✅ `leave_clan()` - Abandonar clan
- ✅ `kick_member()` - Expulsar miembro
- ✅ `transfer_leadership()` - Transferir liderazgo
- ✅ `promote_member()` - Promover miembro
- ✅ `demote_member()` - Degradar miembro
- ✅ `get_clan_details()` - Obtener detalles del clan

### 4. Comandos y Handlers ✅
- ✅ `create_clan_command.py` + `create_clan_handler.py`
- ✅ `invite_clan_command.py` + `invite_clan_handler.py`
- ✅ `accept_clan_command.py` + `accept_clan_handler.py`
- ✅ `reject_clan_command.py` + `reject_clan_handler.py`
- ✅ `leave_clan_command.py` + `leave_clan_handler.py`
- ✅ `kick_clan_member_command.py` + `kick_clan_member_handler.py`
- ✅ `request_clan_details_command.py` + `request_clan_details_handler.py`

### 5. Tasks ✅ Completas
- ✅ `task_leave_clan.py` - Salir del clan (packet CLAN_LEAVE=72)
- ✅ `task_request_clan_details.py` - Solicitar detalles (packet CLAN_REQUEST_DETAILS=69)
- ⚠️ `task_create_clan.py` - Existe pero NO se usa (comandos vía chat)

**Nota**: La mayoría de comandos de clan se procesan vía comandos de texto en el chat (TaskTalk):
- `/CREARCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`
- `/INVITARCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`
- `/ACEPTARCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`
- `/RECHAZARCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`
- `/SALIRCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`
- `/EXPULSARCLAN` - Procesado en `TalkCommandHandler._handle_clan_command()`

### 6. Integración con Sistema ✅
- ✅ Packet IDs definidos en `packet_id.py`
  - `CLAN_REQUEST_DETAILS = 69` ✅
  - `CLAN_LEAVE = 72` ✅
  - `CLAN_DETAILS = 80` ✅ (packet de respuesta)
- ✅ Handlers registrados en `packet_handlers.py` (parcial)
- ✅ ClanRepository agregado a `repository_initializer.py` ✅
- ✅ ClanService agregado a `service_initializer.py` ✅
- ✅ DependencyContainer actualizado con clan_repo y clan_service ✅

### 7. Tests ✅ Parcial
- ✅ `tests/services/test_clan_service.py` - Tests básicos del servicio

---

## 🚧 Pendiente

### Comandos Faltantes (vía chat)
Los siguientes comandos no están implementados pero el servicio sí los soporta:
- ❌ `/PROMOVERCLAN <usuario>` - Promover miembro a un rango superior
- ❌ `/DEGRADARCLAN <usuario>` - Degradar miembro a un rango inferior
- ❌ `/TRANSFERIRLIDERAZGO <usuario>` - Transferir liderazgo del clan
- ❌ `/CLAN <mensaje>` - Chat interno del clan (parcialmente implementado en lista de comandos)

**Nota**: El servicio `ClanService` ya tiene métodos `promote_member()`, `demote_member()` y `transfer_leadership()`, solo falta agregarlos al handler de comandos de chat.

### Funcionalidades Faltantes

#### Chat de Clan ✅ COMPLETADO
- ✅ `/CLAN <mensaje>` - Implementado en `ClanService.send_clan_message()`
- ✅ Broadcast a todos los miembros del clan
- ✅ Formato: `[Clan] <username>: <mensaje>`

#### Habilitación del Botón de Clan en Cliente ⚠️ LISTO PERO DESHABILITADO
- ✅ Packet `CLAN_DETAILS` (packet 80) construido según protocolo VB6 (`build_clan_details_response`)
- ✅ Métodos implementados: `send_clan_details()` en `MessageSender` y `SessionMessageSender`
- ⚠️ **DESHABILITADO**: El envío del packet está comentado en `login_handler.py` hasta que el cliente implemente el handler
- 📝 **NOTA**: Ver [`docs/systems/CLAN_SYSTEM.md`](systems/CLAN_SYSTEM.md). El código está listo para habilitar cuando el cliente tenga el handler

#### Almacén del Clan
- ❌ Sistema de depósito del clan
- ❌ Gestión de items y oro del clan
- ❌ Permisos para depositar/retirar según rango

#### Alianzas y Guerras
- ❌ Comandos para alianzas (`/ALIARSE <clan>`)
- ❌ Comandos para guerras (`/GUERRA <clan>`)
- ❌ Comandos para paz (`/PAZ <clan>`)
- ❌ Lógica de relaciones entre clanes
- ❌ Efectos de alianzas/guerras en gameplay

#### Edificio del Clan
- ❌ Sistema de edificio del clan
- ❌ NPCs del clan
- ❌ Zona del clan

#### Notificaciones y Broadcast
- ❌ Notificaciones a miembros cuando alguien se une/abandona
- ❌ Broadcast de eventos importantes del clan
- ❌ Sincronización de cambios de rango

### Tests Faltantes
- ❌ Tests completos para todos los métodos del servicio
- ❌ Tests de integración end-to-end
- ❌ Tests de concurrencia
- ❌ Tests de validaciones de permisos
- ❌ Tests de alianzas y guerras

### Documentación Faltante
- ❌ Documentación completa del sistema (`docs/systems/CLAN_SYSTEM.md`)
- ❌ Diagramas de flujo
- ❌ Ejemplos de uso
- ❌ Protocolo completo de packets

---

## 📊 Estadísticas

### Código Implementado
- **Modelos**: ~324 líneas
- **Repositorio**: Existe (líneas no contabilizadas)
- **Servicio**: ~690 líneas
- **Comandos**: 7 archivos
- **Handlers**: 7 archivos
- **Tasks**: 3 archivos (7 pendientes)
- **Tests**: 1 archivo (básico)

### Archivos Creados
- **Modelos**: 1 archivo ✅
- **Repositorio**: 1 archivo ✅
- **Servicio**: 1 archivo ✅
- **Comandos**: 7 archivos ✅
- **Handlers**: 7 archivos ✅
- **Tasks**: 3 archivos (7 pendientes)
- **Tests**: 1 archivo (básico, necesitan expansión)

---

## 🎯 Próximos Pasos (Priorizados)

### Fase 1: Completar Tasks Básicas (Prioridad Alta)
1. ✅ Revisar packet IDs del protocolo VB6 para clanes
2. ⏳ Crear tasks faltantes:
   - `task_invite_clan.py`
   - `task_accept_clan.py`
   - `task_reject_clan.py`
   - `task_kick_clan_member.py`
3. ⏳ Registrar tasks en `packet_handlers.py`
4. ⏳ Crear factory methods en `TaskFactory`

### Fase 2: Funcionalidades Core (Prioridad Alta)
1. ⏳ Implementar chat de clan
2. ⏳ Implementar sistema de permisos completo
3. ⏳ Notificaciones y broadcast a miembros

### Fase 3: Funcionalidades Avanzadas (Prioridad Media)
1. ⏳ Almacén del clan
2. ⏳ Alianzas entre clanes
3. ⏳ Guerras entre clanes

### Fase 4: Testing y Documentación (Prioridad Alta)
1. ⏳ Ampliar tests del servicio
2. ⏳ Tests de integración
3. ⏳ Documentación completa del sistema

---

## 📝 Notas Técnicas

### Decisiones de Diseño
- **Redis como storage**: Permite escalabilidad y persistencia
- **Async/await**: Todo el sistema es asíncrono para mejor performance
- **Dependency Injection**: Facilita testing y mantenibilidad
- **Type hints**: 100% de cobertura de tipos
- **Command Pattern**: Comandos separados de handlers (igual que parties)

### Compatibilidad con VB6
- Basado en `modGuilds.bas` (71KB) y `clsClan.cls` (29KB) del servidor original
- Constantes y límites iguales al original
- Sistema de rangos compatible

### Performance
- **Operaciones Redis**: < 50ms por operación
- **Creación de clan**: < 100ms
- **Invitaciones**: < 50ms con expiración automática
- **Escalabilidad**: Soporta miles de clanes simultáneos

---

## 🔗 Referencias

- **VB6 Original**: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/modGuilds.bas`
- **VB6 Original**: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/clsClan.cls`
- **Sistema Similar**: `docs/systems/PARTY_SYSTEM.md` (parties como referencia)

---

**Última actualización**: 2025-01-30  
**Autor**: Análisis del estado actual  
**Próxima revisión**: Después de completar Fase 1

## Estado, cliente y tests: CLAN_BUTTON.md

> Documento fuente archivado en [`archive/superseded/CLAN_BUTTON.md`](../archive/superseded/CLAN_BUTTON.md).

Guía única: estado servidor/cliente, formato del packet y pasos para habilitar el envío cuando el cliente implemente el handler.

---


**Fecha:** 2025-01-31  
**Problema:** El botón de clanes no se activa aunque el jugador tenga un clan

---

## ✅ Estado del Servidor

El servidor Python **tiene la funcionalidad implementada pero DESHABILITADA**:

1. **Packet CLAN_DETAILS (ID: 80)** - Implementado según protocolo VB6
   - Archivo: `src/network/msg_clan.py`
   - Función: `build_clan_details_response()`
   - Formato: Compatible con `Protocol.WriteGuildDetails` del servidor VB6 original

2. **Envío durante Login** - ⚠️ **DESHABILITADO** hasta que el cliente lo implemente
   - Archivo: `src/command_handlers/login_handler.py`
   - El código está comentado con un TODO
   - **NO se envía** hasta que el cliente tenga el handler implementado

3. **Métodos Listos**
   - Métodos implementados en `MessageSender` y `SessionMessageSender`
   - Todo está listo para habilitar cuando el cliente lo necesite

---

## ⚠️ Estado del Cliente

El cliente Godot **NO procesa el packet CLAN_DETAILS**:

1. **Enum existe** - `GuildDetails` está definido en `enums.gd` (línea 273)
2. **Handler NO existe** - No hay archivo `GuildDetails.gd` en `network/commands/`
3. **Handler NO está registrado** - No hay case en `game_screen.gd` para el packet 80
4. **Botón existe** - `btnGuilds` existe en la UI pero no se habilita

**El cliente ignora el packet porque no tiene el código para procesarlo.**

**El servidor NO envía el packet actualmente** - Está deshabilitado hasta que el cliente implemente el handler.

---

## 🔍 Formato del Packet Enviado

El servidor envía el packet con el siguiente formato (según protocolo VB6):

```
Byte 0:        PacketID (80 = CLAN_DETAILS)
Bytes 1-2:     Longitud GuildName (int16)
Bytes 3-N:     GuildName (latin-1)
Bytes N+1-N+2: Longitud Founder (int16)
Bytes N+3-M:   Founder (latin-1)
... (y así sucesivamente para todos los campos)
```

Campos incluidos:
- GuildName (string)
- Founder (string)
- FoundationDate (string, formato "dd/mm/yyyy")
- Leader (string)
- URL (string)
- MemberCount (int32)
- ElectionsOpen (byte: 0 o 1)
- Alignment (string)
- EnemiesCount (int32)
- AlliesCount (int32)
- AntifactionPoints (string)
- Codex (string)
- GuildDesc (string)

---

## 📋 Solución Requerida

**Para habilitar el botón de clanes, se necesita:**

1. **Crear handler en cliente Godot** (no modificable según requerimiento):
   - `clientes/ArgentumOnlineGodot/network/commands/GuildDetails.gd`
   - Parser para leer todos los campos del packet
   
2. **Registrar handler en game_screen.gd**:
   - Agregar case para `Enums.ServerPacketID.GuildDetails`
   - Llamar al handler y habilitar el botón `btnGuilds`

**Como el cliente no se puede modificar, el botón NO se habilitará hasta que el cliente tenga el handler implementado.**

---

## ⚠️ Estado Actual

**El servidor NO envía el packet actualmente**:

1. El código está implementado pero comentado
2. Se puede habilitar fácilmente cuando el cliente esté listo
3. Solo hay que descomentar el código en `login_handler.py`
4. El formato del packet es correcto según el protocolo VB6

**Para habilitar cuando el cliente lo implemente:**
- Seguir la sección [Pasos en el servidor (cuando el cliente esté listo)](#pasos-en-el-servidor-cuando-el-cliente-esté-listo) más abajo
- Agregar el código necesario en `login_handler.py` usando `message_sender.send_clan_details(clan)`
- Agregar `clan_service` al constructor de `LoginCommandHandler` si se necesita

---

## 🔗 Referencias

- **Protocolo VB6**: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/Protocol.bas` (línea 17378)
- **Implementación Servidor**: `src/network/msg_clan.py`
- **Integración Login**: `src/command_handlers/login_handler.py` (comentario explicativo en línea ~442)
- **Estado Cliente**: `clientes/ArgentumOnlineGodot/common/enums/enums.gd` (línea 273 - enum existe, handler no)

---

**Conclusión:** El servidor tiene todo listo pero NO envía el packet actualmente. Cuando el cliente implemente el handler, se puede habilitar fácilmente descomentando el código en `login_handler.py`.


---

## Pasos en el servidor (cuando el cliente esté listo)

Cuando el cliente Godot implemente el handler para el packet 80 (GuildDetails):

### Paso 1: Modificar LoginCommandHandler

En `src/command_handlers/login_handler.py`, agregar `clan_service` al constructor y enviar el packet:

```python
# En el constructor, agregar:
clan_service: "ClanService | None" = None,

# Y guardar:
self.clan_service = clan_service
```

Luego, en `_finalize_login()`, después de enviar `SHOW_PARTY_FORM`, agregar:

```python
# Enviar detalles del clan si el jugador pertenece a uno (habilitar botón de clan)
if self.clan_service:
    clan = await self.clan_service.clan_repo.get_user_clan(user_id)
    if clan:
        logger.info(
            "Enviando CLAN_DETAILS para habilitar botón CLAN (user_id: %d, clan: %s)",
            user_id,
            clan.name,
        )
        await self.message_sender.send_clan_details(clan)
```

### Paso 2: Modificar TaskFactory

En `src/tasks/task_factory.py`, en `_get_login_handler()`, agregar `clan_service`:

```python
clan_service=self.deps.clan_service,
```

### Paso 3: Verificar

1. El packet `CLAN_DETAILS` (80) ya está implementado en `src/network/msg_clan.py`
2. Los métodos `send_clan_details()` ya existen en `MessageSender` y `SessionMessageSender`
3. Solo falta habilitar el envío cuando el cliente esté listo

---

El formato del packet se describe en la primera parte de esta guía.

## Estado, cliente y tests: TESTING_CLAN_SYSTEM.md

> Documento fuente archivado en [`archive/superseded/TESTING_CLAN_SYSTEM.md`](../archive/superseded/TESTING_CLAN_SYSTEM.md).

Esta guía te ayudará a probar el sistema de clanes en el juego, primero con un solo jugador y luego con dos.

## 📋 Requisitos Previos

1. **Redis corriendo:**
   ```bash
   # Verificar que Redis está corriendo
   redis-cli ping
   # Debe responder: PONG
   ```

2. **Servidor iniciado:**
   ```bash
   # Desde el directorio del proyecto
   uv run pyao-server
   ```

3. **Cliente conectado:**
   - Conecta tu cliente (Godot o VB6) al servidor
   - Crea o inicia sesión con tu personaje

## 🎮 Pruebas con UN SOLO JUGADOR

### 1. Verificar Comandos Disponibles

```
/AYUDA
```

**Resultado esperado:** Deberías ver la sección "--- Comandos de Clan ---" con todos los comandos listados.

### 2. Verificar Nivel Mínimo

El nivel mínimo para crear un clan es **13**. Si tu personaje es nivel menor:

```
/CREARCLAN MiClan
```

**Resultado esperado:** 
- Mensaje de error: "Debes ser nivel 13 o superior para crear un clan"

**Solución:** 
- Sube de nivel matando NPCs
- O modifica temporalmente `MIN_LEVEL_TO_CREATE` en `src/models/clan.py` para testing

### 3. Crear un Clan (Nivel 13+)

```
/CREARCLAN MiClan
```

**Resultado esperado:**
- Mensaje: "Clan 'MiClan' creado exitosamente" (en color verde/party)

**Verificar:**
- Deberías ser el líder del clan
- El clan debería tener tu nombre como líder

### 4. Intentar Crear Otro Clan

```
/CREARCLAN OtroClan
```

**Resultado esperado:**
- Mensaje de error: "Ya perteneces a un clan. Abandónalo primero con /SALIRCLAN"

### 5. Intentar Invitar a Ti Mismo

```
/INVITARCLAN TuNombre
```

**Resultado esperado:**
- Mensaje de error: "No puedes invitarte a ti mismo"

### 6. Abandonar el Clan

```
/SALIRCLAN
```

**Resultado esperado:**
- Mensaje: "Abandonaste el clan 'MiClan'" o similar

**Nota:** Como eres el líder, el clan debería eliminarse automáticamente.

### 7. Crear Clan con Descripción

```
/CREARCLAN MiClan2 Esta es mi descripción del clan
```

**Resultado esperado:**
- Clan creado con descripción

### 8. Intentar Aceptar Invitación Sin Tener Una

```
/ACEPTARCLAN
```

**Resultado esperado:**
- Mensaje de error: "No tienes invitaciones pendientes" o similar

### 9. Intentar Rechazar Invitación Sin Tener Una

```
/RECHAZARCLAN
```

**Resultado esperado:**
- Mensaje de error: "No tienes invitaciones pendientes" o similar

### 10. Intentar Expulsar Sin Estar en Clan

```
/EXPULSARCLAN Alguien
```

**Resultado esperado:**
- Mensaje de error: "No perteneces a un clan"

## 👥 Pruebas con DOS JUGADORES

### Preparación

1. **Jugador 1 (Líder):**
   - Nivel 13+ (mínimo para crear clan)
   - Crea un clan: `/CREARCLAN MiClan`

2. **Jugador 2 (Invitado):**
   - Nivel 1+ (mínimo para unirse)
   - Conectado al mismo servidor

### 1. Invitar al Jugador 2

**Jugador 1 ejecuta:**
```
/INVITARCLAN NombreJugador2
```

**Resultado esperado:**
- Jugador 1: "Invitación enviada a NombreJugador2"
- Jugador 2: Debería recibir una notificación (si está implementada) o simplemente poder aceptar

### 2. Aceptar Invitación

**Jugador 2 ejecuta:**
```
/ACEPTARCLAN
```

**Resultado esperado:**
- Jugador 2: "Te uniste al clan 'MiClan'"
- Jugador 2 ahora es miembro del clan con rango MEMBER

### 3. Verificar Miembros

**Jugador 1 ejecuta:**
```
/CLAN
```

**Resultado esperado:**
- Lista de miembros del clan (si el comando está implementado)
- O simplemente verificar que ambos están en el mismo clan

### 4. Intentar Invitar de Nuevo

**Jugador 1 ejecuta:**
```
/INVITARCLAN NombreJugador2
```

**Resultado esperado:**
- Mensaje de error: "El usuario ya pertenece a un clan"

### 5. Expulsar Miembro

**Jugador 1 (Líder) ejecuta:**
```
/EXPULSARCLAN NombreJugador2
```

**Resultado esperado:**
- Jugador 1: "NombreJugador2 fue expulsado del clan"
- Jugador 2: Debería recibir notificación (si está implementada)

### 6. Intentar Expulsar Como Miembro (No Líder)

**Jugador 2 ejecuta (si aún está en el clan):**
```
/EXPULSARCLAN NombreJugador1
```

**Resultado esperado:**
- Mensaje de error: "Solo los oficiales pueden expulsar miembros"

### 7. Re-invitar y Aceptar

**Jugador 1:**
```
/INVITARCLAN NombreJugador2
```

**Jugador 2:**
```
/ACEPTARCLAN
```

### 8. Abandonar Clan (Miembro)

**Jugador 2 ejecuta:**
```
/SALIRCLAN
```

**Resultado esperado:**
- Jugador 2: "Abandonaste el clan 'MiClan'"
- Jugador 2 ya no pertenece al clan

### 9. Intentar Expulsar Como Líder Único

**Jugador 1 ejecuta:**
```
/EXPULSARCLAN NombreJugador1
```

**Resultado esperado:**
- Mensaje de error: "No puedes expulsarte a ti mismo. Usa /SALIRCLAN para disolver el clan"

### 10. Disolver Clan (Líder Abandona)

**Jugador 1 ejecuta:**
```
/SALIRCLAN
```

**Resultado esperado:**
- Mensaje: "Abandonaste el clan 'MiClan'. El clan fue disuelto porque eras el líder"

## 🔍 Verificación en Redis (Opcional)

Si quieres verificar que los datos se guardan correctamente en Redis:

```bash
# Conectar a Redis
redis-cli

# Ver todos los clanes
KEYS clan:*

# Ver un clan específico
GET clan:1

# Ver miembros de un clan
HGETALL clan:1:members

# Ver invitaciones
KEYS invitation:*
```

## 🐛 Problemas Comunes

### "Sistema de clanes no disponible"
- **Causa:** El `ClanService` no se inicializó correctamente
- **Solución:** Verifica los logs del servidor al iniciar. Debería aparecer "✓ Servicio de clanes inicializado"

### "Usuario no encontrado" al invitar
- **Causa:** El nombre del jugador no existe o está offline
- **Solución:** Verifica que el jugador esté conectado y que el nombre sea exacto (case-sensitive)

### "Debes ser nivel X" pero tienes el nivel correcto
- **Causa:** Los stats no se cargaron correctamente
- **Solución:** Usa `/EST` para verificar tu nivel actual

### Comandos no funcionan
- **Causa:** El comando no se parsea correctamente
- **Solución:** 
  - Verifica que no haya espacios extra
  - Usa exactamente: `/CREARCLAN Nombre` (sin espacios antes de `/`)
  - Revisa los logs del servidor para ver errores

## 📝 Checklist de Funcionalidades

### Con un Jugador:
- [ ] Ver comandos en /AYUDA
- [ ] Error al crear clan con nivel bajo (< 13)
- [ ] Crear clan exitosamente (nivel 13+)
- [ ] Error al crear segundo clan
- [ ] Error al invitarse a sí mismo
- [ ] Abandonar clan
- [ ] Crear clan con descripción
- [ ] Error al aceptar sin invitación
- [ ] Error al rechazar sin invitación
- [ ] Error al expulsar sin estar en clan

### Con dos Jugadores:
- [ ] Invitar jugador
- [ ] Aceptar invitación
- [ ] Error al invitar de nuevo
- [ ] Expulsar miembro (como líder)
- [ ] Error al expulsar (como miembro)
- [ ] Abandonar clan (como miembro)
- [ ] Error al expulsarse a sí mismo
- [ ] Disolver clan (líder abandona)

## 🎯 Próximos Pasos

Una vez que todas las pruebas básicas pasen, puedes probar:
- Sistema de rangos (promover/degradar miembros)
- Transferir liderazgo
- Chat interno del clan (cuando esté implementado)
- Alianzas y guerras (cuando estén implementadas)

