"""Ficha pública versionada, separada del roster para no perder ediciones."""

import json
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from src.utils.durability import ensure_aof, require_durable
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

PROFILE_LIMIT = 200
PROFILE_BYTES = 1200
LEADER_RANK = 4
FIRST_PRINTABLE = 32


def validate_profile(params: dict[str, Any]) -> None:
    """Valida textos y URL sin interpretar HTML ni ejecutar contenido.

    Raises:
        ValueError: Por límites, caracteres o dirección web no admitidos.
    """
    fields = {key: params[key] for key in ("description", "news", "website")}
    for value in fields.values():
        if len(value) > PROFILE_LIMIT or any(
            ord(char) < FIRST_PRINTABLE and char != "\n" for char in value
        ):
            msg = "Cada campo admite hasta 200 caracteres, sin caracteres de control."
            raise ValueError(msg)
        value.encode("latin-1")
    if len(json.dumps(fields, ensure_ascii=True).encode()) > PROFILE_BYTES:
        msg = "La ficha excede el tamaño permitido; acortá los textos."
        raise ValueError(msg)
    website = fields["website"]
    url = urlsplit(website)
    if website and (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or any(value is not None for value in (url.username, url.password))
        or any(char.isspace() for char in website)
    ):
        msg = "El sitio debe ser una dirección http:// o https:// sin credenciales."
        raise ValueError(msg)


async def update_profile(
    deps: DependencyContainer, user: int, request: dict[str, Any]
) -> dict[str, Any]:
    """Verifica membresía, líder y versión dentro de WATCH/EXEC.

    Returns:
        Edición durable o conflicto recuperable sin sobrescribir textos ajenos.
    """
    params = request["params"]
    validate_profile(params)
    clan_id = params["clan"]
    if clan_id < 1 or params["version"] < 0:
        return {"applied": False, "message": "Clan o versión inválidos."}
    clan_key, members = f"clan:{clan_id}", f"clan:{clan_id}:members"
    own, profile = f"user:{user}:clan", f"clan:{clan_id}:profile"

    def decide(snapshot: Snapshot) -> Decision:
        metadata = json.loads(str(snapshot[clan_key] or "{}"))
        roster = cast("dict[str, str]", snapshot[members])
        actor = json.loads(roster.get(str(user), "{}"))
        if (
            str(snapshot[own]) != str(clan_id)
            or int(metadata.get("leader_id", 0)) != user
            or int(actor.get("rank", 0)) != LEADER_RANK
        ):
            return Decision(
                {"applied": False, "message": "Sólo el líder vigente puede editar la ficha."}, {}
            )
        current = cast("dict[str, str]", snapshot[profile])
        version = int(current.get("revision", 0))
        if version != params["version"]:
            return Decision(
                {
                    "applied": False,
                    "conflict": True,
                    "message": (
                        "La ficha cambió. Tu borrador se conserva; "
                        "revisá los datos antes de reenviar."
                    ),
                },
                {},
            )
        return Decision(
            {
                "applied": True,
                "version": version + 1,
                "message": "Ficha pública del clan actualizada.",
            },
            {
                profile: {
                    **{key: params[key] for key in ("description", "news", "website")},
                    "revision": str(version + 1),
                }
            },
        )

    redis = deps.redis_client.redis
    await ensure_aof(redis)
    result = await transact(
        redis,
        (
            Resource(clan_key, "string"),
            Resource(members, "hash"),
            Resource(own, "string"),
            Resource(profile, "hash"),
        ),
        request["id"],
        {"clan_profile": user, "params": params},
        decide,
    )
    await require_durable(redis)
    return result
