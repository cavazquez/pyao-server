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

### ❌ Pendiente

- [ ] Actualizar `TaskLogin` para usar repositorios en lugar de `redis_client`
  - Cambiar `self.redis_client.get_player_position()` → `self.player_repo.get_position()`
  - Cambiar `self.redis_client.set_player_position()` → `self.player_repo.set_position()`
  - Cambiar `self.redis_client.get_player_user_stats()` → `self.player_repo.get_stats()`
  - Cambiar `self.redis_client.set_player_user_stats()` → `self.player_repo.set_stats()`
  - Cambiar `self.redis_client.get_player_hunger_thirst()` → `self.player_repo.get_hunger_thirst()`
  - Cambiar `self.redis_client.set_player_hunger_thirst()` → `self.player_repo.set_hunger_thirst()`
  - Cambiar `self.redis_client.get_account()` → `self.account_repo.get_account()`

- [ ] Actualizar `TaskCreateAccount` para usar repositorios
  - Cambiar `self.redis_client.create_account()` → `self.account_repo.create_account()`
  - Cambiar `self.redis_client.set_player_position()` → `self.player_repo.set_position()`
  - Cambiar `self.redis_client.set_player_user_stats()` → `self.player_repo.set_stats()`
  - Cambiar `self.redis_client.set_player_hunger_thirst()` → `self.player_repo.set_hunger_thirst()`

- [ ] Actualizar `TaskRequestAttributes` para usar repositorios
  - Cambiar `self.redis_client.get_player_stats()` → `self.player_repo.get_attributes()`

- [ ] Actualizar tests para usar repositorios

- [ ] Limpiar métodos obsoletos de `RedisClient`:
  - Eliminar `create_account()`
  - Eliminar `get_account()`
  - Eliminar `get_player_position()` / `set_player_position()`
  - Eliminar `get_player_user_stats()` / `set_player_user_stats()`
  - Eliminar `get_player_hunger_thirst()` / `set_player_hunger_thirst()`
  - Eliminar `get_player_stats()` / `set_player_stats()`
  - Mantener solo: conexión, configuración, contadores de sesiones

## Beneficios

1. **Separación de responsabilidades**: RedisClient solo maneja conexión
2. **Código más limpio**: Repositorios con métodos específicos del dominio
3. **Más fácil de testear**: Mock de repositorios en lugar de RedisClient completo
4. **Mejor organización**: Lógica de negocio separada de lógica de persistencia
5. **Escalabilidad**: Fácil cambiar Redis por otra BD en el futuro

## Próximos Pasos

1. Actualizar `TaskLogin` y `TaskCreateAccount` para usar repositorios
2. Actualizar tests
3. Eliminar métodos obsoletos de `RedisClient`
4. Commit y push
