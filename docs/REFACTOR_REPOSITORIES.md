# Refactorización: Separación de Responsabilidades con Repositorios

## Objetivo

Separar la responsabilidad de `RedisClient` en:
1. **RedisClient**: Solo maneja la conexión a Redis (bajo nivel)
2. **PlayerRepository**: Operaciones de datos de jugadores
3. **AccountRepository**: Operaciones de cuentas de usuario

## Estado Actual

### ✅ Completado

- [x] Creado `PlayerRepository` con métodos:
  - `get_position()` / `set_position()`
  - `get_stats()` / `set_stats()`
  - `get_hunger_thirst()` / `set_hunger_thirst()`
  - `get_attributes()` / `set_attributes()`

- [x] Creado `AccountRepository` con métodos:
  - `create_account()`
  - `get_account()`
  - `verify_password()`

- [x] Actualizado `server.py`:
  - Crea `PlayerRepository` y `AccountRepository`
  - Pasa repositorios a `TaskLogin` y `TaskCreateAccount`

### ✅ Completado (Continuación)

- [x] Actualizar `TaskLogin` para usar repositorios
  - ✅ `self.player_repo.get_position()` / `set_position()`
  - ✅ `self.player_repo.get_stats()` / `set_stats()`
  - ✅ `self.player_repo.get_hunger_thirst()` / `set_hunger_thirst()`
  - ✅ `self.account_repo.get_account()` / `verify_password()`

- [x] Actualizar `TaskCreateAccount` para usar repositorios
  - ✅ `self.account_repo.create_account()`
  - ✅ `self.player_repo.set_position()` / `set_stats()` / `set_hunger_thirst()`

- [x] Actualizar tests para usar repositorios
  - ✅ test_account_creation.py: Usa mocks de PlayerRepository y AccountRepository

- [x] Actualizar `TaskRequestAttributes` para usar repositorios
  - ✅ `self.player_repo.get_attributes()`

- [x] Limpiar métodos obsoletos de `RedisClient`
  - ✅ Eliminados todos los métodos de gestión de cuentas y jugadores
  - ✅ RedisClient ahora solo maneja: conexión, configuración, contadores de sesiones
  - ✅ Código más limpio y responsabilidades claras

## Beneficios

1. **Separación de responsabilidades**: RedisClient solo maneja conexión
2. **Código más limpio**: Repositorios con métodos específicos del dominio
3. **Más fácil de testear**: Mock de repositorios en lugar de RedisClient completo
4. **Mejor organización**: Lógica de negocio separada de lógica de persistencia
5. **Escalabilidad**: Fácil cambiar Redis por otra BD en el futuro

## Estado Final

✅ **Refactorización 100% COMPLETADA**

### Arquitectura Final
```
┌─────────────────────────────────────────┐
│         RedisClient                     │
│  (Solo conexión y bajo nivel)           │
│  - connect() / disconnect()             │
│  - get_server_host() / get_server_port()│
│  - increment/decrement_connections()    │
│  - set/delete_player_session()          │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼────────┐ ┌──▼────────────────┐
│ PlayerRepo     │ │ AccountRepo       │
│ (Alto nivel)   │ │ (Alto nivel)      │
│ - position     │ │ - create_account  │
│ - stats        │ │ - get_account     │
│ - hunger/thirst│ │ - verify_password │
│ - attributes   │ │                   │
└───────┬────────┘ └──┬────────────────┘
        │             │
     ┌──┴─────────────┴──┐
     │      Tasks        │
     │  - TaskLogin      │
     │  - TaskCreate     │
     │  - TaskRequest    │
     └───────────────────┘
```

### Todas las tareas refactorizadas
- ✅ `TaskLogin` → `PlayerRepository` + `AccountRepository`
- ✅ `TaskCreateAccount` → `PlayerRepository` + `AccountRepository`
- ✅ `TaskRequestAttributes` → `PlayerRepository`

### RedisClient limpio
- ✅ Eliminados ~260 líneas de código obsoleto
- ✅ Solo responsabilidades de bajo nivel
- ✅ Código más mantenible y claro
