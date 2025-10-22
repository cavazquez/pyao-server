"""Script para separar items.toml en múltiples archivos organizados por categoría."""

import tomllib
from collections import defaultdict
from pathlib import Path

# Mapeo de ObjType a archivo destino
OBJTYPE_TO_FILE = {
    # equipment/
    2: "equipment/weapons.toml",
    3: "equipment/armors.toml",
    16: "equipment/shields.toml",
    17: "equipment/helmets.toml",
    18: "equipment/rings.toml",
    21: "equipment/jewels.toml",
    # consumables/
    1: "consumables/food.toml",
    13: "consumables/drinks.toml",
    11: "consumables/potions.toml",
    24: "consumables/scrolls.toml",
    # resources/
    14: "resources/wood.toml",
    23: "resources/minerals.toml",
    22: "resources/minerals.toml",  # Yacimientos también van a minerals
    29: "resources/gems.toml",
    30: "resources/flowers.toml",
    # world_objects/
    6: "world_objects/doors.toml",
    8: "world_objects/signs.toml",
    20: "world_objects/furniture.toml",
    4: "world_objects/trees.toml",
    7: "world_objects/containers.toml",
    # tools/
    9: "tools/keys.toml",
    26: "tools/instruments.toml",
    27: "tools/blacksmith.toml",
    28: "tools/blacksmith.toml",  # Fragua también va a blacksmith
    12: "tools/books.toml",
    10: "tools/books.toml",  # Foros también van a books
    # misc/
    32: "misc/arrows.toml",
    31: "misc/boats.toml",
    33: "misc/bottles.toml",
    34: "misc/bottles.toml",
    19: "misc/teleports.toml",
    5: "misc/money.toml",
    15: "misc/other.toml",
    25: "misc/other.toml",
    35: "misc/other.toml",
    36: "misc/other.toml",
    37: "misc/other.toml",
}


def split_items() -> None:  # noqa: PLR0915
    """Separa items.toml en múltiples archivos."""
    # Cargar items.toml original
    items_file = Path("data/items.toml")

    if not items_file.exists():
        print(f"❌ Error: {items_file} no existe")
        return

    print(f"📖 Leyendo {items_file}...")
    with items_file.open("rb") as f:
        data = tomllib.load(f)

    items = data.get("item", [])
    print(f"✓ {len(items)} items encontrados")

    # Agrupar items por archivo destino
    items_by_file = defaultdict(list)
    unknown_items = []

    for item in items:
        obj_type = item.get("ObjType")
        target_file = OBJTYPE_TO_FILE.get(obj_type)

        if target_file:
            items_by_file[target_file].append(item)
        else:
            unknown_items.append(item)
            # Items sin mapeo van a misc/other.toml
            items_by_file["misc/other.toml"].append(item)

    if unknown_items:
        print(f"⚠️  {len(unknown_items)} items sin ObjType mapeado, van a misc/other.toml")

    # Crear directorio data/items/
    items_dir = Path("data/items")
    items_dir.mkdir(exist_ok=True)

    # Crear subdirectorios
    for subdir in ["equipment", "consumables", "resources", "world_objects", "tools", "misc"]:
        (items_dir / subdir).mkdir(exist_ok=True)

    # Constantes para formato TOML
    ascii_limit = 127
    priority_fields = {"id", "Name", "GrhIndex", "ObjType"}

    # Escribir archivos
    total_written = 0
    for target_file, file_items in sorted(items_by_file.items()):
        output_path = items_dir / target_file

        # Ordenar items por ID
        file_items.sort(key=lambda x: x.get("id", 0))

        # Construir contenido TOML manualmente
        lines = [f"# {output_path.stem.title()} - {len(file_items)} items\n"]
        lines.append("# Generated from items.toml\n\n")

        for item in file_items:
            lines.append("[[item]]\n")

            # Escribir campos en orden específico primero
            for key in ["id", "Name", "GrhIndex", "ObjType"]:
                if key in item:
                    value = item[key]
                    # Poner entre comillas keys con caracteres especiales
                    key_str = (
                        f'"{key}"' if any(ord(c) > ascii_limit or c in " -" for c in key) else key
                    )

                    if isinstance(value, str):
                        # Escapar strings correctamente en TOML
                        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                        lines.append(f'{key_str} = "{escaped}"\n')
                    else:
                        lines.append(f"{key_str} = {value}\n")

            # Resto de campos
            for key, value in sorted(item.items()):
                if key not in priority_fields:
                    # Poner entre comillas keys con caracteres especiales
                    key_str = (
                        f'"{key}"' if any(ord(c) > ascii_limit or c in " -" for c in key) else key
                    )

                    if isinstance(value, str):
                        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                        lines.append(f'{key_str} = "{escaped}"\n')
                    else:
                        lines.append(f"{key_str} = {value}\n")

            lines.append("\n")

        # Escribir archivo
        output_path.write_text("".join(lines), encoding="utf-8")
        total_written += len(file_items)
        print(f"✓ {output_path}: {len(file_items)} items")

    print(f"\n✅ Completado: {total_written} items escritos en {len(items_by_file)} archivos")
    print("\n📁 Estructura creada en: data/items/")

    # Crear archivo README
    readme = items_dir / "README.md"
    readme.write_text("""# Items Data

Items organizados por categoría de gameplay.

## Estructura

- **equipment/** - Items equipables (armas, armaduras, etc.)
- **consumables/** - Items consumibles (comida, pociones, etc.)
- **resources/** - Recursos recolectables (madera, minerales, etc.)
- **world_objects/** - Objetos del mundo (puertas, muebles, etc.)
- **tools/** - Herramientas y libros
- **misc/** - Misceláneos (flechas, barcos, etc.)

## Nota

Estos archivos fueron generados automáticamente desde `data/items.toml`.
El loader carga todos los archivos `.toml` de este directorio recursivamente.
""")
    print(f"✓ README creado: {readme}")


if __name__ == "__main__":
    split_items()
