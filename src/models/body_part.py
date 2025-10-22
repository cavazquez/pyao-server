"""Enum para partes del cuerpo en combate.

Basado en el cliente Godot y servidor VB6 original.
Usado en mensajes de daño (NPCHitUser).
"""

from enum import IntEnum


class BodyPart(IntEnum):
    """Partes del cuerpo que pueden ser golpeadas en combate."""

    HEAD = 1  # Cabeza (bCabeza)
    LEFT_LEG = 2  # Pierna izquierda (bPiernaIzquierda)
    RIGHT_LEG = 3  # Pierna derecha (bPiernaDerecha)
    RIGHT_ARM = 4  # Brazo derecho (bBrazoDerecho)
    LEFT_ARM = 5  # Brazo izquierdo (bBrazoIzquierdo)
    TORSO = 6  # Torso (bTorso)
