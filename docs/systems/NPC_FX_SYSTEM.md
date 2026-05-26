# 🎨 Sistema de Efectos Visuales (FX) para NPCs

## Descripción

Sistema completo de efectos visuales para NPCs que soporta dos tipos de efectos:
- **FX de muerte**: Efecto one-shot que se reproduce cuando el NPC muere
- **FX de aura**: Efecto continuo (loop infinito) que se reproduce mientras el NPC está vivo

---

## 📊 Arquitectura

### Campos en NPC

```python
@dataclass
class NPC:
    # ... otros campos ...
    
    fx: int = 0          # FX ID al morir (one-shot)
    fx_loop: int = 0     # FX ID continuo (aura, loop infinito)
```

### NPCFactory

Los NPCs se crean con sus efectos configurados:

```python
# Goblin con sangre al morir
goblin = NPCFactory.create_goblin(x=50, y=50, map_id=1, char_index=10001)
# → fx=5 (sangre)

# Araña con veneno y aura venenosa
arana = NPCFactory.create_arana(x=60, y=60, map_id=1, char_index=10002)
# → fx=10 (veneno al morir) + fx_loop=15 (aura venenosa)
```

---

## 🎯 IDs de Efectos Visuales

### FX de Muerte (One-shot)

| ID | Efecto | NPCs que lo usan |
|----|--------|------------------|
| 5  | Sangre | Goblin, Lobo, Orco |
| 10 | Veneno | Araña Gigante |
| 25 | Explosión de fuego | (Future: Dragón, Demonio) |
| 30 | Hielo | (Future: Elementales de hielo) |
| 35 | Rayo | (Future: Elementales eléctricos) |

### FX de Aura (Loop Infinito)

| ID | Efecto | NPCs que lo usan |
|----|--------|------------------|
| 15 | Aura venenosa | Araña Gigante |
| 20 | Aura de fuego | (Future: Dragón) |
| 45 | Aura sagrada | (Future: NPCs divinos) |
| 50 | Aura oscura | (Future: NPCs demoníacos) |

---

## 🔄 Flujo de Ejecución

### 1. Spawn de NPC (con Aura)

```
NPCService.spawn_npc()
  ├─> broadcast_character_create()
  └─> if npc.fx_loop > 0:
        └─> broadcast_create_fx(fx=fx_loop, loops=-1)  # Infinito
```

**Secuencia:**
1. NPC aparece en el mundo
2. Broadcast CHARACTER_CREATE a todos los jugadores
3. Si tiene aura (fx_loop > 0), broadcast CREATE_FX con loop infinito

### 2. Muerte de NPC (con FX)

```
NPCDeathService._remove_npc_from_game()
  ├─> if npc.fx > 0:
  │     └─> broadcast_create_fx(fx=fx, loops=1)  # One-shot
  ├─> map_manager.remove_npc()
  └─> broadcast_character_remove()
```

**Secuencia:**
1. NPC muere
2. Si tiene FX de muerte (fx > 0), broadcast CREATE_FX one-shot
3. NPC se remueve del mapa
4. Broadcast CHARACTER_REMOVE a todos los jugadores

### 3. Jugador se loguea (ve NPCs con aura)

```
NPCService.send_npcs_to_player()
  └─> for each npc:
        └─> send_character_create(fx=npc.fx_loop, loops=-1)
```

**Secuencia:**
1. Jugador se loguea
2. Recibe CHARACTER_CREATE de cada NPC
3. NPCs con aura tienen fx=fx_loop y loops=-1

---

## 💻 Implementación

### NPCFactory Configuration

```python
class NPCFactory:
    @staticmethod
    def _create_hostile_base(
        # ... otros parámetros ...
        fx: int = 0,
        fx_loop: int = 0,
    ) -> NPC:
        return NPC(
            # ... otros campos ...
            fx=fx,
            fx_loop=fx_loop,
        )
    
    @staticmethod
    def create_goblin(x: int, y: int, map_id: int, char_index: int) -> NPC:
        return NPCFactory._create_hostile_base(
            npc_id=1,
            name="Goblin",
            # ... otros parámetros ...
            fx=5,  # Sangre al morir
        )
    
    @staticmethod
    def create_arana(x: int, y: int, map_id: int, char_index: int) -> NPC:
        return NPCFactory._create_hostile_base(
            npc_id=8,
            name="Araña Gigante",
            # ... otros parámetros ...
            fx=10,      # Veneno al morir
            fx_loop=15,  # Aura venenosa
        )
```

### MultiplayerBroadcastService

```python
async def broadcast_create_fx(
    self, map_id: int, char_index: int, fx: int, loops: int
) -> None:
    """Envía CREATE_FX a todos los jugadores en un mapa.
    
    Args:
        map_id: ID del mapa.
        char_index: CharIndex del personaje/NPC.
        fx: ID del efecto visual.
        loops: Número de loops (-1 = infinito, 1 = one-shot).
    """
    if not self.map_manager:
        return
    
    players = self.map_manager.get_all_message_senders_in_map(map_id)
    for message_sender in players:
        await message_sender.send_create_fx(char_index, fx, loops)
```

---

## 🎮 Gameplay

### NPCs con Efectos Visuales

**Goblin:**
- Al morir: Sangre (fx=5)
- Aura: Ninguna

**Lobo:**
- Al morir: Sangre (fx=5)
- Aura: Ninguna

**Orco:**
- Al morir: Sangre (fx=5)
- Aura: Ninguna

**Araña Gigante:**
- Al morir: Veneno (fx=10)
- Aura: Aura venenosa (fx_loop=15) 💚✨

### Impacto Visual

Los efectos visuales aportan:
- **Feedback inmediato** de acciones (muerte)
- **Identidad única** de cada NPC (auras)
- **Ambiente inmersivo** (efectos ambientales)
- **Advertencia visual** (NPCs peligrosos con auras)

---

## 🔧 Logging

### Eventos Loggeados

**DEBUG - FX de muerte:**
```
FX de muerte enviado para Araña Gigante: fx=10 en (50,50)
```

**DEBUG - FX de aura en spawn:**
```
FX aura enviado para Araña Gigante: fx_loop=15 en (50,50)
```

**DEBUG - Broadcast:**
```
Broadcast CREATE_FX: CharIndex=10001 fx=5 loops=1 - 3 notificados
```

---

## 🚀 Próximas Mejoras

### NPCs Boss con FX Épicos

```python
@staticmethod
def create_dragon(x: int, y: int, map_id: int, char_index: int) -> NPC:
    return NPCFactory._create_hostile_base(
        npc_id=10,
        name="Dragón",
        body_id=200,
        hp=1000,
        level=50,
        x=x,
        y=y,
        map_id=map_id,
        char_index=char_index,
        description="Un dragón ancestral y devastador",
        gold_min=500,
        gold_max=2000,
        fx=25,      # Explosión de fuego al morir 🔥
        fx_loop=20,  # Aura de fuego 🔥✨
    )
```

### FX Dinámicos

- FX según estado del NPC (envenenado, congelado, etc.)
- FX escalables según nivel
- FX de habilidades especiales

### FX Ambientales

- Portales con FX de loop
- Altares con auras sagradas
- Zonas de peligro con FX de advertencia

---

## 📊 Métricas

**Versión:** 0.5.0-alpha  
**Tests:** 973 pasando (100%)  
**Cobertura:** 100% de funcionalidad FX  
**NPCs con FX:** 4/4 hostiles (100%)

---

## 📝 Notas de Implementación

1. **Performance:** Los efectos se envían solo a jugadores en el mapa (broadcast eficiente)
2. **Sincronización:** FX se envían después de CHARACTER_CREATE para garantizar que el cliente esté listo
3. **Delays:** 50ms entre NPCs al login para evitar saturar el cliente
4. **Loops infinitos:** Los clientes deben manejar loops=-1 correctamente

---

**Última actualización:** 2025-10-20  
**Autor:** Equipo PyAO  
**Estado:** ✅ Completado
