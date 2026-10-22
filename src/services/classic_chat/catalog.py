"""Catálogo compartido de nombres, sintaxis y permisos de chat."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """Descripción pública de una ruta; no concede permisos al cliente."""

    name: str
    syntax: str
    description: str
    role: str
    transport: str
    source_line: int


CATALOG_PATH = Path(__file__).parents[2] / "network/protocol/chat_commands.json"
COMMANDS = {
    row["name"]: CommandDefinition(**row)
    for row in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["commands"]
}
MODERN_COMMANDS = frozenset(
    {
        "/METRICS",
        "/CREARCLAN",
        "/INVITARCLAN",
        "/ACEPTARCLAN",
        "/RECHAZARCLAN",
        "/EXPULSARCLAN",
        "/PROMOVERCLAN",
        "/DEGRADARCLAN",
        "/TRANSFERIRLIDERAZGO",
        "/CLAN",
        "/PET",
        "/MUTE",
        "/UNMUTE",
    }
)


def command_token(text: str) -> str:
    """Normaliza sólo el primer token, sin alterar nombres ni mensajes.

    Returns:
        Nombre exacto en mayúsculas, o cadena vacía.
    """
    parts = text.strip().split(maxsplit=1)
    return parts[0].upper() if parts else ""


def available_commands(*, gm: bool = False, autoupdate: bool = False) -> list[CommandDefinition]:
    """Filtra roles y funciones que requieren configuración del operador.

    Returns:
        Definiciones que pueden anunciarse a esta sesión.
    """
    return [
        entry
        for entry in COMMANDS.values()
        if (gm or entry.role != "gm") and (autoupdate or entry.name != "/AUTOUPDATE")
    ]


def help_text(*, gm: bool = False, page: int = 1, autoupdate: bool = False) -> str:
    """Forma una página de ayuda a partir del mismo catálogo del despacho.

    Returns:
        Sintaxis y explicación, con los comandos GM limitados a administradores.

    Raises:
        ValueError: Si la página no existe.
    """
    rows = available_commands(gm=gm, autoupdate=autoupdate)
    rows.sort(key=lambda definition: definition.name)
    pages = max(1, (len(rows) + 19) // 20)
    if not 1 <= page <= pages:
        message = f"Página inválida. Usa /AYUDA 1 a {pages}."
        raise ValueError(message)
    lines = [f"--- Comandos Disponibles ({page}/{pages}) ---"]
    lines.extend(
        f"{definition.syntax} - {definition.description}"
        for definition in rows[(page - 1) * 20 : page * 20]
    )
    lines.append(f"/AYUDA página (1 a {pages}).")
    return "\n".join(lines)
