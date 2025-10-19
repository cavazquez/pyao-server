# Migración de Tests: MapMessageSender

## Resumen

Se crearon tests unitarios completos para el componente `MapMessageSender`, que maneja el envío de información de mapa y posición al cliente.

## Estado

- ✅ **Tests creados:** 9 tests
- ✅ **Tests pasando:** 650/650 (100%)
- ✅ **Linting:** Sin errores
- ✅ **Documentación:** README actualizado
- ✅ **Integración:** MessageSender ahora delega a MapMessageSender
- ✅ **Imports limpiados:** Removidos imports no usados de msg.py

## Archivo Creado

### `tests/test_message_map_sender.py` (9 tests)

Tests para todos los métodos públicos de `MapMessageSender`:

1. **`test_send_change_map()`** - Verifica envío de cambio de mapa con versión
2. **`test_send_change_map_default_version()`** - Verifica versión por defecto (0)
3. **`test_send_pos_update()`** - Verifica envío de actualización de posición
4. **`test_send_object_create()`** - Verifica creación de objetos en el mapa
5. **`test_send_object_delete()`** - Verifica eliminación de objetos del mapa
6. **`test_send_block_position_blocked()`** - Verifica bloqueo de tiles (blocked=True)
7. **`test_send_block_position_unblocked()`** - Verifica desbloqueo de tiles (blocked=False)
8. **`test_map_message_sender_initialization()`** - Verifica inicialización correcta
9. **`test_multiple_map_messages()`** - Verifica envío de múltiples mensajes consecutivos

## Métodos Testeados

### `MapMessageSender`

| Método | Descripción | Tests |
|--------|-------------|-------|
| `send_change_map()` | Envía cambio de mapa | 2 |
| `send_pos_update()` | Envía actualización de posición | 1 |
| `send_object_create()` | Crea objeto en el mapa | 1 |
| `send_object_delete()` | Elimina objeto del mapa | 1 |
| `send_block_position()` | Bloquea/desbloquea tile | 2 |
| Inicialización | Constructor | 1 |
| Múltiples mensajes | Envíos consecutivos | 1 |

## Protocolo Verificado

### CHANGE_MAP (Packet ID: 3)
- **Formato:** PacketID (u8) + map_number (int16 LE) + version (int16 LE)
- **Tamaño:** 5 bytes
- **Uso:** Cambiar de mapa

### POS_UPDATE (Packet ID: 4)
- **Formato:** PacketID (u8) + x (u8) + y (u8)
- **Tamaño:** 3 bytes
- **Uso:** Actualizar posición del jugador

### OBJECT_CREATE (Packet ID: 9)
- **Formato:** PacketID (u8) + x (u8) + y (u8) + grh_index (int16 LE)
- **Tamaño:** 5 bytes
- **Uso:** Mostrar item en el suelo

### OBJECT_DELETE (Packet ID: 10)
- **Formato:** PacketID (u8) + x (u8) + y (u8)
- **Tamaño:** 3 bytes
- **Uso:** Remover item del suelo

### BLOCK_POSITION (Packet ID: 11)
- **Formato:** PacketID (u8) + x (u8) + y (u8) + blocked (u8)
- **Tamaño:** 4 bytes
- **Uso:** Marcar tile como bloqueado/desbloqueado

## Cobertura

Todos los métodos públicos de `MapMessageSender` están cubiertos al 100%:

- ✅ Inicialización
- ✅ Cambio de mapa (con y sin versión)
- ✅ Actualización de posición
- ✅ Creación de objetos
- ✅ Eliminación de objetos
- ✅ Bloqueo/desbloqueo de tiles
- ✅ Múltiples mensajes consecutivos

## Integración con MessageSender

`MessageSender` ahora delega los métodos de mapa a `MapMessageSender`:

```python
class MessageSender:
    def __init__(self, connection: ClientConnection):
        self.connection = connection
        # Componentes especializados
        self.map = MapMessageSender(connection)
    
    async def send_change_map(self, map_number: int, version: int = 0) -> None:
        await self.map.send_change_map(map_number, version)
    
    async def send_pos_update(self, x: int, y: int) -> None:
        await self.map.send_pos_update(x, y)
    
    async def send_object_create(self, x: int, y: int, grh_index: int) -> None:
        await self.map.send_object_create(x, y, grh_index)
    
    async def send_object_delete(self, x: int, y: int) -> None:
        await self.map.send_object_delete(x, y)
    
    async def send_block_position(self, x: int, y: int, blocked: bool) -> None:
        await self.map.send_block_position(x, y, blocked)
```

### Imports Limpiados

Se removieron de `message_sender.py`:
- `build_change_map_response`
- `build_pos_update_response`
- `build_object_create_response`
- `build_object_delete_response`
- `build_block_position_response`

Estos ahora solo se importan en `message_map_sender.py`.

## Uso en el Código

El componente `MapMessageSender` es utilizado en:

- **`task_login.py`** - Envía posición inicial y objetos del mapa
- **`player_service.py`** - Envía cambio de mapa al jugador
- **`task_request_position_update.py`** - Envía actualización de posición
- **`multiplayer_broadcast_service.py`** - Broadcast de objetos y bloqueos a todos los jugadores

**Nota:** El código existente sigue funcionando sin cambios, ya que `MessageSender` delega transparentemente a `MapMessageSender`.

## Comandos de Verificación

```bash
# Ejecutar solo tests de MapMessageSender
uv run pytest tests/test_message_map_sender.py -v

# Ejecutar todos los tests
uv run pytest -v

# Verificar linting
uv run ruff check tests/test_message_map_sender.py

# Verificar cobertura
uv run pytest tests/test_message_map_sender.py --cov=src.message_map_sender --cov-report=term-missing
```

## Próximos Pasos

Continuar con la migración de tests para los demás componentes de MessageSender:

- [ ] `message_console_sender.py`
- [ ] `message_audio_sender.py`
- [ ] `message_visual_effects_sender.py`
- [ ] `message_player_stats_sender.py`
- [ ] `message_character_sender.py`
- [ ] `message_inventory_sender.py`

## Notas

- Todos los tests usan mocks de `ClientConnection` para aislar la lógica
- Se verifican tanto la estructura de los packets como los valores exactos
- Los tests cubren casos normales y casos edge (versión por defecto, blocked true/false, etc.)
- El formato de los packets sigue el protocolo estándar de Argentum Online
