"""Pruebas de datos corruptos y referencias sin Redis ni arranque del mundo."""

import json
from pathlib import Path

import pytest

from src.validation.dataset import DatasetValidator, Entry, main
from tools.compression.decompress_map_data import decompress_map_data


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[Path, Path]:
    """Crea un dataset mínimo completo y válido."""
    data = tmp_path / "data"
    maps = tmp_path / "map_data"
    files = {
        "items/test.toml": '[[item]]\nid=1\nName="Prueba"\nObjType=1\nGrhIndex=1\n',
        "npcs/hostiles.toml": "[npcs_hostiles]\n[[npcs_hostiles.npcs]]\nid=1\n",
        "npcs/friendly.toml": "npc=[]\n",
        "spells.toml": (
            "[[spell]]\n"
            "id=1\n"
            "mana_cost=1\n"
            "stamina_cost=1\n"
            "min_damage=0\n"
            "max_damage=1\n"
            "min_skill=0\n"
        ),
        "npcs/merchants.toml": "[[merchant]]\nnpc_id=1\n[[merchant.item]]\nitem_id=1\nquantity=1\n",
        "npcs/loot_tables.toml": (
            "[[loot_table]]\n"
            "id=1\n"
            "items=[{item_id=1,probability=0.5,min_quantity=1,max_quantity=2}]"
            "\n"
        ),
        "npcs/summons.toml": "[summon_list]\nnpcs=[{id=1}]\n",
        "crafting/materials.toml": (
            '[crafting_materials]\nmaterials=[{id="hierro",index=1,skill_requirement=1}]\n'
        ),
        "crafting/weapons.toml": (
            "[weapons_recipes]\n"
            'recipes=[{id="w1",index=1,skill_requirement=1,success_rate=50,mat'
            'erials=[{item="hierro",quantity=1}]}]\n'
        ),
        "crafting/armor.toml": "[armor_recipes]\nrecipes=[]\n",
        "crafting/carpentry.toml": (
            "[carpentry]\nrecipe=[{item_id=1,skill_level=0,materials=[{item_id=1,quantity=1}]}]\n"
        ),
        "world/map_npcs.toml": "[map_npcs.1]\nspawn_points=[{npc_id=1,x=1,y=1,direction=3}]\n",
        "world/cities.toml": (
            '[cities]\ndefault_city="Prueba"\ncity=[{name="Prueba",map_id=1,spawn_x=1,spawn_y=1}]\n'
        ),
        "world/map_doors.toml": "door=[]\n",
        "world/map_index.json": '{"total_maps":1,"maps":{"1":{}}}\n',
    }
    for name, text in files.items():
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    maps.mkdir()
    for name, row in {
        "metadata_test.json": {"i": 1, "w": 10, "h": 10},
        "blocked_test.json": {"m": 1, "x": 1, "y": 1, "t": "b"},
        "objects_test.json": {"m": 1, "x": 2, "y": 2, "g": 1, "t": "tree"},
        "transitions_test.json": {
            "from_map": 1,
            "exits": [{"x": 1, "y": 1, "to_map": 1, "to_x": 2, "to_y": 2}],
        },
    }.items():
        (maps / name).write_text(json.dumps(row) + "\n")
    return data, maps


def test_valid_dataset_is_read_only_and_repeatable(dataset):
    """Valida dos veces sin crear archivos ni conectar a Redis."""
    data, maps = dataset
    before = {p: p.read_bytes() for p in data.parent.rglob("*") if p.is_file()}
    validator = DatasetValidator(data, maps)
    first = validator.validate().to_dict()
    assert first["errors"] == 0
    assert first["counts"]["items"] == 1
    assert validator.validate().to_dict() == first
    assert {p: p.read_bytes() for p in data.parent.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    ("name", "old", "new", "field"),
    [
        ("items/test.toml", "id=1", "id=true", "id"),
        ("items/test.toml", "GrhIndex=1", "GrhIndex=-1", "GrhIndex"),
        ("items/test.toml", "ObjType=1", "ObjType=1\nHechizoIndex=999", "HechizoIndex"),
        ("items/test.toml", "ObjType=1", "ObjType=1\nIndexAbierta=999", "IndexAbierta"),
        ("spells.toml", "id=1", "id=1\ninvoke_npc_id=999", "invoke_npc_id"),
        ("spells.toml", "min_skill=0", "min_skill=102", "min_skill"),
        ("spells.toml", "max_damage=1", "max_damage=-1", "max_damage"),
        ("npcs/merchants.toml", "item_id=1", "item_id=999", "item_id"),
        ("npcs/loot_tables.toml", "probability=0.5", "probability=nan", "probability"),
        ("npcs/loot_tables.toml", "min_quantity=1", "min_quantity=3", "max_quantity"),
        ("crafting/weapons.toml", 'item="hierro"', 'item="inexistente"', "item"),
        ("crafting/carpentry.toml", "quantity=1", "quantity=0", "quantity"),
        ("world/map_npcs.toml", "npc_id=1", "npc_id=999", "npc_id"),
        ("world/map_npcs.toml", "x=1", "x=11", "x"),
        ("world/cities.toml", 'default_city="Prueba"', 'default_city="Otra"', "default_city"),
    ],
)
def test_invalid_references_and_ranges(dataset, name, old, new, field):
    """Informa el archivo, campo e identidad cuando un dato deja de ser válido."""
    data, maps = dataset
    path = data / name
    path.write_text(path.read_text().replace(old, new))
    report = DatasetValidator(data, maps).validate()
    assert report.errors > 0
    assert any(f.file == str(path) and f.field.endswith(field) for f in report.findings)


def test_duplicate_ids_cannot_be_silently_overwritten(dataset):
    """Detecta duplicados entre archivos del mismo catálogo."""
    data, maps = dataset
    (data / "items/second.toml").write_text((data / "items/test.toml").read_text())
    report = DatasetValidator(data, maps).validate()
    assert any("duplicado 1" in f.message for f in report.findings)


@pytest.mark.parametrize("kind", ["missing", "malformed", "wrong_shape"])
def test_required_files_and_shapes(dataset, kind):
    """Los archivos ausentes, inválidos o con una sección mal tipada bloquean."""
    data, maps = dataset
    path = data / "spells.toml"
    if kind == "missing":
        path.unlink()
    else:
        path.write_text("[" if kind == "malformed" else "spell=1")
    assert DatasetValidator(data, maps).validate().errors > 0


@pytest.mark.parametrize(("key", "value"), [("to_map", 999), ("to_x", 11), ("to_y", 0)])
def test_exit_destinations_are_validated(dataset, key, value):
    """No alcanza con que el origen de una salida sea correcto."""
    data, maps = dataset
    path = maps / "transitions_test.json"
    row = json.loads(path.read_text())
    row["exits"][0][key] = value
    path.write_text(json.dumps(row) + "\n")
    report = DatasetValidator(data, maps).validate()
    assert any(f.file == str(path) and f.field.endswith(key) for f in report.findings)


def test_invalid_ndjson_is_not_skipped(dataset):
    """Conserva el número de línea de JSON corrupto, incluso entre filas válidas."""
    data, maps = dataset
    path = maps / "objects_test.json"
    with path.open("a") as stream:
        stream.write("{invalid\n[]\n")
    report = DatasetValidator(data, maps).validate()
    assert any(f.field == "line[2]" for f in report.findings)
    assert any(f.field == "line[3]" for f in report.findings)


def test_random_spawns_do_not_require_fixed_spawns(dataset):
    """Acepta mapas sólo aleatorios y controla el área elegida."""
    data, maps = dataset
    path = data / "world/map_npcs.toml"
    path.write_text(
        '[map_npcs.1]\nrandom_spawns=[{npc_type="hostile",count=2,area={x1=1,y1=1,x2=10,y2=10}}]'
    )
    assert DatasetValidator(data, maps).validate().errors == 0
    path.write_text(path.read_text().replace("x2=10", "x2=11"))
    assert DatasetValidator(data, maps).validate().errors > 0


def test_optional_invisible_object_and_disabled_spell(dataset):
    """Los centinelas del dataset no habilitan excepciones generales a las referencias."""
    data, maps = dataset
    path = data / "items/test.toml"
    path.write_text(path.read_text().replace("GrhIndex=1", "GrhIndex=0"))
    path = data / "spells.toml"
    path.write_text(path.read_text().replace("min_skill=0", "min_skill=101"))
    report = DatasetValidator(data, maps).validate()
    assert report.errors == 0
    assert any(f.field.endswith("GrhIndex") and f.severity == "warning" for f in report.findings)


def test_cli_exit_status_and_json(dataset, capsys):
    """La CI recibe un código distinto de cero ante datos inválidos."""
    data, maps = dataset
    args = ["--data-dir", str(data), "--maps-dir", str(maps), "--json"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["errors"] == 0
    (data / "spells.toml").unlink()
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["errors"] > 0


def test_client_resources_are_checked_when_selected(dataset):
    """Un checkout explícito con archivos faltantes produce errores, no un skip."""
    data, maps = dataset
    report = DatasetValidator(data, maps, data.parent / "missing_client").validate()
    assert any("Índice gráfico inválido" in f.message for f in report.findings)
    assert any("Mapa requerido ausente" in f.message for f in report.findings)


def test_versioned_dataset(tmp_path: Path):
    """Los datos reales también deben pasar, incluyendo recetas y 290 mapas."""
    root = Path(__file__).resolve().parents[1]
    maps = tmp_path / "map_data"
    decompress_map_data(root / "archives/map_data.xz", maps, overwrite=False)
    report = DatasetValidator(root / "data", maps).validate()
    assert report.errors == 0, report.to_dict()
    assert report.counts["maps"] == 290
    assert report.counts["items"] == 1078


def test_bad_dimensions_produce_diagnostics_instead_of_crashing(dataset):
    """Continúa informando después de un tamaño de mapa de tipo incorrecto."""
    data, maps = dataset
    (maps / "metadata_test.json").write_text('{"i":1,"w":"bad","h":0}\n')
    assert DatasetValidator(data, maps).validate().errors > 0


def test_integer_rejects_float_and_bool(dataset):
    """Los números no enteros nunca se truncan ni aceptan como IDs."""
    data, maps = dataset
    validator = DatasetValidator(data, maps)
    for value in (True, 1.5, "1", None):
        assert validator.integer(Entry(data, "", {"id": value}), "id", 1) is None
    assert validator.report.errors == 4


def test_duplicate_json_keys_are_errors(dataset):
    """No pierde mapas duplicados al leer un objeto JSON."""
    data, maps = dataset
    (data / "world/map_index.json").write_text('{"maps":{"1":{},"1":{}},"total_maps":1}')
    report = DatasetValidator(data, maps).validate()
    assert any("Clave JSON duplicada" in f.message for f in report.findings)
