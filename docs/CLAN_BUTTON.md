# Botón de clan en el cliente (GuildDetails / packet 80)

Guía única: estado servidor/cliente, formato del packet y pasos para habilitar el envío cuando el cliente implemente el handler.

---


**Fecha:** 2025-01-31  
**Problema:** El botón de clanes no se activa aunque el jugador tenga un clan

---

## ✅ Estado del Servidor

El servidor Python **tiene la funcionalidad implementada pero DESHABILITADA**:

1. **Packet CLAN_DETAILS (ID: 80)** - Implementado según protocolo VB6
   - Archivo: `src/network/msg_clan.py`
   - Función: `build_clan_details_response()`
   - Formato: Compatible con `Protocol.WriteGuildDetails` del servidor VB6 original

2. **Envío durante Login** - ⚠️ **DESHABILITADO** hasta que el cliente lo implemente
   - Archivo: `src/command_handlers/login_handler.py`
   - El código está comentado con un TODO
   - **NO se envía** hasta que el cliente tenga el handler implementado

3. **Métodos Listos**
   - Métodos implementados en `MessageSender` y `SessionMessageSender`
   - Todo está listo para habilitar cuando el cliente lo necesite

---

## ⚠️ Estado del Cliente

El cliente Godot **NO procesa el packet CLAN_DETAILS**:

1. **Enum existe** - `GuildDetails` está definido en `enums.gd` (línea 273)
2. **Handler NO existe** - No hay archivo `GuildDetails.gd` en `network/commands/`
3. **Handler NO está registrado** - No hay case en `game_screen.gd` para el packet 80
4. **Botón existe** - `btnGuilds` existe en la UI pero no se habilita

**El cliente ignora el packet porque no tiene el código para procesarlo.**

**El servidor NO envía el packet actualmente** - Está deshabilitado hasta que el cliente implemente el handler.

---

## 🔍 Formato del Packet Enviado

El servidor envía el packet con el siguiente formato (según protocolo VB6):

```
Byte 0:        PacketID (80 = CLAN_DETAILS)
Bytes 1-2:     Longitud GuildName (int16)
Bytes 3-N:     GuildName (latin-1)
Bytes N+1-N+2: Longitud Founder (int16)
Bytes N+3-M:   Founder (latin-1)
... (y así sucesivamente para todos los campos)
```

Campos incluidos:
- GuildName (string)
- Founder (string)
- FoundationDate (string, formato "dd/mm/yyyy")
- Leader (string)
- URL (string)
- MemberCount (int32)
- ElectionsOpen (byte: 0 o 1)
- Alignment (string)
- EnemiesCount (int32)
- AlliesCount (int32)
- AntifactionPoints (string)
- Codex (string)
- GuildDesc (string)

---

## 📋 Solución Requerida

**Para habilitar el botón de clanes, se necesita:**

1. **Crear handler en cliente Godot** (no modificable según requerimiento):
   - `clientes/ArgentumOnlineGodot/network/commands/GuildDetails.gd`
   - Parser para leer todos los campos del packet
   
2. **Registrar handler en game_screen.gd**:
   - Agregar case para `Enums.ServerPacketID.GuildDetails`
   - Llamar al handler y habilitar el botón `btnGuilds`

**Como el cliente no se puede modificar, el botón NO se habilitará hasta que el cliente tenga el handler implementado.**

---

## ⚠️ Estado Actual

**El servidor NO envía el packet actualmente**:

1. El código está implementado pero comentado
2. Se puede habilitar fácilmente cuando el cliente esté listo
3. Solo hay que descomentar el código en `login_handler.py`
4. El formato del packet es correcto según el protocolo VB6

**Para habilitar cuando el cliente lo implemente:**
- Seguir la sección [Pasos en el servidor (cuando el cliente esté listo)](#pasos-en-el-servidor-cuando-el-cliente-esté-listo) más abajo
- Agregar el código necesario en `login_handler.py` usando `message_sender.send_clan_details(clan)`
- Agregar `clan_service` al constructor de `LoginCommandHandler` si se necesita

---

## 🔗 Referencias

- **Protocolo VB6**: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/Protocol.bas` (línea 17378)
- **Implementación Servidor**: `src/network/msg_clan.py`
- **Integración Login**: `src/command_handlers/login_handler.py` (comentario explicativo en línea ~442)
- **Estado Cliente**: `clientes/ArgentumOnlineGodot/common/enums/enums.gd` (línea 273 - enum existe, handler no)

---

**Conclusión:** El servidor tiene todo listo pero NO envía el packet actualmente. Cuando el cliente implemente el handler, se puede habilitar fácilmente descomentando el código en `login_handler.py`.


---

## Pasos en el servidor (cuando el cliente esté listo)

Cuando el cliente Godot implemente el handler para el packet 80 (GuildDetails):

### Paso 1: Modificar LoginCommandHandler

En `src/command_handlers/login_handler.py`, agregar `clan_service` al constructor y enviar el packet:

```python
# En el constructor, agregar:
clan_service: "ClanService | None" = None,

# Y guardar:
self.clan_service = clan_service
```

Luego, en `_finalize_login()`, después de enviar `SHOW_PARTY_FORM`, agregar:

```python
# Enviar detalles del clan si el jugador pertenece a uno (habilitar botón de clan)
if self.clan_service:
    clan = await self.clan_service.clan_repo.get_user_clan(user_id)
    if clan:
        logger.info(
            "Enviando CLAN_DETAILS para habilitar botón CLAN (user_id: %d, clan: %s)",
            user_id,
            clan.name,
        )
        await self.message_sender.send_clan_details(clan)
```

### Paso 2: Modificar TaskFactory

En `src/tasks/task_factory.py`, en `_get_login_handler()`, agregar `clan_service`:

```python
clan_service=self.deps.clan_service,
```

### Paso 3: Verificar

1. El packet `CLAN_DETAILS` (80) ya está implementado en `src/network/msg_clan.py`
2. Los métodos `send_clan_details()` ya existen en `MessageSender` y `SessionMessageSender`
3. Solo falta habilitar el envío cuando el cliente esté listo

---

El formato del packet se describe en la primera parte de esta guía.

