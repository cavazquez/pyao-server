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

## 🔒 Seguridad

Para producción, considera:

1. **Usar contraseña**: `--requirepass tu_password_seguro`
2. **Limitar conexiones**: `--bind 127.0.0.1` (solo localhost)
3. **Configurar maxmemory**: `--maxmemory 256mb`
4. **Habilitar persistencia**: Configurar `save` en redis.conf

## 📝 Versión

Este Dockerfile usa **Redis 8 Alpine**, la última versión estable de Redis con una imagen ligera basada en Alpine Linux.
