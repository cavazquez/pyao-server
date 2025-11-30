# Sistema de Ítems

## Visión General
El sistema de ítems maneja la interacción con los objetos del juego, permitiendo a los jugadores usar, equipar y gestionar sus posesiones.

---

## ✅ Implementación Actual

### Uso de Ítems Básicos

#### Comida
- **Manzanas (ID: 1)**: Restauran 20 puntos de hambre al ser consumidas.

#### Pociones ✅ IMPLEMENTADO
El sistema completo de pociones está implementado y funcional:

##### 🔵 Poción Azul (ID 37)
- **Tipo**: Restauración de Mana (TipoPocion 4)
- **Efecto**: Restaura Mana inmediatamente
- **Cantidad**: 12-20 puntos (aleatorio entre `MinModificador` y `MaxModificador`)
- **Uso**: Doble clic en el inventario

##### 🔴 Poción Roja (ID 38)
- **Tipo**: Restauración de HP (TipoPocion 3)
- **Efecto**: Restaura HP inmediatamente
- **Cantidad**: 30 puntos (valor fijo)
- **Uso**: Doble clic en el inventario

##### 🟢 Poción Verde (ID 39)
- **Tipo**: Modificador de Fuerza (TipoPocion 2)
- **Efecto**: Aumenta Fuerza temporalmente
- **Modificador**: +2 a +6 puntos (aleatorio)
- **Duración**: Configurable desde `DuracionEfecto` (por defecto 1000ms = 1 segundo)
- **Uso**: Doble clic en el inventario

##### 🟡 Poción Amarilla (ID 36)
- **Tipo**: Modificador de Agilidad (TipoPocion 1)
- **Efecto**: Aumenta Agilidad temporalmente
- **Modificador**: +3 a +5 puntos (aleatorio)
- **Duración**: Configurable desde `DuracionEfecto` (por defecto 1000ms = 1 segundo)
- **Uso**: Doble clic en el inventario

##### 🟣 Poción Violeta (ID 166)
- **Tipo**: Cura Veneno (TipoPocion 5)
- **Efecto**: Remueve el estado de envenenamiento
- **Uso**: Doble clic en el inventario

##### ⚫ Poción Negra (ID 645)
- **Tipo**: Invisibilidad (TipoPocion 6)
- **Efecto**: Te vuelve invisible por 5 minutos
- **Mecánica**: 
  - Otros jugadores no te pueden ver (envía `CHARACTER_REMOVE` a todos los jugadores en tu mapa)
  - El efecto se almacena en `invisible_until` y se limpia automáticamente al expirar
- **Uso**: Doble clic en el inventario

#### Herramientas de Trabajo
- **Hacha de Leñador (ID 561)**: Activa modo trabajo de talar
- **Piquete de Minero (ID 562)**: Activa modo trabajo de minería
- **Caña de pescar (ID 563)**: Activa modo trabajo de pesca

#### Barca (ID 173)
- Alterna entre modo navegación y caminata
- Requiere estar cerca del agua para activar
- Requiere estar cerca de tierra para desactivar

---

## 🏗️ Arquitectura

### Componentes Principales

```
UseItemCommandHandler
    ↓
ItemCatalog (obtiene datos completos del TOML)
    ↓
Aplica efectos según TipoPocion:
    - Restauración inmediata (HP/Mana)
    - Modificadores temporales (Agilidad/Fuerza)
    - Curación de estados (Veneno)
    - Efectos especiales (Invisibilidad)
```

### Archivos Principales

- `src/command_handlers/use_item_handler.py`: Handler principal para uso de items
- `src/models/item_catalog.py`: Catálogo de items con datos completos desde TOML
- `src/models/item_types.py`: Tipos de objetos y pociones (TipoPocion enum)
- `src/models/items_catalog.py`: Catálogo de items procesados
- `data/items/consumables/potions.toml`: Definiciones de pociones

### Dependencias

- `ItemCatalog`: Acceso a datos completos de items desde TOML
- `PlayerRepository`: Actualización de stats (HP, Mana, atributos)
- `MapManager`: Broadcast multijugador (para invisibilidad)
- `BroadcastService`: Envío de CHARACTER_REMOVE para invisibilidad

---

## 📝 Tipos de Pociones (TipoPocion)

Según `src/models/item_types.py`:

```python
class TipoPocion(IntEnum):
    AGILIDAD = 1   # Modifica la Agilidad
    FUERZA = 2     # Modifica la Fuerza
    HP = 3         # Repone HP
    MANA = 4       # Repone Mana
    CURA_VENENO = 5  # Cura Envenenamiento
    INVISIBLE = 6  # Invisibilidad
```

---

## 🔧 Flujo de Uso de Pociones

1. **Jugador usa poción** (doble clic en inventario)
2. **UseItemCommandHandler detecta TipoPocion**
3. **Consume el item** (decrementa cantidad o elimina si es el último)
4. **Aplica efectos según tipo**:
   - **HP/Mana**: Restauración inmediata → `UPDATE_USER_STATS`
   - **Agilidad/Fuerza**: Modificador temporal → `UPDATE_STRENGTH_AND_DEXTERITY`
   - **Cura Veneno**: Remueve `poisoned_until` → sin paquete adicional
   - **Invisibilidad**: Establece `invisible_until` → `CHARACTER_REMOVE` a otros jugadores
5. **Actualiza inventario** en el cliente

---

## 📊 Datos de Pociones en TOML

Las pociones se definen en `data/items/consumables/potions.toml` con los siguientes campos:

```toml
[[item]]
id = 37
Name = "Poción Azul"
TipoPocion = 4          # Tipo de poción
MinModificador = 12     # Valor mínimo (para mana)
MaxModificador = 20     # Valor máximo (para mana)
DuracionEfecto = 1000   # Duración en ms (para modificadores temporales)
```

---

## 🎮 Uso en el Juego

### Ejemplo: Usar Poción Azul
1. Jugador tiene Poción Azul en el inventario (slot 5, cantidad 30)
2. Doble clic en la poción
3. Se consume 1 unidad (queda 29)
4. Se restaura entre 12-20 puntos de Mana aleatoriamente
5. Se actualiza la barra de Mana en el cliente
6. Se muestra mensaje: "¡Has usado Poción Azul!"

### Ejemplo: Usar Poción Negra
1. Jugador usa Poción Negra
2. Se aplica invisibilidad por 5 minutos
3. Todos los jugadores en el mapa reciben `CHARACTER_REMOVE` del jugador
4. El jugador ya no es visible para otros
5. Al expirar (o usar hechizo que remueve invisibilidad), vuelve a ser visible

---

## 🔄 Integración con Otros Sistemas

### Sistema de Estados
- **Veneno**: Removido por Poción Violeta
- **Invisibilidad**: Aplicado por Poción Negra, removido por hechizos específicos

### Sistema de Atributos
- **Modificadores temporales**: Agilidad y Fuerza se aplican y se limpian automáticamente
- **Efecto**: El `AttributeModifiersEffect` verifica y limpia modificadores expirados cada 10 segundos

### Sistema de Broadcast
- **Invisibilidad**: Usa `CHARACTER_REMOVE` para ocultar jugador
- **Reaparición**: Usa `CHARACTER_CREATE` para mostrar jugador nuevamente

---

## 🚀 Próximas Mejoras

- [ ] Más tipos de pociones (estamina, hambre/sed)
- [ ] Pociones con efectos combinados
- [ ] Sistema de cooldown para pociones
- [ ] Efectos visuales al usar pociones
- [ ] Sonidos al consumir pociones

---

## 📚 Referencias

- `src/models/item_types.py`: Tipos de pociones
- `data/items/consumables/potions.toml`: Definiciones completas
- `src/command_handlers/use_item_handler.py`: Implementación del handler
- `docs/MAGIC_SYSTEM.md`: Sistema de magia relacionado (hechizos)
