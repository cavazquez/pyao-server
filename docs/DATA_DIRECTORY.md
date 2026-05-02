# Datos del Juego (TOML)

Este directorio contiene todos los datos del juego en formato TOML.

## 📁 Estructura

```
data/
├── classes/              # Sistema de clases de personaje
│   ├── definitions.toml  # Definiciones de las 11 clases
│   └── balance.toml      # Modificadores de combate y razas
│
├── crafting/             # Sistemas de crafting
│   ├── armor.toml        # Recetas de herrería (armaduras)
│   ├── weapons.toml      # Recetas de herrería (armas)
│   ├── carpentry.toml    # Recetas de carpintería
│   └── materials.toml    # Materiales para crafting
│
├── items/                # Catálogo de items (1,096 items)
│   ├── consumables/      # Comida, pociones, bebidas, scrolls
│   ├── equipment/        # Armas, armaduras, escudos, cascos
│   ├── misc/             # Teleports, flechas, barcos
│   ├── resources/        # Minerales, madera, gemas, flores
│   ├── tools/            # Llaves, libros, instrumentos
│   └── world_objects/    # Puertas, árboles, muebles
│
├── npcs/                 # NPCs y merchants
│   ├── complete.toml     # Todos los NPCs (336)
│   ├── hostiles.toml     # NPCs hostiles (147)
│   ├── traders.toml      # NPCs comerciantes (80)
│   ├── friendly.toml     # NPCs amigables
│   ├── merchants.toml    # Inventarios de merchants (640 items)
│   ├── summons.toml      # NPCs invocables (20)
│   └── loot_tables.toml  # Tablas de loot
│
├── world/                # Mapas y mundo
│   ├── cities.toml       # Ciudades y puntos de spawn (7)
│   ├── map_npcs.toml     # Spawns de NPCs en mapas
│   └── map_doors.toml    # Configuración de puertas
│
└── spells.toml           # Catálogo de hechizos (45)
```

## 📊 Estadísticas

| Categoría | Archivos | Registros |
|-----------|----------|-----------|
| NPCs | 7 | 336 totales |
| Items | 30 | 1,096 |
| Hechizos | 1 | 45 |
| Clases | 2 | 11 |
| Crafting | 4 | ~150 recetas |
| Mundo | 3 | 7 ciudades |

## 🔧 Uso en el Servidor

### Cargar NPCs
```python
from src.services.game.npc_service import NPCService

service = NPCService(Path('data'))
print(f'{len(service.all_npcs)} NPCs cargados')
```

### Cargar Items
```python
from src.models.item_catalog import ItemCatalog

catalog = ItemCatalog()
item = catalog.get_item_data(1)  # Manzana Roja
```

### Cargar Hechizos
```python
from src.models.spell_catalog import SpellCatalog

catalog = SpellCatalog()
spell = catalog.get_spell_data(2)  # Dardo Mágico
```

## 📝 Notas

- Todos los archivos usan encoding UTF-8
- El formato TOML es validado automáticamente por `tomllib`
- Los IDs deben ser únicos dentro de cada catálogo
- Los archivos se cargan al iniciar el servidor
