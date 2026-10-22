"""Extrae hechos de la revisión fijada de AO 0.13.3, sin copiar código VB6."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def decode(path):
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def enum(text, name):
    match = re.search(r"\bEnum\s+" + re.escape(name) + r"\s*\n(.*?)End Enum", text, re.S | re.I)
    if match is None:
        raise ValueError(f"Missing original enum {name}")
    rows, number = [], -1
    for offset, line in enumerate(match.group(1).splitlines()):
        line = line.split("'")[0].strip()
        if not line:
            continue
        symbol, equal, value = line.partition("=")
        number = int(value.strip()) if equal else number + 1
        rows.append(
            {
                "id": number,
                "name": symbol.strip(),
                "line": text.count("\n", 0, match.start(1)) + offset + 1,
            }
        )
    return rows


def functions(text):
    pattern = re.compile(
        r"^(?:Public |Private |Friend )?(?:Sub|Function) (\w+)\b(.*?)(?:^End (?:Sub|Function))",
        re.M | re.S | re.I,
    )
    result = []
    for match in pattern.finditer(text):
        body = "\n".join(line.split("'")[0] for line in match.group(2).splitlines())
        result.append(
            {
                "name": match.group(1),
                "line": text.count("\n", 0, match.start()) + 1,
                "packets": sorted(set(re.findall(r"\b(?:Client|Server)PacketID\.(\w+)", body))),
                "gm": sorted(set(re.findall(r"\beGMCommands\.(\w+)", body))),
                "primitives": re.findall(
                    r"\.(WriteByte|WriteInteger|WriteLong|WriteSingle|WriteASCIIString|ReadByte|ReadInteger|ReadLong|ReadSingle|ReadASCIIString)\b",
                    body,
                ),
                "field_operations": [
                    {
                        "operation": item.group(1),
                        "expression": item.group(2).strip(),
                        "line": text.count("\n", 0, match.start())
                        + body.count("\n", 0, item.start())
                        + 1,
                    }
                    for item in re.finditer(
                        r"\.(WriteByte|WriteInteger|WriteLong|WriteSingle|WriteASCIIString)\(([^\n]*)\)",
                        body,
                    )
                ],
                "schema_complete": False,
            }
        )
    return result


def extract(root, origin, catalog):
    files = {}
    for record in origin["files"]:
        path = root / record["path"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("La referencia no coincide con su SHA256: " + record["path"])
        files[record["path"]] = decode(path)
    client = files["client/CODIGO/Protocol.bas"]
    server = files["server/Codigo/Protocol.bas"]
    declares = files["client/CODIGO/Declares.bas"]
    tx = {"client": functions(client), "server": functions(server)}
    commands = files["client/CODIGO/ProtocolCmdParse.bas"]
    definitions = {row["name"]: row for row in catalog["commands"]}
    bindings = []
    pattern = re.compile(r'^\s*Case\s+"(/[^" ]+)"[^\n]*\n(.*?)(?=^\s*Case\s+"/|\Z)', re.S | re.M)
    by_writer = {f["name"].casefold(): f for f in tx["client"]}
    for match in pattern.finditer(commands):
        name = match.group(1).upper()
        raw_name = name
        if name not in definitions:
            try:
                repaired = name.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                repaired = name
            if repaired in definitions:
                name = repaired
        original_writers = []
        for called in sorted(set(re.findall(r"\b(Write\w+)\b", match.group(2)))):
            writer = by_writer.get(called.casefold())
            if writer:
                original_writers.append(writer)
        bindings.append(
            {
                "command": name,
                "original_token": raw_name,
                "line": commands.count("\n", 0, match.start()) + 1,
                "writers": original_writers,
                "current_transport": definitions.get(name, {}).get("transport", "not_in_catalog"),
            }
        )
    ids = {row["name"].casefold(): row["id"] for row in enum(client, "ClientPacketID")}
    replacements = {}
    for binding in bindings:
        if binding["current_transport"] not in {"text", "ui"}:
            continue
        for writer in binding["writers"]:
            for packet in writer["packets"]:
                number = ids.get(packet.casefold())
                if number is not None:
                    replacements.setdefault(str(number), []).append(binding["command"])
    for number in replacements:
        replacements[number] = sorted(set(replacements[number]))
    return {
        "origin": {key: origin[key] for key in ("repository", "commit", "branch", "files")},
        "enums": {
            "client": enum(client, "ClientPacketID"),
            "server": enum(client, "ServerPacketID"),
            "gm": enum(declares, "eGMCommands"),
            "messages": enum(declares, "eMessages"),
        },
        "writers": tx,
        "command_bindings": bindings,
        "replacement_commands": replacements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract(
        args.reference, json.loads(args.origin.read_text()), json.loads(args.catalog.read_text())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "original_commit": result["origin"]["commit"],
                "counts": {k: len(v) for k, v in result["enums"].items()},
            }
        )
    )


if __name__ == "__main__":
    main()
