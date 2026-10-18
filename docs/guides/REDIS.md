# Redis para PyAO Server

Este directorio contiene la configuración de Redis para el servidor de Argentum Online.

## 🐳 Docker

### Construir la imagen

```bash
docker build -t pyao-redis ./redis
```

### Ejecutar el contenedor

```bash
# Modo básico
docker run -d --name pyao-redis -p 6379:6379 pyao-redis

# Con persistencia de datos
docker run -d --name pyao-redis \
  -p 6379:6379 \
  -v pyao-redis-data:/data \
  pyao-redis

# Con configuración personalizada
docker run -d --name pyao-redis \
  -p 6379:6379 \
  -v $(pwd)/redis.conf:/usr/local/etc/redis/redis.conf \
  pyao-redis redis-server /usr/local/etc/redis/redis.conf
```

### Comandos útiles

```bash
# Ver logs
docker logs pyao-redis

# Acceder a Redis CLI
docker exec -it pyao-redis redis-cli

# Detener el contenedor
docker stop pyao-redis

# Iniciar el contenedor
docker start pyao-redis

# Eliminar el contenedor
docker rm pyao-redis

# Eliminar el volumen de datos
docker volume rm pyao-redis-data
```

## 🔧 Configuración

### Variables de entorno

Puedes pasar variables de entorno al contenedor:

```bash
docker run -d --name pyao-redis \
  -p 6379:6379 \
  -e REDIS_PASSWORD=tu_password_seguro \
  pyao-redis redis-server --requirepass tu_password_seguro
```

### Configuración avanzada

Para configuración avanzada, crea un archivo `redis.conf` y móntalo:

```bash
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

```bash
docker run -d --name pyao-redis \
  -p 6379:6379 \
  -v $(pwd)/redis/redis.conf:/usr/local/etc/redis/redis.conf \
  pyao-redis redis-server /usr/local/etc/redis/redis.conf
```

## 🐳 Docker Compose (Recomendado)

Si usas Docker Compose, agrega esto a tu `docker-compose.yml`:

```yaml
services:
  redis:
    build: ./redis
    container_name: pyao-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  redis-data:
```

Luego ejecuta:

```bash
docker-compose up -d redis
```

## 📊 Monitoreo

### Verificar estado

```bash
# Ping
docker exec pyao-redis redis-cli ping

# Info
docker exec pyao-redis redis-cli info

# Estadísticas de memoria
docker exec pyao-redis redis-cli info memory

# Clientes conectados
docker exec pyao-redis redis-cli client list
```

### Monitorear comandos en tiempo real

```bash
docker exec -it pyao-redis redis-cli monitor
```

## 🖥️ Redis Insight (GUI Recomendada)

**Redis Insight** es la herramienta oficial de Redis para gestión visual y monitoreo. Proporciona una interfaz gráfica moderna para:

- Visualizar y editar claves en tiempo real
- Monitorear rendimiento y métricas
- Ejecutar comandos con autocompletado
- Analizar uso de memoria
- Depurar consultas lentas

### Instalación

#### Snap (Ubuntu/Debian)

```bash
sudo snap install redis-insight
```

Ejecutar:
```bash
redis-insight
```

#### Flatpak (Distribuciones con soporte Flatpak)

```bash
# Agregar repositorio Flathub (si no está agregado)
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Instalar Redis Insight
flatpak install flathub com.redis.RedisInsight

# Ejecutar
flatpak run com.redis.RedisInsight
```

#### Otras opciones

```bash
# Docker
docker run -d --name redis-insight \
  -p 5540:5540 \
  redis/redisinsight:latest

# Acceder en: http://localhost:5540

# AppImage (descarga desde redis.com/redis-enterprise/redis-insight/)
chmod +x RedisInsight-v2-linux-x86_64.AppImage
./RedisInsight-v2-linux-x86_64.AppImage
```

### Conectar a Redis local

1. Abrir Redis Insight
2. Click en "Add Redis Database"
3. Configurar:
   - **Host**: `localhost`
   - **Port**: `6379`
   - **Name**: `PyAO Redis`
4. Click en "Add Redis Database"

### Conectar a Redis en Docker

Si Redis está en Docker, usa:
- **Host**: `localhost` (si usas `-p 6379:6379`)
- **Port**: `6379`

O desde la red de Docker:
- **Host**: `pyao-redis` (nombre del contenedor)
- **Port**: `6379`

## 🔒 Seguridad

Para producción, considera:

1. **Usar contraseña**: `--requirepass tu_password_seguro`
2. **Limitar conexiones**: `--bind 127.0.0.1` (solo localhost)
3. **Configurar maxmemory**: `--maxmemory 256mb`
4. **Habilitar persistencia**: Configurar `save` en redis.conf

## 📝 Versión

Este Dockerfile usa **Redis 8 Alpine**, la última versión estable de Redis con una imagen ligera basada en Alpine Linux.

## Perfil persistente y red de desarrollo

Compose publica Redis y Redis Insight exclusivamente en `127.0.0.1`; Insight
sigue siendo optativo con `--profile tools`. Para otro puerto local usar
`PYAO_REDIS_PORT` / `PYAO_REDIS_INSIGHT_PORT`. Desde otra máquina utilizar un túnel
SSH hacia loopback. La red interna de Compose conserva el servicio `redis:6379`.

El perfil conserva `protected-mode yes` y exige una credencial mediante Docker
secret. Para prepararla, sin imprimirla ni incorporarla a Git:

```bash
uv run --locked python -m src.operations.redis_secret --output .local/redis-password
export PYAO_REDIS_PASSWORD_FILE="$PWD/.local/redis-password"
docker compose up -d --build redis
uv run --locked pyao-server
```

El generador usa creación exclusiva y permisos 0600; no sobrescribe un archivo
existente. El servidor admite esa variable legado o `PYAO_REDIS__PASSWORD_FILE`
y la opción `redis.password_file` del TOML. El entrypoint convierte el secreto en
un hash ACL privado, sin poner la contraseña en argumentos ni logs. Redis Insight
se configura manualmente con la misma credencial y el servicio interno `redis`.
Para una instalación externa sin autenticación, dejar password_file ausente.

La imagen de Redis fija versión 8.10.2 y digest. `redis/redis.conf` habilita AOF
con `appendfsync everysec`, sin desactivar fsync durante rewrite, y snapshots RDB
a los 900 s/1 cambio, 300 s/10 cambios o 60 s/10000 cambios. Se persiste **todo**
`/data`, incluido `appendonlydir` y su manifiesto; no copiar sólo un archivo AOF.
El cierre limpio guarda el trabajo pendiente. Ante caída abrupta, everysec puede
perder aproximadamente el último segundo de escrituras; discos, controlador y
filesystem deben cumplir fsync. Un reinicio de proceso no equivale a un corte
eléctrico. Los snapshots son puntos de recuperación adicionales y el volumen
local no sustituye un backup externo.

Ensayo aislado, sin acceder al Redis del operador:

```bash
uv run --locked python -m src.operations.redis_persistence
```

El comando crea contenedor/volumen con UUID y puerto aleatorio sólo en loopback,
comprueba CONFIG GET, persiste cuenta/oro/inventario sintéticos y prueba reinicio
limpio y SIGKILL después de WAITAOF local confirmado. Retira únicamente sus
recursos. Este último caso demuestra persistencia confirmada, no ausencia de
pérdida para escrituras todavía no sincronizadas.

Antes de aplicar esta configuración sobre un volumen existente, hacer y verificar
un backup. Activar AOF sobre una instancia que ya contiene sólo RDB exige cargar
primero ese RDB y habilitar AOF en memoria; iniciar directamente con un AOF vacío
puede seleccionar un estado vacío. El procedimiento de restauración utiliza un
volumen nuevo y deja intacta la instancia activa. Referencia: [persistencia de
Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).
