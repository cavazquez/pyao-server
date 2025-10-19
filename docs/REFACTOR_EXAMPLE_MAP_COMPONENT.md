# Ejemplo de Refactorización: Uso Explícito de Componentes

## Opción 1: Mantener MessageSender (Recomendado - Sin Cambios)

### Estado Actual (Funciona Perfectamente)

```python
# task_login.py
class TaskLogin:
    def __init__(self, message_sender: MessageSender):
        self.message_sender = message_sender
    
    async def execute(self):
        # Usa métodos delegados
        await self.message_sender.send_change_map(position["map"])
        await self.message_sender.send_pos_update(position["x"], position["y"])
        await self.message_sender.send_object_create(x, y, grh_index)
```

**Ventajas:**
- ✅ Código existente funciona sin cambios
- ✅ Una sola dependencia
- ✅ Acceso a todos los tipos de mensajes

**Desventajas:**
- ❌ No es explícito qué tipo de mensajes usa
- ❌ Dependencia más grande de lo necesario

## Opción 2: Acceso Explícito a Componentes (Recomendado - Código Nuevo)

### Refactorización Sugerida

```python
# task_login.py
class TaskLogin:
    def __init__(self, message_sender: MessageSender):
        self.message_sender = message_sender
    
    async def execute(self):
        # Agrupa operaciones de mapa
        await self.message_sender.map.send_change_map(position["map"])
        await self.message_sender.map.send_pos_update(position["x"], position["y"])
        await self.message_sender.map.send_object_create(x, y, grh_index)
        
        # Agrupa operaciones de audio
        await self.message_sender.audio.play_music_newbie()
        
        # Agrupa operaciones de consola
        await self.message_sender.console.send_console_msg("Bienvenido!")
```

**Ventajas:**
- ✅ Código más legible (agrupa operaciones relacionadas)
- ✅ Documenta intención
- ✅ Mantiene flexibilidad de MessageSender

**Desventajas:**
- ❌ Requiere refactorización del código existente

## Opción 3: Inyección de Componentes Específicos (Avanzado)

### Para Servicios Altamente Especializados

```python
# map_broadcast_service.py (NUEVO - Ejemplo)
class MapBroadcastService:
    """Servicio especializado solo para broadcast de mensajes de mapa."""
    
    def __init__(self, map_manager: MapManager):
        self.map_manager = map_manager
    
    async def broadcast_object_create(
        self,
        map_id: int,
        x: int,
        y: int,
        grh_index: int
    ) -> int:
        """Broadcast de OBJECT_CREATE a todos en el mapa."""
        # Obtiene MessageSenders y accede al componente de mapa
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
        
        notified = 0
        for sender in all_senders:
            # Usa componente de mapa directamente
            await sender.map.send_object_create(x, y, grh_index)
            notified += 1
        
        return notified
```

**Ventajas:**
- ✅ Dependencias muy explícitas
- ✅ Código altamente enfocado
- ✅ Tests más simples

**Desventajas:**
- ❌ Requiere crear nuevos servicios
- ❌ Más archivos en el proyecto

## Comparación de Enfoques

### Ejemplo: PlayerService.send_map_info()

#### Opción 1: Delegación (Actual)
```python
async def send_map_info(self, position: dict[str, int]):
    await self.message_sender.send_change_map(position["map"])
```

#### Opción 2: Componente Explícito
```python
async def send_map_info(self, position: dict[str, int]):
    await self.message_sender.map.send_change_map(position["map"])
```

#### Opción 3: Inyección de Componente
```python
class PlayerService:
    def __init__(
        self,
        player_repo: PlayerRepository,
        map_sender: MapMessageSender,  # ← Componente específico
    ):
        self.player_repo = player_repo
        self.map_sender = map_sender

async def send_map_info(self, position: dict[str, int]):
    await self.map_sender.send_change_map(position["map"])
```

## Recomendación Final

### Para Código Existente: NO CAMBIAR

El código actual funciona perfectamente. La delegación es transparente:

```python
# Esto funciona y es correcto
await self.message_sender.send_change_map(1)
```

### Para Código Nuevo: Usar Componentes Explícitos

Cuando escribas código nuevo, considera agrupar operaciones:

```python
# Más legible - agrupa operaciones de mapa
await self.message_sender.map.send_change_map(1)
await self.message_sender.map.send_pos_update(50, 50)

# Más legible - agrupa operaciones de audio
await self.message_sender.audio.play_music_newbie()
await self.message_sender.audio.play_sound_click()
```

### Para Servicios Especializados: Considerar Inyección

Si creas un servicio que **solo** usa mensajes de mapa:

```python
class MapRenderService:
    def __init__(self, map_sender: MapMessageSender):
        self.map_sender = map_sender
```

## Ejemplo Práctico: Refactorización Gradual

### Antes (Funciona Perfectamente)

```python
# task_login.py
await self.message_sender.send_change_map(position["map"])
await self.message_sender.send_pos_update(position["x"], position["y"])
await self.message_sender.send_console_msg("Bienvenido!")
await self.message_sender.play_music_newbie()
```

### Después (Más Legible - Opcional)

```python
# task_login.py
# Operaciones de mapa
await self.message_sender.map.send_change_map(position["map"])
await self.message_sender.map.send_pos_update(position["x"], position["y"])

# Operaciones de consola
await self.message_sender.console.send_console_msg("Bienvenido!")

# Operaciones de audio
await self.message_sender.audio.play_music_newbie()
```

## Conclusión

1. **No refactorices código existente** - Funciona perfectamente
2. **Usa componentes explícitos en código nuevo** - Más legible
3. **Considera inyección de componentes para servicios especializados** - Mejor diseño
4. **Ambos enfoques son válidos** - Elige según el contexto

La migración es **gradual y opcional**. El patrón Facade permite ambos estilos de código.
