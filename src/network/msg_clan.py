"""Construcción de mensajes de clanes."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.models.clan import Clan


def build_clan_details_response(clan: Clan) -> bytes:
    """Construye el paquete CLAN_DETAILS del protocolo AO estándar.

    Basado en Protocol.WriteGuildDetails del servidor VB6.

    Args:
        clan: Objeto Clan con los datos del clan.

    Returns:
        Paquete de bytes con el formato: PacketID (80) + datos del clan.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CLAN_DETAILS)

    # GuildName (ASCII string con longitud int16)
    packet.add_unicode_string(clan.name)

    # Founder (nombre del fundador - por ahora usar leader)
    founder_name = clan.leader_username or ""
    packet.add_unicode_string(founder_name)

    # FoundationDate (fecha de fundación)
    foundation_date = datetime.fromtimestamp(clan.created_at, tz=UTC).strftime("%d/%m/%Y")
    packet.add_unicode_string(foundation_date)

    # Leader (nombre del líder actual)
    leader_name = clan.leader_username or ""
    packet.add_unicode_string(leader_name)

    # URL (sitio web del clan)
    website = clan.website or ""
    packet.add_unicode_string(website)

    # MemberCount (cantidad de miembros)
    packet.add_int32(clan.member_count)

    # ElectionsOpen (si hay elecciones abiertas - siempre False por ahora)
    elections_open = False
    packet.add_byte(1 if elections_open else 0)

    # Alignment (alineación del clan - "NEUTRO" por defecto)
    alignment = "NEUTRO"
    packet.add_unicode_string(alignment)

    # EnemiesCount (cantidad de enemigos)
    enemies_count = len(clan.wars)
    packet.add_int32(enemies_count)

    # AlliesCount (cantidad de aliados)
    allies_count = len(clan.alliances)
    packet.add_int32(allies_count)

    # AntifactionPoints (puntos de antifacción - "0/5" por defecto)
    antifaction_points = "0/5"
    packet.add_unicode_string(antifaction_points)

    # Codex (códices del clan - string vacío por ahora)
    codex = ""
    packet.add_unicode_string(codex)

    # GuildDesc (descripción del clan)
    description = clan.description or ""
    packet.add_unicode_string(description)

    return packet.to_bytes()
