> **Última consolidación:** 2026-05

# Arquitectura de Integración con Redis

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        PyAO Server                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                    │
│  │ run_server.py│────────>│ArgentumServer│                    │
│  └──────────────┘         └───────┬──────┘                    │
│                                    │                            │
│                                    │ usa                        │
│                                    ▼                            │
│                           ┌────────────────┐                   │
│                           │  RedisClient   │                   │
│                           │  (Singleton)   │                   │
│                           └────────┬───────┘                   │
│                                    │                            │
│                                    │ conecta                    │
└────────────────────────────────────┼────────────────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  Redis Server   │
                            │  (localhost:6379)│
                            └─────────────────┘
```

## Flujo de Inicio del Servidor

```
1. run_server.py crea ArgentumServer
2. ArgentumServer.start() se ejecuta
3. Si use_redis=True:
   a. Crea RedisClient (singleton)
   b. Conecta a Redis
   c. Carga configuración (host, port) desde Redis
   d. Resetea contador de conexiones
4. Inicia servidor TCP con configuración
5. Espera conexiones de clientes
```

## Flujo de Conexión de Cliente

```
Cliente conecta
    │
    ▼
ArgentumServer.handle_client()
    │
    ├─> Crea ClientConnection
    ├─> Crea MessageSender
    │
    ├─> Redis: increment_connections()
    ├─> Redis: get_connections_count()
    │
    ├─> Loop: Leer datos del cliente
    │   ├─> Crear Task apropiada
    │   └─> Ejecutar Task
    │
    └─> Al desconectar:
        ├─> Redis: decrement_connections()
        └─> Redis: get_connections_count()
```

## Estructura de Datos en Redis

### Configuración del Servidor

```redis
SET config:server:host "0.0.0.0"
SET config:server:port "7666"
SET config:server:max_connections "1000"
```

### Estado del Servidor

```redis
SET server:connections:count "5"
SET server:uptime "3600"
```

### Sesiones de Jugadores

```redis
# Sesión activa (hash)
HSET session:123:active username "player1" level "10" class "warrior"

# Último acceso (timestamp)
SET session:123:last_seen "1697000000"
```

### Estado del Jugador

```redis
# Posición (hash)
HSET player:123:position x "100" y "200" map "1"

# Estadísticas (hash)
HSET player:123:stats strength "18" agility "15" intelligence "12"

# Inventario (hash o lista)
HSET player:123:inventory slot1 "sword" slot2 "shield" gold "1000"
```

## Métodos del RedisClient

### Configuración

- `get_server_host()` - Obtiene el host del servidor
- `get_server_port()` - Obtiene el puerto del servidor
- `set_server_host(host)` - Establece el host del servidor
- `set_server_port(port)` - Establece el puerto del servidor

### Conexiones

- `increment_connections()` - Incrementa contador de conexiones
- `decrement_connections()` - Decrementa contador de conexiones
- `get_connections_count()` - Obtiene número de conexiones activas

### Sesiones de Jugadores

- `set_player_session(user_id, data)` - Establece sesión de jugador
- `get_player_session(user_id)` - Obtiene sesión de jugador
- `delete_player_session(user_id)` - Elimina sesión de jugador
- `update_player_last_seen(user_id)` - Actualiza último acceso

## Ventajas de la Integración

### 1. Configuración Centralizada
- Cambiar puerto/host sin reiniciar el servidor
- Configuración compartida entre múltiples instancias
- Fácil gestión desde herramientas externas

### 2. Estado Distribuido
- Múltiples servidores pueden compartir estado
- Persistencia de sesiones entre reinicios
- Escalabilidad horizontal

### 3. Métricas en Tiempo Real
- Monitoreo de conexiones activas
- Estadísticas de uso
- Debugging y troubleshooting

### 4. Flexibilidad
- Redis es opcional (fallback a configuración local)
- Fácil de deshabilitar para desarrollo
- Sin dependencias fuertes

## Ejemplo de Uso

### Configurar el servidor desde Redis CLI

```bash
# Conectar a Redis
redis-cli

# Cambiar puerto del servidor
SET config:server:port "8080"

# Cambiar host
SET config:server:host "127.0.0.1"

# Ver conexiones activas
GET server:connections:count

# Ver sesión de un jugador
HGETALL session:123:active
```

### Desde Python

```python
from src.redis_client import RedisClient
from src.redis_config import RedisConfig

# Conectar a Redis
client = RedisClient()
await client.connect(RedisConfig(host="localhost", port=6379))

# Cambiar configuración
await client.set_server_port(8080)

# Ver conexiones
count = await client.get_connections_count()
print(f"Conexiones activas: {count}")

# Gestionar sesión de jugador
await client.set_player_session(123, {
    "username": "player1",
    "level": "10",
    "class": "warrior"
})
```

## Testing

Los tests utilizan `fakeredis` para simular Redis sin necesidad de un servidor real:

```python
from fakeredis import aioredis

# En tests
client._redis = await aioredis.FakeRedis(decode_responses=True)
```

Esto permite:
- Tests rápidos sin dependencias externas
- CI/CD sin configurar Redis
- Desarrollo sin Redis instalado

## Próximos Pasos

1. **Autenticación**: Guardar tokens de sesión en Redis
2. **Rate Limiting**: Limitar peticiones por IP usando Redis
3. **Pub/Sub**: Comunicación entre servidores usando Redis Pub/Sub
4. **Caché**: Cachear consultas frecuentes (mapas, NPCs, etc.)
5. **Leaderboards**: Rankings de jugadores usando Sorted Sets
6. **Chat Global**: Sistema de chat usando Redis Streams

---

## Integración: REDIS_ARCHITECTURE.md

> Documento fuente archivado en [`archive/superseded/REDIS_ARCHITECTURE.md`](../archive/superseded/REDIS_ARCHITECTURE.md).

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        PyAO Server                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                    │
│  │ run_server.py│────────>│ArgentumServer│                    │
│  └──────────────┘         └───────┬──────┘                    │
│                                    │                            │
│                                    │ usa                        │
│                                    ▼                            │
│                           ┌────────────────┐                   │
│                           │  RedisClient   │                   │
│                           │  (Singleton)   │                   │
│                           └────────┬───────┘                   │
│                                    │                            │
│                                    │ conecta                    │
└────────────────────────────────────┼────────────────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  Redis Server   │
                            │  (localhost:6379)│
                            └─────────────────┘
```

## Flujo de Inicio del Servidor

```
1. run_server.py crea ArgentumServer
2. ArgentumServer.start() se ejecuta
3. Si use_redis=True:
   a. Crea RedisClient (singleton)
   b. Conecta a Redis
   c. Carga configuración (host, port) desde Redis
   d. Resetea contador de conexiones
4. Inicia servidor TCP con configuración
5. Espera conexiones de clientes
```

## Flujo de Conexión de Cliente

```
Cliente conecta
    │
    ▼
ArgentumServer.handle_client()
    │
    ├─> Crea ClientConnection
    ├─> Crea MessageSender
    │
    ├─> Redis: increment_connections()
    ├─> Redis: get_connections_count()
    │
    ├─> Loop: Leer datos del cliente
    │   ├─> Crear Task apropiada
    │   └─> Ejecutar Task
    │
    └─> Al desconectar:
        ├─> Redis: decrement_connections()
        └─> Redis: get_connections_count()
```

## Estructura de Datos en Redis

### Configuración del Servidor

```redis
SET config:server:host "0.0.0.0"
SET config:server:port "7666"
SET config:server:max_connections "1000"
```

### Estado del Servidor

```redis
SET server:connections:count "5"
SET server:uptime "3600"
```

### Sesiones de Jugadores

```redis
# Sesión activa (hash)
HSET session:123:active username "player1" level "10" class "warrior"

# Último acceso (timestamp)
SET session:123:last_seen "1697000000"
```

### Estado del Jugador

```redis
# Posición (hash)
HSET player:123:position x "100" y "200" map "1"

# Estadísticas (hash)
HSET player:123:stats strength "18" agility "15" intelligence "12"

# Inventario (hash o lista)
HSET player:123:inventory slot1 "sword" slot2 "shield" gold "1000"
```

## Métodos del RedisClient

### Configuración

- `get_server_host()` - Obtiene el host del servidor
- `get_server_port()` - Obtiene el puerto del servidor
- `set_server_host(host)` - Establece el host del servidor
- `set_server_port(port)` - Establece el puerto del servidor

### Conexiones

- `increment_connections()` - Incrementa contador de conexiones
- `decrement_connections()` - Decrementa contador de conexiones
- `get_connections_count()` - Obtiene número de conexiones activas

### Sesiones de Jugadores

- `set_player_session(user_id, data)` - Establece sesión de jugador
- `get_player_session(user_id)` - Obtiene sesión de jugador
- `delete_player_session(user_id)` - Elimina sesión de jugador
- `update_player_last_seen(user_id)` - Actualiza último acceso

## Ventajas de la Integración

### 1. Configuración Centralizada
- Cambiar puerto/host sin reiniciar el servidor
- Configuración compartida entre múltiples instancias
- Fácil gestión desde herramientas externas

### 2. Estado Distribuido
- Múltiples servidores pueden compartir estado
- Persistencia de sesiones entre reinicios
- Escalabilidad horizontal

### 3. Métricas en Tiempo Real
- Monitoreo de conexiones activas
- Estadísticas de uso
- Debugging y troubleshooting

### 4. Flexibilidad
- Redis es opcional (fallback a configuración local)
- Fácil de deshabilitar para desarrollo
- Sin dependencias fuertes

## Ejemplo de Uso

### Configurar el servidor desde Redis CLI

```bash
# Conectar a Redis
redis-cli

# Cambiar puerto del servidor
SET config:server:port "8080"

# Cambiar host
SET config:server:host "127.0.0.1"

# Ver conexiones activas
GET server:connections:count

# Ver sesión de un jugador
HGETALL session:123:active
```

### Desde Python

```python
from src.redis_client import RedisClient
from src.redis_config import RedisConfig

# Conectar a Redis
client = RedisClient()
await client.connect(RedisConfig(host="localhost", port=6379))

# Cambiar configuración
await client.set_server_port(8080)

# Ver conexiones
count = await client.get_connections_count()
print(f"Conexiones activas: {count}")

# Gestionar sesión de jugador
await client.set_player_session(123, {
    "username": "player1",
    "level": "10",
    "class": "warrior"
})
```

## Testing

Los tests utilizan `fakeredis` para simular Redis sin necesidad de un servidor real:

```python
from fakeredis import aioredis

# En tests
client._redis = await aioredis.FakeRedis(decode_responses=True)
```

Esto permite:
- Tests rápidos sin dependencias externas
- CI/CD sin configurar Redis
- Desarrollo sin Redis instalado

## Próximos Pasos

1. **Autenticación**: Guardar tokens de sesión en Redis
2. **Rate Limiting**: Limitar peticiones por IP usando Redis
3. **Pub/Sub**: Comunicación entre servidores usando Redis Pub/Sub
4. **Caché**: Cachear consultas frecuentes (mapas, NPCs, etc.)
5. **Leaderboards**: Rankings de jugadores usando Sorted Sets
6. **Chat Global**: Sistema de chat usando Redis Streams

## Integración: REDIS_INTEGRATION.md

> Documento fuente archivado en [`archive/superseded/REDIS_INTEGRATION.md`](../archive/superseded/REDIS_INTEGRATION.md).

## 📋 Resumen

Se ha integrado Redis exitosamente en el servidor PyAO para gestionar configuración centralizada, estado del juego y métricas en tiempo real.

## 🎯 Características Implementadas

### 1. **Configuración Centralizada**
- Host y puerto del servidor almacenados en Redis
- Configuración cargada automáticamente al iniciar
- Valores por defecto si Redis no está disponible

### 2. **Gestión de Estado**
- Contador de conexiones activas en tiempo real
- Sesiones de jugadores (activas y último acceso)
- Soporte para posiciones, estadísticas e inventarios

### 3. **Arquitectura Robusta**
- Redis es obligatorio para el funcionamiento del servidor
- El servidor no iniciará sin conexión a Redis
- Patrón singleton para el cliente Redis

## 📁 Archivos Creados

### Código Fuente
- **`src/redis_config.py`** - Configuración y constantes de Redis
- **`src/redis_client.py`** - Cliente Redis singleton con soporte async

### Tests
- **`tests/test_redis_client.py`** - 18 tests para Redis (100% cobertura)

### Documentación
- **`REDIS_ARCHITECTURE.md`** - Arquitectura detallada y diagramas
- **`REDIS_INTEGRATION.md`** - Este archivo (resumen de cambios)

## 🔧 Archivos Modificados

### Dependencias
- **`pyproject.toml`**
  - Agregado `redis>=5.2.0` como dependencia
  - Agregado `fakeredis>=2.26.0` para tests
  - Agregado `PLR6301` a ignores de tests

### Código del Servidor
- **`src/server.py`**
  - Conexión obligatoria a Redis en `start()`
  - Carga de configuración desde Redis
  - Tracking de conexiones activas
  - Desconexión limpia en `stop()`
  - El servidor termina con error si Redis no está disponible

### Documentación
- **`README.md`**
  - Agregada sección de Redis en Tecnologías
  - Agregado Redis a Requisitos
  - Agregada sección de configuración de Redis
  - Actualizada estructura del proyecto
  - Agregada sección de Integración con Redis

## 🚀 Uso

### Instalación de Dependencias

```bash
uv sync --dev
```

### Iniciar Redis (Obligatorio)

```bash
# Opción 1: Redis local
redis-server

# Opción 2: Docker
docker run -d -p 6379:6379 redis:latest
```

### Ejecutar el Servidor

```bash
# Asegúrate de que Redis esté ejecutándose primero
uv run pyao-server
```

**Nota:** El servidor requiere Redis para funcionar. Si Redis no está disponible, el servidor terminará con un error.

### Configurar desde Redis CLI

```bash
redis-cli

# Cambiar puerto
SET config:server:port "8080"

# Cambiar host
SET config:server:host "127.0.0.1"

# Ver conexiones activas
GET server:connections:count
```

### Interfaz Gráfica (Recomendado)

Para una experiencia visual y más amigable, se recomienda usar **Redis Insight**, la GUI oficial de Redis.

Ver instrucciones de instalación en [`guides/REDIS.md`](REDIS.md#-redis-insight-gui-recomendada) (disponible en Snap, Flatpak, Docker y AppImage).

## 🧪 Tests

Todos los tests pasan exitosamente:

```bash
# Tests de Redis
uv run pytest tests/test_redis_client.py -v
# 18 passed

# Todos los tests
uv run pytest -v
# 70 passed (52 originales + 18 nuevos)
```

## 📊 Estructura de Datos en Redis

### Configuración
```
config:server:host = "0.0.0.0"
config:server:port = "7666"
config:server:max_connections = "1000"
```

### Estado del Servidor
```
server:connections:count = "5"
server:uptime = "3600"
```

### Sesiones de Jugadores
```
session:{user_id}:active (hash) = {username, level, class, ...}
session:{user_id}:last_seen = "1697000000"
```

### Estado del Jugador
```
player:{user_id}:position (hash) = {x, y, map}
player:{user_id}:stats (hash) = {strength, agility, intelligence, ...}
player:{user_id}:inventory (hash) = {slot1, slot2, ..., gold}
```

## 🔑 API del RedisClient

### Configuración
- `get_server_host()` → str
- `get_server_port()` → int
- `set_server_host(host: str)`
- `set_server_port(port: int)`

### Conexiones
- `increment_connections()` → int
- `decrement_connections()` → int
- `get_connections_count()` → int

### Sesiones
- `set_player_session(user_id: int, data: dict)`
- `get_player_session(user_id: int)` → dict
- `delete_player_session(user_id: int)`
- `update_player_last_seen(user_id: int)`

## ✅ Validación de Calidad

### Linting
```bash
uv run ruff check .
# All checks passed!
```

### Type Checking
```bash
uv run mypy .
# Success: no issues found in 19 source files
```

### Tests
```bash
uv run pytest -v
# 70 passed in 0.06s
```

## 🎯 Próximos Pasos Sugeridos

1. **Autenticación**: Tokens de sesión en Redis
2. **Rate Limiting**: Limitar peticiones por IP
3. **Pub/Sub**: Comunicación entre múltiples instancias del servidor
4. **Caché**: Cachear mapas, NPCs, objetos del mundo
5. **Leaderboards**: Rankings usando Redis Sorted Sets
6. **Chat Global**: Sistema de chat usando Redis Streams
7. **Persistencia**: Configurar Redis con AOF/RDB para persistencia

## 📝 Notas Importantes

- **Redis es obligatorio**: El servidor requiere Redis para funcionar
- **Validación en inicio**: El servidor verifica la conexión a Redis al iniciar
- **Tests con fakeredis**: No requiere Redis real para tests
- **Singleton pattern**: Una sola instancia de RedisClient
- **Type-safe**: Totalmente tipado con mypy strict mode
- **Async/await**: Soporte completo para operaciones asíncronas

## 🐛 Troubleshooting

### Redis no conecta
```bash
# El servidor terminará con error
# Logs mostrarán: "No se pudo conectar a Redis" y "El servidor requiere Redis para funcionar"

# Solución: Iniciar Redis
redis-server
# o con Docker:
docker run -d -p 6379:6379 redis:8-alpine
```

### Tests fallan
```bash
# Asegurarse de tener fakeredis instalado
uv sync --dev

# Verificar que pytest-asyncio esté configurado
uv run pytest --version
```

### Mypy errors
```bash
# Regenerar el entorno
uv sync --dev

# Limpiar caché de mypy
rm -rf .mypy_cache
uv run mypy .
```

## 📚 Referencias

- [Redis Python Async](https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [FakeRedis](https://github.com/cunla/fakeredis-py)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Arquitectura detallada](architecture/REDIS_DATA.md)

---

**Fecha de Integración**: Octubre 2025  
**Versión**: 0.1.0  
**Estado**: ✅ Completado y Testeado

