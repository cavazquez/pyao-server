"""Catálogo de autocompletado compacto, derivado de los permisos del servidor."""

from typing import TYPE_CHECKING

from src.config.config_manager import config_manager
from src.services.classic_chat.catalog import COMMANDS, available_commands

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

BASE_COMMANDS = tuple(
    (entry.name, entry.syntax) for entry in COMMANDS.values() if entry.role != "gm"
)


async def command_snapshot(deps: DependencyContainer, user: int) -> dict[str, list[str]]:
    """Envía nombres compactos; el cliente comparte sus metadatos de sintaxis.

    Returns:
        Catálogo completo autorizado, dentro de un único frame de estado.
    """
    gm = await deps.account_repo.is_gm_by_user_id(user)
    names = [
        entry.name
        for entry in available_commands(
            gm=gm, autoupdate=bool(config_manager.get("server.autoupdate_hook", ""))
        )
    ]
    return {"names": sorted(set(names))}
