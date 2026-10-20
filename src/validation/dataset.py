"""Valida los catálogos y mapas seleccionados sin iniciar el mundo ni usar Redis."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.models.item_catalog import ItemCatalog
from src.models.item_types import ObjType
from src.models.potion_duration import normalize_potion_duration
from src.models.spell_extensions import validate_extensions
from src.services.expansion.catalog import ExpansionCatalog
from src.services.npc.loot_table_service import LootTableService
from src.services.nutrition import NutritionRule

MAX_ID = 65535
MAX_SKILL = 100
Record = dict[str, Any]


def _json_object(pairs: list[tuple[str, Any]]) -> Record:
    """Rechaza claves repetidas de JSON en vez de perder una definición.

    Returns:
        Objeto con claves únicas.

    Raises:
        ValueError: Si una clave ya existe.
    """
    result: Record = {}
    for key, value in pairs:
        if key in result:
            message = f"Clave JSON duplicada: {key}"
            raise ValueError(message)
        result[key] = value
    return result


@dataclass(frozen=True)
class Finding:
    """Problema localizado en un archivo, campo y registro del dataset."""

    severity: Literal["error", "warning"]
    file: str
    field: str
    record_id: str
    message: str


@dataclass
class Report:
    """Resultado serializable; solamente los errores bloquean la validación."""

    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> int:
        """Cantidad de errores bloqueantes."""
        return sum(f.severity == "error" for f in self.findings)

    def to_dict(self) -> Record:
        """Devuelve el informe para JSON.

        Returns:
            Contadores y diagnósticos localizados.
        """
        return {
            "errors": self.errors,
            "warnings": len(self.findings) - self.errors,
            "counts": self.counts,
            "findings": [asdict(f) for f in self.findings],
        }


@dataclass(frozen=True)
class Entry:
    """Registro con su ubicación original para emitir diagnósticos precisos."""

    file: Path
    field: str
    data: Record
    record_id: str = ""

    @property
    def identity(self) -> str:
        """Identidad propia o heredada de su registro contenedor."""
        for key in ("id", "npc_id", "m", "i", "from_map", "item_id"):
            if key in self.data:
                return str(self.data[key])
        return self.record_id or "?"

    def child(self, key: str, data: Record) -> Entry:
        """Ubica un registro anidado.

        Returns:
            Registro con la ruta de campos extendida.
        """
        return Entry(self.file, f"{self.field}.{key}".strip("."), data, self.identity)


class DatasetValidator:
    """Comprueba el dataset efectivo del servidor y sus referencias cruzadas."""

    def __init__(self, data_dir: Path, maps_dir: Path, client_dir: Path | None = None) -> None:
        """Selecciona explícitamente los directorios que se leerán."""
        self.data_dir = data_dir
        self.maps_dir = maps_dir
        self.client_dir = client_dir
        self.report = Report()
        self.items: dict[int, Entry] = {}
        self.npcs: dict[int, Entry] = {}
        self.spells: dict[int, Entry] = {}
        self.maps: dict[int, Entry] = {}

    def problem(
        self,
        entry: Entry,
        key: str,
        message: str,
        severity: Literal["error", "warning"] = "error",
    ) -> None:
        """Registra un problema sin detener el resto de comprobaciones."""
        self.report.findings.append(
            Finding(
                severity,
                str(entry.file),
                f"{entry.field}.{key}".strip("."),
                entry.identity,
                message,
            )
        )

    def read(self, path: Path) -> Entry:
        """Lee TOML o JSON y conserva los errores de formato en el informe.

        Returns:
            Objeto leído, o registro vacío cuando el archivo es inválido.
        """
        entry = Entry(path, "", {})
        try:
            text = path.read_text(encoding="utf-8")
            data = (
                tomllib.loads(text)
                if path.suffix == ".toml"
                else json.loads(text, object_pairs_hook=_json_object)
            )
        except (OSError, UnicodeError, ValueError) as exc:
            self.problem(entry, "", f"No se puede leer el archivo requerido: {exc}")
            return entry
        if not isinstance(data, dict):
            self.problem(entry, "", "Se esperaba un objeto/tabla")
            return entry
        return Entry(path, "", data)

    def section(self, entry: Entry, key: str) -> Entry:
        """Obtiene una tabla requerida.

        Returns:
            Tabla localizada o vacía si su estructura es inválida.
        """
        value = entry.data.get(key)
        if not isinstance(value, dict):
            self.problem(entry, key, "Se esperaba una tabla")
            value = {}
        return entry.child(key, value)

    def rows(self, entry: Entry, key: str) -> list[Entry]:
        """Obtiene registros de una lista requerida, incluso si hay filas inválidas.

        Returns:
            Registros con rutas que incluyen su posición (base cero).
        """
        value = entry.data.get(key)
        if not isinstance(value, list):
            self.problem(entry, key, "Se esperaba una lista")
            return []
        result = []
        for index, row in enumerate(value):
            location = f"{key}[{index}]"
            if isinstance(row, dict):
                result.append(entry.child(location, row))
            else:
                self.problem(entry, location, "Se esperaba un registro")
        return result

    def integer(self, entry: Entry, key: str, low: int = 0, high: int = MAX_ID) -> int | None:
        """Comprueba un entero sin aceptar booleanos ni conversiones silenciosas.

        Returns:
            Entero válido o None.
        """
        value = entry.data.get(key)
        if type(value) is not int or not low <= value <= high:
            self.problem(entry, key, f"Se esperaba un entero entre {low} y {high}; valor={value!r}")
            return None
        return int(value)

    def reference(self, entry: Entry, key: str, catalog: dict[int, Entry]) -> None:
        """Comprueba que una referencia requerida exista en el catálogo efectivo."""
        value = self.integer(entry, key, 1)
        if value is not None and value not in catalog:
            self.problem(entry, key, f"Referencia inexistente: {value}")

    def unique(self, entries: list[Entry], key: str = "id") -> dict[int, Entry]:
        """Construye un índice y denuncia IDs duplicados antes de sobrescribirlos.

        Returns:
            Índice de registros válidos.
        """
        result: dict[int, Entry] = {}
        for entry in entries:
            value = self.integer(entry, key, 1)
            if value is None:
                continue
            if value in result:
                previous = result[value]
                self.problem(
                    entry, key, f"ID duplicado {value}; anterior: {previous.file}:{previous.field}"
                )
            else:
                result[value] = entry
        return result

    def pair(self, entry: Entry, minimum: str, maximum: str, low: int = 0) -> None:
        """Comprueba extremos enteros y su orden cuando están presentes."""
        if minimum not in entry.data and maximum not in entry.data:
            return
        lower = self.integer(entry, minimum, low, 2147483647)
        upper = self.integer(entry, maximum, low, 2147483647)
        if lower is not None and upper is not None and lower > upper:
            self.problem(entry, maximum, f"Debe ser mayor o igual que {minimum}={lower}")

    def catalogs(self) -> None:
        """Valida los catálogos que realmente carga ItemCatalog/NPCCatalog/SpellCatalog."""
        files = sorted((self.data_dir / "items").glob("**/*.toml"))
        if not files:
            self.problem(Entry(self.data_dir / "items", "", {}), "", "No hay catálogos de ítems")
        items = [row for path in files for row in self.rows(self.read(path), "item")]
        self.items = self.unique(items)
        hostile = self.section(self.read(self.data_dir / "npcs/hostiles.toml"), "npcs_hostiles")
        friendly = self.read(self.data_dir / "npcs/friendly.toml")
        self.npcs = self.unique(self.rows(hostile, "npcs") + self.rows(friendly, "npc"))
        self.spells = self.unique(self.rows(self.read(self.data_dir / "spells.toml"), "spell"))
        for name, catalog in (("items", self.items), ("npcs", self.npcs), ("spells", self.spells)):
            self.report.counts[name] = len(catalog)
            if not catalog:
                self.problem(Entry(self.data_dir, name, {}), "", "El catálogo está vacío")
        for entry in self.items.values():
            self.integer(entry, "ObjType", 1)
            self.integer(entry, "GrhIndex", 0, 2147483647)
            if entry.data.get("GrhIndex") == 0:
                self.problem(
                    entry,
                    "GrhIndex",
                    "Objeto invisible: el mapa no dibuja sprite (GrhIndex=0)",
                    "warning",
                )
            for key in ("Valor", "MinHIT", "MaxHIT", "MinDef", "MaxDef"):
                if key in entry.data:
                    self.integer(entry, key, 0, 2147483647)
            self.pair(entry, "MinHIT", "MaxHIT")
            self.pair(entry, "MinDef", "MaxDef")
            for key in (
                "IndexAbierta",
                "IndexCerrada",
                "IndexCerradaLlave",
                "MineralIndex",
                "Lingoteindex",
            ):
                if entry.data.get(key, 0) != 0:
                    self.reference(entry, key, self.items)
            if entry.data.get("HechizoIndex", 0) != 0:
                self.reference(entry, "HechizoIndex", self.spells)
        for entry in self.spells.values():
            try:
                validate_extensions(entry.data, set(self.items))
            except (ValueError, TypeError) as exc:
                self.problem(entry, "extensions", str(exc))
            for key in ("mana_cost", "stamina_cost", "min_damage", "max_damage"):
                self.integer(entry, key)
            # 101 es el centinela del dataset VB6 para magia inaccesible por skill normal.
            self.integer(entry, "min_skill", 0, MAX_SKILL + 1)
            self.pair(entry, "min_damage", "max_damage")
            if "invoke_npc_id" in entry.data:
                self.reference(entry, "invoke_npc_id", self.npcs)
        for entry in self.npcs.values():
            for minimum, maximum in (("oro_min", "oro_max"), ("respawn_time", "respawn_time_max")):
                self.pair(entry, minimum, maximum)
            if "combat" in entry.data:
                self.pair(self.section(entry, "combat"), "min_hp", "max_hp")

    def inventories(self) -> None:
        """Comprueba mercaderes, tablas de loot e invocaciones."""
        for entry in self.items.values():
            try:
                normalize_potion_duration(entry.data)
            except (ValueError, TypeError) as exc:
                self.problem(entry, "EffectDurationSeconds", str(exc))
            if entry.data.get("ObjType") in {
                ObjType.COMIDA,
                ObjType.BEBIDA,
                ObjType.BOTELLAS_LLENAS,
            }:
                try:
                    NutritionRule.from_item(int(entry.identity), entry.data)
                except (ValueError, TypeError) as exc:
                    self.problem(entry, "nutrition", str(exc))
        merchants = self.rows(self.read(self.data_dir / "npcs/merchants.toml"), "merchant")
        self.unique(merchants, "npc_id")
        for entry in merchants:
            self.reference(entry, "npc_id", self.npcs)
            stock = self.rows(entry, "item")
            self.unique(stock, "item_id")
            for item in stock:
                self.reference(item, "item_id", self.items)
                self.integer(item, "quantity", 1, 2147483647)
        loot_file = self.read(self.data_dir / "npcs/loot_tables.toml")
        if "version" in loot_file.data:
            self.loot_policy(loot_file)
        loot = self.rows(loot_file, "loot_table")
        self.unique(loot)
        for entry in loot:
            self.reference(entry, "id", self.npcs)
            for item in self.rows(entry, "items"):
                self.reference(item, "item_id", self.items)
                self.pair(item, "min_quantity", "max_quantity", 1)
                value = item.data.get("probability")
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    or not 0 <= value <= 1
                ):
                    self.problem(item, "probability", "Probabilidad requerida entre 0 y 1")
        summons = self.section(self.read(self.data_dir / "npcs/summons.toml"), "summon_list")
        entries = self.rows(summons, "npcs")
        self.unique(entries)
        for entry in entries:
            self.reference(entry, "id", self.npcs)

    def loot_policy(self, entry: Entry) -> None:
        """Valida las bandas y clasifica cada objeto y cada NPC del dataset efectivo."""
        try:
            service = LootTableService(
                str(entry.file), catalog=ItemCatalog(str(self.data_dir / "items.toml"))
            )
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            self.problem(entry, "bands", f"Política de botín inválida: {exc}")
            return
        self.report.counts["loot_eligible"] = sum(
            not rule.reason for rule in service.item_rules.items.values()
        )
        self.report.counts["loot_excluded"] = sum(
            bool(rule.reason) for rule in service.item_rules.items.values()
        )
        for npc in self.npcs.values():
            profile = npc.data.get("loot_profile", "none")
            if profile not in service.rules["profiles"]:
                self.problem(npc, "loot_profile", "Perfil de botín inexistente")
            if profile != "none":
                self.integer(npc, "nivel", 1, 255)
            material = npc.data.get("loot_material", 0)
            if material and material not in service.catalog.get_all_item_ids():
                self.problem(npc, "loot_material", "Material de especie inexistente")

    def recipes(self) -> None:
        """Valida recetas, sus productos y materiales sin ejecutar crafting."""
        material_file = self.read(self.data_dir / "crafting/materials.toml")
        material_rows = self.rows(self.section(material_file, "crafting_materials"), "materials")
        materials: set[str] = set()
        for entry in material_rows:
            name = entry.data.get("id")
            if not isinstance(name, str) or not name or name in materials:
                self.problem(entry, "id", "ID de material vacío, inválido o duplicado")
            else:
                materials.add(name)
            # 'index' pertenece al catálogo de materiales; no es un ID de ítem.
            self.integer(entry, "index", 1)
            self.integer(entry, "skill_requirement", 0, MAX_SKILL)
        self.unique(material_rows, "index")
        for name in ("weapons", "armor", "carpentry"):
            file = self.read(self.data_dir / f"crafting/{name}.toml")
            section = self.section(file, name if name == "carpentry" else f"{name}_recipes")
            entries = self.rows(section, "recipe" if name == "carpentry" else "recipes")
            seen: set[str] = set()
            for entry in entries:
                key = "item_id" if name == "carpentry" else "index"
                self.reference(entry, key, self.items)
                identity = entry.data.get("item_id" if name == "carpentry" else "id")
                if not isinstance(identity, (str, int)) or str(identity) in seen:
                    self.problem(entry, "id", "Receta sin ID válido o duplicada")
                seen.add(str(identity))
                self.integer(
                    entry,
                    "skill_level" if name == "carpentry" else "skill_requirement",
                    0,
                    MAX_SKILL,
                )
                if name != "carpentry":
                    self.integer(entry, "success_rate", 0, MAX_SKILL)
                ingredients = self.rows(entry, "materials")
                if not ingredients:
                    self.problem(entry, "materials", "Una receta requiere materiales")
                for ingredient in ingredients:
                    self.integer(ingredient, "quantity", 1)
                    if name == "carpentry" or "item_id" in ingredient.data:
                        self.reference(ingredient, "item_id", self.items)
                    elif (
                        not isinstance(ingredient.data.get("item"), str)
                        or ingredient.data["item"] not in materials
                    ):
                        self.problem(ingredient, "item", "Material de crafting inexistente")
            self.report.counts[f"recipes_{name}"] = len(entries)

    def ndjson(self, path: Path) -> Iterator[Entry]:
        """Lee mapas línea por línea sin ocultar registros malformados.

        Yields:
            Registros localizados por número de línea (base uno).
        """
        try:
            with path.open(encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    entry = Entry(path, f"line[{number}]", {})
                    try:
                        value = json.loads(line, object_pairs_hook=_json_object)
                    except ValueError as exc:
                        self.problem(entry, "", f"JSON inválido: {exc}")
                        continue
                    if isinstance(value, dict):
                        yield Entry(path, entry.field, value)
                    else:
                        self.problem(entry, "", "Se esperaba un objeto")
        except (OSError, UnicodeError) as exc:
            self.problem(Entry(path, "", {}), "", f"No se puede leer el mapa: {exc}")

    def coordinates(self, entry: Entry, map_key: str, x_key: str, y_key: str) -> None:
        """Comprueba mapa y coordenadas usando las dimensiones de sus metadatos."""
        self.reference(entry, map_key, self.maps)
        map_id = entry.data.get(map_key)
        metadata = self.maps.get(map_id) if type(map_id) is int else None
        width = metadata.data.get("w", MAX_SKILL) if metadata else MAX_SKILL
        height = metadata.data.get("h", MAX_SKILL) if metadata else MAX_SKILL
        width = width if type(width) is int and width > 0 else MAX_SKILL
        height = height if type(height) is int and height > 0 else MAX_SKILL
        self.integer(entry, x_key, 1, width)
        self.integer(entry, y_key, 1, height)

    def world(self) -> None:
        """Comprueba índice, geometría, objetos y destinos de salida del mundo."""
        metadata_files = sorted(self.maps_dir.glob("metadata_*.json"))
        entries = [row for path in metadata_files for row in self.ndjson(path)]
        self.maps = self.unique(entries, "i")
        self.report.counts["maps"] = len(self.maps)
        if not self.maps:
            self.problem(Entry(self.maps_dir, "", {}), "", "No hay metadatos de mapas")
        for entry in entries:
            self.integer(entry, "w", 1, MAX_SKILL)
            self.integer(entry, "h", 1, MAX_SKILL)
        index = self.section(self.read(self.data_dir / "world/map_index.json"), "maps")
        expected = {str(map_id) for map_id in self.maps}
        if set(index.data) != expected:
            self.problem(
                index,
                "",
                f"Índice distinto de metadata; faltan={sorted(expected - set(index.data))}; "
                f"sobran={sorted(set(index.data) - expected)}",
            )
        self.integer(
            self.read(self.data_dir / "world/map_index.json"),
            "total_maps",
            len(expected),
            len(expected),
        )
        for prefix in ("blocked", "objects", "transitions"):
            paths = sorted(self.maps_dir.glob(f"{prefix}_*.json"))
            if not paths:
                self.problem(Entry(self.maps_dir, prefix, {}), "", "Faltan archivos requeridos")
            covered: set[int] = set()
            for path in paths:
                for entry in self.ndjson(path):
                    key = "from_map" if prefix == "transitions" else "m"
                    map_id = entry.data.get(key)
                    if type(map_id) is int:
                        covered.add(map_id)
                    if prefix == "transitions":
                        self.transitions(entry)
                    else:
                        self.coordinates(entry, "m", "x", "y")
                        if prefix == "objects":
                            self.integer(entry, "g", 1, 2147483647)
            if prefix == "transitions":
                required = {
                    int(key)
                    for key, value in index.data.items()
                    if key.isdecimal()
                    and isinstance(value, dict)
                    and isinstance(value.get("exits"), int)
                    and value["exits"] > 0
                }
                if required - covered:
                    self.problem(
                        Entry(self.maps_dir, prefix, {}),
                        "",
                        f"Mapas sin transiciones requeridas: {sorted(required - covered)}",
                    )
            if prefix == "blocked" and set(self.maps) - covered:
                self.problem(
                    Entry(self.maps_dir, prefix, {}),
                    "",
                    f"Mapas sin colisiones: {sorted(set(self.maps) - covered)}",
                )

    def transitions(self, entry: Entry) -> None:
        """Valida las salidas de un mapa sin corregir ni generar adyacencias."""
        self.reference(entry, "from_map", self.maps)
        positions: set[tuple[int, int]] = set()
        for exit_entry in self.rows(entry, "exits"):
            source = exit_entry.child(
                "source", {**exit_entry.data, "m": entry.data.get("from_map")}
            )
            self.coordinates(source, "m", "x", "y")
            self.coordinates(exit_entry, "to_map", "to_x", "to_y")
            x = self.integer(exit_entry, "x", 1, MAX_SKILL)
            y = self.integer(exit_entry, "y", 1, MAX_SKILL)
            if x is None or y is None:
                continue
            if (x, y) in positions:
                self.problem(exit_entry, "x,y", "Salida duplicada")
            positions.add((x, y))

    def spawns(self) -> None:
        """Comprueba puntos de aparición, ciudades y puertas manuales."""
        file = self.read(self.data_dir / "world/map_npcs.toml")
        maps = self.section(file, "map_npcs")
        for key in maps.data:
            group = self.section(maps, key)
            try:
                map_id = int(key)
            except ValueError:
                self.problem(group, "", "ID de mapa inválido")
                continue
            self.reference(group.child("map", {"id": map_id}), "id", self.maps)
            for entry in self.rows(group, "spawn_points") if "spawn_points" in group.data else []:
                self.reference(entry, "npc_id", self.npcs)
                self.coordinates(
                    entry.child("position", {**entry.data, "map_id": map_id}), "map_id", "x", "y"
                )
                self.integer(entry, "direction", 1, 4)
            for entry in self.rows(group, "random_spawns") if "random_spawns" in group.data else []:
                self.integer(entry, "count", 1)
                area = self.section(entry, "area")
                self.pair(area, "x1", "x2", 1)
                self.pair(area, "y1", "y2", 1)
                for x_key, y_key in (("x1", "y1"), ("x2", "y2")):
                    self.coordinates(
                        area.child("position", {**area.data, "map_id": map_id}),
                        "map_id",
                        x_key,
                        y_key,
                    )
        cities = self.section(self.read(self.data_dir / "world/cities.toml"), "cities")
        names: set[str] = set()
        for entry in self.rows(cities, "city"):
            name = entry.data.get("name")
            if not isinstance(name, str) or not name or name in names:
                self.problem(entry, "name", "Nombre de ciudad inválido o duplicado")
            else:
                names.add(name)
            self.coordinates(entry, "map_id", "spawn_x", "spawn_y")
        if cities.data.get("default_city") not in names:
            self.problem(cities, "default_city", "Ciudad por defecto inexistente")
        for entry in self.rows(self.read(self.data_dir / "world/map_doors.toml"), "door"):
            self.coordinates(entry, "map_id", "x", "y")
            self.reference(entry, "item_id", self.items)
            self.integer(entry, "grh_index", 1, 2147483647)

    def validate(self) -> Report:
        """Ejecuta las comprobaciones sin modificar archivos ni conectar a servicios.

        Returns:
            Informe completo del dataset seleccionado.
        """
        self.report = Report()
        self.catalogs()
        self.inventories()
        if any(
            (self.data_dir / "world" / name).exists() for name in ("quests.toml", "factions.toml")
        ):
            try:
                ExpansionCatalog(self.data_dir)
            except (OSError, ValueError, TypeError) as exc:
                self.problem(
                    Entry(self.data_dir / "world/quests.toml", "", {}), "catalog", str(exc)
                )
        self.recipes()
        self.world()
        self.spawns()
        self.client_resources()
        return self.report

    def client_resources(self) -> None:
        """Valida recursos propios cuando se selecciona también el checkout del cliente."""
        if self.client_dir is None:
            self.problem(
                Entry(self.data_dir, "client_assets", {}),
                "",
                "Sin --client-dir: validación audiovisual omitida; "
                "el servidor no usa esos archivos.",
                "warning",
            )
            return
        path = self.client_dir / "Assets/Init/graficos.ind"
        graphics: set[int] = set()
        try:
            data = path.read_bytes()
            offset = 8  # versión y cantidad (int32)
            struct.unpack_from("<II", data)
            while offset < len(data):
                grh_id, frames = struct.unpack_from("<IH", data, offset)
                graphics.add(grh_id)
                if frames < 1:
                    self.problem(Entry(path, "", {"id": grh_id}), "", "GRH sin frames")
                    break
                offset += 6
                offset += frames * 4 + 4 if frames > 1 else 12
            if offset != len(data):
                self.problem(Entry(path, "", {}), "", "Índice gráfico truncado")
        except (OSError, ValueError, struct.error) as exc:
            self.problem(Entry(path, "", {}), "", f"Índice gráfico inválido: {exc}")
        for entry in self.items.values():
            grh_id = entry.data.get("GrhIndex")
            if type(grh_id) is int and grh_id > 0 and grh_id not in graphics:
                self.problem(entry, "GrhIndex", f"GRH {grh_id} inexistente en {path}")
        for map_id in self.maps:
            for name in (f"Assets/Maps/mapa{map_id}.map", f"Maps/Map{map_id}.tscn"):
                resource = self.client_dir / name
                if not resource.is_file():
                    self.problem(Entry(resource, "", {"id": map_id}), "", "Mapa requerido ausente")
        for entry in self.spells.values():
            sound = entry.data.get("wav", 0)
            if sound and not (self.client_dir / f"Assets/Sfx/{sound}.wav").is_file():
                self.problem(
                    entry,
                    "wav",
                    f"Sonido {sound} ausente; AudioManager omite su reproducción",
                    "warning",
                )


def main(argv: Sequence[str] | None = None) -> int:
    """Ejecuta la herramienta con uv run python -m src.validation.dataset.

    Returns:
        Cero si los datos son válidos; uno ante errores bloqueantes.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    from src.runtime_paths import data_dir, maps_dir  # ruff: ignore[import-outside-top-level]

    parser.add_argument("--data-dir", type=Path, default=data_dir())
    parser.add_argument("--maps-dir", type=Path, default=maps_dir())
    parser.add_argument("--client-dir", type=Path, help="Checkout propio del cliente (opcional)")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    report = DatasetValidator(args.data_dir, args.maps_dir, args.client_dir).validate()
    if args.json_output:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for finding in report.findings:
            print(
                f"{finding.severity.upper()} {finding.file}:{finding.field} "
                f"ID={finding.record_id}: {finding.message}"
            )
        print(
            f"{report.errors} errores; {len(report.findings) - report.errors} advertencias; "
            f"{report.counts}"
        )
    return int(report.errors > 0)


if __name__ == "__main__":
    sys.exit(main())
