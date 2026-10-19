"""Extrae yunques/fraguas de .inf; esos objetos no están en las capas gráficas .map."""

import argparse
import struct
import tomllib
from pathlib import Path


def read_workshops(path: Path, definitions: dict[int, tuple[str, int]]) -> list[dict]:
    """Lee exactamente 100x100 tiles con los flags del LoadMapData original."""
    data = path.read_bytes()
    offset = 10  # Double + Integer; cada tile puede incluir exit, NPC y objeto.
    result = []
    for y in range(1, 101):
        for x in range(1, 101):
            flags = data[offset]
            offset += 1
            if flags & 1:
                offset += 6
            if flags & 2:
                offset += 2
            if flags & 4:
                item_id, _amount = struct.unpack_from("<HH", data, offset)
                offset += 4
                if item_id in definitions:
                    kind, graphic = definitions[item_id]
                    result.append({"x": x, "y": y, "kind": kind, "grh_index": graphic})
    return result


def main() -> None:
    """Genera el catálogo TOML sin cambiar mapas ni datos de jugadores."""
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maps", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / "data/world/map_workshops.toml")
    args = parser.parse_args()
    with (root / "data/items/tools/blacksmith.toml").open("rb") as source:
        definitions = {
            item["id"]: ("anvil" if item["ObjType"] == 27 else "forge", item["GrhIndex"])
            for item in tomllib.load(source)["item"]
            if item["ObjType"] in (27, 28)
        }
    lines = [
        "# Objetos de los .inf de AO 0.13.3; coordenadas de 1 a 100.",
        "# Regenerar: python -m tools.extraction.extract_map_workshops --maps RUTA_MAPAS_VB6",
    ]
    count = 0
    for path in sorted(args.maps.glob("Mapa*.inf"), key=lambda p: int(p.stem[4:])):
        for row in read_workshops(path, definitions):
            lines.extend(["", "[[workshop]]", f"map_id = {int(path.stem[4:])}"])
            lines.extend(f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value}" for key, value in row.items())
            count += 1
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{count} talleres extraídos a {args.output}")


if __name__ == "__main__":
    main()
