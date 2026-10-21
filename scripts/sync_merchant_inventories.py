#!/usr/bin/env python3
"""Sincroniza inventarios de mercaderes desde npcs_*.toml a merchant_inventories.toml.

Este script lee los inventarios definidos en:
- npcs_complete.toml
- npcs_traders_extended.toml

Y genera un archivo merchant_inventories.toml unificado.

Nota: Los archivos TOML originales tienen errores de formato (claves duplicadas),
así que usamos un parser basado en regex en lugar de tomllib estándar.
"""

import re
import sys
from pathlib import Path
from typing import NotRequired, TypedDict


class MerchantItem(TypedDict):
    """Artículo y cantidad del catálogo de un comerciante."""

    item_id: int
    quantity: int
    nombre: str


class MerchantData(TypedDict):
    """Datos de un comerciante antes de generar TOML."""

    npc_id: int
    nombre: str
    descripcion: str
    items: list[MerchantItem]
    source: NotRequired[str]


def parse_npc_blocks(content: str) -> list[MerchantData]:
    """Parsea bloques de NPCs desde el contenido del archivo."""
    npcs = []

    # Buscar todos los bloques [[npcs_*.npcs]]
    pattern = r"\[\[(?:npcs_complete|npcs_traders|npcs_hostiles)\.npcs\]\]"
    blocks = re.split(pattern, content)

    for block in blocks[1:]:  # Skip first empty split
        npc = parse_npc_block(block)
        if npc:
            npcs.append(npc)

    return npcs


def parse_npc_block(block: str) -> MerchantData | None:
    """Parsea un bloque individual de NPC."""
    # Extraer id
    id_match = re.search(r"^id\s*=\s*(\d+)", block, re.MULTILINE)
    if not id_match:
        return None

    npc_id = int(id_match.group(1))

    # Extraer name
    name_match = re.search(r'^name\s*=\s*"([^"]*)"', block, re.MULTILINE)
    name = name_match.group(1) if name_match else "Unknown"

    # Extraer description
    desc_match = re.search(r'^description\s*=\s*"""([^"]*)"""', block, re.MULTILINE | re.DOTALL)
    if not desc_match:
        desc_match = re.search(r'^description\s*=\s*"([^"]*)"', block, re.MULTILINE)
    description = desc_match.group(1) if desc_match else ""

    # Verificar si comercia
    trades_match = re.search(r"^trades\s*=\s*(\d+)", block, re.MULTILINE)
    trades = int(trades_match.group(1)) if trades_match else 0

    if not trades:
        return None

    # Extraer items del inventario
    items = parse_inventory_items(block)

    if not items:
        return None

    return {
        "npc_id": npc_id,
        "nombre": name,
        "descripcion": description.strip(),
        "items": items,
    }


def parse_inventory_items(block: str) -> list[MerchantItem]:
    """Extrae items del bloque de inventario."""
    items: list[MerchantItem] = []

    # Buscar la sección [inventory] y items = [...]
    inventory_match = re.search(r"\[inventory\]\s*items\s*=\s*\[(.*?)\]", block, re.DOTALL)

    if not inventory_match:
        return []

    items_content = inventory_match.group(1)

    # Parsear cada item {slot = X, item_id = Y, quantity = Z, description = "..."}
    item_pattern = r'\{[^}]*item_id\s*=\s*(\d+)[^}]*quantity\s*=\s*(\d+)[^}]*(?:description\s*=\s*"([^"]*)")?[^}]*\}'

    for match in re.finditer(item_pattern, items_content):
        item_id = int(match.group(1))
        quantity = int(match.group(2))
        description = match.group(3) or f"Item #{item_id}"

        items.append(
            {
                "item_id": item_id,
                "quantity": quantity,
                "nombre": description,
            }
        )

    return items


def load_merchants_from_file(path: Path, source_name: str) -> list[MerchantData]:
    """Carga comerciantes desde un archivo TOML usando parser tolerante."""
    if not path.exists():
        print(f"⚠️  Archivo no encontrado: {path}")
        return []

    content = path.read_text(encoding="utf-8")
    merchants = parse_npc_blocks(content)

    # Agregar source a cada merchant
    for m in merchants:
        m["source"] = source_name

    return merchants


def generate_toml_content(merchants: list[MerchantData]) -> str:
    """Genera el contenido TOML para merchant_inventories.toml."""
    lines = [
        "# Inventarios de mercaderes - GENERADO AUTOMÁTICAMENTE",
        "# No editar manualmente, usar scripts/sync_merchant_inventories.py",
        "#",
        f"# Total: {len(merchants)} mercaderes",
        "",
    ]

    for merchant in sorted(merchants, key=lambda x: x["npc_id"]):
        npc_id = merchant["npc_id"]
        nombre = merchant["nombre"]
        descripcion = merchant.get("descripcion", "")[:100]  # Truncar
        source = merchant.get("source", "unknown")
        items = merchant["items"]

        lines.append(f"# === {nombre} (ID: {npc_id}) - from {source} ===")
        lines.append("[[merchant]]")
        lines.append(f"npc_id = {npc_id}")
        lines.append(f'nombre = "{nombre}"')

        # Escapar comillas en descripción
        desc_escaped = descripcion.replace('"', '\\"').replace("\n", " ")
        lines.append(f'descripcion = "{desc_escaped}"')
        lines.append("")

        for item in items:
            lines.append("[[merchant.item]]")
            lines.append(f"item_id = {item['item_id']}")
            lines.append(f"quantity = {item['quantity']}")

            item_name = item.get("nombre", "").replace('"', '\\"')
            lines.append(f'nombre = "{item_name}"')
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Ejecuta la sincronización."""
    data_dir = Path("data")

    if not data_dir.exists():
        print("❌ Directorio 'data' no encontrado. Ejecutar desde raíz del proyecto.")
        return 1

    all_merchants: dict[int, MerchantData] = {}  # npc_id -> merchant data

    # 1. Cargar npcs_complete.toml (usando parser tolerante)
    print("📄 npcs_complete.toml:")
    merchants = load_merchants_from_file(data_dir / "npcs_complete.toml", "npcs_complete.toml")
    print(f"   ↳ {len(merchants)} comerciantes con inventario")
    for m in merchants:
        all_merchants[m["npc_id"]] = m

    # 2. Cargar npcs_traders_extended.toml (prioridad sobre complete)
    print("📄 npcs_traders_extended.toml:")
    merchants = load_merchants_from_file(
        data_dir / "npcs_traders_extended.toml", "npcs_traders_extended.toml"
    )
    print(f"   ↳ {len(merchants)} comerciantes con inventario")
    for m in merchants:
        all_merchants[m["npc_id"]] = m

    # 3. Generar archivo
    print(f"\n✨ Total: {len(all_merchants)} comerciantes únicos")

    if not all_merchants:
        print("❌ No se encontraron comerciantes con inventario")
        return 1

    content = generate_toml_content(list(all_merchants.values()))

    output_path = data_dir / "merchant_inventories.toml"

    # Backup del archivo anterior
    if output_path.exists():
        backup_path = data_dir / "merchant_inventories.toml.bak"
        output_path.rename(backup_path)
        print(f"📦 Backup creado: {backup_path}")

    output_path.write_text(content)
    print(f"✅ Archivo generado: {output_path}")

    # Estadísticas
    total_items = sum(len(m["items"]) for m in all_merchants.values())
    print(f"   ↳ {total_items} items totales en inventarios")

    return 0


if __name__ == "__main__":
    sys.exit(main())
