"""Packet builders para habilidades del jugador."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_update_skills_response(
    magic: int,
    robustness: int,
    agility: int,
    woodcutting: int,
    fishing: int,
    mining: int,
    blacksmithing: int,
    carpentry: int,
    survival: int,
) -> bytes:
    """Construye el packet SEND_SKILLS con todas las habilidades del jugador.

    Args:
        magic: Nivel de magia (int16).
        robustness: Nivel de robustez (int16).
        agility: Nivel de agilidad (int16).
        woodcutting: Nivel de tala (int16).
        fishing: Nivel de pesca (int16).
        mining: Nivel de minería (int16).
        blacksmithing: Nivel de herrería (int16).
        carpentry: Nivel de carpintería (int16).
        survival: Nivel de supervivencia (int16).

    Returns:
        Bytes del packet SEND_SKILLS (ID 71).
    """
    return (
        PacketBuilder()
        .add_byte(ServerPacketID.SEND_SKILLS)
        .add_int16(magic)  # 1. Magia
        .add_int16(robustness)  # 2. Robustez
        .add_int16(woodcutting)  # 3. Talar (Tácticas)
        .add_int16(agility)  # 4. Agilidad
        .add_int16(fishing)  # 5. Pesca
        .add_int16(mining)  # 6. Minería
        .add_int16(blacksmithing)  # 7. Herrería
        .add_int16(carpentry)  # 8. Carpintería
        .add_int16(survival)  # 9. Supervivencia
        .to_bytes()
    )
