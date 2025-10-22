"""Constantes y utilidades para sonidos del juego."""

from enum import IntEnum


class SoundID(IntEnum):
    """IDs de sonidos WAV del cliente Argentum Online.

    Estos IDs corresponden a los archivos de sonido en el cliente.
    Los valores están basados en el cliente original de VB6.
    """

    # Sonidos de sistema
    LOGIN = 3  # Sonido al entrar al juego
    LOGOUT = 4  # Sonido al salir del juego
    CLICK = 5  # Click en UI

    # Sonidos de combate
    SWORD_HIT = 10  # Golpe con espada
    ARROW_HIT = 11  # Flecha impactando
    MISS = 12  # Ataque fallido

    # Sonidos de magia
    SPELL_CAST = 20  # Lanzar hechizo
    HEAL = 21  # Curación
    FIREBALL = 22  # Bola de fuego

    # Sonidos de items
    POTION_DRINK = 30  # Beber poción
    GOLD_PICKUP = 31  # Recoger oro
    ITEM_PICKUP = 32  # Recoger item
    ITEM_DROP = 33  # Soltar item

    # Sonidos de NPCs/Criaturas
    GOBLIN_ATTACK = 40  # Ataque de goblin
    DRAGON_ROAR = 41  # Rugido de dragón

    # Sonidos ambientales
    DOOR_OPEN = 50  # Abrir puerta
    DOOR_CLOSE = 51  # Cerrar puerta
    FOOTSTEP = 52  # Paso

    # Sonidos de notificación
    LEVEL_UP = 60  # Subir de nivel
    QUEST_COMPLETE = 61  # Misión completada
    ERROR = 62  # Error/acción inválida

    # TODO: Completar con más IDs según los archivos WAV del cliente
    # Estos valores son aproximados y deben verificarse con el cliente real


class MusicID(IntEnum):
    """IDs de música MIDI del cliente Argentum Online.

    Estos IDs corresponden a los archivos MIDI en el cliente.
    """

    MAIN_THEME = 1  # Tema principal
    BATTLE = 2  # Música de batalla
    TOWN = 3  # Música de ciudad
    DUNGEON = 4  # Música de mazmorra

    # TODO: Completar con más IDs según los archivos MIDI del cliente
