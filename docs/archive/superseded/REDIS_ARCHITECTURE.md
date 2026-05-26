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
