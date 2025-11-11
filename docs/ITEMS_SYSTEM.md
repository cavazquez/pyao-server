# Sistema de Ítems

## Visión General
El sistema de ítems maneja la interacción con los objetos del juego, permitiendo a los jugadores usar, equipar y gestionar sus posesiones.

## Implementación Actual

### Uso de Ítems
- **Manzanas (ID: 1)**: Restauran 20 puntos de hambre al ser consumidas.
- **Otros ítems**: Muestran un mensaje indicando que no se pueden usar.

### Archivos Principales
- `src/tasks/inventory/task_use_item.py`: Maneja la lógica de uso de ítems.
- `src/network/packet_handlers.py`: Mapea el paquete `USE_ITEM` a `TaskUseItem`.

## Próximas Mejoras
- [ ] Implementar `ItemFactory` para crear instancias de ítems.
- [ ] Añadir más tipos de ítems (pociones, equipo, etc.).
- [ ] Documentar el sistema completo una vez implementado.

## Uso
1. **Consumir una manzana**:
   - Doble clic en la manzana en el inventario.
   - La barra de hambre aumentará en 20 puntos.
   - Se mostrará un mensaje de confirmación.

2. **Verificar logs**:
   - Los mensajes de depuración se registran en los logs del servidor.
