"""Catálogo completo, límites de tokens y autorización antes de cualquier efecto."""

import json
from pathlib import Path

import pytest

from src.services.classic_chat.catalog import COMMANDS, MODERN_COMMANDS, command_token, help_text
from src.services.classic_chat.native import NATIVE_NAMES
from src.services.classic_chat.service import HANDLERS
from src.services.world.commands import command_snapshot


def test_every_original_and_own_command_has_an_explicit_route():
    """Una respuesta genérica de no implementado nunca cuenta como ruta completada."""
    original = json.loads(
        (Path(__file__).parents[1] / "fixtures/classic_commands.json").read_text()
    )
    assert len(original["commands"]) == 177
    assert set(original["commands"]) <= COMMANDS.keys()
    assert len(COMMANDS) == 194
    external = MODERN_COMMANDS | {"/BAN", "/UNBAN", "/COMERCIAR", "/SALIRCLAN", "/AYUDA"}
    forms = {entry.name for entry in COMMANDS.values() if entry.transport == "form"}
    assert not COMMANDS.keys() - (HANDLERS.keys() | NATIVE_NAMES | external | forms)
    assert all(entry.syntax.startswith(entry.name) for entry in COMMANDS.values())
    assert all(not entry.description.startswith("Administración:") for entry in COMMANDS.values())


@pytest.mark.asyncio
async def test_all_prefixes_and_unknown_tokens_are_private(chat_world):
    """Ni mayúsculas, tabs ni un prefijo de un comando desvían argumentos al mapa."""
    world = chat_world
    cases = [entry.name + "X" for entry in COMMANDS.values()] + ["/", "/???", "/METRICS_EXTRA"]
    for command in cases:
        assert command not in COMMANDS
        result = await world.talk("  " + command + "\tsecret-never-broadcast", user=2)
        assert "desconocido" in result.lower(), command
        assert "secret-never-broadcast" not in result, command
        assert not world.senders[1].lines, command
        assert not world.senders[3].lines, command
    assert command_token(" \t/aPaSs\tJugador@Offline ") == "/APASS"


@pytest.mark.asyncio
async def test_all_gm_commands_reject_normal_account_before_argument_parsing(chat_world):
    """El cliente no concede roles y argumentos inválidos no saltan la autorización."""
    world = chat_world
    before = sorted(await world.redis.keys("*"))
    for entry in COMMANDS.values():
        if entry.role == "gm":
            result = await world.run(entry.name + " invalid-secret", user=2)
            assert result == "No tienes permisos de Game Master.", entry.name
    assert sorted(await world.redis.keys("*")) == before
    assert not world.stops
    assert not world.senders[1].lines
    assert not world.senders[3].lines


@pytest.mark.asyncio
async def test_help_and_completion_share_permissions_and_pages(chat_world):
    """Help and completion share permissions and pages."""
    normal = await command_snapshot(chat_world.deps, 2)
    gm = await command_snapshot(chat_world.deps, 1)
    assert "/CONSULTA" not in normal["names"]
    assert "/METRICS" not in normal["names"]
    assert "/MUTE" not in normal["names"]
    assert "/CONSULTA" in gm["names"]
    assert "/AUTOUPDATE" not in gm["names"]  # Requiere agente configurado.
    assert len(json.dumps(gm, ensure_ascii=False).encode()) < 3800
    for names, operator in ((normal["names"], False), (gm["names"], True)):
        pages = (len(names) + 19) // 20
        text = "\n".join(help_text(gm=operator, page=page) for page in range(1, pages + 1))
        assert all(name in text for name in names)
    for page in (0, -1, 999):
        with pytest.raises(ValueError, match="Página"):
            help_text(page=page)
