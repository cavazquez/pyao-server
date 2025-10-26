"""Utility script to inspect the SpellInfo handler in the original VB6 source."""

from __future__ import annotations

import argparse
from itertools import islice
from pathlib import Path

DEFAULT_OFFSET = 3340
DEFAULT_LINES = 40


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Print a portion of the VB6 Protocol.bas file around HandleSpellInfo to aid "
            "the Python port."
        )
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=DEFAULT_OFFSET,
        help="0-based line offset where reading should start (default: %(default)s)",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=DEFAULT_LINES,
        help="Number of lines to show from the offset (default: %(default)s)",
    )
    args = parser.parse_args()

    path = Path(
        "clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/Protocol.bas"
    )
    if not path.exists():
        raise SystemExit(f"Protocol file not found: {path}")

    with path.open("r", encoding="latin-1", errors="ignore") as file:
        snippet = list(islice(file, args.offset, args.offset + args.lines))

    for index, line in enumerate(snippet, start=args.offset + 1):
        print(f"{index:04d}: {line.rstrip()}" )


if __name__ == "__main__":
    main()
