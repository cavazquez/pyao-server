"""Envío de mensajes específicos al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import (
    build_attributes_response,
    build_change_inventory_slot_response,
    build_change_map_response,
    build_character_change_response,
    build_character_create_response,
    build_character_move_response,
    build_character_remove_response,
    build_commerce_end_response,
    build_console_msg_response,
    build_create_fx_response,
    build_dice_roll_response,
    build_error_msg_response,
    build_logged_response,
    build_object_create_response,
    build_object_delete_response,
    build_play_midi_response,
    build_play_wave_response,
    build_pos_update_response,
    build_update_exp_response,
    build_update_hp_response,
    build_update_hunger_and_thirst_response,
    build_update_mana_response,
    build_update_sta_response,
    build_update_user_stats_response,
    build_user_char_index_in_server_response,
)
from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID
from src.sounds import MusicID, SoundID
from src.visual_effects import FXLoops, VisualEffectID

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class MessageSender:  # noqa: PLR0904
    """Encapsula la lógica de envío de mensajes específicos del juego."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el enviador de mensajes.

        Args:
            connection: Conexión del cliente para enviar mensajes.
        """
        self.connection = connection

    async def send_dice_roll(
        self,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
    ) -> None:
        """Envía el resultado de una tirada de dados al cliente.

        Args:
            strength: Valor de fuerza (6-18).
            agility: Valor de agilidad (6-18).
            intelligence: Valor de inteligencia (6-18).
            charisma: Valor de carisma (6-18).
            constitution: Valor de constitución (6-18).
        """
        response = build_dice_roll_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
        logger.info(
            "[%s] Enviando DICE_ROLL: STR=%d AGI=%d INT=%d CHA=%d CON=%d",
            self.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )
        await self.connection.send(response)

    async def send_attributes(
        self,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
    ) -> None:
        """Envía los atributos del personaje al cliente usando PacketID 50.

        Args:
            strength: Valor de fuerza.
            agility: Valor de agilidad.
            intelligence: Valor de inteligencia.
            charisma: Valor de carisma.
            constitution: Valor de constitución.
        """
        response = build_attributes_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
        logger.info(
            "[%s] Enviando ATTRIBUTES: STR=%d AGI=%d INT=%d CHA=%d CON=%d",
            self.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )
        await self.connection.send(response)

    async def send_logged(self, user_class: int) -> None:
        """Envía paquete Logged del protocolo AO estándar.

        Args:
            user_class: Clase del personaje (1 byte).
        """
        response = build_logged_response(user_class=user_class)
        logger.info("[%s] Enviando LOGGED: userClass=%d", self.connection.address, user_class)
        await self.connection.send(response)

    async def send_change_map(self, map_number: int, version: int = 0) -> None:
        """Envía paquete ChangeMap del protocolo AO estándar.

        Args:
            map_number: Número del mapa (int16).
            version: Versión del mapa (int16), por defecto 0.
        """
        response = build_change_map_response(map_number=map_number, version=version)
        logger.info(
            "[%s] Enviando CHANGE_MAP: map=%d, version=%d",
            self.connection.address,
            map_number,
            version,
        )
        await self.connection.send(response)

    async def send_pos_update(self, x: int, y: int) -> None:
        """Envía paquete PosUpdate del protocolo AO estándar.

        Args:
            x: Posición X del personaje (0-255).
            y: Posición Y del personaje (0-255).
        """
        response = build_pos_update_response(x=x, y=y)
        logger.info("[%s] Enviando POS_UPDATE: x=%d, y=%d", self.connection.address, x, y)
        await self.connection.send(response)

    async def send_user_char_index_in_server(self, char_index: int) -> None:
        """Envía paquete UserCharIndexInServer del protocolo AO estándar.

        Args:
            char_index: Índice del personaje del jugador en el servidor (int16).
        """
        response = build_user_char_index_in_server_response(char_index=char_index)
        logger.info(
            "[%s] Enviando USER_CHAR_INDEX_IN_SERVER: charIndex=%d",
            self.connection.address,
            char_index,
        )
        await self.connection.send(response)

    async def send_error_msg(self, error_message: str) -> None:
        """Envía paquete ErrorMsg del protocolo AO estándar.

        Args:
            error_message: Mensaje de error.
        """
        response = build_error_msg_response(error_message=error_message)
        logger.info("[%s] Enviando ERROR_MSG: %s", self.connection.address, error_message)
        await self.connection.send(response)

    async def send_update_hp(self, hp: int) -> None:
        """Envía paquete UpdateHP del protocolo AO estándar.

        Args:
            hp: Puntos de vida actuales (int16).
        """
        response = build_update_hp_response(hp=hp)
        logger.info("[%s] Enviando UPDATE_HP: %d", self.connection.address, hp)
        await self.connection.send(response)

    async def send_update_mana(self, mana: int) -> None:
        """Envía paquete UpdateMana del protocolo AO estándar.

        Args:
            mana: Puntos de mana actuales (int16).
        """
        response = build_update_mana_response(mana=mana)
        logger.info("[%s] Enviando UPDATE_MANA: %d", self.connection.address, mana)
        await self.connection.send(response)

    async def send_update_sta(self, stamina: int) -> None:
        """Envía paquete UpdateSta del protocolo AO estándar.

        Args:
            stamina: Puntos de stamina actuales (int16).
        """
        response = build_update_sta_response(stamina=stamina)
        logger.info("[%s] Enviando UPDATE_STA: %d", self.connection.address, stamina)
        await self.connection.send(response)

    async def send_update_exp(self, experience: int) -> None:
        """Envía paquete UpdateExp del protocolo AO estándar.

        Args:
            experience: Puntos de experiencia actuales (int32).
        """
        response = build_update_exp_response(experience=experience)
        logger.info("[%s] Enviando UPDATE_EXP: %d", self.connection.address, experience)
        await self.connection.send(response)

    async def send_update_gold(self, gold: int) -> None:
        """Envía mensaje de consola informando sobre el oro ganado.

        Args:
            gold: Cantidad de oro ganado.
        """
        # Por ahora solo enviamos un mensaje de consola
        # TODO: Implementar packet específico de oro o enviar UPDATE_USER_STATS completo
        await self.send_console_msg(f"¡Has ganado {gold} monedas de oro!")
        logger.info("[%s] Jugador ganó %d de oro", self.connection.address, gold)

    async def send_update_hunger_and_thirst(
        self, max_water: int, min_water: int, max_hunger: int, min_hunger: int
    ) -> None:
        """Envía paquete UpdateHungerAndThirst del protocolo AO estándar.

        Args:
            max_water: Sed máxima (u8).
            min_water: Sed actual (u8).
            max_hunger: Hambre máxima (u8).
            min_hunger: Hambre actual (u8).
        """
        response = build_update_hunger_and_thirst_response(
            max_water=max_water,
            min_water=min_water,
            max_hunger=max_hunger,
            min_hunger=min_hunger,
        )
        logger.info(
            "[%s] Enviando UPDATE_HUNGER_AND_THIRST: water=%d/%d hunger=%d/%d",
            self.connection.address,
            min_water,
            max_water,
            min_hunger,
            max_hunger,
        )
        await self.connection.send(response)

    async def send_update_user_stats(
        self,
        max_hp: int,
        min_hp: int,
        max_mana: int,
        min_mana: int,
        max_sta: int,
        min_sta: int,
        gold: int,
        level: int,
        elu: int,
        experience: int,
    ) -> None:
        """Envía paquete UpdateUserStats del protocolo AO estándar.

        Args:
            max_hp: HP máximo (int16).
            min_hp: HP actual (int16).
            max_mana: Mana máximo (int16).
            min_mana: Mana actual (int16).
            max_sta: Stamina máxima (int16).
            min_sta: Stamina actual (int16).
            gold: Oro del jugador (int32).
            level: Nivel del jugador (byte).
            elu: Experiencia para subir de nivel (int32).
            experience: Experiencia total (int32).
        """
        response = build_update_user_stats_response(
            max_hp=max_hp,
            min_hp=min_hp,
            max_mana=max_mana,
            min_mana=min_mana,
            max_sta=max_sta,
            min_sta=min_sta,
            gold=gold,
            level=level,
            elu=elu,
            experience=experience,
        )
        logger.info(
            "[%s] Enviando UPDATE_USER_STATS: HP=%d/%d MANA=%d/%d STA=%d/%d "
            "GOLD=%d LVL=%d ELU=%d EXP=%d",
            self.connection.address,
            min_hp,
            max_hp,
            min_mana,
            max_mana,
            min_sta,
            max_sta,
            gold,
            level,
            elu,
            experience,
        )
        await self.connection.send(response)

    async def send_character_create(
        self,
        char_index: int,
        body: int,
        head: int,
        heading: int,
        x: int,
        y: int,
        weapon: int = 0,
        shield: int = 0,
        helmet: int = 0,
        fx: int = 0,
        loops: int = 0,
        name: str = "",
        nick_color: int = 0,
        privileges: int = 0,
    ) -> None:
        """Envía paquete CharacterCreate del protocolo AO estándar.

        Args:
            char_index: Índice del personaje (int16).
            body: ID del cuerpo/raza (int16).
            head: ID de la cabeza (int16).
            heading: Dirección que mira el personaje (byte).
            x: Posición X (byte).
            y: Posición Y (byte).
            weapon: ID del arma equipada (int16), por defecto 0.
            shield: ID del escudo equipado (int16), por defecto 0.
            helmet: ID del casco equipado (int16), por defecto 0.
            fx: ID del efecto visual (int16), por defecto 0.
            loops: Loops del efecto (int16), por defecto 0.
            name: Nombre del personaje (string), por defecto vacío.
            nick_color: Color del nick (byte), por defecto 0.
            privileges: Privilegios del personaje (byte), por defecto 0.
        """
        response = build_character_create_response(
            char_index=char_index,
            body=body,
            head=head,
            heading=heading,
            x=x,
            y=y,
            weapon=weapon,
            shield=shield,
            helmet=helmet,
            fx=fx,
            loops=loops,
            name=name,
            nick_color=nick_color,
            privileges=privileges,
        )
        logger.info(
            "[%s] Enviando CHARACTER_CREATE: charIndex=%d body=%d head=%d heading=%d "
            "pos=(%d,%d) name=%s",
            self.connection.address,
            char_index,
            body,
            head,
            heading,
            x,
            y,
            name,
        )
        await self.connection.send(response)

    async def send_character_change(
        self,
        char_index: int,
        body: int,
        head: int,
        heading: int,
        weapon: int = 0,
        shield: int = 0,
        helmet: int = 0,
        fx: int = 0,
        loops: int = 0,
    ) -> None:
        """Envía paquete CharacterChange del protocolo AO estándar.

        Args:
            char_index: Índice del personaje (int16).
            body: ID del cuerpo/raza (int16).
            head: ID de la cabeza (int16).
            heading: Dirección que mira el personaje (byte).
            weapon: ID del arma equipada (int16), por defecto 0.
            shield: ID del escudo equipado (int16), por defecto 0.
            helmet: ID del casco equipado (int16), por defecto 0.
            fx: ID del efecto visual (int16), por defecto 0.
            loops: Loops del efecto (int16), por defecto 0.
        """
        response = build_character_change_response(
            char_index=char_index,
            body=body,
            head=head,
            heading=heading,
            weapon=weapon,
            shield=shield,
            helmet=helmet,
            fx=fx,
            loops=loops,
        )
        logger.info(
            "[%s] Enviando CHARACTER_CHANGE: charIndex=%d heading=%d",
            self.connection.address,
            char_index,
            heading,
        )
        await self.connection.send(response)

    async def send_character_remove(self, char_index: int) -> None:
        """Envía paquete CharacterRemove del protocolo AO estándar.

        Args:
            char_index: Índice del personaje a remover (int16).
        """
        response = build_character_remove_response(char_index=char_index)
        logger.info(
            "[%s] Enviando CHARACTER_REMOVE: charIndex=%d",
            self.connection.address,
            char_index,
        )
        await self.connection.send(response)

    async def send_console_msg(self, message: str, font_color: int = 7) -> None:
        """Envía paquete ConsoleMsg del protocolo AO estándar.

        Args:
            message: Mensaje a enviar.
            font_color: Color de la fuente (byte), por defecto 7 (blanco).
        """
        response = build_console_msg_response(message=message, font_color=font_color)
        logger.debug(
            "[%s] Enviando CONSOLE_MSG: %s",
            self.connection.address,
            message[:50],  # Solo primeros 50 caracteres en el log
        )
        await self.connection.send(response)

    async def send_multiline_console_msg(self, message: str, font_color: int = 7) -> None:
        r"""Envía un mensaje multilínea dividido por saltos de línea.

        Args:
            message: Mensaje con saltos de línea (\n).
            font_color: Color de la fuente (byte), por defecto 7 (blanco).
        """
        lines = message.split("\n")
        for line in lines:
            await self.send_console_msg(line, font_color)

    async def send_commerce_end(self) -> None:
        """Envía paquete CommerceEnd para cerrar la ventana de comercio."""
        response = build_commerce_end_response()
        logger.debug("[%s] Enviando COMMERCE_END", self.connection.address)
        await self.connection.send(response)

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

    async def send_create_fx(self, char_index: int, fx: int, loops: int) -> None:
        """Envía paquete CreateFX para mostrar un efecto visual.

        Args:
            char_index: ID del personaje/objeto que genera el efecto (int16).
            fx: ID del efecto visual (int16). Usar VisualEffectID para constantes.
            loops: Número de loops (int16). Usar FXLoops para constantes.
        """
        response = build_create_fx_response(char_index=char_index, fx=fx, loops=loops)
        logger.debug(
            "[%s] Enviando CREATE_FX: charIndex=%d, fx=%d, loops=%d",
            self.connection.address,
            char_index,
            fx,
            loops,
        )
        await self.connection.send(response)

    # Métodos de conveniencia para efectos comunes
    async def play_effect_spawn(self, char_index: int) -> None:
        """Muestra efecto de spawn/aparición en un personaje."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.SPAWN_BLUE, loops=FXLoops.ONCE
        )

    async def play_effect_heal(self, char_index: int) -> None:
        """Muestra efecto de curación en un personaje."""
        await self.send_create_fx(char_index=char_index, fx=VisualEffectID.HEAL, loops=FXLoops.ONCE)

    async def play_effect_meditation(self, char_index: int) -> None:
        """Muestra efecto de meditación en un personaje."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.MEDITATION, loops=FXLoops.INFINITE
        )

    async def play_effect_explosion(self, char_index: int) -> None:
        """Muestra efecto de explosión."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.EXPLOSION, loops=FXLoops.ONCE
        )

    async def send_change_inventory_slot(
        self,
        slot: int,
        item_id: int,
        name: str,
        amount: int,
        equipped: bool,
        grh_id: int,
        item_type: int,
        max_hit: int = 0,
        min_hit: int = 0,
        max_def: int = 0,
        min_def: int = 0,
        sale_price: float = 0.0,
    ) -> None:
        """Envía actualización de un slot del inventario.

        Args:
            slot: Número de slot (1-20).
            item_id: ID del item.
            name: Nombre del item.
            amount: Cantidad.
            equipped: Si está equipado.
            grh_id: ID del gráfico.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
            sale_price: Precio de venta.
        """
        response = build_change_inventory_slot_response(
            slot=slot,
            item_id=item_id,
            name=name,
            amount=amount,
            equipped=equipped,
            grh_id=grh_id,
            item_type=item_type,
            max_hit=max_hit,
            min_hit=min_hit,
            max_def=max_def,
            min_def=min_def,
            sale_price=sale_price,
        )
        logger.debug(
            "[%s] Enviando CHANGE_INVENTORY_SLOT: slot=%d, item=%s, amount=%d",
            self.connection.address,
            slot,
            name,
            amount,
        )
        await self.connection.send(response)

    async def send_meditate_toggle(self) -> None:
        """Envía paquete MEDITATE_TOGGLE para confirmar meditación."""
        response = bytes([ServerPacketID.MEDITATE_TOGGLE])
        logger.debug("[%s] Enviando MEDITATE_TOGGLE", self.connection.address)
        await self.connection.send(response)

    async def send_create_fx_at_position(self, _x: int, _y: int, fx: int, loops: int) -> None:
        """Envía efecto visual en una posición específica del mapa.

        Args:
            _x: Coordenada X (no usado por ahora).
            _y: Coordenada Y (no usado por ahora).
            fx: ID del efecto visual.
            loops: Número de loops.
        """
        # Por ahora usamos char_index=0 para efectos en el terreno
        # TODO: Implementar CREATE_FX con coordenadas si el protocolo lo soporta
        await self.send_create_fx(char_index=0, fx=fx, loops=loops)

    async def send_change_spell_slot(self, slot: int, spell_id: int, spell_name: str) -> None:
        """Envía actualización de un slot de hechizo.

        Args:
            slot: Número de slot (1-based).
            spell_id: ID del hechizo.
            spell_name: Nombre del hechizo.
        """
        packet = PacketBuilder()
        packet.add_byte(ServerPacketID.CHANGE_SPELL_SLOT)
        packet.add_byte(slot)
        packet.add_int16(spell_id)
        packet.add_unicode_string(spell_name)
        response = packet.to_bytes()

        logger.debug(
            "[%s] Enviando CHANGE_SPELL_SLOT: slot=%d, spell_id=%d, name=%s",
            self.connection.address,
            slot,
            spell_id,
            spell_name,
        )
        await self.connection.send(response)

    async def send_character_move(self, char_index: int, x: int, y: int) -> None:
        """Envía el packet CHARACTER_MOVE para notificar movimiento de un personaje.

        Args:
            char_index: Índice del personaje que se mueve.
            x: Nueva posición X.
            y: Nueva posición Y.
        """
        response = build_character_move_response(char_index, x, y)
        await self.connection.send(response)

    async def send_object_create(self, x: int, y: int, grh_index: int) -> None:
        """Envía el packet OBJECT_CREATE para mostrar un item en el suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
            grh_index: Índice gráfico del objeto.
        """
        response = build_object_create_response(x, y, grh_index)
        logger.debug(
            "[%s] Enviando OBJECT_CREATE: pos=(%d,%d) grh=%d",
            self.connection.address,
            x,
            y,
            grh_index,
        )
        await self.connection.send(response)

    async def send_object_delete(self, x: int, y: int) -> None:
        """Envía el packet OBJECT_DELETE para remover un item del suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
        """
        response = build_object_delete_response(x, y)
        logger.debug("[%s] Enviando OBJECT_DELETE: pos=(%d,%d)", self.connection.address, x, y)
        await self.connection.send(response)
