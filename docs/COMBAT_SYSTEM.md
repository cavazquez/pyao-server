# Sistema de Combate - PyAO Server

Sistema completo de combate jugador vs NPC con cálculo de daño, experiencia y loot.

## 📋 Tabla de Contenidos

- [Arquitectura](#arquitectura)
- [Flujo de Combate](#flujo-de-combate)
- [Cálculo de Daño](#cálculo-de-daño)
- [Sistema de Experiencia](#sistema-de-experiencia)
- [Sistema de Loot](#sistema-de-loot)
- [Packets](#packets)
- [TODOs](#todos)

## 🏗️ Arquitectura

### Componentes Principales

```
TaskAttack (Packet Handler)
    ↓
CombatService (Lógica de combate)
    ↓
PlayerRepository / NPCRepository (Persistencia)
    ↓
MessageSender (Notificaciones al cliente)
```

### Archivos Clave

- `src/task_attack.py` - Handler del packet ATTACK (ID 8)
- `src/combat_service.py` - Lógica de combate y cálculo de daño
- `src/npc.py` - Modelo de NPC
- `src/player_repository.py` - Persistencia de jugadores
- `src/npc_repository.py` - Persistencia de NPCs

## 🎮 Flujo de Combate

### 1. Jugador Ataca

```python
# Cliente envía packet ATTACK (ID 8)
# Sin parámetros - ataca en la dirección que mira
```

### 2. Validaciones

```python
# TaskAttack.execute()
1. Verificar que el jugador esté logueado
2. Obtener posición del jugador
3. Calcular tile objetivo según dirección (heading)
4. Buscar NPC en ese tile
5. Verificar que el NPC sea atacable
```

### 3. Cálculo de Daño

```python
# CombatService.player_attack_npc()
1. Obtener stats del jugador
2. Obtener arma equipada (si tiene)
3. Calcular daño base (fuerza / 2)
4. Sumar daño del arma
5. Aplicar reducción por defensa del NPC (10% por nivel)
6. Calcular crítico (5% chance, 1.5x daño)
7. Aplicar daño al NPC
```

### 4. Resultado

```python
if NPC murió:
    - Calcular experiencia (nivel * 10 + bonus)
    - Calcular oro (nivel * 5 + bonus 1-50)
    - Dar experiencia al jugador
    - Dropear oro en el suelo (TODO)
    - Remover NPC del mapa
    - Enviar CHARACTER_REMOVE
else:
    - Mostrar HP restante del NPC
    - NPC contraataca (TODO)
```

## ⚔️ Cálculo de Daño

### Daño del Jugador → NPC

```python
# Daño base
base_damage = strength // 2

# Daño del arma (según item equipado)
weapon_damage = get_weapon_damage(user_id)
# - Sin arma (puños): 2
# - Espada Larga (ID 2): 15
# - Hacha (ID 3): 12

# Daño total antes de defensa
total_damage = base_damage + weapon_damage

# Reducción por defensa del NPC
defense_reduction = npc.level * 0.1
damage_after_defense = total_damage * (1 - defense_reduction)

# Crítico (5% chance)
if is_critical:
    damage_after_defense *= 1.5

# Daño mínimo
final_damage = max(1, damage_after_defense)
```

### Ejemplo con Fuerza 10

| Arma | Daño Base | Daño Arma | Total | vs NPC Lvl 5 | Crítico |
|------|-----------|-----------|-------|--------------|---------|
| Puños | 5 | 2 | 7 | 3 | 5 |
| Espada Larga | 5 | 15 | 20 | 10 | 15 |
| Hacha | 5 | 12 | 17 | 8 | 13 |

### Daño del NPC → Jugador

```python
# Daño base del NPC
base_damage = npc.level * 2

# Bonus aleatorio
bonus = random.randint(0, npc.level)

# Daño total
total_damage = base_damage + bonus

# TODO: Reducción por armadura del jugador
# TODO: Esquive basado en agilidad
```

## 📈 Sistema de Experiencia

### Cálculo

```python
# Experiencia otorgada por NPC
base_exp = npc_level * 10
bonus = random.randint(0, npc_level * 2)
experience = base_exp + bonus
```

### Ejemplos

| Nivel NPC | EXP Base | Bonus | Total Aprox |
|-----------|----------|-------|-------------|
| 1 | 10 | 0-2 | 10-12 |
| 5 | 50 | 0-10 | 50-60 |
| 10 | 100 | 0-20 | 100-120 |
| 20 | 200 | 0-40 | 200-240 |

### Flujo

1. NPC muere
2. Se calcula experiencia
3. Se suma a la experiencia actual del jugador
4. Se guarda en Redis
5. Se envía packet UPDATE_EXP (ID 20) al cliente
6. Cliente actualiza barra de experiencia

### Packets

```python
# UPDATE_EXP (ID 20)
packet.add_byte(20)
packet.add_int32(experience)  # Experiencia total
```

## 💰 Sistema de Loot

### Estado Actual

✅ **Implementado:**
- Cálculo de oro dropeado
- Experiencia se da directamente

⏳ **En Progreso:**
- Oro se dropea en el suelo (calculado pero no visible)
- Items se dropean según tabla de loot

❌ **Pendiente:**
- Ground items en MapManager
- Packet OBJECT_CREATE para mostrar items
- Packet PICKUP para recoger items

### Cálculo de Oro

```python
# Oro dropeado por NPC
base_gold = npc_level * 5
bonus = random.randint(1, 50)
gold = base_gold + bonus
```

### Ejemplos

| Nivel NPC | Oro Base | Bonus | Total Aprox |
|-----------|----------|-------|-------------|
| 1 | 5 | 1-50 | 6-55 |
| 5 | 25 | 1-50 | 26-75 |
| 10 | 50 | 1-50 | 51-100 |
| 20 | 100 | 1-50 | 101-150 |

### Flujo Planeado

```python
# Cuando NPC muere
1. Calcular oro y items
2. Crear ground item en tile donde murió
3. Agregar a MapManager._ground_items[(map_id, x, y)]
4. Enviar OBJECT_CREATE a jugadores cercanos
5. Cliente muestra item en el suelo

# Cuando jugador recoge
1. Cliente envía PICKUP (sin parámetros)
2. Servidor busca items en tile del jugador
3. Agregar item/oro al inventario
4. Remover de ground items
5. Enviar OBJECT_DELETE a jugadores cercanos
6. Actualizar inventario del jugador
```

## 📦 Packets

### Cliente → Servidor

#### ATTACK (ID 8)
```python
# Sin parámetros
# Ataca en la dirección que mira el jugador
packet.add_byte(8)
```

#### PICKUP (ID 316) - TODO
```python
# Sin parámetros
# Recoge item del tile donde está el jugador
packet.add_byte(316)
```

### Servidor → Cliente

#### UPDATE_EXP (ID 20)
```python
packet.add_byte(20)
packet.add_int32(experience)  # Experiencia total
```

#### CHARACTER_REMOVE (ID 30)
```python
packet.add_byte(30)
packet.add_int16(char_index)  # Índice del personaje
```

#### OBJECT_CREATE (ID 35) - TODO
```python
packet.add_byte(35)
packet.add_byte(x)
packet.add_byte(y)
packet.add_int16(grh_index)  # Gráfico del item
```

#### OBJECT_DELETE (ID 36) - TODO
```python
packet.add_byte(36)
packet.add_byte(x)
packet.add_byte(y)
```

## 📝 TODOs

### Alta Prioridad

- [ ] **Ground Items System**
  - Implementar `_ground_items` en MapManager
  - Estructura: `{(map_id, x, y): [Item, Item, ...]}`
  - Métodos: `add_ground_item()`, `get_ground_items()`, `remove_ground_item()`

- [ ] **Packet OBJECT_CREATE**
  - Mostrar items en el suelo
  - Enviar a jugadores cercanos cuando se dropea

- [ ] **Packet PICKUP**
  - TaskPickup para manejar el packet
  - Recoger item del tile del jugador
  - Agregar al inventario
  - Enviar OBJECT_DELETE

- [ ] **NPC Contraataca**
  - NPC ataca de vuelta cuando recibe daño
  - Cooldown entre ataques (2-3 segundos)
  - Usar `CombatService.npc_attack_player()`

- [ ] **Sistema de Nivel**
  - Tabla de experiencia por nivel
  - Verificar level up al ganar experiencia
  - Packet LEVEL_UP (ID 63)
  - Aumentar stats al subir nivel

### Media Prioridad

- [ ] **Catálogo de Items**
  - JSON con todos los items del juego
  - Propiedades: daño, defensa, tipo, precio, etc.
  - Reemplazar valores hardcodeados en `_get_weapon_damage()`

- [ ] **Tabla de Loot**
  - Definir qué items dropea cada NPC
  - Probabilidades de drop
  - Cantidad mínima/máxima

- [ ] **Reducción por Armadura**
  - Obtener armadura equipada
  - Calcular reducción de daño
  - Aplicar en `npc_attack_player()`

- [ ] **Sistema de Respawn**
  - Timer de respawn configurable por NPC
  - Respawn en posición original
  - Restaurar HP completo

### Baja Prioridad

- [ ] **Esquive**
  - Chance de esquivar basado en agilidad
  - Mensaje "¡Esquivaste el ataque!"
  - Sonido de esquive

- [ ] **Críticos del NPC**
  - NPCs también pueden hacer críticos
  - Chance basada en nivel

- [ ] **Combate PvP**
  - Jugador vs Jugador
  - Flags de seguro/criminal
  - Penalizaciones por matar ciudadanos

- [ ] **Skills de Combate**
  - Apuñalar (backstab)
  - Golpe mortal
  - Desarmar

## 🧪 Testing

### Tests Actuales

```bash
# Ejecutar tests
./run_tests.sh

# Tests: 374 pasando
```

### Tests Necesarios

- [ ] Test de cálculo de daño con diferentes armas
- [ ] Test de críticos (probabilidad)
- [ ] Test de experiencia por nivel
- [ ] Test de oro dropeado
- [ ] Test de muerte de NPC
- [ ] Test de ground items (cuando se implemente)
- [ ] Test de PICKUP (cuando se implemente)

## 📊 Estadísticas

### Código

- **CombatService**: ~340 líneas
- **TaskAttack**: ~194 líneas
- **Tests**: 374 pasando
- **Cobertura**: Básica (sin tests específicos de combate aún)

### Rendimiento

- Cálculo de daño: ~1ms
- Consulta de arma equipada: ~2-3ms (Redis)
- Total por ataque: ~5-10ms

## 🔗 Referencias

- [Cliente Godot - Item.gd](../clientes/ArgentumOnlineGodot/common/data/Item.gd)
- [Cliente Godot - GameProtocol.gd](../clientes/ArgentumOnlineGodot/engine/autoload/game_protocol.gd)
- [GAME_TICK_SYSTEM.md](./GAME_TICK_SYSTEM.md)
- [TODO.md](../TODO.md)

## 📜 Changelog

### 2025-10-16
- ✅ Implementado sistema de combate básico
- ✅ Daño basado en arma equipada
- ✅ Sistema de experiencia con UPDATE_EXP
- ✅ Cálculo de oro dropeado
- ✅ NPCs desaparecen al morir (CHARACTER_REMOVE)
- ⏳ Ground items en progreso

### Próxima Sesión
- [ ] Implementar ground items
- [ ] Packet PICKUP
- [ ] NPC contraataca
