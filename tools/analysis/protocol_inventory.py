"""Inventario cruzado del protocolo: código alcanzable, evidencia y límites de prueba.

Sólo usa la biblioteca estándar. No importa el servidor ni necesita Redis/Godot.
Las referencias revisadas y las pruebas dinámicas se distinguen del análisis estático.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
CATALOG = Path("docs/audits/protocol-583")
GD_FUNCTION = re.compile(r"^(?:static\s+)?func\s+(\w+)\s*\(", re.M)
GD_CLASS = re.compile(r"^class_name\s+(\w+)", re.M)
CALL = re.compile(r"\b(\w+)\s*\(")
TYPES = {
    "add_byte": "u8",
    "add_int16": "i16",
    "add_int32": "i32",
    "add_unicode_string": "str16",
    "add_float": "f32",
    "add_bytes": "bytes",
}
GD_TYPES = {
    "put_u8": "u8",
    "put_8": "i8",
    "put_16": "i16",
    "put_u16": "u16",
    "put_32": "i32",
    "put_u32": "u32",
    "put_float": "f32",
    "PutUnicodeString": "str16",
    "get_u8": "u8",
    "get_8": "i8",
    "get_16": "i16",
    "get_u16": "u16",
    "get_32": "i32",
    "get_u32": "u32",
    "get_float": "f32",
    "GetUnicodeString": "str16",
    "get_data": "bytes",
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def gd_code(text):
    """Remove comments outside strings; preserve line numbers and quoted payloads."""
    result = []
    for line in text.splitlines():
        quote, escaped, end = "", False, len(line)
        for index, char in enumerate(line):
            if escaped:
                escaped = False
            elif char == "\\" and quote:
                escaped = True
            elif quote:
                if char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "#":
                end = index
                break
        result.append(line[:end])
    return "\n".join(result)


def gd_enum(text, name):
    match = re.search(r"\benum\s+" + re.escape(name) + r"\s*\{([^}]+)\}", gd_code(text), re.S)
    if not match:
        raise ValueError(f"Missing Godot enum {name}")
    result, value = {}, -1
    for entry in match.group(1).split(","):
        entry = entry.strip()
        if not entry:
            continue
        symbol, separator, literal = entry.partition("=")
        value = int(literal.strip(), 0) if separator else value + 1
        result[symbol.strip()] = value
    if len(set(result.values())) != len(result):
        raise ValueError(f"Duplicate IDs in {name}")
    return result


def py_enums(path):
    result = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.ClassDef) and node.name in {"ClientPacketID", "ServerPacketID"}:
            result[node.name] = {
                target.id: ast.literal_eval(item.value)
                for item in node.body
                if isinstance(item, ast.Assign)
                for target in item.targets
                if isinstance(target, ast.Name)
            }
    return result


@dataclass
class Function:
    repo: str
    path: str
    name: str
    line: int
    end: int
    text: str
    node: ast.AST | None = None

    def ref(self):
        return {
            "repository": self.repo,
            "path": self.path,
            "line": self.line,
            "end_line": self.end,
            "symbol": self.name,
        }

    def stub(self):
        if self.node is not None:
            body = list(self.node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]
            return not body or all(
                isinstance(item, ast.Pass)
                or (
                    isinstance(item, ast.Return)
                    and (item.value is None or isinstance(item.value, ast.Constant))
                )
                for item in body
            )
        body = gd_code(self.text).splitlines()[1:]
        statements = [line.strip() for line in body if line.strip()]
        return not statements or all(
            re.fullmatch(r"pass|return(?:\s+(?:null|true|false))?", s) for s in statements
        )

    def calls(self):
        if self.node is not None:
            return {
                node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                for node in ast.walk(self.node)
                if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
            }
        code = gd_code(self.text).split("\n", 1)[-1]
        code = re.sub(
            r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' """.rstrip(),
            lambda m: " " * len(m.group()),
            code,
        )
        return set(CALL.findall(code))

    def primitives(self):
        if self.node is not None:
            result = []

            class Visitor(ast.NodeVisitor):
                def visit_Call(self, node):
                    self.generic_visit(node)
                    if isinstance(node.func, ast.Attribute) and node.func.attr in TYPES:
                        result.append(TYPES[node.func.attr])

            Visitor().visit(self.node)
            return result
        return [
            GD_TYPES[item]
            for item in re.findall(r"\b(" + "|".join(GD_TYPES) + r")\s*\(", gd_code(self.text))
        ]


class Sources:
    def __init__(self, server, client):
        self.roots = {"server": server.resolve(), "client": client.resolve()}
        self.functions = []
        self.contents = {}
        self.classes = {}
        self.used = set()
        self.tests = []
        for path in sorted((server / "src").rglob("*.py")):
            if "operations" in path.relative_to(server).parts or "runtime_data" in path.parts:
                continue
            relative = path.relative_to(server).as_posix()
            text = path.read_text()
            self.contents["server", relative] = text
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions.append(
                        Function(
                            "server",
                            relative,
                            node.name,
                            node.lineno,
                            node.end_lineno,
                            "\n".join(text.splitlines()[node.lineno - 1 : node.end_lineno]),
                            node,
                        )
                    )
        for directory in ("engine", "network", "screens", "ui", "common"):
            for path in sorted((client / directory).rglob("*.gd")):
                relative = path.relative_to(client).as_posix()
                text = path.read_text()
                self.contents["client", relative] = text
                match = GD_CLASS.search(text)
                if match:
                    self.classes[match.group(1)] = relative
                clean = gd_code(text)
                starts = list(GD_FUNCTION.finditer(clean))
                for index, start in enumerate(starts):
                    line = clean.count("\n", 0, start.start()) + 1
                    end = (
                        clean.count("\n", 0, starts[index + 1].start())
                        if index + 1 < len(starts)
                        else len(text.splitlines())
                    )
                    self.functions.append(
                        Function(
                            "client",
                            relative,
                            start.group(1),
                            line,
                            end,
                            "\n".join(text.splitlines()[line - 1 : end]),
                        )
                    )
        for repo, root in self.roots.items():
            for path in sorted((root / "tests").rglob("*")):
                if path.suffix in {".py", ".gd"}:
                    self.tests.append((repo, path.relative_to(root).as_posix(), path.read_text()))
        self.callers = defaultdict(list)
        for function in self.functions:
            for called in function.calls():
                self.callers[function.repo, called].append(function)

    def evidence(self, function):
        self.used.add((function.repo, function.path))
        return function.ref()

    def find(self, repo, name, path=None):
        return [
            f
            for f in self.functions
            if f.repo == repo and f.name == name and (path is None or f.path == path)
        ]

    def references(self, repo, name, exclude=None):
        return [
            self.evidence(f)
            for f in self.callers[repo, name]
            if f is not exclude
            and (not name.startswith("_") or exclude is None or f.path == exclude.path)
        ]


def client_writers(sources, enums):
    result = defaultdict(list)
    for function in sources.functions:
        if function.repo != "client" or function.path != "engine/autoload/game_protocol.gd":
            continue
        match = re.search(
            r"_writer\.put_u8\((Enums\.ClientPacketID\.(\w+)|\d+)\)", gd_code(function.text)
        )
        if match:
            packet_id = enums[match.group(2)] if match.group(2) else int(match.group(1))
            result[packet_id].append(function)
    capabilities = sources.contents["client", "network/client_capabilities.gd"]
    number = int(re.search(r"const PACKET_ID\s*:?=\s*(\d+)", capabilities).group(1))
    result[number].extend(sources.find("client", "begin", "network/client_capabilities.gd"))
    return result


def server_handlers(server, sources, enums):
    path = "src/network/packet_handlers.py"
    tree = ast.parse((server / path).read_text())
    imports = {
        alias.asname or alias.name: (node.module, alias.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    value = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "TASK_HANDLERS"
    )
    result = {}
    for key, item in zip(value.keys, value.values, strict=True):
        number = enums[key.attr]
        module, name = imports[item.id]
        filename = module.replace(".", "/") + ".py"
        result[number] = {
            "task": name,
            "functions": sources.find("server", "execute", filename),
            "registry": {
                "repository": "server",
                "path": path,
                "line": key.lineno,
                "symbol": "TASK_HANDLERS",
            },
        }
    sources.used.add(("server", path))
    return result


def eval_int(node, values):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ServerPacketID"
    ):
        return values.get(node.attr)
    return None


def server_writers(sources, enums):
    result = defaultdict(list)
    constants = {}
    for function in sources.functions:
        if function.repo != "server":
            continue
        if function.path not in constants:
            tree = ast.parse(sources.contents["server", function.path])
            values = dict(enums)
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    value = eval_int(node.value, values)
                    if value is not None:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                values[target.id] = value
            constants[function.path] = values
        values = constants[function.path]
        ids = set()
        first_builders = set()
        for node in sorted(
            (n for n in ast.walk(function.node) if isinstance(n, ast.Call)),
            key=lambda n: (n.lineno, n.col_offset),
        ):
            method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if method == "add_byte" and node.args:
                receiver = node.func.value
                if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Attribute):
                    continue
                buffer = ast.unparse(receiver)
                if buffer in first_builders:
                    continue
                first_builders.add(buffer)
                arg = node.args[0]
                if isinstance(arg, (ast.Attribute, ast.Name, ast.Constant)):
                    value = eval_int(arg, values)
                    if value is not None:
                        ids.add(value)
            if method == "pack" and len(node.args) > 1 and isinstance(node.args[0], ast.Constant):
                if str(node.args[0].value).lstrip("<>=!@").startswith("B"):
                    value = eval_int(node.args[1], values)
                    if value is not None:
                        ids.add(value)
            if isinstance(node.func, ast.Name) and node.func.id == "bytes" and node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.List, ast.Tuple)) and arg.elts:
                    value = eval_int(arg.elts[0], values)
                    if value is not None:
                        ids.add(value)
        for packet_id in ids:
            result[packet_id].append(function)
    return result


def client_receivers(sources, enums):
    result = defaultdict(list)
    dispatcher = gd_code(sources.contents["client", "network/message_dispatcher.gd"])
    pattern = re.compile(
        r"^\t\tEnums\.ServerPacketID\.(\w+):\n(.*?)(?=^\t\t[^\t\n]|\Z)", re.S | re.M
    )
    for match in pattern.finditer(gd_code(dispatcher)):
        line = dispatcher.count("\n", 0, match.start()) + 1
        body = match.group(2)
        handlers = re.findall(r'_emit\(&"(\w+)"', body)
        readers = re.findall(r"\b(\w+)\.new\(stream\)", body)
        result[enums[match.group(1)]].append(
            {
                "path": "network/message_dispatcher.gd",
                "line": line,
                "handlers": handlers,
                "readers": readers,
                "ignored": bool(re.search(r"^\s*pass\s*$", body, re.M)),
            }
        )
    numeric = re.compile(
        r"^\tif packetId (?:== (\d+)|in \[([\d, ]+)\]):\n(.*?)(?=^\t[^\t\n]|\Z)", re.S | re.M
    )
    for match in numeric.finditer(dispatcher):
        numbers = (
            [int(match.group(1))] if match.group(1) else [int(n) for n in match.group(2).split(",")]
        )
        for number in numbers:
            result[number].append(
                {
                    "path": "network/message_dispatcher.gd",
                    "line": dispatcher.count("\n", 0, match.start()) + 1,
                    "handlers": re.findall(r'_emit\(&"(\w+)"', match.group(3)),
                    "readers": re.findall(r"\b(\w+)\.new\([^\n]*stream", match.group(3)),
                    "ignored": bool(re.search(r"^\s*pass\s*$", match.group(3), re.M)),
                }
            )
    # Login y alta reciben paquetes antes de entrar en GameScreen.
    for path in ("screens/login_screen.gd", "screens/character_creation_screen.gd"):
        text = gd_code(sources.contents["client", path])
        for match in re.finditer(r"Enums\.ServerPacketID\.(\w+):", gd_code(text)):
            result[enums[match.group(1)]].append(
                {
                    "path": path,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "handlers": [
                        "_OnDataReceived" if "login_screen" in path else "_OnDataReceivedd"
                    ],
                    "readers": [],
                    "ignored": False,
                }
            )
    function = sources.find("client", "accept", "network/client_capabilities.gd")[0]
    capabilities = sources.contents["client", "network/client_capabilities.gd"]
    number = int(re.search(r"const PACKET_ID\s*:?=\s*(\d+)", capabilities).group(1))
    result[number].append(
        {
            "path": function.path,
            "line": function.line,
            "handlers": ["accept"],
            "readers": [],
            "ignored": False,
        }
    )
    return result


def test_references(files, terms):
    result = []
    pattern = (
        re.compile(r"\b(?:" + "|".join(re.escape(t) for t in sorted(terms) if len(t) > 3) + r")\b")
        if terms
        else None
    )
    if pattern is None:
        return result
    for repo, path, text in files:
        for line, value in enumerate(text.splitlines(), 1):
            if pattern.search(value):
                result.append(
                    {
                        "repository": repo,
                        "path": path,
                        "line": line,
                        "kind": "reference_only_not_execution_proof",
                    }
                )
                break
    return result


def routed_effect(sources, handler):
    """Some dispatcher labels are match arms, not methods with that name."""
    matches = sources.find("client", handler, "screens/game_screen.gd")
    if matches:
        return matches
    router = sources.find("client", "_OnDecodedMessage", "screens/game_screen.gd")[0]
    pattern = re.compile(
        r'^\t\t&"' + re.escape(handler) + r'":(.*?)(?=^\t\t[^\t\n]|\Z)', re.S | re.M
    )
    clean = gd_code(router.text)
    match = pattern.search(clean)
    if not match:
        return []
    line = router.line + clean.count("\n", 0, match.start())
    body = match.group(1)
    return [
        Function(
            "client",
            router.path,
            "_OnDecodedMessage/" + handler,
            line,
            line + body.count("\n"),
            "func routed():\n" + body,
        )
    ]


def fixed_layout(function, expected, *, header):
    """Compare only flat primitive layouts; never infer variable loops/branches."""
    if function.node is not None:
        if any(
            isinstance(n, (ast.For, ast.While, ast.ListComp, ast.If))
            for n in ast.walk(function.node)
        ):
            return {"symbol": function.name, "status": "dynamic_requires_test"}
        if any(
            isinstance(n, ast.Return) and isinstance(n.value, ast.BinOp)
            for n in ast.walk(function.node)
        ):
            return {"symbol": function.name, "status": "composite_requires_test"}
    else:
        code = gd_code(function.text)
        if re.search(r"^\s*(?:for|while|match)\b", code, re.M):
            return {"symbol": function.name, "status": "dynamic_requires_test"}
    actual = function.primitives()
    if not actual:
        return {"symbol": function.name, "status": "requires_test"}
    wanted = (["u8"] if header else []) + [field["type"] for field in expected]
    return {
        "symbol": function.name,
        "status": "consistent_fixed" if actual == wanted else "different_requires_review",
        "expected": wanted,
        "actual": actual,
    }


def original_subtypes(sources, reference, contract, policy):
    """Original GM/MULTI_MESSAGE variants are separate from the parent packet."""
    result = []
    for group, direction, packet_id in [("gm", "client", 122), ("messages", "server", 104)]:
        supported = contract["directions"][direction].get(str(packet_id), {}).get("variants", {})
        enum_group = "EGMCommands" if group == "gm" else "Messages"
        current_enum = gd_enum(sources.contents["client", "common/enums/enums.gd"], enum_group)
        current_by_id = {number: name for name, number in current_enum.items()}
        for original in reference["enums"][group]:
            number = original["id"]
            bindings = []
            for binding in reference["command_bindings"]:
                if any(
                    original["name"].casefold() in [v.casefold() for v in writer["gm"]]
                    for writer in binding["writers"]
                ):
                    bindings.append(
                        {
                            "command": binding["command"],
                            "current_transport": binding["current_transport"],
                        }
                    )
            symbol = current_by_id.get(number)
            evidence = []
            if symbol:
                needle = f"Enums.{enum_group}.{symbol}"
                for function in sources.functions:
                    if function.repo == "client" and needle in gd_code(function.text):
                        evidence.append(sources.evidence(function))
            status = "declared_unused"
            if str(number) in supported:
                status = "wired_not_exercised"
            elif group == "gm" and any(b["current_transport"] == "text" for b in bindings):
                status = "replaced_by_other_transport"
            rule = policy.get("subtypes", {}).get(f"{direction}:{packet_id}:{number}", {})
            if rule.get("replacement"):
                status = "replaced_by_other_transport"
            elif rule.get("retired"):
                status = "retired_not_desired"
            result.append(
                {
                    "direction": "client_to_server"
                    if direction == "client"
                    else "server_to_client",
                    "id": packet_id,
                    "subtype": number,
                    "name": original["name"],
                    "original_line": original["line"],
                    "current_enum_name": symbol,
                    "fields": supported.get(str(number)),
                    "status": status,
                    "command_bindings": bindings,
                    "client_references": evidence,
                    "replacement": rule.get("replacement", []),
                    "issues": rule.get("issues", []),
                    "dynamic_verification": "not_credited_by_static_analysis",
                    "rationale": rule.get(
                        "rationale",
                        "Sólo se acepta el subtipo si figura en variants del contrato; las funciones por TALK no habilitan el opcode antiguo.",
                    ),
                }
            )
    return result


def json_actions(sources):
    """Expose schemas embedded inside the two negotiated JSON request packets."""
    rows = []
    for path, dictionary, packet_id, capability in [
        ("src/tasks/task_skill_action.py", "ACTION_FIELDS", 251, 256),
        ("src/services/world/actions.py", "ACTION_FIELDS", 248, 512),
        ("src/services/expansion/service.py", "EXPANSION_FIELDS", 248, 1536),
    ]:
        text = sources.contents["server", path]
        tree = ast.parse(text)
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == dictionary
        )
        sources.used.add(("server", path))
        for key, fields in zip(node.value.keys, node.value.values, strict=True):
            if not isinstance(key, ast.Constant) or not isinstance(fields, ast.Dict):
                raise ValueError(
                    "Esquema de acción dinámico: requiere extracción explícita " + path
                )
            rows.append(
                {
                    "direction": "client_to_server",
                    "id": packet_id,
                    "subtype": key.value,
                    "fields": {
                        k.value: ast.unparse(v)
                        for k, v in zip(fields.keys, fields.values, strict=True)
                    },
                    "requires_capability": capability,
                    "status": "negotiated_extension",
                    "schema": {
                        "repository": "server",
                        "path": path,
                        "line": key.lineno,
                        "symbol": dictionary,
                    },
                    "dynamic_verification": "not_credited_by_static_analysis",
                }
            )
    return rows


def metadata_diagnostics(sources, contract):
    result = []
    tree = ast.parse(sources.contents["server", "src/network/capabilities.py"])
    enum = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Capability")
    for node in enum.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            name, value = node.targets[0].id, node.value.value
            if value and name.lower() not in contract["capabilities"]["mask_bits"]:
                result.append(
                    {
                        "kind": "capability_missing_from_contract",
                        "name": name,
                        "value": value,
                        "path": "src/network/capabilities.py",
                        "line": node.lineno,
                    }
                )
    text = sources.contents["client", "network/client_capabilities.gd"]
    actual = float(re.search(r"const NEGOTIATION_TIMEOUT_SECONDS\s*:?=\s*([\d.]+)", text).group(1))
    declared = contract["capabilities"]["response_timeout_client_seconds"]
    if actual != declared:
        result.append(
            {"kind": "negotiation_timeout_metadata", "declared": declared, "actual": actual}
        )
    if contract.get("compatibility", {}).get("state") == "implementations_pending":
        result.append({"kind": "stale_compatibility_metadata", "value": "implementations_pending"})
    sources.used.add(("server", "src/network/capabilities.py"))
    return result


def dynamic_evidence(server, sources, rows):
    path = server / CATALOG / "representative.json"
    if not path.exists():
        return None
    proof = read(path)
    result_path = path.parent / "representative-result.json"
    cases_path = path.parent / "representative-scenarios.json"
    if sha(result_path) != proof["result_sha256"] or sha(cases_path) != proof["scenarios_sha256"]:
        raise ValueError("La evidencia representativa fue alterada")
    for filename, expected in proof.get("screenshots", {}).items():
        if sha(path.parent / filename) != expected:
            raise ValueError("La captura representativa fue alterada")
    result, cases = read(result_path), read(cases_path)
    if (
        not result["passed"]
        or result["clients"] != 2
        or not result["native_export"]
        or not result["tls"]
    ):
        raise ValueError("La muestra requiere dos clientes nativos reales y TLS")
    if (
        result["server_commit"] != proof["commits"]["server"]
        or result["client_commit"] != proof["commits"]["client"]
    ):
        raise ValueError("Los commits de la muestra no coinciden")
    stale = []
    for item in proof["runtime_inputs"]:
        root = sources.roots[item["repository"]]
        file = root / item["path"]
        if not file.is_file() or sha(file) != item["sha256"]:
            stale.append({"repository": item["repository"], "path": item["path"]})
    if stale:
        return {
            "file": "representative.json",
            "sha256": sha(path),
            "applicable_to_current_inputs": False,
            "status": "historical_source_changed",
            "changed_inputs": stale,
            "all_packets_exercised": False,
        }
    passed = {row["id"] for row in cases if row["passed"]}
    if set(result["acceptance"]["required"]) != passed:
        raise ValueError("La muestra no completó todos sus escenarios")
    for row in rows:
        direction = "client" if row["direction"] == "client_to_server" else "server"
        credited = proof["packet_cases"].get(direction, {}).get(str(row["id"]), [])
        if credited:
            if not set(credited) <= passed or not row["serialization"] or not row["reception"]:
                raise ValueError("Crédito dinámico sin ruta o sin caso aprobado")
            row["dynamic_verification"] = {
                "status": "representative_scenario_passed",
                "cases": credited,
                "proof": "representative.json",
                "scope": "Efecto observado en la muestra; no acredita cada variante, rechazo ni plataforma.",
            }
            if row["status"] == "wired_not_exercised":
                row["status"] = "operational_end_to_end"
    return {
        "file": "representative.json",
        "sha256": sha(path),
        "applicable_to_current_inputs": True,
        "clients": 2,
        "native_export": True,
        "long_acceptance": result["long_acceptance"],
        "scenarios": sorted(passed),
        "all_packets_exercised": False,
    }


def inventory(server, client, policy, reference):
    sources = Sources(server, client)
    contract = read(server / "src/network/protocol/contract.json")
    peer_contract = read(client / "protocol/contract.json")
    if contract != peer_contract:
        raise ValueError("Los contratos de ambos repositorios difieren")
    py = py_enums(server / "src/network/packet_id.py")
    gd = {
        group: gd_enum((client / "common/enums/enums.gd").read_text(), group)
        for group in ("ClientPacketID", "ServerPacketID")
    }
    writers = {
        "client": client_writers(sources, gd["ClientPacketID"]),
        "server": server_writers(sources, py["ServerPacketID"]),
    }
    handlers = server_handlers(server, sources, py["ClientPacketID"])
    receivers = client_receivers(sources, gd["ServerPacketID"])
    diagnostics, rows = metadata_diagnostics(sources, contract), []
    for direction, group in (("client", "ClientPacketID"), ("server", "ServerPacketID")):
        entries = contract["directions"][direction]
        for name, number in py[group].items():
            if str(number) not in entries or entries[str(number)]["name"] != name:
                diagnostics.append(
                    {
                        "kind": "enum_contract_mismatch",
                        "direction": direction,
                        "id": number,
                        "symbol": name,
                    }
                )
        for number in writers[direction]:
            if str(number) not in entries:
                diagnostics.append(
                    {"kind": "writer_outside_contract", "direction": direction, "id": number}
                )
        for key, entry in sorted(entries.items(), key=lambda pair: int(pair[0])):
            number = int(key)
            tx = writers[direction].get(number, [])
            rx = handlers.get(number, {}).get("functions", []) if direction == "client" else []
            receive_evidence, effect_evidence, reader_evidence = [], [], []
            ignored = False
            if direction == "client" and number in handlers:
                receive_evidence.append(handlers[number]["registry"])
                receive_evidence.extend(sources.evidence(f) for f in rx)
                for function in rx:
                    if not function.stub():
                        effect_evidence.append(sources.evidence(function))
            if direction == "server":
                branches = receivers.get(number, [])
                ignored = bool(branches) and all(b["ignored"] for b in branches)
                for branch in branches:
                    receive_evidence.append(
                        {
                            "repository": "client",
                            "path": branch["path"],
                            "line": branch["line"],
                            "symbol": "dispatch",
                        }
                    )
                    sources.used.add(("client", branch["path"]))
                    for handler in branch["handlers"]:
                        matches = (
                            routed_effect(sources, handler)
                            if branch["path"] == "network/message_dispatcher.gd"
                            else sources.find("client", handler, branch["path"])
                        )
                        effect_evidence.extend(sources.evidence(f) for f in matches)
                        rx.extend(matches)
                    for reader in branch["readers"]:
                        path = sources.classes.get(reader)
                        if path:
                            parser = sources.find("client", "Deserialize", path) or sources.find(
                                "client", "_init", path
                            )
                            reader_evidence.extend(sources.evidence(f) for f in parser)
            enabled = entry["status"] == "supported"
            callers = [ref for f in tx for ref in sources.references(f.repo, f.name, f)]
            stubs = bool(rx) and all(f.stub() for f in rx)
            rule = policy.get("packets", {}).get(f"{direction}:{number}", {})
            replacements = (
                reference.get("replacement_commands", {}).get(str(number), [])
                if direction == "client"
                else []
            )
            if rule.get("replacement") or (not enabled and replacements and number != 122):
                status = "replaced_by_other_transport"
            elif rule.get("retired"):
                status = "retired_not_desired"
            elif ignored or stubs:
                status = "stub_or_noop"
            elif not enabled:
                status = "receiver_without_emitter" if receive_evidence else "declared_unused"
            elif not tx:
                status = "receiver_without_emitter"
            elif not receive_evidence:
                status = "emitter_without_receiver"
            elif not callers and direction == "server":
                status = "declared_unused"
            elif rule.get("partial"):
                status = "partially_implemented"
            elif entry.get("requires_capability"):
                status = "negotiated_extension"
            else:
                status = "wired_not_exercised"
            tx_evidence = [sources.evidence(f) for f in tx]
            wire_writers = []
            for function in tx:
                gated = "_can_write(" in gd_code(function.text) if direction == "client" else None
                variant = None
                if direction == "client" and number == 122:
                    match = re.search(
                        r"_can_write\([^\n]*,\s*Enums.EGMCommands\.(\w+)\)", function.text
                    )
                    if match:
                        variant = gd_enum(
                            sources.contents["client", "common/enums/enums.gd"], "EGMCommands"
                        )[match.group(1)]
                writer_enabled = enabled and (
                    not entry.get("variants") or str(variant) in entry["variants"]
                )
                wire_writers.append(
                    {
                        "symbol": function.name,
                        "contract_gate": gated,
                        "subtype": variant,
                        "enabled_by_contract": writer_enabled,
                        "primitive_operations": function.primitives(),
                    }
                )
                if direction == "client" and not enabled and not gated:
                    diagnostics.append(
                        {"kind": "unguarded_unsupported_writer", "id": number, **function.ref()}
                    )
            generic = {
                "execute",
                "_reply",
                "send_state",
                "_init",
                "Deserialize",
                "begin",
                "accept",
                "_OnDataReceived",
                "_OnDataReceivedd",
                "_OnDecodedMessage",
            }
            terms = {f.name for f in tx + rx if f.name not in generic and "/" not in f.name} | {
                entry["name"]
            }
            tests = test_references(sources.tests, terms)
            originals = [r for r in reference["enums"][direction] if r["id"] == number]
            original_name = originals[0]["name"] if originals else None
            historical = [
                f
                for f in reference["writers"][direction]
                if original_name
                and original_name.casefold() in {name.casefold() for name in f["packets"]}
            ]
            row = {
                "direction": "client_to_server" if direction == "client" else "server_to_client",
                "id": number,
                "name": entry["name"],
                "declared_status": entry["status"],
                "original": originals[0] if originals else None,
                "historical_serializers": historical,
                "fields": entry.get("fields", []) if enabled else None,
                "fields_source": "current_contract"
                if enabled
                else "not_defined_for_unsupported_id",
                "variants": entry.get("variants", {}),
                "requires_capability": entry.get("requires_capability", 0),
                "status": status,
                "binary_support": {
                    "enabled_by_contract": enabled,
                    "writer_found": bool(tx),
                    "receiver_found": bool(receive_evidence),
                    "receiver_noop": ignored or stubs,
                },
                "gameplay_support": "alternative_transport"
                if rule.get("replacement") or (not enabled and replacements)
                else "not_credited_by_static_analysis",
                "ui_support": "effect_route_found" if effect_evidence else "no_effect_route_found",
                "serialization": tx_evidence,
                "production_callers": callers,
                "reception": receive_evidence,
                "readers": reader_evidence,
                "effect_or_ui": effect_evidence,
                "writers": wire_writers,
                "layout_review": [fixed_layout(f, entry.get("fields", []), header=True) for f in tx]
                if not entry.get("variants")
                else [{"status": "variant_requires_test"}],
                "tests": tests,
                "dynamic_verification": "not_credited_by_static_analysis",
                "replacement": rule.get("replacement", replacements),
                "rationale": rule.get(
                    "rationale",
                    "El análisis estático acredita rutas, no la ejecución completa de la mecánica."
                    if enabled
                    else "ID histórico no habilitado; no enviar este opcode desde el cliente actual.",
                ),
                "impact": rule.get(
                    "impact",
                    "Sin ausencia funcional demostrada; verificar la prueba dinámica indicada."
                    if enabled
                    else "El transporte binario histórico no está disponible; revisar la alternativa y la decisión de producto.",
                ),
                "priority": rule.get("priority", "P2" if enabled else "P3"),
                "issues": rule.get("issues", []),
                "reproduction": rule.get(
                    "reproduction",
                    "Consultar las rutas y tests listados; no se acredita una reproducción gráfica por mera referencia de texto.",
                ),
            }
            rows.append(row)
    for repo, path in [
        ("server", "src/network/packet_id.py"),
        ("server", "src/network/protocol/contract.json"),
        ("server", "src/network/packet_handlers.py"),
        ("client", "common/enums/enums.gd"),
        ("client", "protocol/contract.json"),
        ("client", "network/client_capabilities.gd"),
        ("client", "network/packet_framer.gd"),
        ("server", "src/network/packet_framer.py"),
    ]:
        sources.used.add((repo, path))
    subtypes = original_subtypes(sources, reference, contract, policy) + json_actions(sources)
    for row in rows:
        binary = row["binary_support"]
        if row["declared_status"] == "supported" and (
            not binary["writer_found"] or not binary["receiver_found"] or binary["receiver_noop"]
        ):
            diagnostics.append(
                {
                    "kind": "supported_with_incomplete_route",
                    "direction": row["direction"],
                    "id": row["id"],
                    "status": row["status"],
                    "issues": row["issues"],
                }
            )
        if row["status"] == "partially_implemented":
            diagnostics.append(
                {
                    "kind": "partially_implemented_route",
                    "direction": row["direction"],
                    "id": row["id"],
                    "issues": row["issues"],
                }
            )
    dynamic = dynamic_evidence(server, sources, rows)
    if dynamic and not dynamic["applicable_to_current_inputs"]:
        diagnostics.append(
            {
                "kind": "historical_representative_evidence",
                "changed_inputs": dynamic["changed_inputs"],
            }
        )
    return {
        "schema_version": 1,
        "issue": "https://github.com/cavazquez/pyao-server/issues/583",
        "baseline_commits": policy["baseline_commits"],
        "original_reference": reference["origin"],
        "limitations": [
            "Las referencias a tests son índices de evidencia, no resultados de ejecución.",
            "wired_not_exercised y negotiated_extension no cuentan como pruebas extremo a extremo.",
            "Las operaciones primitivas son un índice léxico; #582 verifica los formatos y entradas hostiles.",
        ],
        "summary": {
            "packets": len(rows),
            "by_status": dict(sorted(Counter(r["status"] for r in rows).items())),
            "declared_supported": {
                direction: sum(e["status"] == "supported" for e in entries.values())
                for direction, entries in contract["directions"].items()
            },
        },
        "subtype_summary": {
            "count": len(subtypes),
            "by_status": dict(sorted(Counter(r["status"] for r in subtypes).items())),
        },
        "diagnostics": diagnostics,
        "representative_validation": dynamic,
        "inputs": [
            {"repository": repo, "path": path, "sha256": sha(sources.roots[repo] / path)}
            for repo, path in sorted(sources.used)
        ],
        "packets": rows,
        "subtypes": subtypes,
    }


def markdown(result):
    """A readable generated index; the JSON retains fields and complete references."""
    labels = {
        "declared_unused": "declarado sin uso",
        "emitter_without_receiver": "emisor sin receptor",
        "negotiated_extension": "extensión negociada",
        "receiver_without_emitter": "receptor sin emisor",
        "replaced_by_other_transport": "reemplazado por otra ruta",
        "retired_not_desired": "retirado/no ofrecido",
        "stub_or_noop": "stub/sin efecto",
        "wired_not_exercised": "ruta encontrada, sin prueba completa",
        "operational_end_to_end": "muestra extremo a extremo aprobada",
        "partially_implemented": "parcial",
    }
    lines = [
        "# Inventario generado del protocolo (#583)",
        "",
        "No editar a mano: `protocol_inventory.py` genera este índice y `inventory.json`.",
        "Los campos, serializadores históricos, lectores, consumidores, tests y líneas completas están en el JSON.",
        "",
        f"Paquetes: **{len(result['packets'])}**. Subtipos/acciones: **{len(result['subtypes'])}**.",
        "",
        "Los estados de extensión o de ruta encontrada no acreditan por sí solos una mecánica operativa.",
        "La muestra nativa no cubre todos los mensajes, variantes ni rechazos. Ver `README.md`.",
        "",
    ]
    for direction, title in [
        ("client_to_server", "Cliente → servidor"),
        ("server_to_client", "Servidor → cliente"),
    ]:
        lines += ["## " + title, ""]
        for row in result["packets"]:
            if row["direction"] != direction:
                continue
            refs = row["serialization"][:1] + row["reception"][:1] + row["effect_or_ui"][:1]
            links = []
            for ref in refs:
                repo = "pyao-server" if ref["repository"] == "server" else "ArgentumOnlineGodot"
                commit = result["baseline_commits"][ref["repository"]]
                links.append(
                    f"[{ref['symbol']}](https://github.com/cavazquez/{repo}/blob/{commit}/{ref['path']}#L{ref['line']})"
                )
            fields = ", ".join(f"{f['name']}:{f['type']}" for f in (row["fields"] or [])) or (
                "sin campos" if row["fields"] == [] else "no habilitado"
            )
            if len(fields) > 220:
                fields = fields[:217] + "… (ver JSON)"
            suffix = "; ".join(links) or "sin extremos habilitados"
            lines.append(
                f"- **{row['id']} {row['name']}** — {labels[row['status']]}. Campos: {fields}. {suffix}."
            )
        lines.append("")
    lines += ["## Subtipos originales y acciones JSON", ""]
    for row in result["subtypes"]:
        name = row.get("name", row["subtype"])
        side = "C→S" if row["direction"] == "client_to_server" else "S→C"
        lines.append(
            f"- **{side} {row['id']}/{row['subtype']} {name}** — {labels[row['status']]}; campos y evidencia en JSON."
        )
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, default=SERVER)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    folder = args.server / CATALOG
    result = inventory(
        args.server, args.client, read(folder / "decisions.json"), read(folder / "original.json")
    )
    target = args.output or folder / "inventory.json"
    if args.check:
        expected = read(target)
        if result != expected:
            raise SystemExit(
                "Inventario desactualizado: ejecutar protocol_inventory.py --client <checkout> y revisar los cambios."
            )
        if args.output is None and (folder / "inventory.md").read_text() != markdown(result):
            raise SystemExit("Índice legible desactualizado: regenerar inventory.md")
    else:
        write(target, result)
        if args.output is None:
            (folder / "inventory.md").write_text(markdown(result))
    print(
        json.dumps(
            {"passed": True, **result["summary"], "diagnostics": len(result["diagnostics"])},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
