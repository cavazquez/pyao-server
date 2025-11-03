# TODO: MapManager Public API

**Prioridad:** Media  
**Esfuerzo:** 2-3 horas  
**Archivos afectados:** `src/game/map_manager.py`, `src/services/party_service.py`

## Problema

`PartyService` necesita acceder a información de jugadores online, pero `MapManager` no expone métodos públicos para esto. Actualmente se accede directamente a `_players_by_map` (atributo privado), lo cual genera warnings SLF001.

## Ubicaciones con acceso privado

Todas en `src/services/party_service.py`:

1. **Línea 57**: `_get_player_message_sender()` - Busca MessageSender por user_id
2. **Líneas 81, 83**: `_find_player_by_username()` - Busca user_id por username
3. **Líneas 248, 255**: `invite_to_party()` - Lista jugadores online y busca target
4. **Línea 290**: `invite_to_party()` - Obtiene username del inviter

## Solución Propuesta

Agregar métodos públicos a `MapManager`:

### 1. `get_player_message_sender(user_id: int) -> MessageSender | None`
```python
def get_player_message_sender(self, user_id: int) -> MessageSender | None:
    """Get MessageSender for a specific player.
    
    Args:
        user_id: User ID to search for
        
    Returns:
        MessageSender if player found online, None otherwise
    """
    for players_dict in self._players_by_map.values():
        if user_id in players_dict:
            message_sender, _ = players_dict[user_id]
            return message_sender
    return None
```

### 2. `find_player_by_username(username: str) -> int | None`
```python
def find_player_by_username(self, username: str) -> int | None:
    """Find online player by username (case-insensitive).
    
    Args:
        username: Username to search for
        
    Returns:
        user_id if player found online, None otherwise
    """
    username_lower = username.lower()
    for players_dict in self._players_by_map.values():
        for user_id, (_, player_username) in players_dict.items():
            if player_username.lower() == username_lower:
                return user_id
    return None
```

### 3. `get_all_online_players() -> list[tuple[int, str, int]]`
```python
def get_all_online_players(self) -> list[tuple[int, str, int]]:
    """Get list of all online players.
    
    Returns:
        List of tuples (user_id, username, map_id)
    """
    players = []
    for map_id, players_dict in self._players_by_map.items():
        for user_id, (_, username) in players_dict.items():
            players.append((user_id, username, map_id))
    return players
```

### 4. `get_player_username(user_id: int) -> str | None`
```python
def get_player_username(self, user_id: int) -> str | None:
    """Get username for a specific player.
    
    Args:
        user_id: User ID to search for
        
    Returns:
        Username if player found online, None otherwise
    """
    for players_dict in self._players_by_map.values():
        if user_id in players_dict:
            _, username = players_dict[user_id]
            return username
    return None
```

## Beneficios

- ✅ Elimina 7 warnings SLF001
- ✅ API más limpia y documentada
- ✅ Encapsula lógica de búsqueda en MapManager
- ✅ Más fácil de testear
- ✅ Más fácil de mantener
- ✅ Permite cambiar implementación interna sin afectar PartyService

## Checklist

- [ ] Agregar métodos públicos a `MapManager`
- [ ] Actualizar `PartyService` para usar nuevos métodos
- [ ] Remover `# noqa: SLF001` de `party_service.py`
- [ ] Agregar tests unitarios para nuevos métodos
- [ ] Actualizar documentación

## Notas

- Los métodos propuestos son simples wrappers sobre `_players_by_map`
- No cambian la funcionalidad, solo encapsulan el acceso
- Mantienen la misma complejidad O(n) de búsqueda
- Podrían optimizarse con índices en el futuro si es necesario
