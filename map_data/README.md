# Datos de Mapas - PyAO Server

Esta carpeta contiene todos los datos de mapas del juego en formato JSON, consolidando información de tiles y recursos.

## Formato de Mapa

```json
{
  "id": 1,
  "name": "Nombre del Mapa",
  "width": 100,
  "height": 100,
  "blocked_tiles": [
    {"x": 10, "y": 20, "type": "wall"},
    {"x": 11, "y": 20, "type": "tree"},
    {"x": 12, "y": 20, "type": "water"}
  ],
  "spawn_points": [
    {"x": 50, "y": 50, "description": "Punto de spawn principal"}
  ]
}
```

## Tipos de Tiles Bloqueados

- `wall` - Pared (no se puede atravesar)
- `tree` - Árbol (no se puede atravesar)
- `water` - Agua (no se puede atravesar sin barco)
- `door` - Puerta (puede abrirse/cerrarse)
- `rock` - Roca (no se puede atravesar)

## Conversión desde .map Original

Para convertir un archivo `.map` del AO original:

```bash
# TODO: Implementar script de conversión
python scripts/convert_map.py clientes/Mapa1.map map_data/map_1.json
```

## Estructura de Archivos

La carpeta contiene **580 archivos** (290 mapas × 2 archivos cada uno):

### Archivos de Tiles (`map_*.json`)
- `map_1.json` - Datos del mapa 1 (tiles bloqueados, dimensiones, etc.)
- `map_2.json` - Datos del mapa 2
- `map_3.json` - Datos del mapa 3
- ... hasta `map_290.json`

### Archivos de Recursos (`resources_*.json`)
- `resources_1.json` - Recursos del mapa 1 (objetos, NPCs spawn, etc.)
- `resources_2.json` - Recursos del mapa 2
- `resources_3.json` - Recursos del mapa 3
- ... hasta `resources_290.json`

Cada mapa tiene **dos archivos asociados** con el mismo número de ID.

## Notas

- Los mapas del AO original son 100x100 tiles
- Las coordenadas van de 1 a 100 (no de 0 a 99)
- El formato JSON es temporal, podríamos migrar a formato binario más eficiente
