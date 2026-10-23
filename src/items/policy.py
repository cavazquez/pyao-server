"""Política versionada de desgaste; el catálogo base nunca se modifica al usarlo."""

import tomllib
from dataclasses import dataclass, replace
from functools import cache
from typing import Literal

from src.models.items_catalog import ITEMS_CATALOG
from src.runtime_paths import data_dir

BASIS_POINTS = 10000
SECONDS_PER_DAY = 86400
TOOL_IDS = frozenset({127, 138, 187, 198, 389, 561, 562, 563, 564, 565})
STAT_FIELDS = frozenset(
    {"MinHit", "MaxHit", "MinDef", "MaxDef", "DefensaMagicaMin", "DefensaMagicaMax", "StaffPower"}
)


@dataclass(frozen=True, slots=True)
class ItemPolicy:
    """Cero deshabilita cada límite; el tiempo se cuenta desde la creación UTC."""

    kind: Literal["durable", "consumable", "exempt"]
    max_uses: int = 0
    lifetime_seconds: int = 0
    minimum_factor_bps: int = 5000
    version: int = 1


@cache
def policies() -> dict[int, ItemPolicy]:
    """Carga y valida una clasificación explícita para cada tipo.

    Returns:
        Políticas por ObjType, incluidos tipos sin ejemplares actuales.

    Raises:
        ValueError: Si falta un tipo o los límites no son enteros válidos.
    """
    with (data_dir() / "item_durability.toml").open("rb") as source:
        data = tomllib.load(source)
    result = {}
    for key, values in data["types"].items():
        policy = ItemPolicy(**values)
        if (
            policy.kind not in {"durable", "consumable", "exempt"}
            or any(
                type(value) is not int or value < 0
                for value in (
                    policy.max_uses,
                    policy.lifetime_seconds,
                    policy.version,
                    policy.minimum_factor_bps,
                )
            )
            or not 0 <= policy.minimum_factor_bps <= BASIS_POINTS
            or policy.version < 1
        ):
            msg = "Política de durabilidad inválida"
            raise ValueError(msg)
        if policy.kind != "durable" and (policy.max_uses or policy.lifetime_seconds):
            msg = "Un consumible o exento no puede tener desgaste"
            raise ValueError(msg)
        result[int(key)] = policy
    if not {item.obj_type for item in ITEMS_CATALOG.values()} <= result.keys():
        msg = "Hay tipos del catálogo sin política de durabilidad"
        raise ValueError(msg)
    return result


@cache
def tool_limit() -> int:
    """Carga el límite configurable de las herramientas explícitas.

    Returns:
        Usos máximos; cero deshabilita este límite.

    Raises:
        ValueError: Si no es un entero no negativo.
    """
    with (data_dir() / "item_durability.toml").open("rb") as stream:
        maximum = tomllib.load(stream)["tools"]["max_uses"]
    if type(maximum) is not int or maximum < 0:
        message = "Límite de usos de herramientas inválido"
        raise ValueError(message)
    return maximum


def policy_for(item_id: int) -> ItemPolicy:
    """Obtiene la política del ejemplar sin clasificar por el nombre.

    Returns:
        Política de tipo y especialización explícita de herramientas.
    """
    item = ITEMS_CATALOG.get(item_id)
    if item is None:
        return ItemPolicy("exempt")
    policy = policies()[item.obj_type]
    return replace(policy, max_uses=tool_limit()) if item_id in TOOL_IDS else policy


def individual(item_id: int) -> bool:
    """Indica si el objeto exige identidad individual.

    Returns:
        True para los durables, incluso si sus límites fueron deshabilitados.
    """
    return policy_for(item_id).kind == "durable"
