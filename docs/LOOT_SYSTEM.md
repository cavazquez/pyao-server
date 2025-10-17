# Sistema de Loot - PyAO Server

Sistema de drops de oro e items al matar NPCs, con ground items y sistema de recogida.

## 📋 Tabla de Contenidos

- [Estado Actual](#estado-actual)
- [Arquitectura](#arquitectura)
- [Flujo de Loot](#flujo-de-loot)
- [Ground Items](#ground-items)
- [Packets](#packets)
- [Configuración](#configuración)
- [TODOs](#todos)
- [Referencias](#referencias)

## 🎯 Estado Actual

### ✅ Implementado

- **Cálculo de oro dropeado**
  - Fórmula: `nivel * 5 + random(1, 50)`
  - Se calcula cuando el NPC muere
  - Se retorna en el resultado del combate

- **Experiencia directa**
  - Se da automáticamente al jugador
  - Packet UPDATE_EXP enviado al cliente
  - No requiere recoger

### ⏳ En Progreso

- **Oro en el suelo**
  - Se calcula pero no se muestra
  - Falta crear ground item
  - Falta packet OBJECT_CREATE

### ❌ Pendiente

- **Ground Items System**
  - Estructura de datos en MapManager
  - Métodos para agregar/quitar items
  - Persistencia en Redis (opcional)

- **Packet OBJECT_CREATE**
  - Mostrar items en el suelo
  - Enviar a jugadores cercanos

- **Packet PICKUP**
  - TaskPickup para manejar recogida
  - Validaciones (inventario lleno, etc.)
  - Packet OBJECT_DELETE

- **Tabla de Loot**
  - Definir qué items dropea cada NPC
  - Probabilidades de drop
  - Cantidad mínima/máxima

## 🏗️ Arquitectura

### Componentes Actuales

```
CombatService
    ↓ (calcula oro)
TaskAttack
    ↓ (log de oro dropeado)
[FALTA: Ground Items]
    ↓
[FALTA: OBJECT_CREATE]
    ↓
Cliente (muestra item en suelo)
```

### Componentes Planeados

```
CombatService
    ↓ (calcula oro/items)
TaskAttack
    ↓ (crea ground item)
MapManager._ground_items
    ↓ (almacena items)
MultiplayerBroadcastService
    ↓ (OBJECT_CREATE)
Cliente (muestra item)
    ↓ (jugador presiona tecla)
TaskPickup (PICKUP packet)
    ↓ (recoge item)
InventoryRepository
    ↓ (agrega al inventario)
MultiplayerBroadcastService
    ↓ (OBJECT_DELETE)
Cliente (remueve item del suelo)
```

## 🎮 Flujo de Loot

### 1. NPC Muere

```python
# CombatService.player_attack_npc()
if npc_died:
    experience = self._calculate_experience(npc.level)
    gold = self._calculate_gold_drop(npc.level)
    
    result["experience"] = experience
    result["gold"] = gold  # Para dropear en el suelo
    
    # Experiencia se da directamente
    await self._give_experience(user_id, experience, message_sender)
    
    # Oro se debe dropear en el suelo (TODO)
```

### 2. Crear Ground Item (TODO)

```python
# TaskAttack.execute() - después de matar NPC
if npc_died:
    gold = result.get("gold", 0)
    
    # Crear item de oro en el suelo
    ground_item = {
        "item_id": GOLD_ITEM_ID,  # ID del item oro (ej: 12)
        "quantity": gold,
        "grh_index": GOLD_GRH_INDEX,  # Gráfico del oro
    }
    
    # Agregar a MapManager
    self.map_manager.add_ground_item(
        map_id=target_npc.map_id,
        x=target_npc.x,
        y=target_npc.y,
        item=ground_item
    )
    
    # Broadcast OBJECT_CREATE
    await self.broadcast_service.broadcast_object_create(
        map_id=target_npc.map_id,
        x=target_npc.x,
        y=target_npc.y,
        grh_index=GOLD_GRH_INDEX
    )
```

### 3. Jugador Recoge (TODO)

```python
# Cliente envía PICKUP (sin parámetros)
# TaskPickup.execute()

# Obtener posición del jugador
position = await self.player_repo.get_position(user_id)

# Buscar items en ese tile
items = self.map_manager.get_ground_items(
    map_id=position["map"],
    x=position["x"],
    y=position["y"]
)

if not items:
    await self.message_sender.send_console_msg("No hay nada aquí.")
    return

# Recoger primer item
item = items[0]

# Validar inventario
if await self.inventory_repo.is_full(user_id):
    await self.message_sender.send_console_msg("Inventario lleno.")
    return

# Agregar al inventario
await self.inventory_repo.add_item(user_id, item["item_id"], item["quantity"])

# Remover del suelo
self.map_manager.remove_ground_item(
    map_id=position["map"],
    x=position["x"],
    y=position["y"],
    item_index=0
)

# Broadcast OBJECT_DELETE
await self.broadcast_service.broadcast_object_delete(
    map_id=position["map"],
    x=position["x"],
    y=position["y"]
)

# Notificar al jugador
await self.message_sender.send_console_msg(f"Recogiste {item['quantity']} oro.")
```

## 🗄️ Ground Items

### Estructura de Datos (Planeada)

```python
# En MapManager
class MapManager:
    def __init__(self):
        # Estructura: {(map_id, x, y): [Item, Item, ...]}
        self._ground_items: dict[tuple[int, int, int], list[dict]] = {}
```

### Item en el Suelo

```python
{
    "item_id": int,        # ID del item en el catálogo
    "quantity": int,       # Cantidad (oro, flechas, etc.)
    "grh_index": int,      # Índice gráfico para mostrar
    "owner_id": int | None,  # Dueño temporal (anti-loot steal)
    "spawn_time": float,   # Timestamp de cuando se dropeó
}
```

### Métodos Necesarios

```python
class MapManager:
    def add_ground_item(
        self, map_id: int, x: int, y: int, item: dict
    ) -> None:
        """Agrega un item al suelo."""
        key = (map_id, x, y)
        if key not in self._ground_items:
            self._ground_items[key] = []
        self._ground_items[key].append(item)
    
    def get_ground_items(
        self, map_id: int, x: int, y: int
    ) -> list[dict]:
        """Obtiene items en un tile."""
        key = (map_id, x, y)
        return self._ground_items.get(key, [])
    
    def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> dict | None:
        """Remueve un item del suelo."""
        key = (map_id, x, y)
        if key not in self._ground_items:
            return None
        
        items = self._ground_items[key]
        if item_index >= len(items):
            return None
        
        item = items.pop(item_index)
        
        # Limpiar si no quedan items
        if not items:
            del self._ground_items[key]
        
        return item
    
    def clear_ground_items(self, map_id: int) -> None:
        """Limpia todos los items de un mapa."""
        keys_to_remove = [
            key for key in self._ground_items.keys()
            if key[0] == map_id
        ]
        for key in keys_to_remove:
            del self._ground_items[key]
```

## 📦 Packets

### Cliente → Servidor

#### PICKUP (ID 316)
```python
# Sin parámetros
# Recoge item del tile donde está el jugador
packet.add_byte(316)
```

#### DROP (ID 331)
```python
# Tirar item del inventario al suelo
packet.add_byte(331)
packet.add_byte(slot)        # Slot del inventario
packet.add_int16(quantity)   # Cantidad a tirar
```

### Servidor → Cliente

#### OBJECT_CREATE (ID 35)
```python
# Mostrar item en el suelo
packet.add_byte(35)
packet.add_byte(x)
packet.add_byte(y)
packet.add_int16(grh_index)  # Gráfico del item
```

#### OBJECT_DELETE (ID 36)
```python
# Remover item del suelo
packet.add_byte(36)
packet.add_byte(x)
packet.add_byte(y)
```

#### CHANGE_INVENTORY_SLOT (ID 13)
```python
# Actualizar slot del inventario
packet.add_byte(13)
packet.add_byte(slot)
packet.add_int16(obj_id)
packet.add_string(name)
packet.add_int16(quantity)
packet.add_int16(grh_index)
packet.add_byte(obj_type)
packet.add_int16(max_hit)
packet.add_int16(min_hit)
packet.add_int16(max_def)
packet.add_int16(min_def)
packet.add_int32(value)
packet.add_byte(equipped)  # 1 si está equipado
```

## ⚙️ Configuración

### Oro Dropeado

```python
# Fórmula actual
base_gold = npc_level * 5
bonus = random.randint(1, 50)
gold = base_gold + bonus
```

### Ejemplos por Nivel

| Nivel NPC | Oro Base | Bonus | Total Aprox |
|-----------|----------|-------|-------------|
| 1 | 5 | 1-50 | 6-55 |
| 5 | 25 | 1-50 | 26-75 |
| 10 | 50 | 1-50 | 51-100 |
| 20 | 100 | 1-50 | 101-150 |
| 50 | 250 | 1-50 | 251-300 |

### Tabla de Loot (Planeada)

```python
# En npc_catalog.json o loot_tables.json
{
    "goblin": {
        "gold": {
            "min": 10,
            "max": 50,
            "chance": 100  # 100% de dropear oro
        },
        "items": [
            {
                "item_id": 2,  # Espada Larga
                "quantity": 1,
                "chance": 5    # 5% de drop
            },
            {
                "item_id": 1,  # Manzana
                "quantity": [1, 3],  # 1-3 manzanas
                "chance": 30   # 30% de drop
            }
        ]
    }
}
```

## 📝 TODOs

### Alta Prioridad

- [ ] **Ground Items en MapManager**
  - Implementar `_ground_items: dict[tuple[int, int, int], list[dict]]`
  - Métodos: `add_ground_item()`, `get_ground_items()`, `remove_ground_item()`
  - Límite de items por tile (ej: máximo 10)

- [ ] **Packet OBJECT_CREATE**
  - `build_object_create_response(x, y, grh_index)`
  - `send_object_create()` en MessageSender
  - `broadcast_object_create()` en MultiplayerBroadcastService

- [ ] **Packet OBJECT_DELETE**
  - `build_object_delete_response(x, y)`
  - `send_object_delete()` en MessageSender
  - `broadcast_object_delete()` en MultiplayerBroadcastService

- [ ] **TaskPickup**
  - Handler del packet PICKUP (ID 316)
  - Validar inventario lleno
  - Agregar item al inventario
  - Remover del suelo
  - Broadcast OBJECT_DELETE

- [ ] **Dropear Oro al Matar NPC**
  - Crear ground item en TaskAttack
  - Enviar OBJECT_CREATE
  - Mostrar en cliente

### Media Prioridad

- [ ] **TaskDrop**
  - Handler del packet DROP (ID 331)
  - Validar que el item exista en inventario
  - Crear ground item
  - Remover del inventario
  - Broadcast OBJECT_CREATE

- [ ] **Tabla de Loot**
  - JSON con loot por tipo de NPC
  - Sistema de probabilidades
  - Cantidad variable (min-max)

- [ ] **Item Ownership**
  - Item dropeado es del jugador por N segundos
  - Otros jugadores no pueden recogerlo
  - Después de N segundos, cualquiera puede

- [ ] **Catálogo de Items**
  - JSON con todos los items
  - Propiedades: nombre, tipo, gráfico, stats
  - Usar en lugar de valores hardcodeados

### Baja Prioridad

- [ ] **Items Raros**
  - Items con baja probabilidad de drop
  - Mensaje especial al dropear
  - Efecto visual especial

- [ ] **Auto-Loot**
  - Recoger oro automáticamente
  - Configurable por jugador
  - Solo si hay espacio en inventario

- [ ] **Persistencia de Ground Items**
  - Guardar en Redis al apagar servidor
  - Restaurar al iniciar
  - TTL para items viejos

- [ ] **Stack de Items**
  - Múltiples items en mismo tile
  - Mostrar cantidad en cliente
  - Recoger todos o uno por uno

## 🧪 Testing

### Tests Necesarios

- [ ] Test de `add_ground_item()`
- [ ] Test de `get_ground_items()`
- [ ] Test de `remove_ground_item()`
- [ ] Test de cálculo de oro dropeado
- [ ] Test de PICKUP con inventario lleno
- [ ] Test de PICKUP con inventario vacío
- [ ] Test de DROP
- [ ] Test de tabla de loot (probabilidades)
- [ ] Test de item ownership
- [ ] Test de broadcast OBJECT_CREATE/DELETE

## 📊 Estadísticas

### Código Estimado

- **Ground Items**: ~100 líneas (MapManager)
- **Packets**: ~50 líneas (msg.py)
- **TaskPickup**: ~150 líneas
- **TaskDrop**: ~100 líneas
- **Tabla de Loot**: ~200 líneas
- **Total**: ~600 líneas

### Rendimiento

- **add_ground_item()**: O(1)
- **get_ground_items()**: O(1)
- **remove_ground_item()**: O(n) donde n = items en ese tile (usualmente 1-5)
- **Memoria**: ~100 bytes por item en el suelo

## 🔗 Referencias

- [COMBAT_SYSTEM.md](./COMBAT_SYSTEM.md) - Sistema de combate
- [Cliente Godot - Item.gd](../clientes/ArgentumOnlineGodot/common/data/Item.gd)
- [Cliente Godot - GameProtocol.gd](../clientes/ArgentumOnlineGodot/engine/autoload/game_protocol.gd)
- [TODO.md](../TODO.md)

## 📜 Changelog

### 2025-10-16
- ✅ Cálculo de oro dropeado implementado
- ✅ Experiencia se da directamente
- ⏳ Ground items en progreso
- ⏳ Packets OBJECT_CREATE/DELETE pendientes
- ⏳ TaskPickup pendiente

### Próxima Sesión
- [ ] Implementar ground items en MapManager
- [ ] Implementar packets OBJECT_CREATE/DELETE
- [ ] Implementar TaskPickup
- [ ] Dropear oro visible en el suelo
