# Guía de Pruebas - Sistema de Clanes

Esta guía te ayudará a probar el sistema de clanes en el juego, primero con un solo jugador y luego con dos.

## 📋 Requisitos Previos

1. **Redis corriendo:**
   ```bash
   # Verificar que Redis está corriendo
   redis-cli ping
   # Debe responder: PONG
   ```

2. **Servidor iniciado:**
   ```bash
   # Desde el directorio del proyecto
   uv run pyao-server
   ```

3. **Cliente conectado:**
   - Conecta tu cliente (Godot o VB6) al servidor
   - Crea o inicia sesión con tu personaje

## 🎮 Pruebas con UN SOLO JUGADOR

### 1. Verificar Comandos Disponibles

```
/AYUDA
```

**Resultado esperado:** Deberías ver la sección "--- Comandos de Clan ---" con todos los comandos listados.

### 2. Verificar Nivel Mínimo

El nivel mínimo para crear un clan es **13**. Si tu personaje es nivel menor:

```
/CREARCLAN MiClan
```

**Resultado esperado:** 
- Mensaje de error: "Debes ser nivel 13 o superior para crear un clan"

**Solución:** 
- Sube de nivel matando NPCs
- O modifica temporalmente `MIN_LEVEL_TO_CREATE` en `src/models/clan.py` para testing

### 3. Crear un Clan (Nivel 13+)

```
/CREARCLAN MiClan
```

**Resultado esperado:**
- Mensaje: "Clan 'MiClan' creado exitosamente" (en color verde/party)

**Verificar:**
- Deberías ser el líder del clan
- El clan debería tener tu nombre como líder

### 4. Intentar Crear Otro Clan

```
/CREARCLAN OtroClan
```

**Resultado esperado:**
- Mensaje de error: "Ya perteneces a un clan. Abandónalo primero con /SALIRCLAN"

### 5. Intentar Invitar a Ti Mismo

```
/INVITARCLAN TuNombre
```

**Resultado esperado:**
- Mensaje de error: "No puedes invitarte a ti mismo"

### 6. Abandonar el Clan

```
/SALIRCLAN
```

**Resultado esperado:**
- Mensaje: "Abandonaste el clan 'MiClan'" o similar

**Nota:** Como eres el líder, el clan debería eliminarse automáticamente.

### 7. Crear Clan con Descripción

```
/CREARCLAN MiClan2 Esta es mi descripción del clan
```

**Resultado esperado:**
- Clan creado con descripción

### 8. Intentar Aceptar Invitación Sin Tener Una

```
/ACEPTARCLAN
```

**Resultado esperado:**
- Mensaje de error: "No tienes invitaciones pendientes" o similar

### 9. Intentar Rechazar Invitación Sin Tener Una

```
/RECHAZARCLAN
```

**Resultado esperado:**
- Mensaje de error: "No tienes invitaciones pendientes" o similar

### 10. Intentar Expulsar Sin Estar en Clan

```
/EXPULSARCLAN Alguien
```

**Resultado esperado:**
- Mensaje de error: "No perteneces a un clan"

## 👥 Pruebas con DOS JUGADORES

### Preparación

1. **Jugador 1 (Líder):**
   - Nivel 13+ (mínimo para crear clan)
   - Crea un clan: `/CREARCLAN MiClan`

2. **Jugador 2 (Invitado):**
   - Nivel 1+ (mínimo para unirse)
   - Conectado al mismo servidor

### 1. Invitar al Jugador 2

**Jugador 1 ejecuta:**
```
/INVITARCLAN NombreJugador2
```

**Resultado esperado:**
- Jugador 1: "Invitación enviada a NombreJugador2"
- Jugador 2: Debería recibir una notificación (si está implementada) o simplemente poder aceptar

### 2. Aceptar Invitación

**Jugador 2 ejecuta:**
```
/ACEPTARCLAN
```

**Resultado esperado:**
- Jugador 2: "Te uniste al clan 'MiClan'"
- Jugador 2 ahora es miembro del clan con rango MEMBER

### 3. Verificar Miembros

**Jugador 1 ejecuta:**
```
/CLAN
```

**Resultado esperado:**
- Lista de miembros del clan (si el comando está implementado)
- O simplemente verificar que ambos están en el mismo clan

### 4. Intentar Invitar de Nuevo

**Jugador 1 ejecuta:**
```
/INVITARCLAN NombreJugador2
```

**Resultado esperado:**
- Mensaje de error: "El usuario ya pertenece a un clan"

### 5. Expulsar Miembro

**Jugador 1 (Líder) ejecuta:**
```
/EXPULSARCLAN NombreJugador2
```

**Resultado esperado:**
- Jugador 1: "NombreJugador2 fue expulsado del clan"
- Jugador 2: Debería recibir notificación (si está implementada)

### 6. Intentar Expulsar Como Miembro (No Líder)

**Jugador 2 ejecuta (si aún está en el clan):**
```
/EXPULSARCLAN NombreJugador1
```

**Resultado esperado:**
- Mensaje de error: "Solo los oficiales pueden expulsar miembros"

### 7. Re-invitar y Aceptar

**Jugador 1:**
```
/INVITARCLAN NombreJugador2
```

**Jugador 2:**
```
/ACEPTARCLAN
```

### 8. Abandonar Clan (Miembro)

**Jugador 2 ejecuta:**
```
/SALIRCLAN
```

**Resultado esperado:**
- Jugador 2: "Abandonaste el clan 'MiClan'"
- Jugador 2 ya no pertenece al clan

### 9. Intentar Expulsar Como Líder Único

**Jugador 1 ejecuta:**
```
/EXPULSARCLAN NombreJugador1
```

**Resultado esperado:**
- Mensaje de error: "No puedes expulsarte a ti mismo. Usa /SALIRCLAN para disolver el clan"

### 10. Disolver Clan (Líder Abandona)

**Jugador 1 ejecuta:**
```
/SALIRCLAN
```

**Resultado esperado:**
- Mensaje: "Abandonaste el clan 'MiClan'. El clan fue disuelto porque eras el líder"

## 🔍 Verificación en Redis (Opcional)

Si quieres verificar que los datos se guardan correctamente en Redis:

```bash
# Conectar a Redis
redis-cli

# Ver todos los clanes
KEYS clan:*

# Ver un clan específico
GET clan:1

# Ver miembros de un clan
HGETALL clan:1:members

# Ver invitaciones
KEYS invitation:*
```

## 🐛 Problemas Comunes

### "Sistema de clanes no disponible"
- **Causa:** El `ClanService` no se inicializó correctamente
- **Solución:** Verifica los logs del servidor al iniciar. Debería aparecer "✓ Servicio de clanes inicializado"

### "Usuario no encontrado" al invitar
- **Causa:** El nombre del jugador no existe o está offline
- **Solución:** Verifica que el jugador esté conectado y que el nombre sea exacto (case-sensitive)

### "Debes ser nivel X" pero tienes el nivel correcto
- **Causa:** Los stats no se cargaron correctamente
- **Solución:** Usa `/EST` para verificar tu nivel actual

### Comandos no funcionan
- **Causa:** El comando no se parsea correctamente
- **Solución:** 
  - Verifica que no haya espacios extra
  - Usa exactamente: `/CREARCLAN Nombre` (sin espacios antes de `/`)
  - Revisa los logs del servidor para ver errores

## 📝 Checklist de Funcionalidades

### Con un Jugador:
- [ ] Ver comandos en /AYUDA
- [ ] Error al crear clan con nivel bajo (< 13)
- [ ] Crear clan exitosamente (nivel 13+)
- [ ] Error al crear segundo clan
- [ ] Error al invitarse a sí mismo
- [ ] Abandonar clan
- [ ] Crear clan con descripción
- [ ] Error al aceptar sin invitación
- [ ] Error al rechazar sin invitación
- [ ] Error al expulsar sin estar en clan

### Con dos Jugadores:
- [ ] Invitar jugador
- [ ] Aceptar invitación
- [ ] Error al invitar de nuevo
- [ ] Expulsar miembro (como líder)
- [ ] Error al expulsar (como miembro)
- [ ] Abandonar clan (como miembro)
- [ ] Error al expulsarse a sí mismo
- [ ] Disolver clan (líder abandona)

## 🎯 Próximos Pasos

Una vez que todas las pruebas básicas pasen, puedes probar:
- Sistema de rangos (promover/degradar miembros)
- Transferir liderazgo
- Chat interno del clan (cuando esté implementado)
- Alianzas y guerras (cuando estén implementadas)

