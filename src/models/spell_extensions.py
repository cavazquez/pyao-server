"""Límites de componentes, área, pulsos y barreras definidos por catálogo."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_COMPONENT_TYPES = 8


class StrictRule(BaseModel):
    """Rechaza campos desconocidos y conversiones implícitas del dataset."""

    model_config = ConfigDict(extra="forbid", strict=True)


class Component(StrictRule):
    """Cantidad entera del objeto consumido por un lanzamiento confirmado."""

    item: int = Field(ge=1, le=32767)
    quantity: int = Field(ge=1, le=9999)


class Area(StrictRule):
    """Área acotada centrada en las coordenadas enviadas, siempre revalidada."""

    radius: int = Field(ge=1, le=4)
    shape: Literal["square", "diamond"] = "diamond"
    max_targets: int = Field(ge=1, le=16)
    targets: Literal["players", "npcs", "both"] = "both"


class Periodic(StrictRule):
    """Un efecto por modo; reaplicarlo reemplaza el anterior sin acumular."""

    mode: Literal["damage", "heal"]
    interval_seconds: int = Field(ge=1, le=60)
    duration_seconds: int = Field(ge=1, le=600)
    amount: int = Field(ge=1, le=5000)
    stacking: Literal["replace"] = "replace"

    @model_validator(mode="after")
    def duration_covers_interval(self) -> Periodic:
        """Exige al menos un pulso antes del vencimiento.

        Returns:
            Regla validada.

        Raises:
            ValueError: Si no existe un pulso ejecutable.
        """
        if self.duration_seconds < self.interval_seconds:
            message = "duration_seconds debe cubrir interval_seconds"
            raise ValueError(message)
        return self


class Barrier(StrictRule):
    """Escudo finito; cada daño consume capacidad dentro de su mismo commit."""

    capacity: int = Field(ge=1, le=10000)
    duration_seconds: int = Field(ge=1, le=600)
    damage_types: list[Literal["physical", "magic", "periodic", "poison"]] = Field(
        min_length=1, max_length=4
    )
    stacking: Literal["replace"] = "replace"


def validate_extensions(spell: dict[str, Any], item_ids: set[int]) -> None:
    """Valida referencias y límites antes de iniciar un mundo.

    Raises:
        ValueError: Si un campo o combinación no se puede ejecutar.
    """
    components = [Component.model_validate(row) for row in spell.get("components", [])]
    if len(components) > MAX_COMPONENT_TYPES or len({row.item for row in components}) != len(
        components
    ):
        message = "components: máximo 8 objetos distintos"
        raise ValueError(message)
    if any(row.item not in item_ids for row in components):
        message = "components: referencia a un objeto inexistente"
        raise ValueError(message)
    if "area" in spell:
        Area.model_validate(spell["area"])
        if any(spell.get(flag) for flag in ("revives", "invokes", "warps_pet", "morphs")):
            message = "area: no admite resurrección, invocación o mimetismo"
            raise ValueError(message)
    for key, model in (("periodic", Periodic), ("barrier", Barrier)):
        if key in spell:
            model.model_validate(spell[key])
            if int(spell.get("target", 3)) != 1:
                message = f"{key}: requiere target=1 (jugadores)"
                raise ValueError(message)
    if spell.get("dispels_magic") and int(spell.get("target", 3)) != 1:
        message = "dispels_magic: requiere target=1"
        raise ValueError(message)
