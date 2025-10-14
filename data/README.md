# Catálogos de Datos en TOML

Este directorio contiene los catálogos de datos del juego en formato TOML, reemplazando el archivo `localindex.dat` del cliente original.

## 📁 Archivos

### `npcs.toml`
Catálogo de NPCs (Non-Player Characters)

**Campos**:
- `id` - ID único del NPC
- `nombre` - Nombre del NPC
- `descripcion` - Descripción del NPC
- `body_id` - ID del sprite del cuerpo
- `head_id` - ID del sprite de la cabeza
- `es_hostil` - Si ataca a jugadores
- `es_atacable` - Si puede ser atacado
- `nivel` - Nivel del NPC
- `hp_max` - Vida máxima
- `oro_min` - Oro mínimo que dropea
- `oro_max` - Oro máximo que dropea

**Ejemplo**:
```toml
[[npc]]
id = 1
nombre = "Goblin"
descripcion = "Un goblin salvaje que ataca a los viajeros."
body_id = 500
head_id = 0
es_hostil = true
es_atacable = true
nivel = 5
hp_max = 100
oro_min = 10
oro_max = 50
```

### `hechizos.toml`
Catálogo de Hechizos

**Campos**:
- `id` - ID único del hechizo
- `nombre` - Nombre del hechizo
- `descripcion` - Descripción del hechizo
- `palabras_magicas` - Palabras mágicas para lanzarlo
- `mana_requerido` - Maná necesario
- `min_skill` - Skill mínimo requerido
- `sta_requerido` - Stamina requerida
- `cooldown` - Tiempo de espera en segundos
- `icono_index` - ID del ícono
- `hechizero_msg` - Mensaje para el que lanza
- `propio_msg` - Mensaje cuando se lanza sobre uno mismo
- `target_msg` - Mensaje para el objetivo

**Ejemplo**:
```toml
[[hechizo]]
id = 1
nombre = "Dardo Mágico"
descripcion = "Causa 14 a 18 puntos de daño a la víctima."
palabras_magicas = "OHL VOR PEK"
mana_requerido = 10
min_skill = 0
sta_requerido = 2
cooldown = 0
```

### `objetos.toml`
Catálogo de Objetos (información de texto)

**Nota**: El catálogo completo de items ya existe en `src/items_catalog.py` (1049 items).
Este archivo es para información adicional de texto (descripciones, mensajes de uso, etc.)

**Campos**:
- `id` - ID único del objeto
- `nombre` - Nombre del objeto
- `descripcion` - Descripción del objeto
- `texto_uso` - Mensaje al usar el objeto
- `texto_equipar` - Mensaje al equipar el objeto

**Ejemplo**:
```toml
[[objeto]]
id = 1
nombre = "Poción Roja"
descripcion = "Una poción que restaura 50 puntos de vida."
texto_uso = "Has bebido una Poción Roja y recuperas vida."
```

## 🔧 Uso en el Servidor

### Cargar NPCs

```python
import tomllib

with open("data/npcs.toml", "rb") as f:
    data = tomllib.load(f)
    npcs = data["npc"]

for npc in npcs:
    print(f"{npc['id']}: {npc['nombre']} - {npc['descripcion']}")
```

### Cargar Hechizos

```python
import tomllib

with open("data/hechizos.toml", "rb") as f:
    data = tomllib.load(f)
    hechizos = data["hechizo"]

for hechizo in hechizos:
    print(f"{hechizo['id']}: {hechizo['nombre']} - {hechizo['mana_requerido']} mana")
```

### Cargar Objetos

```python
import tomllib

with open("data/objetos.toml", "rb") as f:
    data = tomllib.load(f)
    objetos = data["objeto"]

for objeto in objetos:
    print(f"{objeto['id']}: {objeto['nombre']} - {objeto['descripcion']}")
```

## 🎯 Servicios Futuros

### NPCCatalog

```python
class NPCCatalog:
    """Catálogo de NPCs cargado desde npcs.toml"""
    
    def __init__(self, toml_path: str = "data/npcs.toml"):
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
            self.npcs = {npc["id"]: npc for npc in data["npc"]}
    
    def get_npc(self, npc_id: int) -> dict | None:
        return self.npcs.get(npc_id)
    
    def get_all_npcs(self) -> list[dict]:
        return list(self.npcs.values())
```

### SpellCatalog

```python
class SpellCatalog:
    """Catálogo de hechizos cargado desde hechizos.toml"""
    
    def __init__(self, toml_path: str = "data/hechizos.toml"):
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
            self.spells = {spell["id"]: spell for spell in data["hechizo"]}
    
    def get_spell(self, spell_id: int) -> dict | None:
        return self.spells.get(spell_id)
```

## 📊 Ventajas sobre localindex.dat

1. **Formato Moderno**: TOML es más legible y mantenible que `.dat`
2. **Separación**: Un archivo por tipo de dato (NPCs, hechizos, objetos)
3. **Versionable**: Fácil de trackear cambios en Git
4. **Tipado**: Estructura clara con tipos de datos
5. **Comentarios**: Se pueden agregar comentarios en el archivo
6. **Validación**: Fácil de validar con schemas
7. **Extensible**: Fácil agregar nuevos campos

## 🔄 Migración desde localindex.dat

Si tienes un `localindex.dat` existente, puedes crear un script de migración:

```python
def migrate_localindex_to_toml():
    """Convierte localindex.dat a archivos TOML separados"""
    # Leer localindex.dat
    # Parsear secciones [NPC], [HECHIZO], [OBJ]
    # Escribir a npcs.toml, hechizos.toml, objetos.toml
    pass
```

## 📝 Notas

- Los archivos TOML usan UTF-8
- Python 3.11+ incluye `tomllib` en la librería estándar
- Para Python < 3.11, usar `tomli` package
- Los IDs deben ser únicos dentro de cada catálogo
- Los archivos se cargan al iniciar el servidor

## 🚀 Próximos Pasos

1. Crear `NPCCatalog`, `SpellCatalog`, `ObjectCatalog`
2. Integrar con `NPCService`
3. Agregar validación de schemas
4. Crear herramienta de edición visual
5. Implementar hot-reload de catálogos
