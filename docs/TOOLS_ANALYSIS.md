# Análisis de Herramientas en `tools/`

Este documento analiza todas las herramientas de mantenimiento y utilidades en la carpeta `tools/`.

## 📋 Resumen Ejecutivo

La carpeta `tools/` contiene **29 herramientas** organizadas en **5 subcarpetas** por categoría:

```
tools/
├── extraction/      # 6 herramientas - Extracción de datos
├── analysis/        # 11 herramientas - Análisis de mapas
├── validation/      # 7 herramientas - Verificación y validación
├── compression/     # 2 herramientas - Compresión/descompresión
└── dev/             # 2 herramientas - Utilidades de desarrollo
```

> **Nota**: Ver `tools/README.md` para instrucciones de uso detalladas.

1. **Extracción de Datos** (7 herramientas)
2. **Análisis de Mapas** (10 herramientas)
3. **Verificación y Validación** (6 herramientas)
4. **Compresión/Descompresión** (2 herramientas)
5. **Utilidades de Desarrollo** (4 herramientas)

---

## 🔍 Categorías Detalladas

### 1. Extracción de Datos

Herramientas para extraer datos desde archivos del cliente VB6 o Godot y convertirlos a formatos TOML/JSON.

#### `extract_npcs_data.py`
- **Propósito**: Extrae todos los NPCs (336 totales) desde `NPCs.dat`
- **Salida**: Estructuras TOML con atributos, inventarios, estadísticas y comportamientos
- **Categorías**: Comerciantes, Banqueros, Entrenadores, Resucitadores, etc.
- **Estado**: ✅ Completo

#### `extract_transitions.py`
- **Propósito**: Extrae transiciones de mapa desde archivos `.inf` del servidor VB6
- **Salida**: Archivos `transitions_XXX-XXX.json` en formato JSON
- **Formato**: Lee archivos binarios VB6 (Integer 16-bit, little-endian)
- **Estado**: ✅ Completo

#### `extract_vb6_map_objects.py`
- **Propósito**: Extrae objetos de mapas VB6 (puertas, yunques, fraguas, etc.)
- **Salida**: Archivos `objects_XXX-XXX.json` con objetos por mapa
- **Estado**: ✅ Completo

#### `extract_balance_data.py`
- **Propósito**: Extrae datos de balance desde `Balance.dat`
- **Salida**: Archivos TOML estructurados con datos de balance
- **Estado**: ✅ Completo

#### `extract_crafting_data.py`
- **Propósito**: Extrae datos de crafting/artesanía
- **Estado**: ⚠️ No revisado en detalle

#### `rebuild_map_from_binary.py`
- **Propósito**: Reconstruye mapas desde formato binario
- **Estado**: ⚠️ No revisado en detalle

#### `analyze_godot_maps.py`
- **Propósito**: Analiza archivos `.map` del cliente Godot para extraer transiciones
- **Formato**: Lee archivos binarios de Godot (headers de 272 bytes)
- **Estado**: ✅ Completo

---

### 2. Análisis de Mapas

Herramientas para analizar, buscar y verificar elementos específicos en los mapas.

#### `find_all_anvils_forges.py`
- **Propósito**: Encuentra todos los yunques (ObjType=27) y fraguas (ObjType=28) en `obj.dat`
- **Uso**: Análisis de recursos de crafting
- **Estado**: ✅ Funcional

#### `find_blocked_objects.py`
- **Propósito**: Encuentra objetos en tiles bloqueados que podrían ser puertas
- **Uso**: Identificación de puertas en mapas
- **Estado**: ✅ Funcional

#### `find_door_grh.py`
- **Propósito**: Busca GrhIndex de puertas en un mapa específico
- **Uso**: Verificación de puertas
- **Estado**: ✅ Funcional

#### `find_grh_in_maps.py`
- **Propósito**: Busca un GrhIndex específico en todos los mapas extraídos
- **Uso**: Búsqueda de gráficos específicos
- **Estado**: ✅ Funcional

#### `search_grh_in_all_maps.py`
- **Propósito**: Busca GrhIndex específicos en TODAS las capas de todos los mapas
- **Uso**: Búsqueda exhaustiva de gráficos
- **Estado**: ✅ Funcional

#### `find_grh_28929.py`
- **Propósito**: Busca específicamente el GrhIndex 28929
- **Uso**: Análisis de un gráfico específico
- **Estado**: ✅ Funcional

#### `analyze_grh_28929.py`
- **Propósito**: Analiza el GrhIndex 28929 en detalle
- **Uso**: Debugging de gráficos específicos
- **Estado**: ✅ Funcional

#### `analyze_missing_tree_grh.py`
- **Propósito**: Analiza árboles faltantes en mapas
- **Uso**: Verificación de recursos de tala
- **Estado**: ✅ Funcional

#### `check_godot_map.py`
- **Propósito**: Verifica el GrhIndex de tiles específicos en el mapa de Godot
- **Uso**: Verificación puntual de coordenadas
- **Estado**: ✅ Funcional

#### `check_tile_grh.py`
- **Propósito**: Verifica el GrhIndex de un tile específico
- **Uso**: Verificación puntual de tiles
- **Estado**: ✅ Funcional

---

### 3. Verificación y Validación

Herramientas para verificar la integridad y correcta carga de datos.

#### `check_signs.py`
- **Propósito**: Verifica cuántos carteles hay en `signs.toml` y si están en los mapas
- **Salida**: Lista de carteles encontrados en mapas
- **Estado**: ✅ Funcional

#### `check_anvils_and_transitions.py`
- **Propósito**: Verifica si yunques y transiciones están cargados correctamente
- **Uso**: Validación de recursos y transiciones
- **Estado**: ✅ Funcional

#### `check_specific_tile.py`
- **Propósito**: Verifica una coordenada específica en cualquier mapa
- **Uso**: Debugging de coordenadas específicas
- **Estado**: ✅ Funcional

#### `check_vb6_map_format.py`
- **Propósito**: Verifica el formato del mapa VB6 en coordenadas específicas
- **Uso**: Comparación entre formatos VB6 y Godot
- **Estado**: ✅ Funcional

#### `check_area_around.py`
- **Propósito**: Verifica un área de 5x5 alrededor de una coordenada
- **Uso**: Análisis de áreas específicas
- **Estado**: ✅ Funcional

#### `check_coord_with_offset.py`
- **Propósito**: Verifica coordenadas con offset +/-1 en X e Y
- **Uso**: Análisis de variaciones de coordenadas
- **Estado**: ✅ Funcional

#### `check_coord.py`
- **Propósito**: Verifica coordenadas específicas
- **Uso**: Verificación básica de coordenadas
- **Estado**: ✅ Funcional

---

### 4. Compresión/Descompresión

Herramientas para comprimir y descomprimir datos de mapas.

#### `compress_map_data.py`
- **Propósito**: Comprime la carpeta `map_data` usando LZMA (.xz)
- **Formato**: Archivo comprimido con headers `FILE:` y `SIZE:`
- **Uso**: Reducir tamaño de archivos de mapas
- **Estado**: ✅ Completo

#### `decompress_map_data.py`
- **Propósito**: Descomprime archivos `map_data.xz` generados por `compress_map_data`
- **Uso**: Restaurar archivos de mapas comprimidos
- **Estado**: ✅ Completo

---

### 5. Utilidades de Desarrollo

Herramientas para desarrollo y testing.

#### `add_test_items.py`
- **Propósito**: Agrega items de prueba al inventario de un usuario
- **Items**: Manzana Roja, Espada Larga, Pociones, Hacha
- **Uso**: Testing de inventario
- **Estado**: ✅ Funcional

#### `normalize_transitions.py`
- **Propósito**: Normaliza archivos `transitions_XXX-XXX.json` en `map_data/`
- **Funciones**:
  - Filtra transiciones válidas (mapas 1-290, coordenadas 1-100)
  - Elimina grupos sin exits válidos
  - Ordena por `from_map` y coordenadas (y, x)
  - Crea backups antes de sobreescribir
- **Uso**: Limpieza y validación de transiciones
- **Estado**: ✅ Completo

---

## 📊 Estadísticas

- **Total de herramientas**: 29 archivos Python
- **Total de líneas de código**: ~4,253 líneas
- **Herramientas completas**: ~25
- **Herramientas con estado desconocido**: 4
- **Categorías principales**: 5

---

## 🔧 Recomendaciones

### 1. Documentación
- ✅ **Bien**: La mayoría de herramientas tienen docstrings descriptivos
- ⚠️ **Mejorable**: Algunas herramientas tienen paths hardcodeados (ej: `find_all_anvils_forges.py`)
- 💡 **Sugerencia**: Crear un README.md en `tools/` con instrucciones de uso

### 2. Organización
- ✅ **Completado**: Herramientas organizadas en subcarpetas por categoría
- ✅ **Estructura**: 
  ```
  tools/
    extraction/      # Extracción de datos
    analysis/        # Análisis de mapas
    validation/      # Verificación y validación
    compression/     # Compresión/descompresión
    dev/             # Utilidades de desarrollo
  ```
- ✅ **README**: Creado `tools/README.md` con instrucciones de uso

### 3. Mantenimiento
- ⚠️ **Atención**: Algunas herramientas tienen paths absolutos hardcodeados
- 💡 **Sugerencia**: Usar paths relativos o configuración desde `pyproject.toml`

### 4. Testing
- ⚠️ **Falta**: No hay tests para las herramientas
- 💡 **Sugerencia**: Agregar tests básicos para herramientas críticas

### 5. Integración
- ✅ **Bien**: `add_test_items.py` usa repositorios del servidor
- 💡 **Sugerencia**: Más herramientas podrían integrarse con el sistema del servidor

---

## 🎯 Herramientas Más Útiles

1. **`extract_npcs_data.py`**: Extracción completa de NPCs
2. **`extract_transitions.py`**: Extracción de transiciones desde VB6
3. **`normalize_transitions.py`**: Normalización y validación de transiciones
4. **`add_test_items.py`**: Utilidad práctica para testing
5. **`compress_map_data.py` / `decompress_map_data.py`**: Gestión de archivos de mapas

---

## 📝 Notas Adicionales

- Todas las herramientas están en Python 3
- La mayoría usa `pathlib.Path` para manejo de archivos
- Varias herramientas procesan archivos binarios del cliente VB6
- Algunas herramientas están específicamente diseñadas para debugging de mapas
- Las herramientas de extracción generan datos en formato TOML/JSON para el servidor

---

## 🔗 Relación con el Proyecto

Estas herramientas son **esenciales** para:
- Migración de datos desde el servidor VB6
- Validación de datos de mapas
- Debugging de problemas de mapas/gráficos
- Mantenimiento de datos del juego
- Testing y desarrollo

---

**Última actualización**: 2025-01-XX
**Autor del análisis**: AI Assistant

