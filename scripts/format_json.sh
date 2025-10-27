#!/bin/bash

# Normaliza los .json de map_data/ escribiéndolos como NDJSON:
# un objeto JSON compacto por línea, soportando entradas
# formateadas en varias líneas o como arreglos.

set -euo pipefail

shopt -s nullglob

for file in map_data/*.json; do
    echo "Formateando: $file"

    python3 - <<'PY' "$file"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

def dump_lines(elements: list[object]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for element in elements:
            out.write(json.dumps(element, ensure_ascii=False))
            out.write("\n")

def parse_stream(source: str) -> list[object]:
    decoder = json.JSONDecoder()
    idx = 0
    length = len(source)
    items: list[object] = []

    while idx < length:
        while idx < length and source[idx] in " \t\r\n":
            idx += 1
        if idx >= length:
            break
        try:
            value, end = decoder.raw_decode(source, idx)
        except json.JSONDecodeError:
            next_newline = source.find("\n", idx)
            if next_newline == -1:
                break
            idx = next_newline + 1
            continue
        else:
            items.append(value)
            idx = end
    return items

try:
    data = json.loads(text)
except json.JSONDecodeError:
    elements = parse_stream(text)
    if not elements:
        print("  No se pudo interpretar JSON válido", file=sys.stderr)
        sys.exit(0)
    dump_lines(elements)
else:
    if isinstance(data, list):
        dump_lines(list(data))
    else:
        dump_lines([data])
PY

    echo "  Formateado correctamente"
done

echo "Proceso completado"