"""Envío de mensajes específicos al cliente."""

import logging
from typing import TYPE_CHECKING

from src.messaging.senders.message_audio_sender import AudioMessageSender
from src.messaging.senders.message_character_sender import CharacterMessageSender
from src.messaging.senders.message_combat_sender import CombatMessageSender
from src.messaging.senders.message_console_sender import ConsoleMessageSender
from src.messaging.senders.message_inventory_sender import InventoryMessageSender
from src.messaging.senders.message_map_sender import MapMessageSender
from src.messaging.senders.message_npc_sender import NPCMessageSender
from src.messaging.senders.message_player_stats_sender import PlayerStatsMessageSender
from src.messaging.senders.message_session_sender import SessionMessageSender
from src.messaging.senders.message_visual_effects_sender import VisualEffectsMessageSender
from src.messaging.senders.message_work_sender import WorkMessageSender
from src.network.msg_user_commerce import (
    build_user_commerce_end_response,
    build_user_commerce_init_response,
)
from src.network.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.models.body_part import BodyPart
    from src.network.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class MessageSender:
    """Encapsula la lógica de envío de mensajes específicos del juego."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el enviador de mensajes.

        Args:
            connection: Conexión del cliente para enviar mensajes.
        """
        self.connection = connection
        # Componentes especializados
        self.audio = AudioMessageSender(connection)
        self.character = CharacterMessageSender(connection)
        self.combat = CombatMessageSender(connection)
        self.console = ConsoleMessageSender(connection)
        self.inventory = InventoryMessageSender(connection)
        self.map = MapMessageSender(connection)
        self.npc = NPCMessageSender(connection)
        self.player_stats = PlayerStatsMessageSender(connection)
        self.session = SessionMessageSender(connection)
        self.visual_effects = VisualEffectsMessageSender(connection)
        self.work = WorkMessageSender(connection)

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
        await self.session.send_dice_roll(strength, agility, intelligence, charisma, constitution)

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
        await self.session.send_attributes(strength, agility, intelligence, charisma, constitution)

    async def send_logged(self, user_class: int) -> None:
        """Envía paquete Logged del protocolo AO estándar.

        Args:
            user_class: Clase del personaje (1 byte).
        """
        await self.session.send_logged(user_class)

    async def send_change_map(self, map_number: int, version: int = 0) -> None:
        """Envía paquete ChangeMap del protocolo AO estándar.

        Args:
            map_number: Número del mapa (int16).
            version: Versión del mapa (int16), por defecto 0.
        """
        await self.map.send_change_map(map_number, version)

    async def send_pos_update(self, x: int, y: int) -> None:
        """Envía paquete PosUpdate del protocolo AO estándar.

        Args:
            x: Posición X del personaje (0-255).
            y: Posición Y del personaje (0-255).
        """
        await self.map.send_pos_update(x, y)

    async def send_user_char_index_in_server(self, char_index: int) -> None:
        """Envía paquete UserCharIndexInServer del protocolo AO estándar.

        Args:
            char_index: Índice del personaje del jugador en el servidor (int16).
        """
        await self.session.send_user_char_index_in_server(char_index)

    async def send_error_msg(self, error_message: str) -> None:
        """Envía paquete ErrorMsg del protocolo AO estándar.

        Args:
            error_message: Mensaje de error a enviar.
        """
        await self.console.send_error_msg(error_message)

    async def send_update_hp(self, hp: int) -> None:
        """Envía paquete UpdateHP del protocolo AO estándar.

        Args:
            hp: Puntos de vida actuales (int16).
        """
        await self.player_stats.send_update_hp(hp)

    async def send_update_mana(self, mana: int) -> None:
        """Envía paquete UpdateMana del protocolo AO estándar.

        Args:
            mana: Puntos de mana actuales (int16).
        """
        await self.player_stats.send_update_mana(mana)

    async def send_update_sta(self, stamina: int) -> None:
        """Envía paquete UpdateSta del protocolo AO estándar.

        Args:
            stamina: Puntos de stamina actuales (int16).
        """
        await self.player_stats.send_update_sta(stamina)

    async def send_update_strength_and_dexterity(self, strength: int, dexterity: int) -> None:
        """Envía paquete UpdateStrengthAndDexterity del protocolo AO estándar."""
        await self.player_stats.send_update_strength_and_dexterity(strength, dexterity)

    async def send_update_strength(self, strength: int) -> None:
        """Envía paquete UpdateStrength del protocolo AO estándar."""
        await self.player_stats.send_update_strength(strength)

    async def send_update_dexterity(self, dexterity: int) -> None:
        """Envía paquete UpdateDexterity del protocolo AO estándar."""
        await self.player_stats.send_update_dexterity(dexterity)

    async def send_update_exp(self, experience: int) -> None:
        """Envía paquete UpdateExp del protocolo AO estándar.

        Args:
            experience: Puntos de experiencia actuales (int32).
        """
        await self.player_stats.send_update_exp(experience)

    async def send_update_gold(self, gold: int) -> None:
        """Envía mensaje de consola informando sobre el oro ganado.

        Args:
            gold: Cantidad de oro ganado.
        """
        # Por ahora solo enviamos un mensaje de consola
        # TODO: Implementar packet específico de oro o enviar UPDATE_USER_STATS completo
        await self.send_console_msg(f"Oro: {gold}")
        logger.info("[%s] Oro actualizado a %d", self.connection.address, gold)

    async def send_update_bank_gold(self, bank_gold: int) -> None:
        """Envía actualización de oro del banco al cliente.

        Args:
            bank_gold: Cantidad de oro en el banco.
        """
        await self.player_stats.send_update_bank_gold(bank_gold)

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
        await self.player_stats.send_update_hunger_and_thirst(
            max_water, min_water, max_hunger, min_hunger
        )

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
        await self.player_stats.send_update_user_stats(
            max_hp, min_hp, max_mana, min_mana, max_sta, min_sta, gold, level, elu, experience
        )

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
        await self.character.send_character_create(
            char_index,
            body,
            head,
            heading,
            x,
            y,
            weapon,
            shield,
            helmet,
            fx,
            loops,
            name,
            nick_color,
            privileges,
        )

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
        await self.character.send_character_change(
            char_index, body, head, heading, weapon, shield, helmet, fx, loops
        )

    async def send_character_remove(self, char_index: int) -> None:
        """Envía paquete CharacterRemove del protocolo AO estándar.

        Args:
            char_index: Índice del personaje a remover (int16).
        """
        await self.character.send_character_remove(char_index)

    async def send_console_msg(self, message: str, font_color: int = 7) -> None:
        """Envía paquete ConsoleMsg del protocolo AO estándar.

        Args:
            message: Mensaje a enviar.
            font_color: Color de la fuente (0-15). Por defecto 7 (gris claro).
        """
        await self.console.send_console_msg(message, font_color)

    async def send_multiline_console_msg(self, message: str, font_color: int = 7) -> None:
        r"""Envía un mensaje multilínea dividido por saltos de línea.

        Args:
            message: Mensaje multilínea a enviar.
            font_color: Color de la fuente (0-15). Por defecto 7 (gris claro).
        """
        await self.console.send_multiline_console_msg(message, font_color)

    async def send_commerce_end(self) -> None:
        """Envía paquete CommerceEnd para cerrar la ventana de comercio."""
        await self.inventory.send_commerce_end()

    async def send_commerce_init(
        self,
        npc_id: int,
        items: list[tuple[int, int, str, int, int, int, int, int, int, int, int]],
    ) -> None:
        """Envía paquete COMMERCE_INIT para abrir ventana de comercio con inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            items: Lista de tuplas con formato:
                (slot, item_id, name, quantity, price, grh_index, obj_type,
                 max_hit, min_hit, max_def, min_def)
        """
        await self.inventory.send_commerce_init(npc_id, items)

    async def send_commerce_init_empty(self) -> None:
        """Envía paquete COMMERCE_INIT vacío (solo abre la ventana).

        El cliente Godot espera que los items se envíen previamente
        con ChangeNPCInventorySlot.
        """
        await self.inventory.send_commerce_init_empty()

    async def send_change_npc_inventory_slot(
        self,
        slot: int,
        name: str,
        amount: int,
        sale_price: float,
        grh_id: int,
        item_id: int,
        item_type: int,
        max_hit: int,
        min_hit: int,
        max_def: int,
        min_def: int,
    ) -> None:
        """Envía paquete ChangeNPCInventorySlot para actualizar un slot del inventario del mercader.

        Args:
            slot: Número de slot (1-20).
            name: Nombre del item.
            amount: Cantidad.
            sale_price: Precio de venta (float).
            grh_id: ID gráfico.
            item_id: ID del item.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
        """
        await self.inventory.send_change_npc_inventory_slot(
            slot,
            name,
            amount,
            sale_price,
            grh_id,
            item_id,
            item_type,
            max_hit,
            min_hit,
            max_def,
            min_def,
        )

    async def send_change_bank_slot(
        self,
        slot: int,
        item_id: int,
        name: str,
        amount: int,
        grh_id: int,
        item_type: int,
        max_hit: int,
        min_hit: int,
        max_def: int,
        min_def: int,
    ) -> None:
        """Envía paquete ChangeBankSlot para actualizar un slot de la bóveda bancaria.

        Args:
            slot: Número de slot (1-20).
            item_id: ID del item.
            name: Nombre del item.
            amount: Cantidad.
            grh_id: ID gráfico.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
        """
        await self.inventory.send_change_bank_slot(
            slot, item_id, name, amount, grh_id, item_type, max_hit, min_hit, max_def, min_def
        )

    async def send_bank_init_empty(self) -> None:
        """Envía paquete BANK_INIT vacío (solo abre la ventana).

        El cliente Godot espera que los items se envíen previamente
        con ChangeBankSlot.
        """
        await self.inventory.send_bank_init_empty()

    async def send_bank_end(self) -> None:
        """Envía packet BANK_END para cerrar la ventana de banco."""
        await self.inventory.send_bank_end()

    async def send_play_midi(self, midi_id: int) -> None:
        """Envía paquete PlayMIDI para reproducir música MIDI en el cliente.

        Args:
            midi_id: ID de la música MIDI a reproducir (byte). Usar MusicID para constantes.
        """
        await self.audio.send_play_midi(midi_id)

    async def send_play_wave(self, wave_id: int, x: int = 0, y: int = 0) -> None:
        """Envía paquete PlayWave para reproducir un sonido en el cliente.

        Args:
            wave_id: ID del sonido a reproducir (byte). Usar SoundID para constantes.
            x: Posición X del sonido (byte), 0 para sonido global.
            y: Posición Y del sonido (byte), 0 para sonido global.
        """
        await self.audio.send_play_wave(wave_id, x, y)

    async def send_create_fx(self, char_index: int, fx: int, loops: int) -> None:
        """Envía paquete CreateFX para mostrar un efecto visual en el cliente.

        Args:
            char_index: ID del personaje/objeto que genera el efecto.
            fx: ID del efecto visual.
            loops: Número de loops. -1 = infinito, 0 = una vez, >0 = número específico.
        """
        await self.visual_effects.send_create_fx(char_index, fx, loops)

    # Métodos de conveniencia para sonidos comunes
    async def play_sound_login(self) -> None:
        """Reproduce el sonido de login."""
        await self.audio.play_sound_login()

    async def play_sound_click(self) -> None:
        """Reproduce el sonido de click."""
        await self.audio.play_sound_click()

    async def play_sound_level_up(self) -> None:
        """Reproduce el sonido de subir de nivel."""
        await self.audio.play_sound_level_up()

    async def play_sound_error(self) -> None:
        """Reproduce el sonido de error."""
        await self.audio.play_sound_error()

    async def play_sound_gold_pickup(self) -> None:
        """Reproduce el sonido de recoger oro."""
        await self.audio.play_sound_gold_pickup()

    async def play_sound_item_pickup(self) -> None:
        """Reproduce el sonido de recoger item."""
        await self.audio.play_sound_item_pickup()

    # Métodos de conveniencia para música MIDI
    async def play_music_main_theme(self) -> None:
        """Reproduce el tema principal."""
        await self.audio.play_music_main_theme()

    async def play_music_battle(self) -> None:
        """Reproduce música de batalla."""
        await self.audio.play_music_battle()

    async def play_music_town(self) -> None:
        """Reproduce música de ciudad."""
        await self.audio.play_music_town()

    async def play_music_dungeon(self) -> None:
        """Reproduce música de mazmorra."""
        await self.audio.play_music_dungeon()

    # Métodos de conveniencia para efectos comunes
    async def play_effect_spawn(self, char_index: int) -> None:
        """Muestra efecto de spawn/aparición en un personaje."""
        await self.visual_effects.play_effect_spawn(char_index)

    async def play_effect_heal(self, char_index: int) -> None:
        """Muestra efecto de curación en un personaje."""
        await self.visual_effects.play_effect_heal(char_index)

    async def play_effect_meditation(self, char_index: int) -> None:
        """Muestra efecto de meditación en un personaje."""
        await self.visual_effects.play_effect_meditation(char_index)

    async def play_effect_explosion(self, char_index: int) -> None:
        """Muestra efecto de explosión."""
        await self.visual_effects.play_effect_explosion(char_index)

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
        await self.inventory.send_change_inventory_slot(
            slot,
            item_id,
            name,
            amount,
            equipped,
            grh_id,
            item_type,
            max_hit,
            min_hit,
            max_def,
            min_def,
            sale_price,
        )

    async def send_meditate_toggle(self) -> None:
        """Envía paquete MEDITATE_TOGGLE para confirmar meditación."""
        await self.inventory.send_meditate_toggle()

    async def send_navigate_toggle(self) -> None:
        """Envía paquete NAVIGATE_TOGGLE para alternar modo navegación."""
        response = bytes([ServerPacketID.NAVIGATE_TOGGLE])
        logger.debug("[%s] Enviando NAVIGATE_TOGGLE", self.connection.address)
        await self.connection.send(response)

    async def send_pong(self) -> None:
        """Envía paquete PONG en respuesta a un PING."""
        await self.session.send_pong()

    async def send_show_party_form(self) -> None:
        """Envía paquete SHOW_PARTY_FORM para habilitar el botón de party en el cliente.

        Este packet habilita la funcionalidad de parties en la UI del cliente.
        Debe enviarse durante el login para que el botón "GRUPO" esté disponible.
        """
        await self.session.send_show_party_form()

    async def send_user_commerce_init(self, partner_username: str) -> None:
        """Envía USER_COMMERCE_INIT con el nombre del otro jugador."""
        response = build_user_commerce_init_response(partner_username)
        logger.info(
            "[%s] Enviando USER_COMMERCE_INIT (partner=%s)",
            self.connection.address,
            partner_username,
        )
        await self.connection.send(response)

    async def send_user_commerce_end(self) -> None:
        """Envía USER_COMMERCE_END para cerrar la ventana de comercio entre jugadores."""
        response = build_user_commerce_end_response()
        logger.info("[%s] Enviando USER_COMMERCE_END", self.connection.address)
        await self.connection.send(response)

    async def send_work_request_target(self, skill_type: int) -> None:
        """Envía paquete WORK_REQUEST_TARGET para cambiar cursor al modo de trabajo.

        Args:
            skill_type: Tipo de habilidad (1=Talar, 2=Minería, 3=Pesca).
        """
        await self.work.send_work_request_target(skill_type)

    async def send_update_skills(
        self,
        magic: int,
        robustness: int,
        agility: int,
        woodcutting: int,
        fishing: int,
        mining: int,
        blacksmithing: int,
        carpentry: int,
        survival: int,
    ) -> None:
        """Envía paquete SEND_SKILLS con todas las habilidades del jugador.

        Args:
            magic: Nivel de magia.
            robustness: Nivel de robustez.
            agility: Nivel de agilidad.
            woodcutting: Nivel de tala.
            fishing: Nivel de pesca.
            mining: Nivel de minería.
            blacksmithing: Nivel de herrería.
            carpentry: Nivel de carpintería.
            survival: Nivel de supervivencia.
        """
        await self.player_stats.send_update_skills(
            magic,
            robustness,
            agility,
            woodcutting,
            fishing,
            mining,
            blacksmithing,
            carpentry,
            survival,
        )

    async def send_create_fx_at_position(self, _x: int, _y: int, fx: int, loops: int) -> None:
        """Envía efecto visual en una posición específica del mapa.

        Args:
            _x: Coordenada X (no usado por ahora).
            _y: Coordenada Y (no usado por ahora).
            fx: ID del efecto visual.
            loops: Número de loops.
        """
        await self.visual_effects.send_create_fx_at_position(_x, _y, fx, loops)

    async def send_change_spell_slot(self, slot: int, spell_id: int, spell_name: str) -> None:
        """Envía actualización de un slot de hechizo.

        Args:
            slot: Número de slot (1-based).
            spell_id: ID del hechizo.
            spell_name: Nombre del hechizo.
        """
        await self.inventory.send_change_spell_slot(slot, spell_id, spell_name)

    async def send_character_move(self, char_index: int, x: int, y: int) -> None:
        """Envía el packet CHARACTER_MOVE para notificar movimiento de un personaje.

        Args:
            char_index: Índice del personaje que se mueve.
            x: Nueva posición X.
            y: Nueva posición Y.
        """
        await self.character.send_character_move(char_index, x, y)

    async def send_object_create(self, x: int, y: int, grh_index: int) -> None:
        """Envía el packet OBJECT_CREATE para mostrar un item en el suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
            grh_index: Índice gráfico del objeto.
        """
        await self.map.send_object_create(x, y, grh_index)

    async def send_block_position(self, x: int, y: int, blocked: bool) -> None:
        """Envía el packet BLOCK_POSITION para marcar un tile como bloqueado o no.

        Args:
            x: Posición X del tile.
            y: Posición Y del tile.
            blocked: True si está bloqueado, False si no.
        """
        await self.map.send_block_position(x, y, blocked)

    async def send_object_delete(self, x: int, y: int) -> None:
        """Envía el packet OBJECT_DELETE para remover un item del suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
        """
        await self.map.send_object_delete(x, y)

    # Métodos de combate
    async def send_npc_hit_user(self, damage: int, body_part: "BodyPart | None" = None) -> None:  # noqa: UP037
        """Envía mensaje cuando un NPC golpea al jugador.

        Args:
            damage: Cantidad de daño infligido.
            body_part: Parte del cuerpo golpeada. Si es None, se elige aleatoriamente.
        """
        await self.combat.send_npc_hit_user(damage, body_part)

    async def send_user_hit_npc(self, damage: int) -> None:
        """Envía mensaje cuando el jugador golpea a un NPC.

        Args:
            damage: Cantidad de daño infligido al NPC.
        """
        await self.combat.send_user_hit_npc(damage)
