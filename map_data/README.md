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
python scripts/convert_map.py clientes/Mapa1.map map_data/001_map.json
```

## Estructura de Archivos

La carpeta contiene **580 archivos** (290 mapas × 2 archivos cada uno):

### Formato de Nombres

Los archivos usan **padding de 3 dígitos** para ordenarse alfabéticamente en pares:

```
001_map.json         # Datos del mapa 1 (tiles bloqueados, dimensiones)
001_resources.json   # Recursos del mapa 1 (objetos, NPCs spawn)
002_map.json         # Datos del mapa 2
002_resources.json   # Recursos del mapa 2
...
290_map.json         # Datos del mapa 290
290_resources.json   # Recursos del mapa 290
```

**Ventajas de este formato:**
- ✅ Se ordenan alfabéticamente con cada par junto
- ✅ Fácil identificar archivos relacionados
- ✅ Nombres descriptivos (`_map` vs `_resources`)
- ✅ Padding uniforme para todos los números (001-290)

## Notas

- Los mapas del AO original son 100x100 tiles
- Las coordenadas van de 1 a 100 (no de 0 a 99)
- El formato JSON es temporal, podríamos migrar a formato binario más eficiente
