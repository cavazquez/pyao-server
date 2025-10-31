# Sistema de Parties - Documentación

## Overview

El sistema de parties permite a los jugadores agruparse para compartir experiencia, chat y loot. Está basado en el sistema del servidor VB6 original de Argentum Online, pero implementado con arquitectura moderna en Python con Redis.

## Características

### ✅ Implementadas
- **Creación de parties**: Líder puede crear party con requisitos mínimos
- **Invitaciones**: Sistema de invitaciones con expiración (30 segundos)
- **Gestión de miembros**: Unirse, abandonar, expulsar miembros
- **Transferencia de liderazgo**: El líder puede ceder el liderazgo a otro miembro
- **Chat de party**: Mensajes privados entre miembros de la party
- **Validaciones**: Nivel mínimo, diferencia de niveles, estado (vivo/muerto)
- **Persistencia**: Todos los datos guardados en Redis

### 🚧 Pendientes
- Experiencia compartida (distribución basada en niveles y distancia)
- Loot compartido (sistema de reparto automático)
- Integración con combate (exp distribuida automáticamente)

## Arquitectura

### Modelos de Datos

#### Party
```python
@dataclass
class Party:
    party_id: int
    leader_id: int
    leader_username: str
    created_at: float
    total_exp_earned: int
    sum_elevated_levels: float  # Para cálculo de experiencia
    member_count: int
    members: Dict[int, PartyMember]
```

#### PartyMember
```python
@dataclass
class PartyMember:
    user_id: int
    username: str
    level: int
    accumulated_exp: float
    is_online: bool
    last_seen: float
```

#### PartyInvitation
```python
@dataclass
class PartyInvitation:
    party_id: int
    inviter_id: int
    inviter_username: str
    target_id: int
    target_username: str
    created_at: float  # Timestamp para control de expiración
```

### Repositorio (Redis)

#### Keys utilizadas:
- `party:next_id` - ID autoincremental para nuevas parties
- `party:{party_id}` - Metadata de la party (hash)
- `party:{party_id}:members` - Miembros de la party (hash)
- `party:index` - Set con todos los IDs de parties activas
- `user:{user_id}:party` - Referencia a la party del usuario
- `party_invitations:{target_id}` - Invitaciones pendientes por usuario (hash)

#### Operaciones principales:
- **CRUD completo** de parties y miembros
- **Invitaciones** con expiración automática
- **Consultas eficientes** por usuario o party
- **Transacciones** para mantener consistencia

### Servicio de Negocio (PartyService)

Centraliza toda la lógica de negocio del sistema:

#### Validaciones:
- **Nivel mínimo**: 15 para crear party
- **Diferencia de niveles**: Máximo 7 niveles entre miembros
- **Estado del personaje**: No puede estar muerto
- **Habilidades**: Carisma + Liderazgo >= 100 para crear party

#### Operaciones:
- `create_party()` - Crear nueva party
- `invite_to_party()` - Enviar invitación
- `accept_invitation()` - Aceptar invitación
- `leave_party()` - Abandonar party (disuelve si es líder)
- `kick_member()` - Expulsar miembro (solo líder)
- `transfer_leadership()` - Transferir liderazgo
- `send_party_message()` - Enviar mensaje a party
- `distribute_experience()` - Distribuir experiencia

## Comandos del Cliente

| Comando | Packet ID | Descripción | Requisitos |
|---------|-----------|-------------|------------|
| `/CREARPARTY` | 92 | Crear nueva party | Nivel 15+, vivo, habilidades |
| `/PARTY <nombre>` | 93 | Invitar a usuario | En party, ser líder |
| `/ACCEPTPARTY <nombre>` | 118 | Aceptar invitación | Tener invitación pendiente |
| `/SALIRPARTY` | 91 | Abandonar party | Ser miembro de party |
| `/PMSG <mensaje>` | 96 | Chat de party | Ser miembro de party |
| `/KICK <nombre>` | 116 | Expulsar miembro | Ser líder |
| `/PARTYLIDER <nombre>` | 117 | Transferir liderazgo | Ser líder |

## Flujo de Operaciones

### 1. Creación de Party
```
1. Jugador usa /CREARPARTY
2. Server valida requisitos (nivel, estado, habilidades)
3. Si válido: crea party en Redis
4. Jugador se convierte en líder automático
5. Confirmación enviada al cliente
```

### 2. Invitación a Party
```
1. Líder usa /PARTY <nombre>
2. Server valida que sea líder y party tenga espacio
3. Crea invitación en Redis (expira en 30s)
4. Notificación enviada al invitado
5. Confirmación enviada al líder
```

### 3. Aceptación de Invitación
```
1. Invitado usa /ACCEPTPARTY <líder>
2. Server busca invitación válida
3. Valida diferencia de niveles y espacio
4. Agrega miembro a la party
5. Limpia invitación
6. Notifica a todos los miembros
```

### 4. Abandono de Party
```
1. Miembro usa /SALIRPARTY
2. Si es líder y hay más miembros: party se disuelve
3. Si es miembro normal: solo abandona
4. Limpia referencias en Redis
5. Notifica a miembros restantes
```

## Constantes del Sistema

```python
# Límites y restricciones
MAX_PARTY_MEMBERS = 5
MIN_LEVEL_TO_CREATE = 15
MAX_LEVEL_DIFFERENCE = 7
MAX_EXP_DISTANCE = 18  # Tiles para compartir experiencia
INVITATION_TIMEOUT = 30  # Segundos

# Experiencia
PARTY_EXPERIENCE_PER_HIT = False  # Distribución por golpe vs total
EXPONENTE_NIVEL_PARTY = 1.2  # Exponente para cálculo de experiencia
```

## Integración con Redis

### Ejemplo de estructura en Redis:

```redis
# Party metadata
HSET party:1 party_id 1 leader_id 1 leader_username "Leader" created_at 1234567890 total_exp_earned 0 sum_elevated_levels 400 member_count 2

# Party members
HSET party:1:members 1 '{"user_id":1,"username":"Leader","level":20,"accumulated_exp":0,"is_online":true,"last_seen":1234567890}'
HSET party:1:members 2 '{"user_id":2,"username":"Member","level":18,"accumulated_exp":0,"is_online":true,"last_seen":1234567890}'

# User references
SET user:1:party 1
SET user:2:party 1

# Party index
SADD party:index 1

# Invitations
HSET party_invitations:3 1 '{"party_id":1,"inviter_id":1,"inviter_username":"Leader","target_id":3,"target_username":"Invited","created_at":1234567890}'
```

## Tests

### Cobertura de Tests
- **Modelos**: 100% cobertura de Party, PartyMember, PartyInvitation
- **Repositorio**: Operaciones CRUD de Redis, manejo de errores
- **Servicio**: Lógica de negocio, validaciones, casos límite
- **Tasks**: Handlers de packets, parsing de datos, manejo de excepciones

### Ejecutar Tests
```bash
# Tests específicos del sistema de parties
uv run pytest tests/test_party_*.py -v

# Tests con cobertura
uv run pytest tests/test_party_*.py --cov=src.models.party --cov=src.repositories.party_repository --cov=src.services.party_service
```

## Performance y Optimización

### Estrategias implementadas:
- **Pipeline de Redis**: Operaciones atómicas múltiples
- **Lazy loading**: Parties cargadas solo cuando se necesitan
- **Índices eficientes**: Sets para búsquedas rápidas
- **Expiración automática**: Invitaciones viejas limpiadas automáticamente

### Métricas esperadas:
- **Creación de party**: < 50ms
- **Invitación**: < 30ms
- **Operaciones CRUD**: < 20ms
- **Chat de party**: < 10ms por mensaje

## Configuración

### Variables de entorno (opcional):
```bash
# Redis
PARTY_REDIS_TTL=3600  # TTL para datos de party (1 hora)

# Balance de juego
PARTY_MIN_LEVEL=15
PARTY_MAX_MEMBERS=5
PARTY_LEVEL_DIFF=7
PARTY_EXP_DISTANCE=18
```

## Troubleshooting

### Problemas comunes:

#### 1. "No puedes crear party - nivel insuficiente"
- **Causa**: Jugador nivel < 15
- **Solución**: Subir nivel o ajustar `MIN_LEVEL_TO_CREATE`

#### 2. "Diferencia de niveles demasiado alta"
- **Causa**: Nivel del invitado > nivel líder + 7
- **Solución**: Invitar a jugadores de nivel similar

#### 3. "No eres miembro de ninguna party"
- **Causa**: Referencia `user:{id}:party` corrupta o faltante
- **Solución**: Limpiar con `DEL user:{id}:party` en Redis

#### 4. Invitaciones no llegan
- **Causa**: Invitación expiró o Redis con problemas
- **Solución**: Verificar `party_invitations:{target_id}` en Redis

### Debug en Redis:
```bash
# Ver todas las parties activas
SMEMBERS party:index

# Ver miembros de una party
HGETALL party:1:members

# Ver invitaciones pendientes
HGETALL party_invitations:3

# Limpiar datos corruptos
DEL user:123:party
DEL party:999
```

## Roadmap Futuro

### v0.8.0-alpha (Próximo)
- [ ] Experiencia compartida automática
- [ ] Sistema de loot compartido
- [ ] Integración con sistema de combate

### v0.9.0-alpha
- [ ] Party finder (búsqueda de parties)
- [ ] Sistema de roles en party (tank, healer, dps)
- [ ] Estadísticas de party

### v1.0.0-alpha
- [ ] Guilds integration
- [ ] Eventos de party
- [ ] Sistema de reputación

## Contribución

### Para agregar nueva funcionalidad:
1. **Modelo**: Agregar/actualizar dataclasses en `src/models/party.py`
2. **Repositorio**: Implementar operaciones en `src/repositories/party_repository.py`
3. **Servicio**: Agregar lógica de negocio en `src/services/party_service.py`
4. **Handler**: Crear task en `src/tasks/task_*.py`
5. **Tests**: Cubrir todos los casos en `tests/test_party_*.py`
6. **Docs**: Actualizar esta documentación

### Estándares de código:
- **Type hints**: Obligatorios en todos los métodos
- **Async/await**: Todas las operaciones de I/O
- **Error handling**: Try/catch con logging apropiado
- **Tests**: Mínimo 90% cobertura
- **Docs**: Docstrings en todos los métodos públicos

---

**Última actualización**: 2025-01-30  
**Versión**: 0.7.0-alpha  
**Estado**: ✅ Core implementado, 🚧 experiencia y loot pendientes
