"""Adaptadores de texto hacia los handlers nativos ya implementados."""

import json
import time
from typing import TYPE_CHECKING

from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.commands.bank_extract_gold_command import BankExtractGoldCommand
from src.commands.information_command import InformationCommand
from src.commands.meditate_command import MeditateCommand
from src.commands.motd_command import MotdCommand
from src.commands.online_command import OnlineCommand
from src.commands.party_accept_command import PartyAcceptCommand
from src.commands.party_create_command import PartyCreateCommand
from src.commands.party_kick_command import PartyKickCommand
from src.commands.party_leave_command import PartyLeaveCommand
from src.commands.party_message_command import PartyMessageCommand
from src.commands.party_set_leader_command import PartySetLeaderCommand
from src.commands.quit_command import QuitCommand
from src.commands.request_clan_details_command import RequestClanDetailsCommand
from src.commands.request_stats_command import RequestStatsCommand
from src.commands.uptime_command import UptimeCommand
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer

if TYPE_CHECKING:
    from src.commands.base import Command


async def native(ctx: ChatContext) -> None:
    """Ejecuta el mismo handler tanto desde paquetes nativos como desde chat.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    from src.tasks.handler_registry import HandlerRegistry  # ruff: ignore[import-outside-top-level] - evita el ciclo del registry con TalkHandler.

    command: Command
    no_args = {
        "/ONLINE": ("online", OnlineCommand(ctx.user)),
        "/SALIR": (
            "quit",
            QuitCommand(ctx.user, ctx.deps.map_manager.get_player_username(ctx.user) or ""),
        ),
        "/MEDITAR": ("meditate", MeditateCommand(ctx.user)),
        "/EST": ("request_stats", RequestStatsCommand(ctx.user)),
        "/MOTD": ("motd", MotdCommand()),
        "/UPTIME": ("uptime", UptimeCommand()),
        "/SERVIDOR": ("information", InformationCommand()),
        "/SALIRPARTY": ("party_leave", PartyLeaveCommand(ctx.user)),
        "/CREARPARTY": ("party_create", PartyCreateCommand(ctx.user)),
        "/DETALLESCLAN": ("request_clan_details", RequestClanDetailsCommand()),
    }
    if ctx.command in no_args:
        handler, command = no_args[ctx.command]
    elif ctx.command in {"/DEPOSITAR", "/RETIRAR"}:
        amount = integer(ctx.arguments, 1, 999_999_999)
        handler, command = (
            ("bank_deposit_gold", BankDepositGoldCommand(ctx.user, amount))
            if ctx.command == "/DEPOSITAR"
            else ("bank_extract_gold", BankExtractGoldCommand(ctx.user, amount))
        )
    elif ctx.command == "/PMSG":
        handler, command = "party_message", PartyMessageCommand(ctx.user, ctx.arguments)
    elif ctx.command == "/PARTY":
        await party_join(ctx)
        return
    elif (
        ctx.command == "/ACCEPTPARTY"
        and (party := await ctx.deps.party_service.get_party_info(ctx.user)) is not None
        and party.is_leader(ctx.user)
    ):
        applicant = await ctx.account(ctx.arguments)
        user = int(applicant["user_id"])
        raw = await ctx.redis.hget(f"party:{party.party_id}:requests", str(user))
        request = json.loads(raw or "{}")
        if (
            int(request.get("leader", 0)) != ctx.user
            or float(request.get("at", 0)) < time.time() - 300
        ):
            message = "Ese jugador no tiene una solicitud vigente para tu party."
            raise ChatCommandError(message)
        error = await ctx.deps.party_service.invite_to_party(ctx.user, applicant["username"])
        if not await ctx.deps.party_service.get_user_invitations(user):
            await ctx.tell(error)
            return
        await ctx.tell(await ctx.deps.party_service.accept_invitation(user, party.party_id))
        return
    elif ctx.command in {"/ECHARPARTY", "/KICK", "/PARTYLIDER", "/ACCEPTPARTY"}:
        if not ctx.arguments or len(ctx.arguments.split()) != 1:
            message = f"Uso: {ctx.command} nombre"
            raise ChatCommandError(message)
        if ctx.command in {"/ECHARPARTY", "/KICK"}:
            handler, command = "party_kick", PartyKickCommand(ctx.user, ctx.arguments)
        elif ctx.command == "/PARTYLIDER":
            handler, command = "party_set_leader", PartySetLeaderCommand(ctx.user, ctx.arguments)
        else:
            handler, command = "party_accept", PartyAcceptCommand(ctx.user, ctx.arguments)
    elif ctx.command == "/PING":
        await ctx.sender.send_pong()
        return
    else:
        message = "Abre esta función desde la interfaz del cliente."
        raise ChatCommandError(message)
    result = (
        await HandlerRegistry(ctx.deps)
        .get(handler, ctx.sender, {"user_id": ctx.user})
        .handle(command)
    )
    if not result.success and result.error_message:
        await ctx.tell(result.error_message)


async def party_join(ctx: ChatContext) -> None:
    """Conserva invitaciones por nombre y completa la solicitud clásica por objetivo.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    if ctx.arguments:
        await ctx.tell(await ctx.deps.party_service.invite_to_party(ctx.user, ctx.arguments))
        return
    leader = await ctx.selected_user()
    party = await ctx.deps.party_service.get_party_info(leader)
    if party is None or not party.is_leader(leader):
        message = "Selecciona al líder de una party."
        raise ChatCommandError(message)
    sender = ctx.deps.map_manager.get_player_message_sender(leader)
    name = ctx.deps.map_manager.get_player_username(ctx.user) or str(ctx.user)
    await ctx.redis.hset(
        f"party:{party.party_id}:requests",
        str(ctx.user),
        json.dumps({"name": name, "leader": leader, "at": time.time()}),
    )
    if sender:
        await sender.send_console_msg(
            f"{name} solicita entrar en tu party. Usa /PARTY {name} para invitarlo."
        )
    await ctx.tell("Solicitud enviada al líder de la party.")


NATIVE_NAMES = frozenset(
    {
        "/ONLINE",
        "/SALIR",
        "/MEDITAR",
        "/EST",
        "/MOTD",
        "/UPTIME",
        "/SERVIDOR",
        "/SALIRPARTY",
        "/CREARPARTY",
        "/PARTY",
        "/PMSG",
        "/DEPOSITAR",
        "/RETIRAR",
        "/ECHARPARTY",
        "/KICK",
        "/PARTYLIDER",
        "/ACCEPTPARTY",
        "/PING",
        "/DETALLESCLAN",
    }
)
