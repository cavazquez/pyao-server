"""Eventos cosméticos posteriores al commit; sin inferencias ni reglas de combate."""

from collections import deque
from typing import TYPE_CHECKING

from src.network.capabilities import Capability
from src.network.packet_builder import PacketBuilder

if TYPE_CHECKING:
    from src.game.map_manager import MapManager

VISUAL_DAMAGE_PACKET = 246
PROJECTILE_PACKET = 247
MAX_EVENTS = 4096
MAX_KIND = 6
MAX_AMOUNT = 2147483647
MAX_COORD = 100


class VisualEvents:
    """Publica a observadores del mapa que negociaron la extensión correspondiente."""

    def __init__(self, maps: MapManager) -> None:
        """Mantiene una ventana acotada de recibos ya publicados."""
        self.maps = maps
        self._recent: set[str] = set()
        self._order: deque[str] = deque()

    async def _send(self, key: str, map_id: int, capability: Capability, payload: bytes) -> None:
        if key in self._recent:
            return
        self._recent.add(key)
        self._order.append(key)
        if len(self._order) > MAX_EVENTS:
            self._recent.discard(self._order.popleft())
        for user in self.maps.get_players_in_map(map_id):
            sender = self.maps.get_player_message_sender(user)
            enabled = getattr(
                getattr(getattr(sender, "connection", None), "capabilities", None), "enabled", 0
            )
            if sender and isinstance(enabled, int) and enabled & capability:
                await sender.connection.send(payload)

    async def damage(
        self, identity: str, map_id: int, actor: int, x: int, y: int, amount: int, kind: int = 0
    ) -> None:
        """Tipos: daño, curación, fallo, bloqueo, crítico, inmunidad, estado.

        Raises:
            ValueError: Si el valor o las coordenadas exceden el contrato.
        """
        if not (
            0 <= kind <= MAX_KIND
            and 0 <= amount <= MAX_AMOUNT
            and 1 <= x <= MAX_COORD
            and 1 <= y <= MAX_COORD
        ):
            msg = "Evento de daño fuera de rango"
            raise ValueError(msg)
        event = f"{identity}:{actor}:{kind}"[:64]
        p = PacketBuilder().add_byte(VISUAL_DAMAGE_PACKET).add_int16(len(event)).add_string(event)
        p.add_int16(map_id).add_int32(actor).add_byte(x).add_byte(y).add_int32(amount).add_byte(
            kind
        )
        await self._send("damage:" + event, map_id, Capability.VISUAL_DAMAGE, p.to_bytes())

    async def projectile(
        self,
        identity: str,
        map_id: int,
        source: int,
        target: int,
        sx: int,
        sy: int,
        tx: int,
        ty: int,
        kind: int,
        asset: int,
        spell_id: int = 0,
    ) -> None:
        """Tipos: 1 magia, 2 flecha. El impacto visual nunca confirma daño.

        Raises:
            ValueError: Si el tipo o las coordenadas exceden el contrato.
        """
        if kind not in {1, 2} or any(not 1 <= n <= MAX_COORD for n in (sx, sy, tx, ty)):
            msg = "Lanzamiento fuera de rango"
            raise ValueError(msg)
        event = f"{identity}:{target}"[:64]
        p = PacketBuilder().add_byte(PROJECTILE_PACKET).add_int16(len(event)).add_string(event)
        p.add_int16(map_id).add_int32(source).add_int32(target)
        for coordinate in (sx, sy, tx, ty):
            p.add_byte(coordinate)
        p.add_byte(kind).add_int16(max(0, min(32767, asset))).add_int16(spell_id)
        await self._send("projectile:" + event, map_id, Capability.PROJECTILES, p.to_bytes())
