# Sistema de Comercio - PyAO Server

Documentación completa del sistema de comercio (compra/venta) con NPCs mercaderes en PyAO Server, basado en el protocolo de Argentum Online 0.13.3 y compatible con el cliente Godot.

## 📋 Tabla de Contenidos

- [Visión General](#visión-general)
- [Arquitectura](#arquitectura)
- [Protocolo de Comunicación](#protocolo-de-comunicación)
- [Flujo de Comercio](#flujo-de-comercio)
- [Implementación del Cliente](#implementación-del-cliente)
- [Casos de Uso](#casos-de-uso)

---

## 🎯 Visión General

El sistema de comercio permite a los jugadores:
- **Comprar items** de NPCs mercaderes usando oro
- **Vender items** de su inventario a NPCs mercaderes
- Ver el **inventario del mercader** con precios
- Ver su **propio inventario** durante la transacción
- **Cerrar la ventana** de comercio en cualquier momento

### Características Principales

- ✅ Interfaz gráfica dual (inventario del mercader + inventario del jugador)
- ✅ Selección de cantidad de items a comprar/vender
- ✅ Visualización de precios y estadísticas de items
- ✅ Validación de oro suficiente para compras
- ✅ Validación de espacio en inventario
- ✅ Transacciones atómicas (todo o nada)
- ✅ Sincronización en tiempo real entre cliente y servidor

---

## 🏗️ Arquitectura

### Componentes del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    Cliente Godot                         │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  MerchantPanel   │  │  BankPanel       │            │
│  │  (UI)            │  │  (UI)            │            │
│  └────────┬─────────┘  └────────┬─────────┘            │
│           │                     │                        │
│  ┌────────▼─────────────────────▼─────────┐            │
│  │      GameProtocol (Packets)             │            │
│  └────────────────┬────────────────────────┘            │
└───────────────────┼─────────────────────────────────────┘
                    │ TCP Socket
┌───────────────────▼─────────────────────────────────────┐
│                 PyAO Server                              │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  TaskLeftClick   │  │  TaskCommerceBuy │            │
│  │  (Abrir ventana) │  │  (Comprar)       │            │
│  └────────┬─────────┘  └────────┬─────────┘            │
│           │                     │                        │
│  ┌────────▼─────────────────────▼─────────┐            │
│  │      CommerceService                    │            │
│  │  - Validar transacciones                │            │
│  │  - Actualizar inventarios               │            │
│  │  - Gestionar oro                        │            │
│  └────────────────┬────────────────────────┘            │
│                   │                                      │
│  ┌────────────────▼────────────────────────┐            │
│  │  InventoryRepository + PlayerRepository │            │
│  │  (Redis)                                 │            │
│  └─────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## 📡 Protocolo de Comunicación

### Packets del Cliente → Servidor

#### 1. LEFT_CLICK (ID: 26)
**Descripción:** Click en un NPC para iniciar comercio

**Formato:**
```python
packet_id: u8 = 26  # LEFT_CLICK
x: u8               # Posición X del NPC
y: u8               # Posición Y del NPC
```

**Ejemplo (GDScript):**
```gdscript
static func WriteLeftClick(x:int, y:int) -> void:
    _writer.put_u8(Enums.ClientPacketID.LeftClick)
    _writer.put_u8(x)
    _writer.put_u8(y)
```

---

#### 2. COMMERCE_BUY (ID: 40)
**Descripción:** Comprar item del mercader

**Formato:**
```python
packet_id: u8 = 40  # COMMERCE_BUY
slot: u8            # Slot del inventario del mercader (1-based)
quantity: u16       # Cantidad a comprar
```

**Ejemplo (GDScript):**
```gdscript
static func WriteCommerceBuy(slot:int, quantity:int) -> void:
    _writer.put_u8(Enums.ClientPacketID.CommerceBuy)
    _writer.put_u8(slot)
    _writer.put_16(quantity)
```

---

#### 3. COMMERCE_SELL (ID: 42)
**Descripción:** Vender item al mercader

**Formato:**
```python
packet_id: u8 = 42  # COMMERCE_SELL
slot: u8            # Slot del inventario del jugador (1-based)
quantity: u16       # Cantidad a vender
```

**Ejemplo (GDScript):**
```gdscript
static func WriteCommerceSell(slot:int, quantity:int) -> void:
    _writer.put_u8(Enums.ClientPacketID.CommerceSell)
    _writer.put_u8(slot)
    _writer.put_16(quantity)
```

---

#### 4. COMMERCE_END (ID: 17)
**Descripción:** Cerrar ventana de comercio

**Formato:**
```python
packet_id: u8 = 17  # COMMERCE_END
```

**Ejemplo (GDScript):**
```gdscript
static func WriteCommerceEnd() -> void:
    _writer.put_u8(Enums.ClientPacketID.CommerceEnd)
```

---

### Packets del Servidor → Cliente

#### 1. COMMERCE_INIT (ID: 7)
**Descripción:** Abrir ventana de comercio con inventario del mercader

**Formato:**
```python
packet_id: u8 = 7           # COMMERCE_INIT
npc_id: u16                 # ID del NPC mercader
num_items: u8               # Número de items en inventario del mercader

# Por cada item:
for i in range(num_items):
    slot: u8                # Número de slot (1-20)
    item_id: u16            # ID del item
    name: unicode_string    # Nombre del item
    quantity: u16           # Cantidad disponible
    price: u32              # Precio de venta (oro)
    grh_index: u16          # Índice gráfico
    obj_type: u8            # Tipo de objeto
    max_hit: u16            # Daño máximo (armas)
    min_hit: u16            # Daño mínimo (armas)
    max_def: u16            # Defensa máxima (armaduras)
    min_def: u16            # Defensa mínima (armaduras)
```

---

#### 2. COMMERCE_END (ID: 5)
**Descripción:** Confirmar cierre de ventana de comercio

**Formato:**
```python
packet_id: u8 = 5  # COMMERCE_END
```

---

#### 3. CHANGE_INVENTORY_SLOT (ID: 47)
**Descripción:** Actualizar un slot del inventario del jugador

**Formato:**
```python
packet_id: u8 = 47          # CHANGE_INVENTORY_SLOT
slot: u8                    # Número de slot (1-20)
item_id: u16                # ID del item (0 si está vacío)
name: unicode_string        # Nombre del item
quantity: u16               # Cantidad
grh_index: u16              # Índice gráfico
obj_type: u8                # Tipo de objeto
equipped: u8                # 1 si está equipado, 0 si no
max_hit: u16                # Daño máximo (armas)
min_hit: u16                # Daño mínimo (armas)
max_def: u16                # Defensa máxima (armaduras)
min_def: u16                # Defensa mínima (armaduras)
sale_price: u32             # Precio de venta
```

---

#### 4. UPDATE_GOLD (ID: 18)
**Descripción:** Actualizar oro del jugador

**Formato:**
```python
packet_id: u8 = 18  # UPDATE_GOLD
gold: u32           # Cantidad de oro actual
```

---

#### 5. CONSOLE_MSG (ID: 24)
**Descripción:** Mensaje en consola (errores, confirmaciones)

**Formato:**
```python
packet_id: u8 = 24          # CONSOLE_MSG
message: unicode_string     # Mensaje a mostrar
font_index: u8              # Índice de fuente (color)
```

---

## 🔄 Flujo de Comercio

### 1. Abrir Ventana de Comercio

**Secuencia:**
1. Jugador hace click en un NPC
2. Cliente envía `LEFT_CLICK(x, y)`
3. Servidor verifica si el NPC es un mercader
4. Si es mercader, servidor envía `COMMERCE_INIT` con inventario
5. Cliente abre `MerchantPanel` y muestra items disponibles

---

### 2. Comprar Item

**Secuencia:**
1. Jugador selecciona item del mercader y cantidad
2. Cliente envía `COMMERCE_BUY(slot, quantity)`
3. Servidor valida oro suficiente y espacio en inventario
4. Si es válido:
   - Resta oro del jugador
   - Agrega item al inventario del jugador
   - Resta item del inventario del mercader
   - Envía `UPDATE_GOLD` y `CHANGE_INVENTORY_SLOT`
5. Si hay error, envía `CONSOLE_MSG` con el error

---

### 3. Vender Item

**Secuencia:**
1. Jugador selecciona item de su inventario y cantidad
2. Cliente envía `COMMERCE_SELL(slot, quantity)`
3. Servidor valida que el item se puede vender
4. Si es válido:
   - Remueve item del inventario del jugador
   - Suma oro al jugador
   - Agrega item al inventario del mercader
   - Envía `UPDATE_GOLD` y `CHANGE_INVENTORY_SLOT`
5. Si hay error, envía `CONSOLE_MSG` con el error

---

### 4. Cerrar Ventana

**Secuencia:**
1. Jugador presiona botón "Cerrar" o tecla ESC
2. Cliente envía `COMMERCE_END`
3. Servidor confirma con `COMMERCE_END`
4. Cliente cierra la ventana

---

## 💻 Implementación del Cliente

### MerchantPanel (GDScript)

El cliente Godot ya tiene implementado `MerchantPanel` en `ui/hub/merchant_panel.gd`:

```gdscript
extends TextureRect
class_name MerchantPanel

@export var _merchantInventoryContainer: InventoryContainer
@export var _playerInventoryContainer: InventoryContainer
@export var _infoLabel: Label
@export var _quantitySpinBox: SpinBox

func _OnBuyButtonPressed() -> void:
    if _merchantInventoryContainer.GetSelectedSlot() == -1:
        return
    GameProtocol.WriteCommerceBuy(
        _merchantInventoryContainer.GetSelectedSlot() + 1,
        _GetQuantity()
    )

func _OnSellButtonPressed() -> void:
    if _playerInventoryContainer.GetSelectedSlot() == -1:
        return
    GameProtocol.WriteCommerceSell(
        _playerInventoryContainer.GetSelectedSlot() + 1,
        _GetQuantity()
    )

func _on_btn_close_pressed() -> void:
    GameProtocol.WriteCommerceEnd()
```

**Características:**
- Muestra dos inventarios lado a lado (mercader y jugador)
- SpinBox para seleccionar cantidad
- Botones "Comprar" y "Vender"
- Muestra información del item seleccionado (nombre, precio, stats)
- Cierra con botón o tecla ESC

---

## 📝 Casos de Uso

### Caso 1: Comprar Poción de Vida

**Escenario:**
- Jugador tiene 1000 oro
- Mercader vende "Poción de Vida" por 50 oro
- Jugador quiere comprar 5 pociones

**Flujo:**
1. Jugador hace click en el mercader
2. Se abre ventana de comercio
3. Jugador selecciona "Poción de Vida" (slot 3)
4. Jugador ingresa cantidad: 5
5. Jugador presiona "Comprar"
6. Servidor valida: 5 * 50 = 250 oro ✓
7. Servidor actualiza:
   - Oro del jugador: 1000 - 250 = 750
   - Inventario del jugador: +5 Pociones de Vida
   - Inventario del mercader: -5 Pociones de Vida
8. Cliente recibe:
   - `UPDATE_GOLD(750)`
   - `CHANGE_INVENTORY_SLOT(slot, poción, 5)`
   - `CONSOLE_MSG("Has comprado 5x Poción de Vida por 250 oro")`

---

### Caso 2: Vender Espada

**Escenario:**
- Jugador tiene "Espada de Hierro" (precio venta: 100 oro)
- Mercader compra items al 50% del precio

**Flujo:**
1. Jugador selecciona "Espada de Hierro" de su inventario
2. Jugador presiona "Vender"
3. Servidor calcula precio: 100 / 2 = 50 oro
4. Servidor actualiza:
   - Oro del jugador: +50
   - Inventario del jugador: -1 Espada de Hierro
   - Inventario del mercader: +1 Espada de Hierro
5. Cliente recibe:
   - `UPDATE_GOLD(nuevo_oro)`
   - `CHANGE_INVENTORY_SLOT(slot, vacío)`
   - `CONSOLE_MSG("Has vendido Espada de Hierro por 50 oro")`

---

### Caso 3: Error - Oro Insuficiente

**Escenario:**
- Jugador tiene 30 oro
- Intenta comprar item de 50 oro

**Flujo:**
1. Jugador selecciona item y presiona "Comprar"
2. Servidor valida oro: 30 < 50 ✗
3. Cliente recibe:
   - `CONSOLE_MSG("No tienes suficiente oro. Necesitas 50 oro.")`
4. No se realiza ninguna transacción

---

### Caso 4: Error - Inventario Lleno

**Escenario:**
- Jugador tiene inventario lleno (20/20 slots)
- Intenta comprar un item nuevo

**Flujo:**
1. Jugador selecciona item y presiona "Comprar"
2. Servidor valida espacio: 0 slots libres ✗
3. Cliente recibe:
   - `CONSOLE_MSG("Tu inventario está lleno")`
4. No se realiza ninguna transacción

---

## 🔧 Implementación del Servidor

### Archivos a Crear

```
src/
├── task_commerce_buy.py        # ⚠️ PENDIENTE
├── task_commerce_sell.py       # ⚠️ PENDIENTE
├── commerce_service.py         # ⚠️ PENDIENTE
├── merchant_repository.py      # ⚠️ PENDIENTE
└── task_commerce_end.py        # ✅ YA EXISTE
```

### Archivos a Modificar

```
src/
├── packet_id.py                # Descomentar COMMERCE_BUY, COMMERCE_SELL, COMMERCE_INIT
├── packet_handlers.py          # Agregar handlers para commerce_buy y commerce_sell
├── msg.py                      # Agregar build_commerce_init_response()
├── message_sender.py           # Agregar send_commerce_init()
└── task_left_click.py          # Detectar NPCs mercaderes y abrir comercio
```

### Estructura de Datos en Redis

```
# Inventario del mercader
merchant:{npc_id}:inventory     # Hash con slots
  slot_1 = "item_id:quantity"
  slot_2 = "item_id:quantity"
  ...

# Sesión de comercio activa
session:{user_id}:active_merchant = npc_id  # String con ID del mercader
```

---

## ✅ Checklist de Implementación

### Fase 1: Infraestructura Básica
- [ ] Crear `MerchantRepository` para gestionar inventarios de mercaderes
- [ ] Agregar campo `is_merchant` a NPCs en `data/npcs.toml`
- [ ] Crear inventarios iniciales de mercaderes en Redis
- [ ] Agregar método `get_merchant_inventory()` en `MerchantRepository`

### Fase 2: Protocolo
- [ ] Descomentar packet IDs en `packet_id.py`
- [ ] Implementar `build_commerce_init_response()` en `msg.py`
- [ ] Implementar `send_commerce_init()` en `message_sender.py`
- [ ] Agregar handlers en `packet_handlers.py`

### Fase 3: Lógica de Negocio
- [ ] Crear `CommerceService` con métodos `buy_item()` y `sell_item()`
- [ ] Implementar validaciones (oro, espacio, cantidad)
- [ ] Implementar transacciones atómicas
- [ ] Agregar logs de auditoría

### Fase 4: Tasks
- [ ] Modificar `TaskLeftClick` para detectar mercaderes
- [ ] Crear `TaskCommerceBuy` para compras
- [ ] Crear `TaskCommerceSell` para ventas
- [ ] Verificar `TaskCommerceEnd` (ya existe)

### Fase 5: Testing
- [ ] Tests unitarios de `CommerceService`
- [ ] Tests de `MerchantRepository`
- [ ] Tests de integración de compra/venta
- [ ] Tests de validaciones y errores

### Fase 6: Datos
- [ ] Configurar NPCs mercaderes en `data/npcs.toml`
- [ ] Crear inventarios iniciales de mercaderes
- [ ] Configurar precios de items en `data/items.toml`
- [ ] Agregar campo `sellable` a items

---

## 📚 Referencias

### Cliente Godot
- **Repositorio:** https://github.com/brian-christopher/ArgentumOnlineGodot
- **Archivo UI:** `ui/hub/merchant_panel.gd`
- **Protocolo:** `engine/autoload/game_protocol.gd`
- **Enums:** `common/enums/enums.gd`

### Servidor PyAO
- **Task existente:** `src/task_commerce_end.py`
- **Inventario:** `src/inventory_repository.py`
- **Items:** `src/items_catalog.py`
- **NPCs:** `data/npcs.toml`

### Protocolo AO
- **Versión:** 0.13.3
- **Basado en:** Argentum Online original (VB6)

---

## 🎯 Próximos Pasos

1. **Crear `MerchantRepository`** para gestionar inventarios de mercaderes en Redis
2. **Implementar `CommerceService`** con lógica de compra/venta
3. **Crear Tasks** para manejar packets `COMMERCE_BUY` y `COMMERCE_SELL`
4. **Modificar `TaskLeftClick`** para abrir ventana de comercio con mercaderes
5. **Agregar tests** para todas las funcionalidades
6. **Configurar mercaderes** en `data/npcs.toml` con inventarios iniciales
7. **Actualizar README.md** con documentación del sistema de comercio

---

**Última actualización:** 2025-10-18  
**Versión:** 0.4.0-alpha (planificado)  
**Estado:** 📝 Documentación completa - Pendiente implementación
