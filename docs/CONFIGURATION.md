# Configuración del servidor PyAO

Este documento describe la configuración del servidor definida en `config/server.toml` y cómo se relaciona con el código.

> Nota: Todas las lecturas desde código se realizan a través de `ConfigManager` (`src/config/config_manager.py`).

---

## Sección `[server]`

Configuración básica del servidor TCP.

- `host` (str)
  - Dirección donde escucha el servidor.
  - Uso: `server.py` (`config_manager.get("server.host", "0.0.0.0")`).
- `port` (int)
  - Puerto TCP del servidor.
  - Uso: `server.py` (`config_manager.get("server.port", 7666)`).
- `max_connections` (int)
  - Máximo de conexiones simultáneas.
- `buffer_size` (int)
  - Tamaño del buffer de lectura de sockets.

---

## Sección `[game]`

Parámetros generales de juego.

- `max_players_per_map` (int)
  - Máxima cantidad de jugadores por mapa.
- `respawn_check_interval` (float)
  - Intervalo (segundos) entre chequeos de respawn.
- `npc_respawn_base_time` / `npc_respawn_random_variance` (float)
  - Tiempo base y variación para respawn de NPCs.

---

## Sección `[game.combat]`

Configuración del sistema de combate.

- `melee_range` (int)
  - Alcance de ataque cuerpo a cuerpo.
  - Uso: `CombatValidator` (`game.combat.melee_range`).
- `base_critical_chance` (float)
  - Probabilidad base de crítico.
- `base_dodge_chance` (float)
  - Probabilidad base de esquive.
- `defense_per_level` (float)
- `armor_reduction` (float)

Críticos y esquives (usado por `CriticalCalculator`):

- `critical_damage_multiplier` (float)
- `critical_agi_modifier` (float)
- `dodge_agi_modifier` (float)
- `max_critical_chance` (float)
- `max_dodge_chance` (float)
- `base_agility` (int)

---

## Sección `[game.work]`

Experiencia de trabajos (talar, pesca, minería) y progresión de skills.

- `exp_wood` (int)
  - Exp por cada acción de tala.
  - Uso: `TaskWorkLeftClick` (`EXP_LENA`).
- `exp_mineral` (int)
  - Exp por cada acción de minería.
- `exp_fish` (int)
  - Exp por cada acción de pesca.
- `exp_per_level` (int)
  - Exp necesaria por nivel de skill.
  - Uso: `PlayerRepository.add_skill_experience`.
- `max_work_distance` (int)
  - Distancia máxima al objetivo para trabajar.

---

## Sección `[game.stamina]`

Configura la energía/stamina de los jugadores.

Valores base:

- `max_stamina` (int)
- `stamina_regen_rate` (float)
- `stamina_drain_rate` (float)

Costos por acción (usados por `StaminaService`):

- `cost_walk` (int)
- `cost_attack` (int)
- `cost_spell` (int)
- `cost_work` (int)

Regeneración (usados por `StaminaService` y `StaminaRegenEffect`):

- `regen_tick` (int)
  - Puntos regenerados por tick.
- `regen_resting` (int)
  - Puntos regenerados por tick cuando el jugador está descansando.

---

## Sección `[game.inventory]`

Configuración de inventario de jugadores.

- `max_slots` (int)
  - Cantidad máxima de slots de inventario.
  - Uso:
    - `InventoryRepository.MAX_SLOTS`.
    - `InventoryStorage.MAX_SLOTS`.
    - Validaciones de slots de inventario en `PacketValidator` y tasks de inventario.

---

## Sección `[game.bank]`

Configuración de bóvedas bancarias.

- `max_slots` (int)
  - Cantidad máxima de slots del banco.
  - Uso:
    - `BankRepository.MAX_SLOTS`.
    - Validaciones de slots de banco en `PacketValidator` y tasks de banco.

---

## Sección `[game.hunger_thirst]`

Defaults del efecto de hambre y sed. Actualmente los valores runtime se leen desde Redis, pero estos parámetros sirven como fuente de verdad/documentación y pueden usarse para inicializar Redis en el futuro.

- `enabled` (bool)
- `interval_sed` (int)
  - Segundos entre ticks de sed.
- `interval_hambre` (int)
  - Segundos entre ticks de hambre.
- `reduccion_agua` (int)
  - Puntos de sed que se reducen por tick.
- `reduccion_hambre` (int)
  - Puntos de hambre que se reducen por tick.

Runtime actual:

- `HungerThirstEffect` lee estos valores desde Redis usando `ServerRepository.get_effect_config_int` y las claves `RedisKeys.CONFIG_HUNGER_THIRST_*`.

---

## Sección `[game.gold_decay]`

Defaults del efecto de decaimiento de oro.

- `enabled` (bool)
- `percentage` (float)
  - Porcentaje de oro a perder en cada tick.
- `interval_seconds` (float)
  - Intervalo entre ticks de decaimiento.

Runtime actual:

- Los valores runtime se almacenan en Redis bajo `RedisKeys.CONFIG_GOLD_DECAY_*` y se leen a través de `ServerRepository` (cuando se implemente el efecto correspondiente).

---

## Sección `[logging]`

Configuración de logging del servidor.

- `level` (str)
- `format` (str)
- `file` (str)

Usadas por la configuración inicial de logging en el arranque del servidor.

---

## Sección `[redis]`

Datos de conexión a Redis.

- `host` (str)
- `port` (int)
- `db` (int)
- `max_connections` (int)

Complementan los defaults definidos en `src/utils/redis_config.RedisConfig` y pueden ser usados por el inicializador del cliente de Redis.

---

## Overrides por variables de entorno

`ConfigManager` permite sobrescribir valores de `server.toml` mediante variables de entorno (ejemplos):

- `PYAO_SERVER_HOST` → `server.host`
- `PYAO_SERVER_PORT` → `server.port`
- `PYAO_SERVER_MAX_CONNECTIONS` → `server.max_connections`
- `PYAO_REDIS_HOST` → `redis.host`

Revisar `ConfigManager._load_env_overrides` para la lista completa.

---

## Nota sobre `src/config.py` (legacy)

Existe un archivo `src/config.py` con dataclasses de configuración que fue parte de una implementación anterior.

Actualmente **no se utiliza en runtime**, porque la configuración real pasa por:

- `config/server.toml` como fuente de verdad editable.
- `src/config/config_manager.py` (`ConfigManager`) como única API de lectura.

Para agregar o modificar configuración, usar siempre `server.toml` + `ConfigManager` y **no** `src/config.py`.
