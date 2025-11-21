# Herramientas de Mantenimiento

Esta carpeta contiene herramientas de mantenimiento y utilidades para el servidor PyAO.

## 📁 Estructura

```
tools/
├── extraction/      # Extracción de datos desde VB6/Godot
├── analysis/        # Análisis de mapas y búsqueda de elementos
├── validation/      # Verificación y validación de datos
├── compression/     # Compresión/descompresión de mapas
└── dev/             # Utilidades de desarrollo y testing
```

## 🔧 Categorías

### 1. Extracción (`extraction/`)

Herramientas para extraer datos desde archivos del cliente VB6 o Godot y convertirlos a formatos TOML/JSON.

- **`extract_npcs_data.py`** - Extrae todos los NPCs (336 totales) desde `NPCs.dat`
- **`extract_transitions.py`** - Extrae transiciones de mapa desde archivos `.inf` del servidor VB6
- **`extract_vb6_map_objects.py`** - Extrae objetos de mapas VB6 (puertas, yunques, fraguas, etc.)
- **`extract_balance_data.py`** - Extrae datos de balance desde `Balance.dat`
- **`extract_crafting_data.py`** - Extrae datos de crafting/artesanía
- **`rebuild_map_from_binary.py`** - Reconstruye mapas desde formato binario

### 2. Análisis (`analysis/`)

Herramientas para analizar, buscar y verificar elementos específicos en los mapas.

- **`find_all_anvils_forges.py`** - Encuentra todos los yunques y fraguas en `obj.dat`
- **`find_blocked_objects.py`** - Encuentra objetos en tiles bloqueados (puertas)
- **`find_door_grh.py`** - Busca GrhIndex de puertas en un mapa específico
- **`find_grh_in_maps.py`** - Busca un GrhIndex específico en todos los mapas
- **`search_grh_in_all_maps.py`** - Busca GrhIndex en todas las capas de todos los mapas
- **`analyze_godot_maps.py`** - Analiza archivos `.map` del cliente Godot
- **`analyze_grh_28929.py`** - Analiza el GrhIndex 28929 en detalle
- **`analyze_missing_tree_grh.py`** - Analiza árboles faltantes en mapas
- **`check_tile_grh.py`** - Verifica el GrhIndex de un tile específico
- **`check_godot_map.py`** - Verifica tiles específicos en mapas de Godot

### 3. Validación (`validation/`)

Herramientas para verificar la integridad y correcta carga de datos.

- **`check_signs.py`** - Verifica carteles en `signs.toml` y si están en los mapas
- **`check_anvils_and_transitions.py`** - Verifica yunques y transiciones
- **`check_specific_tile.py`** - Verifica una coordenada específica en cualquier mapa
- **`check_vb6_map_format.py`** - Verifica formato de mapas VB6
- **`check_area_around.py`** - Verifica un área de 5x5 alrededor de una coordenada
- **`check_coord.py`** - Verifica coordenadas específicas
- **`check_coord_with_offset.py`** - Verifica coordenadas con offset +/-1

### 4. Compresión (`compression/`)

Herramientas para comprimir y descomprimir datos de mapas.

- **`compress_map_data.py`** - Comprime la carpeta `map_data` usando LZMA (.xz)
- **`decompress_map_data.py`** - Descomprime archivos `map_data.xz`

### 5. Desarrollo (`dev/`)

Utilidades para desarrollo y testing.

- **`add_test_items.py`** - Agrega items de prueba al inventario de un usuario
- **`normalize_transitions.py`** - Normaliza archivos `transitions_XXX-XXX.json`

## 🚀 Uso

### Ejecutar una herramienta

```bash
# Desde el directorio raíz del proyecto
uv run python tools/extraction/extract_npcs_data.py
uv run python tools/dev/add_test_items.py <user_id>
uv run python tools/validation/check_signs.py
```

### Ejemplos comunes

```bash
# Agregar items de prueba a un usuario
uv run python tools/dev/add_test_items.py 1

# Normalizar transiciones
uv run python tools/dev/normalize_transitions.py

# Comprimir mapas
uv run python tools/compression/compress_map_data.py

# Verificar carteles
uv run python tools/validation/check_signs.py
```

## 📝 Notas

- Todas las herramientas están en Python 3
- La mayoría usa `pathlib.Path` para manejo de archivos
- Varias herramientas procesan archivos binarios del cliente VB6
- Algunas herramientas tienen paths hardcodeados (considerar refactorizar)

## 🔗 Documentación

Para más detalles, ver:
- `docs/TOOLS_ANALYSIS.md` - Análisis completo de todas las herramientas

## ⚠️ Advertencias

- Algunas herramientas modifican archivos directamente
- Siempre hacer backup antes de ejecutar herramientas que modifican datos
- Verificar que los paths en las herramientas sean correctos para tu sistema

