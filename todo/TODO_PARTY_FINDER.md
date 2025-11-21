# Party Finder - Sistema de Búsqueda de Parties

**Versión objetivo:** v0.8.5-alpha  
**Prioridad:** 🟢 Baja (funcionalidad opcional)  
**Esfuerzo estimado:** 1 semana  
**Estado:** 📋 Planificado  
**Dependencias:** Sistema de Parties (v0.8.0) ✅ Completado

---

## 📋 Descripción

Sistema que permite a los jugadores buscar parties disponibles o anunciar que están buscando grupo, facilitando la formación de grupos para jugadores que no se conocen o no tienen contactos.

## 🎯 Objetivo

Facilitar la formación de parties en servidores con muchos jugadores, permitiendo:
- Buscar parties disponibles que buscan miembros
- Anunciar que estás disponible para unirte a una party
- Filtrar parties por criterios específicos

## ✨ Funcionalidades

### 1. Anunciar Party Disponible
- Líder puede abrir su party al Party Finder
- Configurar criterios de búsqueda (nivel mínimo/máximo, actividad)
- Cerrar anuncio cuando la party esté llena o ya no busque miembros

### 2. Buscar Parties Disponibles
- Ver lista de parties que buscan miembros
- Filtrar por:
  - Nivel mínimo/máximo requerido
  - Actividad (PvE, PvP, Quests, Farming)
  - Zona/mapa actual
  - Clase requerida (futuro, cuando se implementen clases)
- Unirse directamente a una party desde el finder

### 3. Anunciar Disponibilidad
- Jugador sin party puede anunciar que busca grupo
- Otros jugadores pueden ver quién busca party
- Líderes pueden invitar directamente desde el finder

## 📦 Comandos Propuestos

### Para Líderes de Party
```
/PARTYFINDER ABRIR [nivel_min] [nivel_max] [actividad]
  - Abre la party al Party Finder
  - Ejemplo: /PARTYFINDER ABRIR 10 20 PvE

/PARTYFINDER CERRAR
  - Cierra el anuncio de la party

/PARTYFINDER ESTADO
  - Muestra el estado actual del anuncio
```

### Para Jugadores Buscando Party
```
/PARTYFINDER BUSCAR [filtros]
  - Lista parties disponibles
  - Ejemplo: /PARTYFINDER BUSCAR nivel:10-20 actividad:PvE

/PARTYFINDER UNIRSE <líder>
  - Solicita unirse a una party del finder
  - Ejemplo: /PARTYFINDER UNIRSE JugadorA

/PARTYFINDER DISPONIBLE [nivel] [actividad]
  - Anuncia que buscas party
  - Ejemplo: /PARTYFINDER DISPONIBLE 15 PvE

/PARTYFINDER NO_DISPONIBLE
  - Cierra tu anuncio de disponibilidad
```

## 🏗️ Arquitectura

### Modelos de Datos

```python
@dataclass
class PartyFinderListing:
    """Anuncio de party en el Party Finder."""
    party_id: int
    leader_id: int
    leader_username: str
    min_level: int
    max_level: int
    activity: str  # "PvE", "PvP", "Quest", "Farming", "Any"
    current_members: int
    max_members: int
    created_at: float
    expires_at: float  # Auto-expira si no se actualiza

@dataclass
class PartyFinderSeeker:
    """Jugador buscando party."""
    user_id: int
    username: str
    level: int
    activity: str
    created_at: float
    expires_at: float
```

### Repositorio

**Archivo:** `src/repositories/party_finder_repository.py`

**Keys Redis:**
- `party_finder:listings` - Set de party IDs disponibles
- `party_finder:listing:{party_id}` - Hash con detalles del anuncio
- `party_finder:seekers` - Set de user IDs buscando party
- `party_finder:seeker:{user_id}` - Hash con detalles del buscador

**Métodos:**
- `create_listing(party_id, listing_data)`
- `remove_listing(party_id)`
- `get_all_listings(filters)`
- `create_seeker(user_id, seeker_data)`
- `remove_seeker(user_id)`
- `get_all_seekers(filters)`

### Servicio

**Archivo:** `src/services/party_finder_service.py`

**Métodos:**
- `open_party_listing(leader_id, filters)`
- `close_party_listing(party_id)`
- `search_listings(filters)`
- `join_party_from_finder(user_id, party_id)`
- `announce_seeking(user_id, filters)`
- `stop_seeking(user_id)`
- `get_seekers(filters)`

### Tasks

**Archivos:**
- `src/tasks/task_party_finder_open.py` - `/PARTYFINDER ABRIR`
- `src/tasks/task_party_finder_close.py` - `/PARTYFINDER CERRAR`
- `src/tasks/task_party_finder_search.py` - `/PARTYFINDER BUSCAR`
- `src/tasks/task_party_finder_join.py` - `/PARTYFINDER UNIRSE`
- `src/tasks/task_party_finder_seek.py` - `/PARTYFINDER DISPONIBLE`
- `src/tasks/task_party_finder_stop_seek.py` - `/PARTYFINDER NO_DISPONIBLE`

### Packets

**Nuevos Packet IDs necesarios:**
- `PARTY_FINDER_OPEN = 120` (nuevo)
- `PARTY_FINDER_CLOSE = 121` (nuevo)
- `PARTY_FINDER_SEARCH = 122` (nuevo)
- `PARTY_FINDER_JOIN = 123` (nuevo)
- `PARTY_FINDER_LISTINGS = 124` (nuevo) - Respuesta con lista de parties
- `PARTY_FINDER_SEEKERS = 125` (nuevo) - Respuesta con lista de buscadores

## 🔄 Flujo de Uso

### Escenario 1: Líder abre party al finder
1. Líder crea party: `/CREARPARTY`
2. Líder abre al finder: `/PARTYFINDER ABRIR 10 20 PvE`
3. Party aparece en búsquedas
4. Otros jugadores pueden verla: `/PARTYFINDER BUSCAR`
5. Jugador se une: `/PARTYFINDER UNIRSE Líder`
6. Sistema envía invitación automática
7. Cuando party está llena, anuncio se cierra automáticamente

### Escenario 2: Jugador busca party
1. Jugador anuncia disponibilidad: `/PARTYFINDER DISPONIBLE 15 PvE`
2. Aparece en lista de buscadores
3. Líder ve buscadores: `/PARTYFINDER BUSCAR SEEKERS`
4. Líder invita: `/PARTY Jugador`
5. Jugador acepta: `/ACCEPTPARTY`
6. Anuncio se cierra automáticamente

## ⚙️ Configuración

**Archivo:** `config/server.toml`

```toml
[game.party_finder]
enabled = true
listing_expiry_seconds = 300  # 5 minutos sin actualizar = expira
seeker_expiry_seconds = 600   # 10 minutos sin actualizar = expira
max_listings = 100            # Máximo de parties en finder
max_seekers = 200             # Máximo de buscadores
auto_close_when_full = true   # Cerrar anuncio cuando party llena
```

## 🧪 Tests

**Archivo:** `tests/test_party_finder_service.py`

**Tests a crear:**
- Test abrir listing de party
- Test cerrar listing
- Test buscar listings con filtros
- Test unirse a party desde finder
- Test anunciar disponibilidad
- Test expiración automática de listings
- Test expiración automática de seekers
- Test filtros por nivel
- Test filtros por actividad
- Test límite de listings/seekers

## 📊 Métricas de Éxito

- Tiempo promedio para formar party: < 2 minutos
- Tasa de éxito de uniones: > 70%
- Uso del finder: > 30% de parties formadas vía finder

## 🚀 Próximos Pasos

1. Diseñar UI en cliente Godot (opcional, puede ser solo texto)
2. Implementar modelos de datos
3. Crear repositorio en Redis
4. Implementar servicio
5. Crear tasks y handlers
6. Agregar tests
7. Documentar en `docs/PARTY_FINDER.md`

## 📝 Notas

- **No crítico**: El sistema actual de invitaciones funciona bien
- **Opcional**: Puede implementarse cuando haya necesidad real
- **Escalable**: Útil para servidores con > 50 jugadores concurrentes
- **Compatibilidad**: No rompe funcionalidad existente

---

**Última actualización:** 2025-01-30  
**Autor:** Sistema de IA  
**Versión del documento:** 1.0

