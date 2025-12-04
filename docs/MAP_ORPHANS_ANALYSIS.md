# Mapas Huérfanos

Mapas sin transiciones de entrada (no se puede llegar a ellos normalmente).

## Lista de Mapas Huérfanos (13 total)

| ID | Nombre | Tipo | Salidas | Estado |
|----|--------|------|---------|--------|
| 169 | Mapa 169 | water | 0 | ❌ Obsoleto |
| 170 | Mapa 170 | dungeon | 2 | ⚠️ Revisar |
| 198 | Mapa 198 | water | 0 | ❌ Obsoleto |
| 199 | Mapa 199 | unknown | 0 | ❌ Obsoleto |
| 208 | Mapa 208 | dungeon | 0 | ❌ Obsoleto |
| 272 | Mapa 272 | water | 0 | ❌ Obsoleto |
| 273 | Mapa 273 | water | 0 | ❌ Obsoleto |
| 274 | Mapa 274 | water | 4 | ⚠️ Revisar |
| 276 | Mapa 276 | unknown | 0 | ❌ Obsoleto |
| 277 | Mapa 277 | water | 0 | ❌ Obsoleto |
| 278 | Mapa 278 | water | 0 | ❌ Obsoleto |
| 279 | Mapa 279 | water | 0 | ❌ Obsoleto |
| 280 | Mapa 280 | dungeon | 172 | ⚠️ Hub sin entrada |

## Análisis

### Categorías

**Obsoletos (10 mapas)**: Sin salidas ni entradas, probablemente mapas de prueba
- IDs: 169, 198, 199, 208, 272, 273, 276, 277, 278, 279

**Para revisar (3 mapas)**: Tienen salidas pero no entradas
- **Mapa 170**: Dungeon con 2 salidas - posible calabozo oculto
- **Mapa 274**: Agua con 4 salidas - posible zona marítima
- **Mapa 280**: ¡172 salidas! Parece un hub o zona central sin entrada

### Mapa 280 - Caso especial

Este mapa tiene 172 salidas pero 0 entradas. Esto sugiere:
1. Era un mapa hub accesible solo por teleport/comando GM
2. Las transiciones de entrada fueron eliminadas accidentalmente
3. Es una zona de desarrollo/pruebas

### Recomendaciones

1. **No eliminar aún** - Mantener por compatibilidad
2. **Agregar marcador** en metadatos: `orphan = true`
3. **Investigar mapa 280** - Podría ser importante

## Acciones Tomadas

- [x] Documentación generada
- [ ] Marcar como huérfanos en metadatos
- [ ] Investigar mapa 280 en el VB6 original


