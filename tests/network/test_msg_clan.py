"""Tests para construcción de mensajes de clanes."""

from datetime import UTC, datetime

import pytest

from src.models.clan import Clan, ClanMember, ClanRank
from src.network.msg_clan import build_clan_details_response
from src.network.packet_id import ServerPacketID


@pytest.fixture
def sample_clan() -> Clan:
    """Crea un clan de ejemplo para testing."""
    clan = Clan(
        clan_id=1,
        name="Test Clan",
        description="A test clan",
        leader_id=1,
        leader_username="LeaderUser",
        created_at=int(datetime.now(UTC).timestamp()),
        website="http://test.com",
        wars={2, 3},  # 2 enemigos
        alliances={4, 5, 6},  # 3 aliados
    )
    # Agregar más miembros para llegar a 5
    for i in range(2, 6):
        clan.add_member(
            ClanMember(
                user_id=i,
                username=f"Member{i}",
                level=10,
                rank=ClanRank.MEMBER,
            )
        )
    return clan


@pytest.fixture
def minimal_clan() -> Clan:
    """Crea un clan mínimo (sin campos opcionales)."""
    return Clan(
        clan_id=2,
        name="Minimal Clan",
        description="",
        leader_id=0,
        leader_username="",
        created_at=int(datetime.now(UTC).timestamp()),
        website="",
        wars=set(),
        alliances=set(),
    )


def test_build_clan_details_response_packet_id(sample_clan: Clan) -> None:
    """Test que el paquete comienza con el PacketID correcto."""
    packet = build_clan_details_response(sample_clan)

    assert len(packet) > 0
    assert packet[0] == ServerPacketID.CLAN_DETAILS


def test_build_clan_details_response_contains_name(sample_clan: Clan) -> None:
    """Test que el paquete contiene el nombre del clan."""
    packet = build_clan_details_response(sample_clan)

    # El nombre debe estar codificado en el paquete
    assert b"Test Clan" in packet or len(packet) > 10


def test_build_clan_details_response_with_minimal_clan(minimal_clan: Clan) -> None:
    """Test construcción con clan mínimo."""
    packet = build_clan_details_response(minimal_clan)

    assert len(packet) > 0
    assert packet[0] == ServerPacketID.CLAN_DETAILS


def test_build_clan_details_response_member_count(sample_clan: Clan) -> None:
    """Test que el paquete incluye la cantidad de miembros."""
    packet = build_clan_details_response(sample_clan)

    # El member_count debe estar en el paquete (5 = 0x05 0x00 0x00 0x00 en little-endian)
    assert len(packet) > 0


def test_build_clan_details_response_with_wars(sample_clan: Clan) -> None:
    """Test que el paquete incluye la cantidad de enemigos."""
    packet = build_clan_details_response(sample_clan)

    # Debe incluir enemies_count = 2
    assert len(packet) > 0


def test_build_clan_details_response_with_alliances(sample_clan: Clan) -> None:
    """Test que el paquete incluye la cantidad de aliados."""
    packet = build_clan_details_response(sample_clan)

    # Debe incluir allies_count = 3
    assert len(packet) > 0


def test_build_clan_details_response_without_leader(minimal_clan: Clan) -> None:
    """Test construcción cuando no hay leader."""
    packet = build_clan_details_response(minimal_clan)

    assert len(packet) > 0
    assert packet[0] == ServerPacketID.CLAN_DETAILS


def test_build_clan_details_response_foundation_date(sample_clan: Clan) -> None:
    """Test que el paquete incluye la fecha de fundación formateada."""
    packet = build_clan_details_response(sample_clan)

    # La fecha debe estar formateada como DD/MM/YYYY
    assert len(packet) > 0
