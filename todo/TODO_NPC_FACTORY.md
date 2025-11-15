# TODO (Histórico): Sistema de NPC Factory

**Estado:** ✅ **COMPLETADO** - 21 de octubre, 2025  
**Prioridad:** Media  
**Versión objetivo:** 0.6.0-alpha

> **NOTA:** Este sistema ha sido completamente implementado. Ver `docs/NPC_FACTORY_COMPLETED.md` para documentación completa.

---

## 🎯 Objetivo

Crear un sistema de factory methods para encapsular la creación de NPCs y evitar duplicación de código entre criaturas similares (Goblin, Lobo, Araña, etc.).

---

## 🏗️ Diseño Propuesto

### NPCFactory con Factory Methods

```python
# src/npc_factory.py
"""Factory para crear NPCs con comportamientos predefinidos."""

from src.npc import NPC


class NPCFactory:
    """Factory para crear diferentes tipos de NPCs."""
    
    @staticmethod
    def _create_hostile_base(
        npc_id: int,
        name: str,
        body_id: int,
        hp: int,
        level: int,
        x: int,
        y: int,
        map_id: int,
        aggro_range: int = 5,
        attack_damage: int = 10,
        fx: int = 0,              # FX al atacar/morir
        fx_loop: int = 0,         # FX continuo (aura, etc)
    ) -> NPC:
        """Crear base común para NPCs hostiles."""
        return NPC(
            npc_id=npc_id,
            name=name,
            body_id=body_id,
            head_id=0,  # Criaturas sin cabeza
            x=x,
            y=y,
            map_id=map_id,
            hp=hp,
            max_hp=hp,
            level=level,
            hostile=True,
            aggro_range=aggro_range,
            attack_damage=attack_damage,
            movement_speed=1.0,
            fx=fx,
            fx_loop=fx_loop,
        )
    
    @classmethod
    def create_goblin(cls, x: int, y: int, map_id: int) -> NPC:
        """Crear un Goblin hostil."""
        return cls._create_hostile_base(
            npc_id=1,
            name="Goblin",
            body_id=58,
            hp=100,
            level=5,
            x=x,
            y=y,
            map_id=map_id,
            aggro_range=5,
            attack_damage=15,
            fx=5,           # Sangre al morir
            fx_loop=0,      # Sin efecto continuo
        )
    
    @classmethod
    def create_lobo(cls, x: int, y: int, map_id: int) -> NPC:
        """Crear un Lobo hostil."""
        return cls._create_hostile_base(
            npc_id=7,
            name="Lobo",
            body_id=138,
            hp=80,
            level=3,
            x=x,
            y=y,
            map_id=map_id,
            aggro_range=6,  # Los lobos detectan desde más lejos
            attack_damage=12,
            fx=5,           # Sangre al morir
            fx_loop=0,
        )
    
    @classmethod
    def create_araña(cls, x: int, y: int, map_id: int) -> NPC:
        """Crear una Araña Gigante hostil."""
        return cls._create_hostile_base(
            npc_id=8,
            name="Araña Gigante",
            body_id=149,
            hp=150,
            level=8,
            x=x,
            y=y,
            map_id=map_id,
            aggro_range=4,  # Más sigilosa
            attack_damage=20,
            fx=10,          # Veneno al morir
            fx_loop=15,     # Aura venenosa continua
        )
    
    @classmethod
    def create_orco(cls, x: int, y: int, map_id: int) -> NPC:
        """Crear un Orco hostil."""
        return cls._create_hostile_base(
            npc_id=4,
            name="Orco",
            body_id=8,
            hp=200,
            level=10,
            x=x,
            y=y,
            map_id=map_id,
            aggro_range=5,
            attack_damage=25,
            fx=5,           # Sangre al morir
            fx_loop=0,
        )
    
    @classmethod
    def create_dragon(cls, x: int, y: int, map_id: int) -> NPC:
        """Crear un Dragón (boss)."""
        return cls._create_hostile_base(
            npc_id=20,
            name="Dragón Rojo",
            body_id=200,
            hp=1000,
            level=30,
            x=x,
            y=y,
            map_id=map_id,
            aggro_range=8,
            attack_damage=50,
            fx=25,          # Explosión de fuego al morir
            fx_loop=20,     # Aura de fuego continua
        )
    
    @staticmethod
    def create_comerciante(x: int, y: int, map_id: int) -> NPC:
        """Crear un Comerciante (NPC amigable)."""
        return NPC(
            npc_id=2,
            name="Comerciante",
            body_id=501,
            head_id=1,
            x=x,
            y=y,
            map_id=map_id,
            hp=200,
            max_hp=200,
            level=10,
            hostile=False,
            is_merchant=True,
            aggro_range=0,
            attack_damage=0,
            movement_speed=0.0,  # No se mueve
            fx=0,
            fx_loop=0,
        )
    
    @staticmethod
    def create_banquero(x: int, y: int, map_id: int) -> NPC:
        """Crear un Banquero (NPC amigable)."""
        return NPC(
            npc_id=5,
            name="Banquero",
            body_id=504,
            head_id=1,
            x=x,
            y=y,
            map_id=map_id,
            hp=200,
            max_hp=200,
            level=10,
            hostile=False,
            is_banker=True,
            aggro_range=0,
            attack_damage=0,
            movement_speed=0.0,
            fx=0,
            fx_loop=0,
        )
    
    @staticmethod
    def create_guardia(x: int, y: int, map_id: int) -> NPC:
        """Crear un Guardia Real (NPC amigable pero fuerte)."""
        return NPC(
            npc_id=3,
            name="Guardia Real",
            body_id=502,
            head_id=1,
            x=x,
            y=y,
            map_id=map_id,
            hp=500,
            max_hp=500,
            level=20,
            hostile=False,
            aggro_range=0,
            attack_damage=0,
            movement_speed=0.0,
            fx=0,
            fx_loop=0,
        )
```

---

## 📝 Uso Propuesto

```python
# En tu código de spawn
from src.npc_factory import NPCFactory

# Crear NPCs hostiles
goblin = NPCFactory.create_goblin(x=50, y=50, map_id=1)
lobo = NPCFactory.create_lobo(x=60, y=60, map_id=1)
araña = NPCFactory.create_araña(x=70, y=70, map_id=1)
orco = NPCFactory.create_orco(x=80, y=80, map_id=1)

# Crear NPCs amigables
comerciante = NPCFactory.create_comerciante(x=30, y=30, map_id=1)
banquero = NPCFactory.create_banquero(x=35, y=35, map_id=1)
guardia = NPCFactory.create_guardia(x=40, y=40, map_id=1)

# Agregar al mapa
await map_manager.add_npc(goblin)
await map_manager.add_npc(araña)
await map_manager.add_npc(comerciante)
```

---

## 🎨 Efectos Visuales (FX)

### FX al Morir (one-shot)
- **fx=5**: Sangre (muerte normal)
- **fx=10**: Veneno
- **fx=25**: Explosión de fuego
- **fx=30**: Hielo
- **fx=35**: Rayo

### FX Loop (continuo/aura)
- **fx_loop=15**: Aura venenosa
- **fx_loop=20**: Aura de fuego
- **fx_loop=45**: Aura sagrada
- **fx_loop=50**: Aura oscura

---

## 🔧 Integración con NPCService

```python
# src/npc_service.py
from src.npc_factory import NPCFactory

class NPCService:
    """Servicio para gestionar NPCs."""
    
    async def spawn_npc_by_name(
        self,
        npc_name: str,
        x: int,
        y: int,
        map_id: int,
    ) -> NPC | None:
        """Spawnear NPC por nombre usando el factory."""
        factory_method = {
            "goblin": NPCFactory.create_goblin,
            "lobo": NPCFactory.create_lobo,
            "araña": NPCFactory.create_araña,
            "orco": NPCFactory.create_orco,
            "dragon": NPCFactory.create_dragon,
            "comerciante": NPCFactory.create_comerciante,
            "banquero": NPCFactory.create_banquero,
            "guardia": NPCFactory.create_guardia,
        }.get(npc_name.lower())
        
        if not factory_method:
            logger.error("NPC desconocido: %s", npc_name)
            return None
        
        npc = factory_method(x, y, map_id)
        await self.map_manager.add_npc(npc)
        return npc
```

---

## 📊 Actualizar NPC Dataclass

```python
# src/npc.py

@dataclass
class NPC:
    """Representa un NPC en el juego."""
    
    npc_id: int
    name: str
    body_id: int
    head_id: int
    x: int
    y: int
    map_id: int
    hp: int
    max_hp: int
    level: int
    hostile: bool
    aggro_range: int = 5
    attack_damage: int = 10
    movement_speed: float = 1.0
    
    # ⭐ Efectos visuales
    fx: int = 0           # FX al atacar/morir (one-shot)
    fx_loop: int = 0      # FX continuo (aura, partículas)
    
    # Estado
    state: str = "idle"
    target_user_id: int | None = None
    is_merchant: bool = False
    is_banker: bool = False
```

---

## 🎯 Uso de FX en el Juego

### 1. FX al Morir (TaskAttack)

```python
# src/task_attack.py

async def _handle_npc_death(self, npc: NPC) -> None:
    """Manejar muerte del NPC."""
    logger.info("NPC %s ha muerto", npc.name)
    
    # ⭐ Enviar efecto visual de muerte
    if npc.fx > 0:
        await self.message_sender.send_create_fx(
            x=npc.x,
            y=npc.y,
            fx_id=npc.fx,  # Usa el FX definido en el factory
            loops=1,
        )
    
    # Dropear loot
    await self._drop_loot(npc)
    
    # Remover NPC del mapa
    await self.map_manager.remove_npc(npc.map_id, npc.x, npc.y)
```

### 2. FX Loop al Spawnear (NPCService)

```python
# src/npc_service.py

async def spawn_npc(self, npc: NPC) -> None:
    """Spawnear NPC en el mapa."""
    # Agregar al mapa
    await self.map_manager.add_npc(npc)
    
    # ⭐ Enviar FX loop si tiene aura
    if npc.fx_loop > 0:
        await self._broadcast_fx_loop(npc)
    
    # Enviar CHARACTER_CREATE a todos los jugadores cercanos
    await self._broadcast_character_create(npc)

async def _broadcast_fx_loop(self, npc: NPC) -> None:
    """Enviar FX loop a jugadores cercanos."""
    nearby_players = await self.map_manager.get_nearby_players(
        npc.map_id, npc.x, npc.y, radius=15
    )
    
    for player in nearby_players:
        await player.message_sender.send_create_fx(
            x=npc.x,
            y=npc.y,
            fx_id=npc.fx_loop,
            loops=-1,  # -1 = infinito (loop continuo)
        )
```

---

## ✅ Ventajas del Diseño

1. **DRY**: No duplicar código entre Goblin, Lobo, Araña
2. **Simple**: `create_araña()`, `create_lobo()` - nombres claros
3. **Type-safe**: Cada método retorna un `NPC` tipado
4. **Autodocumentado**: Nombres claros de qué crea cada método
5. **Fácil de extender**: Agregar `create_dragon()` es trivial
6. **Centralizado**: Todos los NPCs se crean en un solo lugar
7. **FX integrados**: Cada NPC tiene sus efectos visuales definidos

---

## 📋 Configuración Alternativa en npcs.toml

Si prefieres configurar desde TOML en lugar de código:

```toml
[[spawn]]
map_id = 1
npc_type = "goblin"  # Usa el factory method
x = 50
y = 50
respawn_time = 60

[[spawn]]
map_id = 1
npc_type = "araña"
x = 70
y = 70
respawn_time = 120

[[spawn]]
map_id = 1
npc_type = "comerciante"
x = 30
y = 30
respawn_time = 0  # No respawnea
```

---

## 📝 Checklist de Implementación (histórico)

> Este checklist refleja el plan original de implementación. Hoy se conserva solo como **referencia histórica**; la implementación real y los tests están documentados en `docs/NPC_FACTORY_COMPLETED.md`.

### Fase 1: Estructura Base (completada)
- [x] Crear `src/npc_factory.py` con clase `NPCFactory`
- [x] Implementar `_create_hostile_base()` método helper
- [x] Agregar campos `fx` y `fx_loop` a `src/npc.py`

### Fase 2: Factory Methods (completada)
- [x] Implementar `create_goblin()`
- [x] Implementar `create_lobo()`
- [x] Implementar `create_araña()`
- [x] Implementar `create_orco()`
- [x] Implementar `create_dragon()` / variantes equivalentes

### Fase 3: NPCs Amigables (completada)
- [x] Implementar `create_comerciante()`
- [x] Implementar `create_banquero()`
- [x] Implementar `create_guardia()`

### Fase 4: Integración (completada)
- [x] Modificar `NPCService.spawn_npc_by_name()` para usar factory
- [x] Actualizar spawns en `data/npcs.toml` con `npc_type`
- [x] Implementar envío de FX en `_handle_npc_death()`
- [x] Implementar envío de FX loop en `spawn_npc()`

### Fase 5: Testing (completada)
- [x] Tests unitarios de `NPCFactory`
- [x] Tests de creación de cada tipo de NPC
- [x] Tests de FX al morir
- [x] Tests de FX loop al spawnear

---

## 🚀 Próximos Pasos

1. Crear `src/npc_factory.py` con los factory methods
2. Actualizar `src/npc.py` con campos `fx` y `fx_loop`
3. Modificar `NPCService` para usar el factory
4. Actualizar `TaskAttack` para enviar FX al morir
5. Agregar tests completos

---

## 📚 Referencias

- **Diseño actual:** `src/npc.py`, `src/npc_service.py`
- **Configuración:** `data/npcs.toml`
- **Body IDs:** Ver memoria "Body IDs de NPCs"
- **Efectos visuales:** Basados en Argentum Online 0.13.3

---

**Última actualización:** 2025-10-21  
**Autor:** Diseño propuesto en conversación, luego implementado y documentado en `docs/NPC_FACTORY_COMPLETED.md`  
**Estado:** ✅ Implementado (este archivo se conserva como referencia histórica)
