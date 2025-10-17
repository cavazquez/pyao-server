# Arquitectura de Servicios

## 📋 Visión General

El servidor PyAO utiliza una arquitectura basada en **servicios reutilizables** que encapsulan lógica de negocio específica. Esta arquitectura separa las responsabilidades y permite la reutilización de código entre diferentes tasks.

## 🏗️ Capas de la Arquitectura

```
┌─────────────────────────────────────────────┐
│           Tasks (Handlers)                  │
│  task_login.py, task_account.py, etc.      │
│  - Orquestan el flujo                       │
│  - Parsean paquetes                         │
│  - Delegan a servicios                      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│           Servicios (Lógica)                │
│  PlayerService, AuthenticationService, etc. │
│  - Encapsulan lógica de negocio            │
│  - Reutilizables entre tasks               │
│  - Testeables independientemente           │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│        Repositorios (Datos)                 │
│  PlayerRepository, AccountRepository, etc.  │
│  - Acceso a Redis                           │
│  - CRUD de entidades                        │
└─────────────────────────────────────────────┘
```

## 🔧 Servicios Implementados

### 1. PlayerService

**Responsabilidad**: Gestión completa de datos de jugador y envío al cliente.

**Ubicación**: `src/player_service.py` (267 líneas)

**Métodos Públicos**:
- `send_position(user_id)` - Obtiene/crea posición, envía CHANGE_MAP
- `send_attributes(user_id)` - Obtiene/crea atributos (no los envía, on-demand)
- `send_stats(user_id)` - Obtiene/crea stats, envía UPDATE_USER_STATS
- `send_hunger_thirst(user_id)` - Obtiene/crea hambre/sed, envía UPDATE_HUNGER_AND_THIRST
- `spawn_character(user_id, username, position)` - Envía CHARACTER_CREATE con delay de 500ms
- `send_inventory(user_id)` - Obtiene inventario, envía slots con items

**Patrón**: Cada método sigue el patrón:
1. Obtener datos de Redis
2. Si no existen, crear defaults
3. Enviar al cliente (si corresponde)
4. Retornar los datos

**Usado en**:
- `TaskLogin` - Inicialización completa del jugador
- `TaskCreateAccount` - Indirectamente vía TaskLogin

**Ejemplo de uso**:
```python
player_service = PlayerService(player_repo, message_sender)

# Obtener/crear y enviar posición
position = await player_service.send_position(user_id)

# Obtener/crear y enviar stats
stats = await player_service.send_stats(user_id)

# Spawn con delay incluido
await player_service.spawn_character(user_id, username, position)
```

**Tests**: 7 tests en `tests/test_player_service.py`

---

### 2. AuthenticationService

**Responsabilidad**: Autenticación de usuarios con manejo completo de errores.

**Ubicación**: `src/authentication_service.py` (95 líneas)

**Métodos Públicos**:
- `authenticate(username, password)` - Autentica y retorna `(user_id, user_class) | None`

**Flujo interno**:
1. Verificar que el repositorio esté disponible
2. Obtener datos de la cuenta
3. Hashear contraseña y verificar
4. Enviar mensaje de error al cliente si falla
5. Retornar datos si es exitoso

**Usado en**:
- `TaskLogin` - Autenticación principal

**Ejemplo de uso**:
```python
auth_service = AuthenticationService(account_repo, message_sender)
result = await auth_service.authenticate(username, password)

if result is None:
    # Falló (el servicio ya envió el error al cliente)
    return

user_id, user_class = result
# Continuar con el login...
```

**Tests**: 4 tests en `tests/test_authentication_service.py`

---

### 3. SessionManager

**Responsabilidad**: Gestión centralizada de sesiones de usuario.

**Ubicación**: `src/session_manager.py` (95 líneas)

**Métodos Estáticos**:
- `get_user_id(session_data)` - Obtiene user_id validado
- `get_username(session_data)` - Obtiene username validado
- `set_user_session(session_data, user_id, username)` - Guarda datos en sesión
- `clear_session(session_data)` - Limpia sesión
- `is_logged_in(session_data)` - Verifica si hay usuario logueado

**Patrón**: Métodos estáticos (no requiere instancia)

**Usado en**:
- `TaskLogin` - Guardar sesión después de autenticación
- `TaskQuit` - Obtener user_id para desconexión
- `TaskTalk` - Obtener user_id para chat
- `TaskWalk` - Obtener user_id para movimiento
- `TaskOnline` - Obtener user_id para lista online
- `TaskRequestStats` - Obtener user_id para stats
- `TaskUseItem` - Obtener user_id para usar items
- `TaskInventoryClick` - Obtener user_id para inventario

**Ejemplo de uso**:
```python
# Obtener user_id de la sesión
user_id = SessionManager.get_user_id(session_data)
if user_id is None:
    logger.warning("Usuario no logueado")
    return

# Guardar sesión después de login
SessionManager.set_user_session(session_data, user_id, username)

# Verificar si está logueado
if not SessionManager.is_logged_in(session_data):
    return
```

**Tests**: 13 tests en `tests/test_session_manager.py`

---

### 4. MultiplayerBroadcastService

**Responsabilidad**: Broadcast multijugador (notificar spawn de jugadores).

**Ubicación**: `src/multiplayer_broadcast_service.py` (167 líneas)

**Métodos Públicos**:
- `notify_player_spawn(user_id, username, position, message_sender)` - Orquesta todo el broadcast

**Métodos Privados**:
- `_send_existing_players_to_new_player()` - Envía CHARACTER_CREATE de jugadores existentes
- `_broadcast_new_player_to_others()` - Notifica nuevo spawn a otros jugadores

**Flujo interno**:
1. Enviar CHARACTER_CREATE de jugadores existentes al nuevo jugador
2. Agregar nuevo jugador al MapManager
3. Enviar CHARACTER_CREATE del nuevo jugador a todos los demás

**Usado en**:
- `TaskLogin` - Broadcast al hacer login

**Ejemplo de uso**:
```python
broadcast_service = MultiplayerBroadcastService(
    map_manager,
    player_repo,
    account_repo,
)

await broadcast_service.notify_player_spawn(
    user_id,
    username,
    position,
    message_sender,
)
```

**Tests**: Cubierto por tests de integración

---

## 🔄 Flujo de Login (Ejemplo Completo)

```python
async def execute_with_credentials(self, username: str, password: str) -> None:
    # 1. AUTENTICACIÓN
    auth_service = AuthenticationService(self.account_repo, self.message_sender)
    auth_result = await auth_service.authenticate(username, password)
    if auth_result is None:
        return  # Falló
    
    user_id, user_class = auth_result
    
    # 2. SESIÓN
    SessionManager.set_user_session(self.session_data, user_id, username)
    
    # 3. INICIALIZACIÓN DEL JUGADOR
    player_service = PlayerService(self.player_repo, self.message_sender)
    
    await self.message_sender.send_logged(user_class)
    await self.message_sender.send_user_char_index_in_server(user_id)
    
    position = await player_service.send_position(user_id)
    await player_service.send_attributes(user_id)
    await player_service.send_stats(user_id)
    await player_service.send_hunger_thirst(user_id)
    
    # 4. SPAWN (con delay de 500ms incluido)
    await player_service.spawn_character(user_id, username, position)
    
    # 5. BROADCAST MULTIJUGADOR
    broadcast_service = MultiplayerBroadcastService(...)
    await broadcast_service.notify_player_spawn(user_id, username, position, ...)
    
    # 6. POST-SPAWN
    await player_service.send_inventory(user_id)
    
    # 7. MOTD (reutilizando TaskMotd)
    motd_task = TaskMotd(self.data, self.message_sender, self.server_repo)
    await motd_task.execute()
```

**Resultado**: TaskLogin pasó de 413 líneas a 205 líneas (-50%)

---

## 📐 Principios de Diseño

### 1. Single Responsibility Principle (SRP)
Cada servicio tiene una única responsabilidad:
- `PlayerService` → Gestión de datos de jugador
- `AuthenticationService` → Autenticación
- `SessionManager` → Gestión de sesiones
- `MultiplayerBroadcastService` → Broadcast multijugador

### 2. Don't Repeat Yourself (DRY)
El código se escribe una vez y se reutiliza:
- `SessionManager.get_user_id()` usado en 7+ tasks
- `PlayerService` usado en login y creación de cuenta
- `TaskMotd` reutilizado en lugar de duplicar lógica

### 3. Dependency Injection
Los servicios reciben sus dependencias en el constructor:
```python
player_service = PlayerService(player_repo, message_sender)
```

### 4. Testabilidad
Cada servicio es testeable independientemente:
- 24 tests unitarios para servicios
- Mocks de dependencias
- Tests aislados

---

## 🎯 Beneficios de Esta Arquitectura

### ✅ Mantenibilidad
- Cambios en un solo lugar
- Código más fácil de entender
- Responsabilidades claras

### ✅ Reutilización
- Servicios usados en múltiples tasks
- Elimina código duplicado
- Consistencia en el comportamiento

### ✅ Testabilidad
- Tests unitarios independientes
- Mocks fáciles de crear
- Mayor cobertura de tests

### ✅ Escalabilidad
- Fácil agregar nuevos servicios
- Patrón claro a seguir
- Arquitectura extensible

---

## 🚀 Cómo Agregar un Nuevo Servicio

### Paso 1: Crear el servicio
```python
# src/my_service.py
class MyService:
    def __init__(self, repo, message_sender):
        self.repo = repo
        self.message_sender = message_sender
    
    async def do_something(self, user_id):
        # 1. Obtener datos
        data = await self.repo.get_data(user_id)
        
        # 2. Crear defaults si no existen
        if data is None:
            data = {...defaults...}
            await self.repo.set_data(user_id, data)
        
        # 3. Enviar al cliente (si corresponde)
        await self.message_sender.send_something(data)
        
        # 4. Retornar datos
        return data
```

### Paso 2: Crear tests
```python
# tests/test_my_service.py
@pytest.mark.asyncio
async def test_do_something_creates_default():
    # Arrange
    repo = MagicMock()
    repo.get_data = AsyncMock(return_value=None)
    
    # Act
    service = MyService(repo, message_sender)
    result = await service.do_something(123)
    
    # Assert
    repo.set_data.assert_called_once()
    assert result is not None
```

### Paso 3: Usar en tasks
```python
# src/task_something.py
service = MyService(self.repo, self.message_sender)
await service.do_something(user_id)
```

---

## 📊 Métricas de Impacto

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| **TaskLogin** | 413 líneas | 205 líneas | **-50%** |
| **Código duplicado** | Alto | Bajo | **Eliminado** |
| **Tests** | 252 | 374 | **+122** |
| **Servicios** | 0 | 7 | **+7** |
| **Reutilización** | Baja | Alta | **10+ tasks** |
| **Efectos de Tick** | 2 | 4 | **+2** |

---

### 5. NPCService ✅ IMPLEMENTADO

**Responsabilidad**: Gestión de NPCs (spawn, movimiento, eliminación).

**Ubicación**: `src/npc_service.py`

**Métodos Públicos**:
- `initialize_world_npcs(spawns_path)` - Carga NPCs desde `data/map_npcs.toml`
- `spawn_npc(npc_id, map_id, x, y, heading)` - Crea un NPC en el mapa
- `move_npc(npc, new_x, new_y, new_heading)` - Mueve un NPC y hace broadcast
- `remove_npc(npc)` - Elimina un NPC del mundo
- `send_npcs_to_player(player_id, map_id)` - Envía NPCs del mapa al jugador

**Usado en**:
- `Server.initialize()` - Inicialización de NPCs del mundo
- `TaskLogin` - Enviar NPCs al jugador
- `NPCMovementEffect` - Movimiento automático de NPCs

**Tests**: 11 tests en `tests/test_npc_movement.py`

---

### 6. SpellService ✅ IMPLEMENTADO

**Responsabilidad**: Lógica de hechizos (casteo, validación, efectos).

**Ubicación**: `src/spell_service.py`

**Métodos Públicos**:
- `cast_spell(user_id, spell_id, target_x, target_y)` - Lanza un hechizo
- `validate_spell_range(caster_pos, target_pos, max_range)` - Valida rango
- `apply_spell_effect(spell, target)` - Aplica efectos del hechizo

**Usado en**:
- `TaskCastSpell` - Lanzar hechizos desde el libro

**Tests**: 7 tests de targeting en `tests/test_spell_targeting.py`

---

### 7. EquipmentService ✅ IMPLEMENTADO

**Responsabilidad**: Gestión de equipamiento (equipar, desequipar).

**Ubicación**: `src/equipment_service.py`

**Métodos Públicos**:
- `equip_item(user_id, slot, item_id)` - Equipa un item
- `unequip_item(user_id, slot)` - Desequipa un item
- `get_equipped_items(user_id)` - Obtiene items equipados

**Usado en**:
- `TaskEquipItem` - Equipar items desde inventario

**Tests**: 15 tests en `tests/test_equipment_*.py`

---

## 🔮 Próximos Pasos

### Servicios Potenciales
- `MovementService` - Encapsular lógica de movimiento (TaskWalk, TaskChangeHeading)
- `ServerService` - Encapsular lógica de servidor (MOTD, uptime, info)
- `CombatService` - Encapsular lógica de combate NPC vs Jugador
- `TradeService` - Encapsular lógica de comercio con NPCs
- `QuestService` - Sistema de misiones
- `LootService` - Sistema de drops y experiencia

### Mejoras
- Tests de integración end-to-end
- Documentación de cada servicio
- Métricas y monitoreo
- Optimizaciones de performance

---

## 📚 Referencias

- [LOGIN_FLOW.md](LOGIN_FLOW.md) - Flujo detallado de login
- [GAME_TICK_SYSTEM.md](GAME_TICK_SYSTEM.md) - Sistema de efectos periódicos
- [README.md](../README.md) - Documentación principal del proyecto
