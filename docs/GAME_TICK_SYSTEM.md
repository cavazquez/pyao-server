# Sistema de Tick del Juego

El servidor implementa un **sistema de tick genérico y extensible** que permite aplicar efectos periódicos a todos los jugadores conectados. **Todas las constantes se almacenan en Redis** y pueden modificarse en tiempo real sin reiniciar el servidor.

## Arquitectura

El sistema está compuesto por:

- **`GameTick`**: Clase principal que ejecuta el loop de tick y gestiona los efectos
- **`TickEffect`**: Clase abstracta base para crear nuevos efectos
- **`ServerRepository`**: Provee métodos para leer configuración de efectos desde Redis
- **Efectos implementados**: `HungerThirstEffect`, `GoldDecayEffect`

## Configuración en Redis

Todas las constantes de los efectos se almacenan en Redis con el prefijo `config:effects:`. Los valores se leen en cada tick, permitiendo cambios en tiempo real.

## Efectos Implementados

### 1. HungerThirstEffect

Reduce automáticamente la comida y el agua de los jugadores, basado en el servidor original de VB6 (General.bas:1369-1422).

**Claves de Redis:**
```
config:effects:hunger_thirst:enabled           # 1=habilitado, 0=deshabilitado
config:effects:hunger_thirst:interval_sed      # Segundos entre reducciones de agua (default: 4)
config:effects:hunger_thirst:interval_hambre   # Segundos entre reducciones de comida (default: 6)
config:effects:hunger_thirst:reduccion_agua    # Puntos a reducir (default: 10)
config:effects:hunger_thirst:reduccion_hambre  # Puntos a reducir (default: 10)
```

**Ejemplos de Configuración:**
```bash
# Configuración por defecto
redis-cli SET config:effects:hunger_thirst:interval_sed 4
redis-cli SET config:effects:hunger_thirst:reduccion_agua 10

# Más agresivo (cada 2 segundos, -20 puntos)
redis-cli SET config:effects:hunger_thirst:interval_sed 2
redis-cli SET config:effects:hunger_thirst:reduccion_agua 20

# Desactivar
redis-cli SET config:effects:hunger_thirst:enabled 0
```

**Código (en server.py):**
```python
self.game_tick.add_effect(HungerThirstEffect(self.server_repo))
```

### 2. GoldDecayEffect

Reduce un porcentaje del oro del jugador en intervalos configurables.

**Claves de Redis:**
```
config:effects:gold_decay:enabled          # 1=habilitado, 0=deshabilitado
config:effects:gold_decay:percentage       # Porcentaje a reducir (default: 1.0)
config:effects:gold_decay:interval_seconds # Segundos entre reducciones (default: 60.0)
```

**Ejemplos de Configuración:**
```bash
# Configuración por defecto (1% cada minuto)
redis-cli SET config:effects:gold_decay:percentage 1.0
redis-cli SET config:effects:gold_decay:interval_seconds 60.0

# Más agresivo (5% cada 30 segundos)
redis-cli SET config:effects:gold_decay:percentage 5.0
redis-cli SET config:effects:gold_decay:interval_seconds 30.0

# Más suave (0.5% cada 2 minutos)
redis-cli SET config:effects:gold_decay:percentage 0.5
redis-cli SET config:effects:gold_decay:interval_seconds 120.0

# Desactivar
redis-cli SET config:effects:gold_decay:enabled 0
```

**Código (en server.py):**
```python
self.game_tick.add_effect(GoldDecayEffect(self.server_repo))
```

## Crear Nuevos Efectos

Para crear un nuevo efecto, implementa la clase abstracta `TickEffect`:

```python
from src.tick_effect import TickEffect

class MyCustomEffect(TickEffect):
    """Descripción de tu efecto."""
    
    def __init__(self, param1: int, param2: float) -> None:
        """Inicializa el efecto con parámetros configurables."""
        self.param1 = param1
        self.param2 = param2
        # Contadores por jugador si es necesario
        self._counters: dict[int, int] = {}
    
    async def apply(
        self,
        user_id: int,
        player_repo: "PlayerRepository",
        message_sender: "MessageSender | None",
    ) -> None:
        """Aplica el efecto a un jugador."""
        # 1. Obtener datos del jugador desde player_repo
        stats = await player_repo.get_stats(user_id)
        if not stats:
            return
        
        # 2. Aplicar tu lógica
        # ... modificar stats ...
        
        # 3. Guardar cambios
        await player_repo.set_stats(user_id=user_id, **stats)
        
        # 4. Notificar al cliente (opcional)
        if message_sender:
            await message_sender.send_update_user_stats(**stats)
            await message_sender.send_console_msg("Mensaje al jugador")
    
    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos."""
        return 1.0  # Se ejecuta cada segundo
    
    def get_name(self) -> str:
        """Retorna el nombre del efecto para logging."""
        return "MyCustomEffect"
    
    def cleanup_player(self, user_id: int) -> None:
        """Limpia datos del jugador desconectado (opcional)."""
        if user_id in self._counters:
            del self._counters[user_id]
```

### Agregar el Efecto al Servidor

En `src/server.py`, agrega tu efecto al sistema de tick:

```python
from src.my_custom_effect import MyCustomEffect

# En el método start() de ArgentumServer
self.game_tick.add_effect(MyCustomEffect(param1=10, param2=5.5))
```

## Ejemplos de Efectos Posibles

### Regeneración de HP/Mana
```python
class RegenEffect(TickEffect):
    """Regenera HP y mana cada 5 segundos."""
    
    async def apply(self, user_id, player_repo, message_sender):
        stats = await player_repo.get_stats(user_id)
        if not stats:
            return
        
        # Regenerar 5% de HP y mana
        hp_regen = int(stats["max_hp"] * 0.05)
        mana_regen = int(stats["max_mana"] * 0.05)
        
        stats["min_hp"] = min(stats["max_hp"], stats["min_hp"] + hp_regen)
        stats["min_mana"] = min(stats["max_mana"], stats["min_mana"] + mana_regen)
        
        await player_repo.set_stats(user_id=user_id, **stats)
        if message_sender:
            await message_sender.send_update_user_stats(**stats)
    
    def get_interval_seconds(self) -> float:
        return 5.0
```

### Daño por Veneno
```python
class PoisonEffect(TickEffect):
    """Aplica daño por veneno cada 2 segundos."""
    
    def __init__(self, damage_per_tick: int = 5):
        self.damage_per_tick = damage_per_tick
        self._poisoned_players: set[int] = set()
    
    async def apply(self, user_id, player_repo, message_sender):
        if user_id not in self._poisoned_players:
            return  # Jugador no está envenenado
        
        stats = await player_repo.get_stats(user_id)
        if not stats:
            return
        
        # Aplicar daño
        stats["min_hp"] = max(0, stats["min_hp"] - self.damage_per_tick)
        
        await player_repo.set_stats(user_id=user_id, **stats)
        if message_sender:
            await message_sender.send_update_user_stats(**stats)
            await message_sender.send_console_msg(
                f"¡Estás envenenado! Pierdes {self.damage_per_tick} HP"
            )
        
        # Si el jugador murió, remover veneno
        if stats["min_hp"] <= 0:
            self._poisoned_players.discard(user_id)
    
    def poison_player(self, user_id: int) -> None:
        """Marca un jugador como envenenado."""
        self._poisoned_players.add(user_id)
    
    def cure_player(self, user_id: int) -> None:
        """Cura el veneno de un jugador."""
        self._poisoned_players.discard(user_id)
    
    def get_interval_seconds(self) -> float:
        return 2.0
```

### Experiencia Pasiva
```python
class PassiveXPEffect(TickEffect):
    """Otorga experiencia pasiva cada minuto."""
    
    async def apply(self, user_id, player_repo, message_sender):
        stats = await player_repo.get_stats(user_id)
        if not stats:
            return
        
        # Otorgar 10 puntos de experiencia
        xp_gain = 10
        stats["experience"] += xp_gain
        
        await player_repo.set_stats(user_id=user_id, **stats)
        if message_sender:
            await message_sender.send_update_user_stats(**stats)
            await message_sender.send_console_msg(f"+{xp_gain} XP (pasivo)")
    
    def get_interval_seconds(self) -> float:
        return 60.0
```

## Consideraciones de Rendimiento

- El sistema procesa **todos los jugadores conectados** en cada tick
- Usa `tick_interval=1.0` (1 segundo) para balance entre precisión y rendimiento
- Los efectos deben ser **eficientes** y evitar operaciones costosas
- Usa contadores internos para intervalos largos (evita ejecutar lógica innecesaria)

## Testing

Crea tests para tus efectos en `tests/test_game_tick.py`:

```python
@pytest.mark.asyncio
async def test_my_custom_effect():
    mock_player_repo = AsyncMock()
    mock_message_sender = AsyncMock()
    
    # Configurar mocks
    mock_player_repo.get_stats.return_value = {...}
    
    # Crear y aplicar efecto
    effect = MyCustomEffect(param1=10, param2=5.5)
    await effect.apply(user_id=1, player_repo=mock_player_repo, message_sender=mock_message_sender)
    
    # Verificar resultados
    assert mock_player_repo.set_stats.called
```

## Configuración en Producción

Para deshabilitar un efecto, simplemente no lo agregues al `GameTick`:

```python
# Servidor de desarrollo - todos los efectos
self.game_tick.add_effect(HungerThirstEffect())
self.game_tick.add_effect(GoldDecayEffect(percentage=1.0, interval_seconds=60.0))

# Servidor de producción - solo hambre/sed
self.game_tick.add_effect(HungerThirstEffect())
```

Para ajustar parámetros, modifica los valores al crear el efecto:

```python
# Oro más agresivo: 5% cada 30 segundos
self.game_tick.add_effect(GoldDecayEffect(percentage=5.0, interval_seconds=30.0))

# Oro más suave: 0.5% cada 2 minutos
self.game_tick.add_effect(GoldDecayEffect(percentage=0.5, interval_seconds=120.0))
```
