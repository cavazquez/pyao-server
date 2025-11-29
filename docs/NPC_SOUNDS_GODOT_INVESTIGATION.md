# Investigación: Sonidos de NPCs en el Cliente Godot

## 📋 Resumen Ejecutivo

**Conclusión**: El cliente Godot **NO** tiene un sistema automático de sonidos periódicos para NPCs. Todos los sonidos deben ser enviados explícitamente por el servidor mediante el paquete `PlayWave`.

## 🔍 Hallazgos Detallados

### 1. Sistema de Audio del Cliente

**Archivo**: `engine/autoload/audio_manager.gd`

```gdscript
func PlayAudio(waveId:int) -> void:
    if !ResourceLoader.exists("res://Assets/Sfx/%d.wav" % waveId):
        push_error("AudioManager: Audio resource not found: %d" % waveId)
        return
    
    var audioStreamPlayer = AudioStreamPlayer.new()
    add_child(audioStreamPlayer)
    audioStreamPlayer.stream = load("res://Assets/Sfx/%d.wav" % waveId)
    audioStreamPlayer.bus = "sfx"
    audioStreamPlayer.finished.connect(audioStreamPlayer.queue_free)
    audioStreamPlayer.play()
```

- **Funcionamiento**: Simplemente reproduce un archivo WAV cuando se le pasa un `waveId`
- **Ubicación de sonidos**: `Assets/Sfx/[ID].wav`
- **No hay lógica de reproducción automática o periódica**

### 2. Procesamiento del Paquete PlayWave

**Archivo**: `screens/game_screen.gd`

```gdscript
func _HandlePlayWave(p:PlayWave) -> void:
    AudioManager.PlayAudio(p.wave)
```

**Estructura del paquete** (`network/commands/PlayWave.gd`):
```gdscript
var wave:int  # ID del sonido
var x:int     # Posición X (NO SE USA)
var y:int     # Posición Y (NO SE USA)
```

**Observaciones importantes**:
- ✅ El paquete incluye coordenadas `x` y `y`, pero **el cliente las ignora**
- ✅ Solo se usa el campo `wave` (ID del sonido)
- ✅ El sonido se reproduce de forma global, no posicional

### 3. Sonidos Disponibles

**Ubicación**: `Assets/Sfx/`

- Existen múltiples archivos WAV (1.wav, 2.wav, ..., 210.wav, etc.)
- Ejemplo: `103.wav` existe (usado por serpientes según NPCs.dat del VB6)
- Todos los sonidos deben estar en este directorio para que funcionen

### 4. Sonidos Automáticos del Cliente

**Único caso encontrado**: Sonidos de pasos del jugador

**Archivo**: `engine/character/character.gd`

```gdscript
func PlayWalkSound() -> void:
    _pasoDerecho = !_pasoDerecho
    AudioManager.PlayAudio(Consts.Paso1 if _pasoDerecho else Consts.Paso2)
```

- Se reproduce cuando el jugador camina
- **NO hay equivalente para NPCs**
- Los NPCs NO tienen sonidos automáticos

### 5. Efectos Visuales vs Sonidos

**Archivo**: `engine/character/character_effect.gd`

- Los efectos visuales (FX) SÍ tienen sistema de loops infinitos
- Los efectos visuales se pueden configurar para repetirse automáticamente
- **NO hay sistema equivalente para sonidos**

## 💡 Conclusión

### Sonidos Periódicos de NPCs

**No existen en el cliente**. Para implementar sonidos periódicos de NPCs (como víboras haciendo ruidos cada X segundos), hay dos opciones:

#### Opción 1: Servidor envía sonidos periódicamente (RECOMENDADO)
- El servidor debe implementar un sistema de ticks
- Enviar `PlayWave` periódicamente para NPCs que tienen sonidos ambientales
- Ventaja: Control total desde el servidor
- Ejemplo: Cada 10-15 segundos, enviar `PlayWave(103, x, y)` para víboras

#### Opción 2: Modificar el cliente (NO RECOMENDADO - fuera de alcance)
- Agregar lógica de reproducción periódica en el cliente
- Requeriría modificar el código del cliente
- No es viable según las restricciones del proyecto

## 📝 Recomendación de Implementación

### En el Servidor

1. **Agregar campo `ambient_sound` a NPCs** (opcional, para sonidos periódicos)
2. **Agregar campos `snd1`, `snd2`, `snd3`** (sonidos básicos del VB6)
3. **Implementar sistema de sonidos periódicos**:
   - Crear un `TickEffect` para sonidos ambientales
   - Reproducir sonidos cada X segundos para NPCs con `ambient_sound` configurado
   - Solo enviar a jugadores cerca del NPC (usar coordenadas x, y del PlayWave)

### Ejemplo de Flujo

```
1. NPC Serpiente tiene snd2=103 (sonido al recibir daño)
2. Jugador ataca serpiente → Servidor envía PlayWave(103, x, y)
3. Cliente recibe PlayWave → Reproduce 103.wav

4. NPC Víbora tiene ambient_sound=103, ambient_interval=15
5. Cada 15 segundos → Servidor envía PlayWave(103, x, y) a jugadores cercanos
6. Cliente reproduce el sonido
```

## 🔗 Referencias

- `clientes/ArgentumOnlineGodot/engine/autoload/audio_manager.gd`
- `clientes/ArgentumOnlineGodot/screens/game_screen.gd` (línea 766-767)
- `clientes/ArgentumOnlineGodot/network/commands/PlayWave.gd`
- `clientes/ArgentumOnlineGodot/engine/character/character.gd`

