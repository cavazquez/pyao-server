# Flujo de Login y Mensajes Post-Login

Este documento describe el flujo completo de mensajes entre el cliente (ArgentumOnlineGodot) y el servidor (PyAO Server) durante el proceso de login y los mensajes que se intercambian después de un login exitoso.

**IMPORTANTE**: Este servidor implementa el **protocolo estándar de Argentum Online Godot** (basado en brian-christopher/ArgentumOnlineGodot).

## Descripción General

El flujo de login sigue estos pasos principales:
1. Cliente envía credenciales (`LoginExistingChar`)
2. Servidor valida y responde con éxito (`Logged`) o error (`ErrorMsg`)
3. Cliente puede solicitar información adicional del personaje
4. Servidor envía datos del personaje para iniciar el juego

## Protocolo de Mensajes

### 1. Login Inicial (Cliente → Servidor)

**PacketID**: `0` (`ClientPacketID.LOGIN`)

**Nombre en cliente Godot**: `LoginExistingCharacter`

**Formato**:
```
Byte 0:       PacketID (0)
Bytes 1-2:    Longitud del username (int16, little-endian)
Bytes 3-N:    Username (UTF-8)
Bytes N+1-N+2: Longitud del password (int16, little-endian)
Bytes N+3-M:  Password (UTF-8)
```

**Referencia en cliente**: `login_screen.gd:26` y `game_protocol.gd:25-32`

**Ejemplo en Python**:
```python
from src.packet_id import ClientPacketID

username = "jugador123"
password = "mipassword"

data = bytearray([ClientPacketID.LOGIN])
# Username
data.extend(len(username).to_bytes(2, byteorder="little"))
data.extend(username.encode("utf-8"))
# Password
data.extend(len(password).to_bytes(2, byteorder="little"))
data.extend(password.encode("utf-8"))
```

### 2. Respuestas del Servidor

El servidor puede responder de dos maneras según el resultado del login:

#### 2.1. Login Exitoso (Servidor → Cliente)

**PacketID**: `0` (`ServerPacketID.LOGGED`)

**Nombre en cliente Godot**: `Logged`

**Formato** (Protocolo AO Estándar):
```
Byte 0:       PacketID (0)
Byte 1:       userClass (1 byte) - Clase del personaje
```

**Referencia en cliente**: 
- `login_screen.gd:49-50` (manejo del paquete)
- `network/commands/Logged.gd` (definición del paquete)

**Implementación en servidor**: `src/task.py:262` (método `TaskLogin.execute()`)

**Ejemplo en Python**:
```python
from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID

packet = PacketBuilder()
packet.add_byte(ServerPacketID.LOGGED)  # 0
packet.add_byte(user_class)  # Clase del personaje (1 byte)
response = packet.to_bytes()
```

**Datos incluidos**:
- `userClass`: Clase del personaje (1 byte) - se obtiene de `char_job` en Redis

**Acción del cliente**: 
- Recibe el paquete `Logged` con la clase del personaje
- Pasa estos datos a la pantalla de juego (`login_screen.gd:56-60`)

#### 2.2. Error de Login (Servidor → Cliente)

**PacketID**: `55` (`ServerPacketID.ERROR_MSG`)

**Nombre en cliente Godot**: `ErrorMsg`

**Formato** (Protocolo AO Estándar):
```
Byte 0:       PacketID (55)
Bytes 1-2:    Longitud del mensaje (int16, little-endian)
Bytes 3-N:    Mensaje de error (UTF-8)
```

**Referencia en cliente**: 
- `login_screen.gd:46-47` (manejo del paquete)
- `network/commands/ErrorMsg.gd` (definición del paquete)

**Acción del cliente**:
- Muestra el mensaje de error
- Desconecta al cliente (`login_screen.gd:52-54`)

**Posibles mensajes de error**:
- `"Usuario o contraseña incorrectos"` - Credenciales inválidas
- `"Servicio no disponible"` - Redis no disponible
- `"Error al obtener datos de cuenta"` - Error interno

## 3. Mensajes Post-Login

Después de recibir `LOGIN_SUCCESS`, el cliente típicamente solicita información adicional del personaje:

### 3.1. Solicitud de Atributos (Cliente → Servidor)

**PacketID**: `13` (`ClientPacketID.REQUEST_ATTRIBUTES`)

**Formato**:
```
Byte 0:       PacketID (13)
```

**Implementación en servidor**: `src/task.py:275-369` (clase `TaskRequestAttributes`)

### 3.2. Respuesta de Atributos (Servidor → Cliente)

**PacketID**: `50` (`ServerPacketID.ATTRIBUTES`)

**Formato**:
```
Byte 0:       PacketID (50)
Byte 1:       Fuerza (strength)
Byte 2:       Agilidad (agility)
Byte 3:       Inteligencia (intelligence)
Byte 4:       Carisma (charisma)
Byte 5:       Constitución (constitution)
```

**Fuentes de datos**:
1. **Sesión temporal**: Si hay atributos de dados guardados en la sesión (para personajes nuevos)
2. **Redis**: Obtiene los atributos desde `player:{user_id}:stats`

**Ejemplo en Python**:
```python
from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID

packet = PacketBuilder()
packet.add_byte(ServerPacketID.ATTRIBUTES)
packet.add_byte(strength)
packet.add_byte(agility)
packet.add_byte(intelligence)
packet.add_byte(charisma)
packet.add_byte(constitution)
response = packet.to_bytes()
```

## Flujo Completo de Secuencia

```
Cliente (Godot)                          Servidor (Python)
     |                                          |
     |  1. LoginExistingChar (username, pwd)   |
     |----------------------------------------->|
     |                                          |
     |                    [Validación en Redis] |
     |                                          |
     |  2a. Logged (userClass)                 |
     |<-----------------------------------------|
     |     o                                    |
     |  2b. ErrorMsg (mensaje)                 |
     |<-----------------------------------------|
     |                                          |
     | [Si Logged recibido]                     |
     |                                          |
     |  3. RequestAtributes                     |
     |----------------------------------------->|
     |                                          |
     |                  [Obtiene datos de Redis]|
     |                                          |
     |  4. Atributes (stats)                    |
     |<-----------------------------------------|
     |                                          |
     | [Cliente carga pantalla de juego]        |
     |                                          |
```

## Validación en el Servidor

El servidor realiza las siguientes validaciones durante el login (`src/task.py:205-260`):

1. **Parseo del paquete**: Verifica que el formato sea correcto
2. **Disponibilidad de Redis**: Verifica que Redis esté conectado
3. **Existencia de cuenta**: Verifica que el username exista en Redis
4. **Verificación de contraseña**: Compara el hash SHA-256 de la contraseña
5. **Sesión**: Guarda el `user_id` en `session_data` para uso posterior

## Almacenamiento en Redis

### Datos de Login

```
account:{username}:data → {
    user_id: "123",
    username: "jugador123",
    password_hash: "abc123...",
    email: "jugador@example.com",
    created_at: "1697123456",
    ...
}

account:username:{username} → user_id
```

### Datos de Atributos

```
player:{user_id}:stats → {
    strength: "15",
    agility: "12",
    intelligence: "14",
    charisma: "10",
    constitution: "13"
}
```

## Datos de Sesión

Durante la conexión, el servidor mantiene un diccionario de sesión (`session_data`) que se comparte entre todas las tareas de esa conexión:

```python
session_data = {
    "user_id": 123,  # Guardado después de LOGIN_SUCCESS
    "dice_attributes": {  # Guardado después de THROW_DICES (para creación)
        "strength": 15,
        "agility": 12,
        "intelligence": 14,
        "charisma": 10,
        "constitution": 13
    }
}
```

Este diccionario permite que diferentes mensajes accedan a información de la sesión sin necesidad de pasarla explícitamente.

## Protocolo AO Estándar Implementado

**✅ Este servidor implementa el protocolo estándar de Argentum Online Godot**

Basado en: [brian-christopher/ArgentumOnlineGodot](https://github.com/brian-christopher/ArgentumOnlineGodot)

**Paquetes implementados**:
- `LOGGED = 0`: Login exitoso con clase del personaje
- `POS_UPDATE = 22`: Actualización de posición del personaje
- `ATTRIBUTES = 50`: Atributos del personaje (Atributes en el protocolo)
- `ERROR_MSG = 55`: Mensajes de error
- `DICE_ROLL = 67`: Tirada de dados para creación de personaje

**Ventajas del protocolo estándar**:
- Compatibilidad total con el cliente Godot oficial
- Protocolo probado y estable
- Comunidad activa de desarrollo
- Facilita la integración con otros servidores AO

## Próximos Mensajes a Implementar

Según el protocolo estándar de AO (comentados en `src/packet_id.py`), los siguientes mensajes típicamente se envían después del login:

1. **`USER_INDEX_IN_SERVER`** (27): Índice del usuario en el servidor
2. **`CHARACTER_CREATE`** (29): Crear el personaje en el mapa
3. **`CHANGE_MAP`** (21): Cambiar al mapa inicial
4. ~~**`POS_UPDATE`** (22): Actualizar posición del personaje~~ ✅ **Implementado**
5. **`UPDATE_USER_STATS`** (45): Enviar estadísticas completas (HP, mana, etc.)
6. **`UPDATE_HP`** (17): Actualizar puntos de vida
7. **`UPDATE_MANA`** (16): Actualizar puntos de maná
8. **`UPDATE_STA`** (15): Actualizar stamina
9. **`UPDATE_GOLD`** (18): Actualizar oro
10. **`UPDATE_EXP`** (20): Actualizar experiencia
11. **`CHANGE_INVENTORY_SLOT`** (47): Enviar items del inventario
12. **`SEND_SKILLS`** (71): Enviar habilidades del personaje
13. **`PLAY_MIDI`** (38): Reproducir música del mapa
14. **`CONSOLE_MSG`** (24): Mensaje de bienvenida

## Referencias del Código

### Servidor (Python)

- **Login**: `src/task.py:132-273` (clase `TaskLogin`)
- **Atributos**: `src/task.py:275-369` (clase `TaskRequestAttributes`)
- **Mensajes**: `src/msg.py:98-128` (funciones de construcción)
- **Packet IDs**: `src/packet_id.py:10-269`
- **Message Sender**: `src/message_sender.py:102-118`

### Cliente (Godot)

- **Login Screen**: `screens/login_screen.gd:26` (envío de login)
- **Login Screen**: `screens/login_screen.gd:46-60` (manejo de respuesta)
- **Game Protocol**: `game_protocol.gd:25-32` (construcción del paquete)

## Consideraciones de Seguridad

1. **Hashing de Contraseñas**: Se usa SHA-256 (considerar migrar a bcrypt/argon2)
2. **Validación de Entrada**: Todos los campos son validados
3. **Sesión Temporal**: Los datos de sesión se limpian al cerrar la conexión
4. **Redis**: Las contraseñas nunca se almacenan en texto plano

## Testing

Para probar el flujo de login:

```bash
# Tests de login
uv run pytest tests/test_task.py::TestTaskLogin -v

# Tests de atributos
uv run pytest tests/test_task.py::TestTaskRequestAttributes -v

# Todos los tests
uv run pytest -v
```

## Mejoras Futuras

- [x] ~~Implementar el paquete `LOGGED` estándar del protocolo AO~~ ✅ **Implementado**
- [x] ~~Enviar posición del personaje después del login~~ ✅ **Implementado** (posición por defecto)
- [ ] Obtener posición del personaje desde Redis
- [ ] Enviar más datos en el login (mapa, stats completos)
- [ ] Implementar sistema de sesiones persistentes en Redis
- [ ] Agregar timeout de sesión
- [ ] Implementar reconexión automática
- [ ] Agregar logs de auditoría de logins
- [ ] Implementar rate limiting para prevenir ataques de fuerza bruta
