# TODOs del Cliente Godot

Lista de mejoras y funcionalidades que deben implementarse en el cliente Godot.

## 🔴 Alta Prioridad

### 1. Mostrar Posición del Jugador en GUI
**Descripción:** La GUI debería mostrar la posición actual del jugador (X, Y, Mapa) en tiempo real.

**Beneficios:**
- Facilita debugging
- Ayuda en testing
- Útil para reportar bugs
- Permite verificar sincronización con servidor

**Implementación Sugerida:**
```gdscript
# En HUD o Debug Panel
Label: "Pos: (50, 50) Mapa: 1"
```

**Ubicación en Cliente:**
- `ui/hub/hub_controller.gd` - Actualizar en cada movimiento
- Packet `POS_UPDATE` ya envía la posición
- Solo falta mostrarla en UI

**Prioridad:** Alta - Muy útil para testing

---

## 🟡 Media Prioridad

### 2. Indicador Visual de Ground Items
**Descripción:** Mejorar visualización de items en el suelo.

**Sugerencias:**
- Highlight cuando el jugador está sobre un item
- Tooltip mostrando nombre y cantidad
- Animación de brillo para items raros

### 3. Feedback de Acciones
**Descripción:** Mejorar feedback visual/sonoro de acciones.

**Acciones que necesitan feedback:**
- Recoger item (sonido + animación)
- Tirar item (sonido + animación)
- Atacar (efecto visual mejorado)
- Recibir daño (screen shake, efecto rojo)

### 4. Panel de Inventario
**Descripción:** Implementar UI de inventario completa.

**Funcionalidades:**
- Mostrar items con iconos
- Drag & drop para reorganizar
- Click derecho para usar/equipar
- Tooltip con stats del item

---

## 🟢 Baja Prioridad

### 5. Minimapa
**Descripción:** Mostrar minimapa con posición del jugador.

### 6. Panel de Stats Detallado
**Descripción:** Mostrar todos los stats del jugador.

**Stats a mostrar:**
- HP, Mana, Stamina (ya implementado)
- Hambre, Sed (ya implementado)
- Nivel, Experiencia
- Oro
- Atributos (Fuerza, Agilidad, etc.)

### 7. Chat Mejorado
**Descripción:** Mejorar sistema de chat.

**Mejoras:**
- Historial de mensajes
- Diferentes colores por tipo
- Comandos con autocompletado
- Filtros de mensajes

---

## 📋 Checklist de Testing

### Posición del Jugador
- [ ] Mostrar X, Y en GUI
- [ ] Mostrar ID del mapa
- [ ] Actualizar en tiempo real al moverse
- [ ] Formato claro y legible

### Ground Items
- [ ] Oro se muestra correctamente
- [ ] Oro desaparece al recogerlo
- [ ] Oro aparece al tirarlo
- [ ] Múltiples items en mismo tile

### Feedback Visual
- [ ] Animación al recoger
- [ ] Animación al tirar
- [ ] Sonidos de acciones
- [ ] Efectos de combate

---

## 🔗 Referencias

**Archivos Relevantes del Cliente:**
- `ui/hub/hub_controller.gd` - Controlador principal del HUD
- `engine/autoload/game_protocol.gd` - Manejo de packets
- `common/enums/enums.gd` - Enums y constantes

**Packets del Servidor:**
- `POS_UPDATE` (ID 5) - Actualización de posición
- `OBJECT_CREATE` (ID 35) - Crear item en suelo
- `OBJECT_DELETE` (ID 36) - Remover item del suelo
- `UPDATE_USER_STATS` (ID 6) - Actualizar stats (incluye oro)

---

## 📝 Notas

**Fecha de Creación:** 2025-10-17

**Prioridad General:**
1. Posición en GUI (debugging crítico)
2. Feedback de acciones (UX)
3. Inventario completo (gameplay)
4. Features adicionales (polish)

**Coordinación con Servidor:**
- Servidor ya envía toda la información necesaria
- Cliente solo necesita mostrarla en UI
- No requiere cambios en protocolo
