"""Componente para enviar audio (música y sonidos) al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg_audio import build_play_midi_response, build_play_wave_response
from src.sounds import MusicID, SoundID

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class AudioMessageSender:
    """Maneja el envío de música y sonidos al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de audio.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_play_midi(self, midi_id: int) -> None:
        """Envía paquete PlayMIDI para reproducir música MIDI en el cliente.

        Args:
            midi_id: ID de la música MIDI a reproducir (byte). Usar MusicID para constantes.
        """
        response = build_play_midi_response(midi_id=midi_id)
        logger.debug("[%s] Enviando PLAY_MIDI: midi=%d", self.connection.address, midi_id)
        await self.connection.send(response)

    async def send_play_wave(self, wave_id: int, x: int = 0, y: int = 0) -> None:
        """Envía paquete PlayWave para reproducir un sonido en el cliente.

        Args:
            wave_id: ID del sonido a reproducir (byte). Usar SoundID para constantes.
            x: Posición X del sonido (byte), 0 para sonido global.
            y: Posición Y del sonido (byte), 0 para sonido global.
        """
        response = build_play_wave_response(wave_id=wave_id, x=x, y=y)
        logger.debug(
            "[%s] Enviando PLAY_WAVE: wave=%d, pos=(%d,%d)", self.connection.address, wave_id, x, y
        )
        await self.connection.send(response)

    # Métodos de conveniencia para sonidos comunes
    async def play_sound_login(self) -> None:
        """Reproduce el sonido de login."""
        await self.send_play_wave(wave_id=SoundID.LOGIN)

    async def play_sound_click(self) -> None:
        """Reproduce el sonido de click."""
        await self.send_play_wave(wave_id=SoundID.CLICK)

    async def play_sound_level_up(self) -> None:
        """Reproduce el sonido de subir de nivel."""
        await self.send_play_wave(wave_id=SoundID.LEVEL_UP)

    async def play_sound_error(self) -> None:
        """Reproduce el sonido de error."""
        await self.send_play_wave(wave_id=SoundID.ERROR)

    async def play_sound_gold_pickup(self) -> None:
        """Reproduce el sonido de recoger oro."""
        await self.send_play_wave(wave_id=SoundID.GOLD_PICKUP)

    async def play_sound_item_pickup(self) -> None:
        """Reproduce el sonido de recoger item."""
        await self.send_play_wave(wave_id=SoundID.ITEM_PICKUP)

    # Métodos de conveniencia para música MIDI
    async def play_music_main_theme(self) -> None:
        """Reproduce el tema principal."""
        await self.send_play_midi(midi_id=MusicID.MAIN_THEME)

    async def play_music_battle(self) -> None:
        """Reproduce música de batalla."""
        await self.send_play_midi(midi_id=MusicID.BATTLE)

    async def play_music_town(self) -> None:
        """Reproduce música de ciudad."""
        await self.send_play_midi(midi_id=MusicID.TOWN)

    async def play_music_dungeon(self) -> None:
        """Reproduce música de mazmorra."""
        await self.send_play_midi(midi_id=MusicID.DUNGEON)
