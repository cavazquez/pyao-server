"""Componente para enviar mensajes de efectos de estado al cliente."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from src.network.msg_status_effects import (
    build_blind_no_more_response,
    build_blind_response,
    build_dumb_no_more_response,
    build_dumb_response,
    build_paralize_ok_response,
    build_rest_ok_response,
    build_set_invisible_response,
    build_update_tag_and_status_response,
)
from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.network.client_connection import ClientConnection
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class StatusEffectsMessageSender:
    """Maneja el envío de mensajes de efectos de estado al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de efectos de estado.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection
        self._status_lock = asyncio.Lock()
        self._paralyzed = False
        self._blind = False
        self._dumb = False
        self._visibility: dict[int, bool] = {}
        self._meditating = False
        self._campfire_map = 0
        self._campfires: set[tuple[int, int]] = set()

    def record_meditation_toggle(self) -> None:
        """Registra un toggle enviado por una acción explícita del jugador."""
        self._meditating = not self._meditating

    async def sync_campfires(self, user_id: int, repository: PlayerRepository) -> None:
        """Restaura fogatas visibles y retira las que vencieron aunque cambie la conexión."""
        position = await repository.get_position(user_id)
        if position is None:
            return
        map_id = position["map"]
        if self._campfire_map != map_id:
            self._campfire_map, self._campfires = map_id, set()
        fires: set[tuple[int, int]] = set()
        async for key in repository.redis.redis.scan_iter(
            match=f"world:campfire:{map_id}:*", count=100
        ):
            data = await repository.redis.hgetall(str(key))
            if float(data.get("until", 0)) > time.time():
                fires.add((int(data["x"]), int(data["y"])))
        for x, y in fires - self._campfires:
            await self.connection.send(
                PacketBuilder()
                .add_byte(ServerPacketID.OBJECT_CREATE)
                .add_byte(x)
                .add_byte(y)
                .add_int16(1521)
                .to_bytes()
            )
        for x, y in self._campfires - fires:
            await self.connection.send(
                PacketBuilder()
                .add_byte(ServerPacketID.OBJECT_DELETE)
                .add_byte(x)
                .add_byte(y)
                .to_bytes()
            )
        self._campfires = fires

    def invalidate_character(self, char_index: int) -> None:
        """Obliga a reenviar visibilidad cuando un actor se vuelve a crear."""
        self._visibility.pop(char_index, None)

    async def sync_visibility(
        self, user_id: int, repository: PlayerRepository, maps: MapManager
    ) -> None:
        """Publica transiciones a cada observador y recupera expiraciones/reconexiones."""
        position = await repository.get_position(user_id)
        if position is None:
            return
        users = set(maps.get_players_in_map(position["map"])) | {user_id}
        self._visibility = {uid: hidden for uid, hidden in self._visibility.items() if uid in users}
        now = time.time()
        for uid in users:
            stats = await repository.redis.hgetall(RedisKeys.player_user_stats(uid))
            hidden = (
                int(stats.get("min_hp", 0)) > 0
                and max(float(stats.get("invisible_until", 0)), float(stats.get("hidden_until", 0)))
                > now
            )
            if self._visibility.get(uid) != hidden:
                await self.send_set_invisible(uid, hidden)
                self._visibility[uid] = hidden

    async def send_blind(self) -> None:
        """Envía paquete BLIND para activar efecto de ceguera."""
        response = build_blind_response()
        logger.info("[%s] Enviando BLIND", self.connection.address)
        await self.connection.send(response)
        self._blind = True

    async def send_blind_no_more(self) -> None:
        """Envía paquete BLIND_NO_MORE para desactivar efecto de ceguera."""
        response = build_blind_no_more_response()
        logger.info("[%s] Enviando BLIND_NO_MORE", self.connection.address)
        await self.connection.send(response)
        self._blind = False

    async def send_dumb(self) -> None:
        """Envía paquete DUMB para activar efecto de estupidez."""
        response = build_dumb_response()
        logger.info("[%s] Enviando DUMB", self.connection.address)
        await self.connection.send(response)
        self._dumb = True

    async def send_dumb_no_more(self) -> None:
        """Envía paquete DUMB_NO_MORE para desactivar efecto de estupidez."""
        response = build_dumb_no_more_response()
        logger.info("[%s] Enviando DUMB_NO_MORE", self.connection.address)
        await self.connection.send(response)
        self._dumb = False

    async def send_paralize_ok(self) -> None:
        """Envía paquete PARALIZE_OK para confirmar parálisis/inmovilización."""
        async with self._status_lock:
            response = build_paralize_ok_response()
            await self.connection.send(response)
            self._paralyzed = not self._paralyzed

    async def sync_status(self, user_id: int, repository: PlayerRepository) -> None:
        """Lee dentro del lock y emite sólo transiciones, incluso con publicaciones concurrentes."""
        async with self._status_lock:
            stats = await repository.redis.hgetall(RedisKeys.player_user_stats(user_id))
            alive = int(stats.get("min_hp", stats.get("hp", 0))) > 0
            now = time.time()
            paralyzed = alive and float(stats.get("immobilized_until", 0)) > now
            blind = alive and float(stats.get("blinded_until", 0)) > now
            dumb = alive and float(stats.get("dumb_until", 0)) > now
            meditating = alive and stats.get("meditating") == "1"
            if meditating != self._meditating:
                await self.connection.send(bytes([ServerPacketID.MEDITATE_TOGGLE]))
                self._meditating = meditating
            if paralyzed != self._paralyzed:
                await self.connection.send(build_paralize_ok_response())
                self._paralyzed = paralyzed
            if blind != self._blind:
                await self.connection.send(
                    build_blind_response() if blind else build_blind_no_more_response()
                )
                self._blind = blind
            if dumb != self._dumb:
                await self.connection.send(
                    build_dumb_response() if dumb else build_dumb_no_more_response()
                )
                self._dumb = dumb

    async def send_rest_ok(self) -> None:
        """Envía paquete REST_OK para confirmar descanso."""
        response = build_rest_ok_response()
        logger.info("[%s] Enviando REST_OK", self.connection.address)
        await self.connection.send(response)

    async def send_set_invisible(self, char_index: int, invisible: bool) -> None:
        """Envía paquete SET_INVISIBLE para marcar personaje como invisible/visible.

        Args:
            char_index: Índice del personaje.
            invisible: True para ocultar el personaje, False para mostrarlo.
        """
        self._visibility[char_index] = invisible
        response = build_set_invisible_response(char_index, invisible)
        logger.info(
            "[%s] Enviando SET_INVISIBLE: charIndex=%d, invisible=%s",
            self.connection.address,
            char_index,
            invisible,
        )
        await self.connection.send(response)

    async def send_update_tag_and_status(
        self, char_index: int, nick_color: int, user_tag: str
    ) -> None:
        """Envía paquete UPDATE_TAG_AND_STATUS para actualizar nick color y tag.

        Args:
            char_index: Índice del personaje.
            nick_color: Color del nick (0=Ciudadano, 1=Criminal, 2=Newbie, etc.).
            user_tag: Nombre/tag del personaje.
        """
        response = build_update_tag_and_status_response(char_index, nick_color, user_tag)
        logger.info(
            "[%s] Enviando UPDATE_TAG_AND_STATUS: charIndex=%d, nickColor=%d, tag=%s",
            self.connection.address,
            char_index,
            nick_color,
            user_tag,
        )
        await self.connection.send(response)
