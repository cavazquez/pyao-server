# TODO: Party Public Methods

**Prioridad:** Baja  
**Esfuerzo:** 30 minutos  
**Archivos afectados:** `src/models/party.py`, `src/services/party_service.py`

## Problema

`PartyService` accede al método privado `_can_join_by_level()` de la clase `Party`, generando warning SLF001.

## Ubicación

`src/services/party_service.py` línea 210:
```python
if not party._can_join_by_level(target_level):  # noqa: SLF001
```

## Solución

Hacer público el método `_can_join_by_level()` en `src/models/party.py`:

### Antes:
```python
def _can_join_by_level(self, target_level: int) -> bool:
    """Check if target level is within acceptable range."""
    # ...
```

### Después:
```python
def can_join_by_level(self, target_level: int) -> bool:
    """Check if target level is within acceptable range.
    
    Args:
        target_level: Level of the player trying to join
        
    Returns:
        True if level difference is acceptable, False otherwise
    """
    # ...
```

## Beneficios

- ✅ Elimina 1 warning SLF001
- ✅ API más clara (método debería ser público)
- ✅ Mejor documentación
- ✅ Más fácil de testear

## Checklist

- [ ] Renombrar `_can_join_by_level()` a `can_join_by_level()` en `Party`
- [ ] Actualizar llamada en `PartyService`
- [ ] Remover `# noqa: SLF001`
- [ ] Agregar docstring completo
- [ ] Verificar que no haya otras referencias al método privado

## Notas

Este método debería haber sido público desde el principio, ya que es parte de la lógica de negocio de Party que otros servicios necesitan usar.
