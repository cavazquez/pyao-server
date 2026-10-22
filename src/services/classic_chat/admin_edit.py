"""Variantes originales de /MOD: perfil, habilidades, reputación y posición."""

import unicodedata
from typing import cast

from src.config.config_manager import config_manager
from src.game.character_constants import GENDER_ID_TO_NAME, JOB_ID_TO_CLASS_NAME, RACE_ID_TO_NAME
from src.models.skills import CATALOG
from src.services.classic_chat.admin_common import audited
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.services.player_progression import level_points_between, publish_progress
from src.utils.level_calculator import calculate_elu_for_level, calculate_total_exp_for_level
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAX_GOLD_VALUE = 999999999
MAX_SKILL_POINTS = 32767
POSITION_COMPONENTS = 3
SKILL_COMPONENTS = 2

EXTENDED_FIELDS = frozenset(
    {
        "body",
        "head",
        "level",
        "skills",
        "skillslibres",
        "clase",
        "cri",
        "ciu",
        "nob",
        "ase",
        "sex",
        "raza",
        "agregar",
        "vida",
        "poss",
    }
)


def normalized(value: str) -> str:
    """Compara nombres del catálogo con acentos y separadores históricos.

    Returns:
        Identificador para búsquedas, sin alterar el texto guardado.
    """
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value.replace("+", " ").casefold())
        if unicodedata.category(char) != "Mn"
    )


def catalog_id(value: str, names: dict[int, str]) -> int:
    """Acepta el nombre original o el ID propio de clase, raza o género.

    Returns:
        Identificador válido.

    Raises:
        ChatCommandError: Si no existe el valor.
    """
    for identifier, name in names.items():
        if value == str(identifier) or normalized(name) == normalized(value):
            return identifier
    message = "Valor desconocido; opciones: " + ", ".join(names.values())
    raise ChatCommandError(message)


async def edit(ctx: ChatContext, name: str, field: str, argument: str) -> None:  # ruff: ignore[too-many-statements, too-many-locals] - las 17 variantes EditChar comparten validación y un único commit.
    """Aplica variantes de EditChar sin escribir claves elegidas por el usuario.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.account(name)
    user = int(account["user_id"])
    stats_key, profile_key, skills_key = (
        RedisKeys.player_user_stats(user),
        RedisKeys.account_data(account["username"]),
        RedisKeys.player_skills(user),
    )
    if field == "poss":
        parts = argument.replace(",", "-").split("-")
        if len(parts) != POSITION_COMPONENTS:
            message = "Uso: /MOD nombre POSS mapa-x-y"
            raise ChatCommandError(message)
        map_id, x, y = (
            integer(parts[0], 1, 290),
            integer(parts[1], 1, 100),
            integer(parts[2], 1, 100),
        )
        if not ctx.deps.map_manager.has_map(map_id) or not ctx.deps.map_manager.can_move_to(
            map_id, x, y
        ):
            message = "La posición no existe o está ocupada/bloqueada."
            raise ChatCommandError(message)
        if ctx.deps.map_manager.get_player_message_sender(user):
            from src.services.classic_chat.admin_character import warp  # ruff: ignore[import-outside-top-level] - evita el ciclo del editor con su fachada administrativa.

            await warp(ctx, account["username"], map_id, x, y)
        else:
            position_key = RedisKeys.player_position(user)
            await audited(
                ctx,
                (Resource(position_key, "hash"),),
                {"target": user, "position": [map_id, x, y]},
                lambda _snapshot: Decision(
                    {"applied": True},
                    {position_key: {"map": str(map_id), "x": str(x), "y": str(y)}},
                ),
            )
        await ctx.tell("Posición actualizada.")
        return

    profile: dict[str, str] = {}
    skill: dict[str, str] = {}
    stats: dict[str, str] = {}
    value = 0
    if field in {"body", "head"}:
        profile[f"char_{field}"] = str(integer(argument, 0, 32767))
    elif field in {"clase", "raza", "sex"}:
        column, names = {
            "clase": ("char_job", JOB_ID_TO_CLASS_NAME),
            "raza": ("char_race", RACE_ID_TO_NAME),
            "sex": ("char_gender", GENDER_ID_TO_NAME),
        }[field]
        value = catalog_id(argument, names)
        profile[column] = str(value)
        if field == "clase":
            stats["class_id"] = str(value)
    elif field == "skills":
        parts = argument.rsplit(maxsplit=1)
        if len(parts) != SKILL_COMPONENTS:
            message = "Uso: /MOD nombre SKILLS habilidad nivel(0 a 100)"
            raise ChatCommandError(message)
        entry = next(
            (
                entry
                for entry in CATALOG
                if entry.key
                and normalized(parts[0])
                in {normalized(entry.key), normalized(entry.name), str(entry.skill_id)}
            ),
            None,
        )
        if entry is None or entry.key is None:
            message = "Habilidad desconocida o reservada por el catálogo."
            raise ChatCommandError(message)
        level = integer(parts[1], 0, 100)
        skill = {
            f"level:{entry.key}": str(level),
            f"partial:{entry.key}": "0",
            f"xp:{entry.key}": "0",
            "progress_version": "2",
        }
    elif field == "skillslibres":
        skill["points"] = str(integer(argument, 0, 32767))
    elif field == "level":
        value = integer(argument, 1, 100)
    elif field in {"cri", "ciu", "nob", "ase"}:
        column = {
            "cri": "criminal_kills",
            "ciu": "citizen_kills",
            "nob": "rep_noble",
            "ase": "rep_murderer",
        }[field]
        stats[column] = str(integer(argument, 0, 999999999))
        if field == "ase":
            stats["criminal"] = "1" if int(stats[column]) else "0"
    elif field == "agregar":
        value = integer(argument, -999999999, 999999999)
    elif field == "vida":
        value = integer(argument, 1, 32767)

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[stats_key])
        current_skills = cast("dict[str, str]", snapshot[skills_key])
        current_profile = cast("dict[str, str]", snapshot[profile_key])
        if not before or current_profile.get("user_id") != str(user):
            return Decision(
                {"applied": False, "message": "El personaje ya no tiene una identidad válida."}, {}
            )
        changes, skills = dict(stats), dict(skill)
        if field == "agregar":
            balance = int(before.get("gold", 0)) + value
            if not 0 <= balance <= MAX_GOLD_VALUE:
                return Decision(
                    {"applied": False, "message": "El saldo quedaría fuera de los límites."}, {}
                )
            changes["gold"] = str(balance)
        elif field == "vida":
            if int(before.get("min_hp", 0)) <= 0:
                return Decision(
                    {
                        "applied": False,
                        "message": (
                            "Usa /REVIVIR para liquidar la muerte y resucitar antes de editar VIDA."
                        ),
                    },
                    {},
                )
            changes.update({"max_hp": str(value), "min_hp": str(value)})
            if "hp" in before:
                changes["hp"] = str(value)
        elif field == "level":
            granted = int(current_skills.get("points_granted_through", before.get("level", 1)))
            points = int(current_skills.get("points", 0)) + level_points_between(granted, value)
            if points > MAX_SKILL_POINTS:
                return Decision(
                    {
                        "applied": False,
                        "message": "El presupuesto de habilidades excedería el máximo.",
                    },
                    {},
                )
            changes.update(
                {
                    "level": str(value),
                    "experience": str(calculate_total_exp_for_level(value, config_manager)),
                    "elu": str(calculate_elu_for_level(value, config_manager)),
                }
            )
            skills.update(
                {"points_granted_through": str(max(granted, value)), "points": str(points)}
            )
        return Decision(
            {"applied": True}, {stats_key: changes, skills_key: skills, profile_key: profile}
        )

    await audited(
        ctx,
        (Resource(stats_key, "hash"), Resource(profile_key, "hash"), Resource(skills_key, "hash")),
        {"edit": field, "target": user},
        decide,
    )
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if sender:
        await publish_progress(ctx.deps.player_repo, user, sender)
        if ctx.deps.player_death_service:
            await ctx.deps.player_death_service.publish_state(user)
    await ctx.tell("Personaje actualizado.")
