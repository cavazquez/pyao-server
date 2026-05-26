# Mejoras en Configuration Management

**Fecha:** 2025-01-XX  
**Versión:** 0.6.4-alpha  
**Estado:** ✅ Completado

---

## 📋 Resumen

Se ha mejorado el sistema de configuración del servidor PyAO implementando:

1. ✅ **Validación estricta con Pydantic**: Validación automática de tipos y rangos
2. ✅ **Soporte completo de variables de entorno**: Todas las configuraciones pueden ser sobrescritas
3. ✅ **Compatibilidad hacia atrás**: El código existente sigue funcionando sin cambios
4. ✅ **Mejor documentación**: Valores válidos documentados en el código

---

## 🎯 Cambios Implementados

### 1. Nuevo Sistema con Pydantic

Se creó `src/config/game_config.py` con clases Pydantic para validación estricta:

```python
from src.config.game_config import GameConfig, get_game_config

# Cargar configuración
config = get_game_config()

# Acceso type-safe
port = config.server.port  # int, validado entre 1024-65535
critical_chance = config.game.combat.base_critical_chance  # float, validado 0.0-1.0
```

**Beneficios:**
- ✅ Validación automática de tipos
- ✅ Validación de rangos (puertos, probabilidades, etc.)
- ✅ Type hints completos
- ✅ Autocompletado en IDEs

### 2. Variables de Entorno

Todas las configuraciones pueden ser sobrescritas con variables de entorno:

```bash
# Ejemplos
export PYAO_SERVER__PORT=9999
export PYAO_SERVER__HOST=0.0.0.0
export PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE=0.20
export PYAO_GAME__INVENTORY__MAX_SLOTS=40
export PYAO_GAME__BANK__MAX_SLOTS=50
```

**Notación:**
- Prefijo: `PYAO_`
- Separador de niveles: `__` (doble guión bajo)
- Ejemplo: `PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE`

### 3. Compatibilidad con ConfigManager

El `ConfigManager` existente ahora usa internamente el nuevo sistema:

```python
from src.config.config_manager import config_manager

# Código existente sigue funcionando
port = config_manager.get("server.port")  # ✅ Funciona igual
critical = config_manager.get("game.combat.base_critical_chance")  # ✅ Funciona igual
```

**Internamente:**
- `ConfigManager` carga con `GameConfig` (Pydantic)
- Sincroniza a dict legacy para compatibilidad
- Validación automática por Pydantic

---

## 📚 Estructura de Configuración

### ServerConfig
```python
server:
  host: str = "0.0.0.0"
  port: int = 7666  # Validado: 1024-65535
  max_connections: int = 1000  # Validado: >= 1
  buffer_size: int = 4096  # Validado: >= 1024
```

### GameConfigSection
```python
game:
  max_players_per_map: int = 100  # Validado: >= 1
  respawn_check_interval: float = 5.0  # Validado: >= 0.1
  npc_respawn_base_time: float = 30.0  # Validado: >= 1.0
  npc_respawn_random_variance: float = 15.0  # Validado: >= 0.0
  
  combat: CombatConfig
  work: WorkConfig
  stamina: StaminaConfig
  hunger_thirst: HungerThirstConfig
  gold_decay: GoldDecayConfig
  inventory: InventoryConfig
  bank: BankConfig
  character: CharacterConfig
```

### CombatConfig
```python
game.combat:
  melee_range: int = 1  # Validado: 1-10
  base_critical_chance: float = 0.15  # Validado: 0.0-1.0
  base_dodge_chance: float = 0.05  # Validado: 0.0-1.0
  defense_per_level: float = 0.1  # Validado: >= 0.0
  armor_reduction: float = 0.1  # Validado: 0.0-1.0
  critical_damage_multiplier: float = 2.0  # Validado: >= 1.0
  critical_agi_modifier: float = 0.005  # Validado: >= 0.0
  dodge_agi_modifier: float = 0.007  # Validado: >= 0.0
  max_critical_chance: float = 0.50  # Validado: 0.0-1.0
  max_dodge_chance: float = 0.40  # Validado: 0.0-1.0
  base_agility: int = 10  # Validado: >= 1
```

---

## 🔄 Migración

### Opción 1: Mantener código existente (Recomendado)
```python
# Código existente sigue funcionando sin cambios
from src.config.config_manager import config_manager

port = config_manager.get("server.port")
```

### Opción 2: Migrar a nuevo sistema (Opcional)
```python
# Nuevo código puede usar GameConfig directamente
from src.config.game_config import get_game_config

config = get_game_config()
port = config.server.port  # Type-safe, validado automáticamente
```

---

## ✅ Validaciones Automáticas

### Puertos
- Rango: 1024-65535
- Tipo: int

### Probabilidades (combate)
- Rango: 0.0-1.0
- Tipo: float
- Ejemplos: `base_critical_chance`, `base_dodge_chance`, `max_critical_chance`

### Valores Positivos
- Muchos valores deben ser >= 1 o >= 0
- Validación automática por Pydantic

### Strings (logging level)
- Pattern: `^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$`
- Validación automática

---

## 🧪 Testing

Tests completos en `tests/config/test_game_config.py`:

```bash
uv run pytest tests/config/test_game_config.py -v
```

**Cobertura:**
- ✅ Carga desde TOML
- ✅ Validación de tipos
- ✅ Validación de rangos
- ✅ Variables de entorno
- ✅ Método `get()` para compatibilidad
- ✅ Método `reload()`

---

## 📝 Ejemplos de Uso

### Cargar configuración
```python
from src.config.game_config import get_game_config

config = get_game_config()
print(f"Puerto: {config.server.port}")
print(f"Crítico base: {config.game.combat.base_critical_chance}")
```

### Usar variables de entorno
```bash
# .env o export
PYAO_SERVER__PORT=9999
PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE=0.25
```

```python
from src.config.game_config import GameConfig

# Carga automáticamente desde .env y variables de entorno
config = GameConfig()
assert config.server.port == 9999
assert config.game.combat.base_critical_chance == 0.25
```

### Recargar configuración
```python
from src.config.game_config import get_game_config

config = get_game_config()
config.reload("config/server.toml")  # Recarga desde archivo
```

### Compatibilidad con código existente
```python
from src.config.config_manager import config_manager

# Todo el código existente sigue funcionando
port = config_manager.get("server.port")
critical = config_manager.get("game.combat.base_critical_chance")
```

---

## 🚀 Próximos Pasos (Opcional)

1. **Migración gradual**: Ir migrando código a usar `GameConfig` directamente
2. **Documentación automática**: Generar docs desde modelos Pydantic
3. **Validación en runtime**: Agregar validación cuando se cambian valores

---

## 📚 Referencias

- **Pydantic**: https://docs.pydantic.dev/
- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Archivo de configuración**: `config/server.toml`
- **Código fuente**: `src/config/game_config.py`

---

**Última actualización:** 2025-01-XX

