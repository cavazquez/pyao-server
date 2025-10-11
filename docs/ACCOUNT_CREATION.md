# Creación de Cuentas

Este documento describe la funcionalidad de creación de cuentas en PyAO Server.

## Descripción General

El servidor soporta la creación de cuentas de usuario mediante el protocolo de paquetes. Las cuentas se almacenan en Redis con contraseñas hasheadas usando SHA-256.

## Protocolo de Paquetes

### Paquete de Creación de Cuenta (Cliente → Servidor)

**PacketID**: `2` (`ClientPacketID.CREATE_ACCOUNT`)

**Formato**:
```
Byte 0:       PacketID (2)
Bytes 1-2:    Longitud del username (int16, little-endian)
Bytes 3-N:    Username (UTF-8)
Bytes N+1-N+2: Longitud del password (int16, little-endian)
Bytes N+3-M:  Password (UTF-8)
Byte M+1:     race (1 byte)
Bytes M+2-M+3: Desconocido (int16, little-endian)
Byte M+4:     gender (1 byte)
Byte M+5:     job/class (1 byte)
Byte M+6:     Desconocido (1 byte)
Bytes M+7-M+8: head (int16, little-endian)
Bytes M+9-M+10: Longitud del email (int16, little-endian)
Bytes M+11-P: Email (UTF-8)
Byte P+1:     home (1 byte)
```

**Ejemplo en Python**:
```python
from src.packet_id import ClientPacketID

username = "jugador123"
password = "mipassword"
email = "jugador@example.com"

data = bytearray([ClientPacketID.CREATE_ACCOUNT])
# Username
data.extend(len(username).to_bytes(2, byteorder="little"))
data.extend(username.encode("utf-8"))
# Password
data.extend(len(password).to_bytes(2, byteorder="little"))
data.extend(password.encode("utf-8"))
# Datos del personaje
data.append(1)  # race
data.extend((0).to_bytes(2, byteorder="little"))  # desconocido
data.append(1)  # gender
data.append(1)  # job
data.append(1)  # desconocido
data.extend((18).to_bytes(2, byteorder="little"))  # head
# Email
data.extend(len(email).to_bytes(2, byteorder="little"))
data.extend(email.encode("utf-8"))
# Home
data.append(1)  # home
```

### Respuesta de Cuenta Creada (Servidor → Cliente)

**PacketID**: `68` (`ServerPacketID.ACCOUNT_CREATED`)

**Formato**:
```
Byte 0:       PacketID (68)
Bytes 1-4:    user_id (int32, little-endian)
```

### Respuesta de Error (Servidor → Cliente)

**PacketID**: `69` (`ServerPacketID.ACCOUNT_ERROR`)

**Formato**:
```
Byte 0:       PacketID (69)
Bytes 1-2:    Longitud del mensaje (int16, little-endian)
Bytes 3-N:    Mensaje de error (UTF-8)
```

## Validaciones

El servidor valida los siguientes criterios:

- **Username**: Mínimo 3 caracteres
- **Password**: Mínimo 6 caracteres
- **Email**: Debe contener el carácter '@'
- **Unicidad**: El username no debe existir previamente

## Almacenamiento en Redis

### Estructura de Datos

Cada cuenta se almacena usando las siguientes claves:

1. **Contador de cuentas**:
   ```
   accounts:counter → user_id autoincremental
   ```

2. **Mapeo username → user_id**:
   ```
   account:username:{username} → user_id
   ```

3. **Datos de la cuenta** (hash):
   ```
   account:{username}:data → {
       user_id: "123",
       username: "jugador123",
       password_hash: "abc123...",
       email: "jugador@example.com",
       created_at: "1697123456",
       char_job: "1",
       char_race: "1",
       char_gender: "1",
       char_home: "1",
       char_head: "18"
   }
   ```

### Seguridad

- Las contraseñas se hashean usando **SHA-256** antes de almacenarse
- El hash es hexadecimal de 64 caracteres
- Las contraseñas en texto plano nunca se almacenan

## Uso desde el Código

### Crear una Cuenta Manualmente

```python
from src.redis_client import RedisClient
import hashlib

# Conectar a Redis
redis_client = RedisClient()
await redis_client.connect()

# Crear cuenta
username = "jugador123"
password = "mipassword"
email = "jugador@example.com"

# Hashear contraseña
password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

# Crear cuenta
user_id = await redis_client.create_account(
    username=username,
    password_hash=password_hash,
    email=email
)

print(f"Cuenta creada con ID: {user_id}")
```

### Verificar si una Cuenta Existe

```python
exists = await redis_client.account_exists("jugador123")
if exists:
    print("La cuenta ya existe")
```

### Obtener Datos de una Cuenta

```python
account_data = await redis_client.get_account_data("jugador123")
print(f"User ID: {account_data['user_id']}")
print(f"Email: {account_data['email']}")
```

### Obtener user_id por Username

```python
user_id = await redis_client.get_user_id_by_username("jugador123")
if user_id:
    print(f"User ID: {user_id}")
```

## Manejo de Errores

El servidor puede devolver los siguientes errores:

| Error | Descripción |
|-------|-------------|
| `"Formato de paquete inválido"` | El paquete recibido está malformado |
| `"El nombre de usuario debe tener al menos 3 caracteres"` | Username muy corto |
| `"La contraseña debe tener al menos 6 caracteres"` | Password muy corto |
| `"Email inválido"` | Email no contiene '@' |
| `"La cuenta '{username}' ya existe"` | Username duplicado |
| `"Servicio de cuentas no disponible"` | Redis no está conectado |
| `"Error interno del servidor"` | Error inesperado |

## Testing

El módulo incluye tests exhaustivos en `tests/test_account_creation.py`:

- Creación exitosa de cuenta
- Validación de username, password y email
- Manejo de cuentas duplicadas
- Manejo de paquetes malformados
- Soporte para caracteres Unicode
- Verificación de hashing de contraseñas

Ejecutar tests:
```bash
uv run pytest tests/test_account_creation.py -v
```

## Consideraciones de Seguridad

1. **Hashing de Contraseñas**: Se usa SHA-256 para hashear contraseñas
2. **Validación de Entrada**: Todos los campos son validados antes de procesarse
3. **Prevención de Duplicados**: Se verifica la existencia antes de crear
4. **Encoding Seguro**: Todo el texto usa UTF-8 para evitar problemas de encoding

## Mejoras Futuras

Posibles mejoras a considerar:

- [ ] Usar bcrypt o argon2 en lugar de SHA-256 para mayor seguridad
- [ ] Agregar salt a las contraseñas
- [ ] Implementar rate limiting para prevenir ataques de fuerza bruta
- [ ] Agregar verificación de email
- [ ] Implementar recuperación de contraseña
- [ ] Agregar validación más robusta de email (regex)
- [ ] Implementar límite de longitud máxima para campos
