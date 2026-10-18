"""Petición real de detalles: repositorio, permiso, builder y siguiente paquete alineado."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.ping_handler import PingCommandHandler
from src.command_handlers.request_clan_details_handler import RequestClanDetailsCommandHandler
from src.messaging.message_sender import MessageSender
from src.models.clan import Clan, ClanMember
from src.network.client_connection import ClientConnection
from src.network.msg_clan import build_clan_details_response
from src.network.packet_framer import PacketFramer, packet_length
from src.repositories.clan_repository import ClanRepository
from src.tasks.clan.task_request_clan_details import TaskRequestClanDetails
from src.tasks.task_ping import TaskPing


@pytest.mark.asyncio
@pytest.mark.parametrize("member", [True, False])
async def test_clan_request_response_and_following_ping(redis_client, member):
    """Un índice de clan sin membresía real no filtra los datos privados."""
    repository = ClanRepository(redis_client)
    clan = Clan(
        clan_id=1,
        name="Peña",
        description="Árboles y aventuras",
        leader_id=1,
        leader_username="Líder",
        members={1: ClanMember(1, "Líder", 25)},
    )
    await repository.save_clan(clan)
    user_id = 1 if member else 3
    if not member:
        await redis_client.set(repository.USER_CLAN_KEY.format(user_id=user_id), "1")
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 1234)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    connection = ClientConnection(MagicMock(), writer)
    connection.mark_authenticated()
    sender = MessageSender(connection)
    handler = RequestClanDetailsCommandHandler(SimpleNamespace(clan_repo=repository), sender, 0)
    framer = PacketFramer()
    framer.feed(bytes([69, 119]))
    try:
        await TaskRequestClanDetails(
            framer.next_packet(), sender, handler, {"user_id": user_id}
        ).execute()
        await TaskPing(framer.next_packet(), sender, PingCommandHandler(sender)).execute()
        await connection.flush()
        pending = b"".join(call.args[0] for call in writer.write.call_args_list)
        packets = []
        while pending:
            length = packet_length(pending, "server")
            assert length is not None
            packets.append(pending[:length])
            pending = pending[length:]
        assert packets[0][0] == 80
        assert packets[-1] == bytes([88])
        if member:
            assert packets[0] == build_clan_details_response(clan)
        else:
            assert packets[0] == build_clan_details_response(Clan(0, "", created_at=0))
            assert "Peña".encode("latin-1") not in b"".join(packets)
    finally:
        connection.close()
        await connection.wait_closed()
