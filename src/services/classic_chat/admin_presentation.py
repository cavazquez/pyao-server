"""Clima, música, sonidos y voz de NPC con audiencia y recursos validados."""

from typing import TYPE_CHECKING, cast

from src.network.chat_channel import deliver_chat
from src.services.classic_chat.admin_common import audited, fields
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAP_ARGUMENTS = 2
MAX_NPC_MESSAGE_LENGTH = 400
POSITIONAL_SOUND_ARGUMENTS = 4
RGB_COMPONENTS = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def media(ctx: ChatContext) -> None:
    """Reproduce en un mapa o globalmente los mismos paquetes usados por el juego.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.replace(",", " ").split()
    allowed = (
        {1, 2, 4}
        if ctx.command == "/FORCEWAVMAP"
        else {1, 2}
        if ctx.command.endswith("MAP")
        else {1}
    )
    if len(parts) not in allowed:
        message = f"Uso: {ctx.command} número" + (
            " [mapa [x y]]"
            if ctx.command == "/FORCEWAVMAP"
            else " [mapa]"
            if ctx.command.endswith("MAP")
            else ""
        )
        raise ChatCommandError(message)
    midi = "MIDI" in ctx.command
    number = integer(parts[0], 0, 255)
    position = await ctx.position()
    map_id = integer(parts[1], 1, 32767) if len(parts) >= MAP_ARGUMENTS else position["map"]
    x, y = (
        (integer(parts[2], 1, 100), integer(parts[3], 1, 100))
        if len(parts) == POSITIONAL_SOUND_ARGUMENTS
        else (0, 0)
    )
    if not ctx.deps.map_manager.has_map(map_id):
        message = "Mapa desconocido."
        raise ChatCommandError(message)
    await audited(
        ctx,
        (),
        {"media": number, "map": map_id if ctx.command.endswith("MAP") else "all"},
        lambda _snapshot: Decision({"applied": True}, {}),
    )
    users = (
        ctx.deps.map_manager.get_players_in_map(map_id)
        if ctx.command.endswith("MAP")
        else ctx.deps.map_manager.get_all_connected_user_ids()
    )
    for user in users:
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        if sender:
            if midi:
                await sender.send_play_midi(number)
            else:
                await sender.send_play_wave(number, x, y)
    await ctx.tell(f"Reproducción enviada a {len(users)} jugador(es).")


async def weather(ctx: ChatContext) -> None:
    """Alterna lluvia o noche persistidas y publicadas por el canal climático.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if ctx.deps.world_state is None:
        message = "El clima no está disponible."
        raise ChatCommandError(message)
    position = await ctx.position()
    service = ctx.deps.world_state.weather
    if not (await service.snapshot(ctx.user))["outdoor"]:
        message = "El mapa actual es un interior."
        raise ChatCommandError(message)
    key = f"world:weather:{position['map']}"
    field = "raining" if ctx.command == "/LLUVIA" else "night"

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        active = state.get(field) != "1"
        updates = {field: "1" if active else "0"}
        if field == "raining":
            updates["intensity"] = "70" if active else "0"
        return Decision({"applied": True, "active": active}, {key: updates})

    result = await audited(
        ctx, (Resource(key, "hash"),), {"weather": field, "map": position["map"]}, decide
    )
    await ctx.tell(f"{ctx.command}: {'activado' if result['active'] else 'desactivado'}.")


async def talk_as(ctx: ChatContext) -> None:
    """Hace hablar a la instancia seleccionada sin atribuir el mensaje al GM.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    npc = await ctx.npc()
    if not ctx.arguments or len(ctx.arguments) > MAX_NPC_MESSAGE_LENGTH:
        message = "Uso: /TALKAS mensaje (hasta 400 caracteres)"
        raise ChatCommandError(message)
    await audited(
        ctx, (), {"npc": npc.instance_id}, lambda _snapshot: Decision({"applied": True}, {})
    )
    for sender in ctx.deps.map_manager.get_all_message_senders_in_map(npc.map_id):
        await deliver_chat(
            sender,
            "public",
            npc.char_index,
            npc.name,
            ctx.arguments,
            legacy=f"{npc.name}: {ctx.arguments}",
            context="npc",
        )


async def chat_color(ctx: ChatContext) -> None:
    """Guarda RGB para el chat estructurado y una fuente de respaldo para consola.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.replace(",", " ").split() if ctx.arguments else ["0", "255", "0"]
    if len(parts) != RGB_COMPONENTS:
        message = "Uso: /CHATCOLOR rojo verde azul (0 a 255)"
        raise ChatCommandError(message)
    rgb = [integer(value, 0, 255) for value in parts]
    await fields(ctx, ctx.key, {"chat_rgb": ",".join(map(str, rgb))})
    await ctx.tell("Color del chat actualizado.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(("/FORCEMIDI", "/FORCEWAV", "/FORCEMIDIMAP", "/FORCEWAVMAP"), media),
    "/LLUVIA": weather,
    "/NOCHE": weather,
    "/TALKAS": talk_as,
    "/CHATCOLOR": chat_color,
}
