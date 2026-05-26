# Sistema de Movimiento de Personajes

Documentación completa del sistema de movimiento de personajes en PyAO Server.

## Visión General

El sistema de movimiento es un proceso colaborativo entre cliente (Godot) y servidor (Python). El cliente maneja validación local y animación, mientras el servidor es la autoridad final sobre posiciones y maneja el broadcast.

## Componentes Principales

**Cliente (Godot):**
- `game_screen.gd::_MovePlayer()` - Input del jugador
- `game_screen.gd::_CanMoveTo()` - Validación local
- `GameProtocol.WriteWalk()` - Envía WALK al servidor

**Servidor (Python):**
- `task_walk.py::TaskWalk` - Procesa WALK
- `map_manager.py` - Índice espacial
- `multiplayer_broadcast_service.py` - Broadcast

## Paquetes del Protocolo

### WALK (ClientPacketID = 6)
- Cliente → Servidor
- Formato: PacketID (1) + Heading (1)

### CHARACTER_MOVE (ServerPacketID = 32)
- Servidor → Cliente
- Formato: PacketID (1) + CharIndex (2) + X (1) + Y (1)
- ⚠️ NO incluye heading (compatibilidad Godot)

### CHARACTER_CHANGE (ServerPacketID = 34)
- Servidor → Cliente
- Incluye: body, head, heading, armas, etc.

### POS_UPDATE (ServerPacketID = 22)
- Servidor → Cliente
- NO se envía al jugador que se movió

## Problemas y Soluciones

### Problema 1: Bug de Parsing CHARACTER_MOVE

**Síntoma:** Cliente recibía NAVIGATE_TOGGLE falsos

**Causa:** Servidor enviaba 6 bytes (con heading), cliente leía 5. El byte extra se interpretaba como PacketID.

**Solución:** Eliminar heading de CHARACTER_MOVE, enviarlo en CHARACTER_CHANGE

### Problema 2: Saltos Visuales

**Síntoma:** Personaje "saltaba" al moverse

**Causa:** Servidor enviaba POS_UPDATE al jugador que se movió

**Solución:** NO enviar POS_UPDATE al jugador que se movió

### Problema 3: Heading Hardcodeado

**Síntoma:** Siempre miraba al Sur al login

**Solución:** Leer desde Redis: `position.get("heading", 3)`

### Problema 4: Body/Head Hardcodeados

**Síntoma:** Todos se veían iguales

**Solución:** Leer desde AccountRepository

### Problema 5: Minimapa Vacío

**Síntoma:** Minimapa no se actualizaba al login

**Solución:** Enviar POS_UPDATE después de CHARACTER_CREATE

## Optimizaciones

### 1. Índice Espacial
- Validación O(1) en memoria
- Redis solo para persistencia

### 2. Broadcast por Rango
- Solo envía a jugadores en 15 tiles
- Distancia de Chebyshev

### 3. Caché de Username
- Username en MapManager
- Sin consultas a Redis

## Archivos Relevantes

**Servidor:**
- `src/task_walk.py`
- `src/map_manager.py`
- `src/multiplayer_broadcast_service.py`

**Cliente:**
- `screens/game_screen.gd`
- `network/commands/CharacterMove.gd`

**Tests:**
- `tests/test_task_walk.py`
- `tests/test_broadcast_movement.py`

---

**Versión:** 0.2.0-alpha  
**Tests:** 380 pasando
