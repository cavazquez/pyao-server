# Cómo Configurar un Usuario como Game Master (GM)

## 📋 Método 1: Usando Redis CLI (Recomendado)

### Paso 1: Conectar a Redis

```bash
redis-cli
```

### Paso 2: Buscar el username del usuario

Primero necesitas encontrar la clave de la cuenta. Las cuentas se guardan con el formato:
```
account:{username}:data
```

### Paso 3: Establecer el flag de GM

```bash
# Establecer usuario como GM
HSET account:{username}:data is_gm 1

# Ejemplo:
HSET account:Admin:data is_gm 1
HSET account:TestUser:data is_gm 1
```

### Paso 4: Verificar que se guardó correctamente

```bash
# Ver todos los datos de la cuenta
HGETALL account:{username}:data

# Ver solo el flag de GM
HGET account:{username}:data is_gm
# Debe devolver: 1
```

### Paso 5: Quitar permisos de GM

```bash
# Quitar GM
HSET account:{username}:data is_gm 0
```

## 📋 Método 2: Usando un Script Python

Crea un script temporal `set_gm.py`:

```python
import asyncio
from src.utils.redis_client import RedisClient
from src.repositories.account_repository import AccountRepository

async def set_gm(username: str, is_gm: bool):
    """Establece el estado de GM de un usuario."""
    redis_client = await RedisClient.create()
    account_repo = AccountRepository(redis_client)
    
    await account_repo.set_gm_status(username, is_gm)
    status = "GM" if is_gm else "No GM"
    print(f"Usuario '{username}' ahora es {status}")
    
    # Verificar
    result = await account_repo.is_gm(username)
    print(f"Verificación: is_gm = {result}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Uso: python set_gm.py <username> <1|0>")
        print("  1 = Hacer GM")
        print("  0 = Quitar GM")
        sys.exit(1)
    
    username = sys.argv[1]
    is_gm = sys.argv[2] == "1"
    
    asyncio.run(set_gm(username, is_gm))
```

Ejecutar:
```bash
uv run python set_gm.py Admin 1    # Hacer GM
uv run python set_gm.py Admin 0    # Quitar GM
```

## 📋 Método 3: Usando Redis Insight (GUI)

Si tienes Redis Insight instalado:

1. Abre Redis Insight
2. Conecta a tu instancia de Redis
3. Busca la clave `account:{username}:data`
4. Edita el campo `is_gm` y ponlo en `1`
5. Guarda los cambios

## ✅ Verificación

Después de configurar un usuario como GM:

1. **Reinicia el servidor** (si está corriendo) o simplemente reconecta el cliente
2. **Inicia sesión** con el usuario configurado como GM
3. **Prueba un comando GM** (teletransporte desde el cliente)
4. **Deberías poder usar comandos GM** sin recibir el mensaje "No tienes permisos de Game Master"

## 🔍 Listar Todos los GMs

Para ver todos los usuarios que son GM:

```bash
redis-cli

# Buscar todas las cuentas
KEYS account:*:data

# Para cada cuenta, verificar is_gm
# (puedes hacer un script para automatizar esto)
```

O usando un script Python:

```python
import asyncio
from src.utils.redis_client import RedisClient

async def list_gms():
    redis_client = await RedisClient.create()
    keys = await redis_client.redis.keys("account:*:data")
    
    gms = []
    for key in keys:
        account_data = await redis_client.redis.hgetall(key)
        if account_data.get("is_gm") == "1":
            username = account_data.get("username", "Unknown")
            gms.append(username)
    
    if gms:
        print("Usuarios GM:")
        for gm in gms:
            print(f"  - {gm}")
    else:
        print("No hay usuarios GM configurados")

asyncio.run(list_gms())
```

## ⚠️ Notas Importantes

1. **El flag `is_gm` debe ser "1" (string)**, no el número 1
2. **Los cambios son inmediatos** - no necesitas reiniciar Redis
3. **El usuario debe reconectarse** para que los cambios surtan efecto (o reiniciar el servidor)
4. **Por defecto, todos los usuarios nuevos tienen `is_gm = "0"`**

## 🛡️ Seguridad

- **No compartas** los permisos de GM con usuarios no confiables
- **Revisa periódicamente** quién tiene permisos de GM
- **Usa nombres de usuario seguros** para cuentas de administración
- **Considera implementar** un sistema de logs para comandos GM

