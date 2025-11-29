# Análisis de Sonidos de NPCs

## 📋 Resumen

Los NPCs en Argentum Online tienen hasta 3 tipos de sonidos diferentes que se reproducen en momentos específicos.

## 🔊 Sonidos de NPCs

### 1. Snd1 - Sonido de Ataque
- **Cuándo**: Se reproduce cuando el NPC ataca a un jugador
- **Ubicación en VB6**: `SistemaCombate.bas` línea 699, 813
- **Ejemplo**: Un Goblin haciendo su grito de ataque

### 2. Snd2 - Sonido al Recibir Daño
- **Cuándo**: Se reproduce cuando el NPC recibe daño (de jugador o de otro NPC)
- **Ubicación en VB6**: `SistemaCombate.bas` línea 829, 868
- **Ejemplo**: Una Serpiente hace `SND2=103` cuando recibe daño

### 3. Snd3 - Sonido al Morir
- **Cuándo**: Se reproduce cuando el NPC muere (solo si fue matado por un jugador)
- **Ubicación en VB6**: `MODULO_NPCs.bas` línea 106-107
- **Ejemplo**: Sonido de muerte característico del NPC

## 📊 Estructura en NPCs.dat

```
[NPC505]
Name=Goblin
...
Snd1=47    # Sonido de ataque (opcional)
Snd2=103   # Sonido al recibir daño (opcional)
Snd3=62    # Sonido al morir (opcional)
```

## 🔍 Observaciones

### Sonidos Periódicos
- **Problema**: El usuario menciona que NPCs (víboras, etc.) hacen ruidos característicos cada tanto segundos
- **Estado**: No encontré evidencia directa en el código del servidor VB6 de sonidos periódicos automáticos
- **Posibles causas**:
  1. Puede ser algo manejado por el cliente (reproducción automática)
  2. Puede requerir implementación propia basada en timers
  3. Puede estar relacionado con el movimiento del NPC (cuando se mueve hace sonido)

### Sonidos de Serpientes
- En `NPCs.dat`, la Serpiente (NPC 504) tiene `SND2=103`
- Este sonido se reproduce cuando recibe daño
- Para sonidos periódicos, necesitamos investigar más o implementar un sistema

## 💡 Plan de Implementación

### Fase 1: Sonidos Básicos (Implementar ahora)
1. ✅ Agregar campos `snd1`, `snd2`, `snd3` al modelo NPC
2. ✅ Cargar estos campos desde `NPCs.dat` o TOML
3. ✅ Reproducir `Snd1` cuando el NPC ataca
4. ✅ Reproducir `Snd2` cuando el NPC recibe daño
5. ✅ Reproducir `Snd3` cuando el NPC muere

### Fase 2: Sonidos Periódicos (Investigar/Implementar)
1. ⏳ Investigar si el cliente maneja sonidos periódicos
2. ⏳ Implementar sistema de sonidos periódicos si es necesario
3. ⏳ Configurar intervalos por tipo de NPC

## 📝 Referencias

- `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/SistemaCombate.bas`
- `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/MODULO_NPCs.bas`
- `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Dat/NPCs.dat`

