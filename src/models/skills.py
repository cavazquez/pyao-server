"""Catálogo canónico y proyección de nivel/experiencia del progreso persistido."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CATALOG_DATA = json.loads(
    (Path(__file__).parents[1] / "network/protocol/skills.json").read_text(encoding="utf-8")
)
MAX_SKILL_LEVEL = 100


def skill_threshold(level: int, base: int = 200) -> int:
    """Calcula el umbral creciente de la versión clásica sin truncar el redondeo.

    Returns:
        Experiencia requerida para el siguiente punto.
    """
    return max(1, round(base * 1.05 ** max(0, min(MAX_SKILL_LEVEL, level))))


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """ID estable, nombre y semántica histórica; los IDs propios no se pierden."""

    skill_id: int
    name: str
    key: str | None
    implemented: bool
    legacy_semantics: str


CATALOG = tuple(
    SkillDefinition(
        entry["id"], entry["name"], entry["key"], entry["implemented"], entry["legacy_semantics"]
    )
    for entry in CATALOG_DATA["skills"]
)
SKILLS_BY_KEY = {entry.key: entry for entry in CATALOG if entry.key is not None}


@dataclass(frozen=True, slots=True)
class SkillProgress:
    """Nivel, experiencia acumulada y porcentaje serializable son valores distintos."""

    definition: SkillDefinition
    level: int
    experience: int
    percentage: int


def skill_progress(
    values: Mapping[str, str | int], default_threshold: int = 100
) -> list[SkillProgress]:
    """Lee formato canónico o proyecta un legado sin modificarlo.

    Returns:
        Catálogo completo; IDs sin almacenamiento son cero y se conserva progreso histórico.

    Raises:
        ValueError: Si el formato canónico tiene nivel, XP o umbral inválido.
    """
    threshold = int(values.get("xp_per_level", default_threshold))
    if threshold < 1:
        msg = "Umbral de experiencia de habilidades inválido"
        raise ValueError(msg)
    result = []
    for definition in CATALOG:
        level = experience = 0
        if definition.key is not None:
            key = definition.key
            if f"level:{key}" in values:
                level = int(values[f"level:{key}"])
                experience = int(values.get(f"xp:{key}", 0))
                if not 0 <= level <= MAX_SKILL_LEVEL or experience < 0:
                    msg = "Progreso canónico de habilidades inválido"
                    raise ValueError(msg)
            elif definition.legacy_semantics == "experience":
                experience = max(0, int(values.get(key, 0)))
                level = min(MAX_SKILL_LEVEL, experience // threshold)
            else:
                level = min(MAX_SKILL_LEVEL, max(0, int(values.get(key, 0))))
        if str(values.get("progress_version", "")) == "2" and definition.key is not None:
            required = skill_threshold(level, int(values.get("natural_xp_base", 200)))
            percentage = min(
                99, max(0, int(values.get(f"partial:{definition.key}", 0))) * 100 // required
            )
        else:
            percentage = (experience % threshold) * 100 // threshold
        if level == MAX_SKILL_LEVEL:
            percentage = 0
        result.append(SkillProgress(definition, level, experience, percentage))
    return result


def skill_migration_fields(values: Mapping[str, str | int], threshold: int = 100) -> dict[str, str]:
    """Separa XP/nivel conservando intactos todos los campos históricos.

    Returns:
        Campos nuevos a agregar, o vacío si ya fue migrado.

    Raises:
        ValueError: Si el formato ya versionado es desconocido.
    """
    version = values.get("progress_version")
    if str(version) == "2":
        return {}
    if version is not None and str(version) != "1":
        msg = "Versión de progreso de habilidades desconocida"
        raise ValueError(msg)
    result = {"progress_version": "2", "xp_per_level": str(threshold), "natural_xp_base": "200"}
    result["assigned_points"] = str(min(10, max(0, 10 - int(values.get("points", 10)))))
    if "points" not in values:
        result["points"] = "10"
    for progress in skill_progress(values, threshold):
        if progress.definition.key is not None:
            key = progress.definition.key
            result[f"level:{key}"] = str(progress.level)
            result[f"xp:{key}"] = str(progress.experience)
            result[f"partial:{key}"] = str(
                progress.percentage * skill_threshold(progress.level) // 100
            )
    return result
