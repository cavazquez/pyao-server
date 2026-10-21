"""Aplica únicamente las decisiones de coordenadas versionadas en la revisión del mundo."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
from typing import Any


def apply_review(source: Path, scenes: Path, manifest: dict[str, Any]) -> dict[str, int]:
    """Conserva obstáculos y enlaces, salvo las celdas expresamente selladas.

    Returns:
        Cantidad de reparaciones de llegada, sellados y colisiones revisadas.

    Raises:
        ValueError: Si una fuente ya no coincide con la revisión o falta un mapa.
    """
    repairs = {tuple(row["source"]): row for row in manifest["repairs"]}
    seen: set[tuple[int, int, int]] = set()
    blocked: dict[int, set[tuple[int, int]]] = {}
    for path in sorted(source.glob("transitions_*.json")):
        groups = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        for group in groups:
            exits = []
            for row in group["exits"]:
                key = (group["from_map"], row["x"], row["y"])
                decision = repairs.get(key)
                if decision:
                    actual = [row[k] for k in ("to_map", "to_x", "to_y")]
                    target = decision["destination"]
                    if actual != decision["original_destination"] and actual != target:
                        raise ValueError(f"La salida cambió fuera de la revisión: {key}")
                    seen.add(key)
                    if target is None:
                        blocked.setdefault(key[0], set()).add(key[1:])
                        continue
                    row.update(zip(("to_map", "to_x", "to_y"), target, strict=True))
                exits.append(row)
            group["exits"] = exits
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in groups))
    # Los sellados pueden estar ya aplicados; jamás restaurar automáticamente la salida.
    for key, decision in repairs.items():
        if key not in seen and decision["destination"] is not None:
            raise ValueError(f"Falta la salida revisada: {key}")
        if decision["destination"] is None:
            blocked.setdefault(key[0], set()).add(key[1:])
    for row in manifest["collisions"]:
        if row["kind"] == "sign":
            blocked.setdefault(row["map"], set()).add((row["x"], row["y"]))
    for path in sorted(source.glob("blocked_*.json")):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        maps = {row["m"] for row in rows}
        known = {(row["m"], row["x"], row["y"]) for row in rows}
        for map_id in sorted(maps):
            for x, y in sorted(blocked.get(map_id, set())):
                if (map_id, x, y) not in known:
                    rows.append({"m": map_id, "x": x, "y": y, "t": "b"})
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    client_blocked = {mid: set(cells) for mid, cells in blocked.items()}
    for row in manifest["collisions"]:
        client_blocked.setdefault(row["map"], set()).add((row["x"], row["y"]))
    for map_id, cells in sorted(client_blocked.items()):
        path = scenes / f"Map{map_id}.tscn"
        text = path.read_text()
        match = re.search(r'metadata/data = PackedByteArray\("([A-Za-z0-9+/=]+)"\)', text)
        if not match:
            raise ValueError(f"Faltan flags canónicos del mapa {map_id}")
        flags = bytearray(base64.b64decode(match[1], validate=True))
        if len(flags) != 10000:
            raise ValueError(f"Tamaño incorrecto del mapa {map_id}")
        for x, y in cells:
            flags[x - 1 + (y - 1) * 100] |= 1
        for row in manifest["collisions"]:
            if row["map"] == map_id and row["kind"] == "door":
                # Graphic 9200 / item 246 is explicitly an OPEN wooden door.
                flags[row["x"] - 1 + (row["y"] - 1) * 100] &= ~1
        text = text[: match.start(1)] + base64.b64encode(flags).decode() + text[match.end(1) :]
        path.write_text(text)
    return {
        "reviewed_landings": len(repairs),
        "sealed_border_cells": sum(row["destination"] is None for row in repairs.values()),
        "reviewed_collisions": len(manifest["collisions"]),
    }


def main() -> None:
    """Aplica una revisión explícita; no busca automáticamente otra llegada."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("map_data"))
    parser.add_argument("--scenes", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/world/route-repairs.json"))
    args = parser.parse_args()
    print(json.dumps(apply_review(args.source, args.scenes, json.loads(args.manifest.read_text()))))


if __name__ == "__main__":
    main()
