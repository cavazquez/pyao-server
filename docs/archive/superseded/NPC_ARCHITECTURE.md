# 🏗️ Arquitectura del Sistema de NPCs

## Descripción General

El sistema de NPCs está diseñado con una **arquitectura de capas** que separa:
- **Configuración** (archivos TOML)
- **Factory** (creación de instancias)
- **Service** (lógica de negocio)
- **Repository** (persistencia en Redis)

---

## 📊 Flujo de Datos

```
data/npcs_hostiles.toml
         ↓
    NPCCatalog (lee TOML)
         ↓
    NPCService (lógica)
         ↓
    NPCFactory.create_hostile(parámetros del TOML)
         ↓
    NPC (instancia)
         ↓
    NPCRepository (persiste en Redis)
```

---

## 🔧 Componentes

### 1. **NPCCatalog**
**Ubicación:** `src/npc_catalog.py`

**Responsabilidad:** Leer y parsear archivos TOML

```python
catalog = NPCCatalog("data/npcs_hostiles.toml")
npc_data = catalog.get_npc_data(npc_id=1)  # Devuelve dict con todos los parámetros
```

**Formato TOML:**
```toml
[[npc]]
id = 1
nombre = "Goblin"
body_id = 14
hp_max = 110
nivel = 5
ataque = 8
cooldown_ataque = 2.5
rango_agresion = 6
# ... más parámetros
```

---

### 2. **NPCFactory**
**Ubicación:** `src/npc_factory.py`

**Responsabilidad:** Crear instancias de NPCs con parámetros configurables

```python
# Método genérico (usado por NPCService)
npc = NPCFactory.create_hostile(
    npc_id=1,
    name="Goblin",
    body_id=14,
    hp=110,
    level=5,
    x=50, y=50,
    map_id=1,
    char_index=10001,
    attack_damage=8,
    attack_cooldown=2.5,
    aggro_range=6,
    fx=5,
    fx_loop=0
)

# Métodos helper (conveniencia)
npc = NPCFactory.create_goblin(x=50, y=50, map_id=1, char_index=10001)
```

**Ventajas:**
- ✅ **100% configurable desde TOML**
- ✅ Factory no tiene lógica de negocio
- ✅ Fácil agregar nuevos NPCs sin cambiar código
- ✅ Métodos helper opcionales para conveniencia

---

### 3. **NPCService**
**Ubicación:** `src/npc_service.py`

**Responsabilidad:** Coordinar la creación y spawneo de NPCs

**Flujo en `spawn_npc()`:**

```python
async def spawn_npc(self, npc_id: int, map_id: int, x: int, y: int) -> NPC | None:
    # 1. Obtener datos del catálogo (TOML)
    npc_data = self.npc_catalog.get_npc_data(npc_id)
    
    # 2. Asignar CharIndex único
    char_index = self._next_char_index
    self._next_char_index += 1
    
    # 3. Crear instancia via Repository (usa TOML data)
    npc = await self.npc_repository.create_npc_instance(
        npc_id=npc_id,
        char_index=char_index,
        map_id=map_id,
        x=x, y=y,
        name=npc_data.get("nombre"),
        body_id=npc_data.get("body_id"),
        hp=npc_data.get("hp_max"),
        # ... TODOS los parámetros del TOML
        attack_damage=npc_data.get("ataque", 10),
        attack_cooldown=npc_data.get("cooldown_ataque", 3.0),
        aggro_range=npc_data.get("rango_agresion", 8)
    )
    
    # 4. Agregar al mapa
    self.map_manager.add_npc(map_id, npc)
    
    # 5. Broadcast a jugadores
    await self.broadcast_service.broadcast_character_create(...)
    
    # 6. Enviar FX si tiene aura
    if npc.fx_loop > 0:
        await self.broadcast_service.broadcast_create_fx(...)
    
    return npc
```

**El NPCService YA hace lo que pediste:**
- ✅ Lee parámetros del TOML
- ✅ Usa factory genérico
- ✅ No tiene lógica hardcodeada
- ✅ Totalmente configurable

---

### 4. **NPCRepository**
**Ubicación:** `src/npc_repository.py`

**Responsabilidad:** Persistencia en Redis

```python
# Crear y persistir
npc = await npc_repo.create_npc_instance(
    npc_id=1,
    char_index=10001,
    # ... todos los parámetros
)

# Recuperar de Redis
npc = await npc_repo.get_npc_by_instance_id("uuid-123")

# Actualizar
await npc_repo.update_npc(npc)

# Eliminar
await npc_repo.remove_npc("uuid-123")
```

---

## 🎯 Ejemplo Completo: Agregar un NPC Nuevo

### 1. Agregar al TOML

```toml
[[npc]]
id = 25
nombre = "Troll de Hielo"
descripcion = "Un troll gigante de las montañas heladas."
body_id = 180
head_id = 0
es_hostil = true
es_atacable = true
nivel = 30
hp_max = 3000
oro_min = 200
oro_max = 800
respawn_time = 180
respawn_time_max = 360
ataque = 80
cooldown_ataque = 4.0
rango_agresion = 12
```

### 2. Spawnear el NPC

```python
# En map_npcs.toml
[[spawn]]
map_id = 5
npc_id = 25  # <-- Nuevo Troll
x = 50
y = 50
heading = 3
```

### 3. ¡Listo!

**NO necesitas:**
- ❌ Modificar código Python
- ❌ Crear método en Factory
- ❌ Tocar NPCService
- ❌ Escribir tests específicos

**El sistema automáticamente:**
- ✅ Lee el TOML
- ✅ Crea la instancia
- ✅ Spawnea el NPC
- ✅ Persiste en Redis
- ✅ Envía al cliente

---

## 📈 Ventajas de esta Arquitectura

### Separación de Responsabilidades
- **NPCCatalog**: Solo lee archivos
- **NPCFactory**: Solo crea instancias
- **NPCService**: Solo orquesta
- **NPCRepository**: Solo persiste

### Configurabilidad
- Todos los stats en TOML
- Sin código hardcodeado
- Fácil balanceo

### Escalabilidad
- Agregar 100 NPCs = 100 entradas en TOML
- Sin cambios en código
- Sin riesgo de bugs

### Mantenibilidad
- Un solo lugar para cambiar stats
- Cambios sin deployar código
- Hot-reload posible en futuro

---

## 🧪 Testing

El sistema está diseñado para testing fácil:

```python
# Test con datos mock
npc_data = {
    "nombre": "Test NPC",
    "body_id": 1,
    "hp_max": 100,
    # ...
}

npc = NPCFactory.create_hostile(
    **npc_data,
    x=50, y=50,
    map_id=1,
    char_index=10001
)

assert npc.name == "Test NPC"
assert npc.hp == 100
```

---

## 📊 Catálogo Actual

**24 NPCs hostiles configurados:**
- Murciélago (id=16)
- Serpiente (id=9)
- Lobo (id=7)
- Goblin (id=1)
- Esqueleto (id=11)
- Escorpión (id=17)
- Zombie (id=12)
- Araña Gigante (id=8)
- Bandido (id=18)
- Oso Pardo (id=19)
- Orco (id=4)
- Tigre Salvaje (id=20)
- Licántropo (id=21)
- Golem (id=23)
- Ogro (id=14)
- Liche (id=22)
- Elemental de Fuego (id=24)
- Demonio (id=15)
- Dragón Rojo (id=10)
- Gran Dragón Rojo (id=13) - BOSS

**Todos con:**
- Body IDs correctos del VB6
- Stats balanceados
- Configuración completa

---

## 🔄 Próximas Mejoras

### Hot-Reload de Configuración
```python
# Recargar TOML sin reiniciar servidor
await npc_service.reload_catalog()
```

### Validación de TOML
```python
# Validar al cargar
NPCCatalog.validate("data/npcs_hostiles.toml")
```

### NPCs por Loot Table
```toml
[[npc]]
id = 25
# ...
loot_table = "boss_dragon"  # Referencia a loot_tables.toml
```

---

**Última actualización:** 2025-10-21  
**Autor:** Equipo PyAO  
**Estado:** ✅ Producción
