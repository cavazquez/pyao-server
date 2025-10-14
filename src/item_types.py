"""Tipos de objetos y pociones de Argentum Online.

Extraído del archivo obj.dat del cliente VB6.
"""

from enum import IntEnum


class ObjType(IntEnum):
    """Tipos de objetos (ObjType)."""

    COMIDA = 1
    ARMAS = 2
    ARMADURAS = 3
    ARBOLES = 4
    DINERO = 5
    PUERTAS = 6
    CONTENEDORES = 7  # Bolsas y cofres
    CARTELES = 8
    LLAVES = 9
    FOROS = 10
    POCIONES = 11
    LIBROS = 12
    BEBIDA = 13
    LENA = 14
    FOGATA = 15
    ESCUDOS = 16
    CASCOS = 17
    ANILLOS = 18
    TELEPORT = 19
    MUEBLES = 20
    JOYAS = 21
    YACIMIENTO = 22
    METALES = 23
    PERGAMINOS = 24
    AURA = 25
    INSTRUMENTOS_MUSICALES = 26
    YUNQUE = 27
    FRAGUA = 28
    GEMAS = 29
    FLORES = 30
    BARCOS = 31
    FLECHAS = 32
    BOTELLAS_VACIAS = 33
    BOTELLAS_LLENAS = 34
    MANCHAS = 35


class TipoPocion(IntEnum):
    """Tipos de pociones."""

    AGILIDAD = 1  # Modifica la Agilidad
    FUERZA = 2  # Modifica la Fuerza
    HP = 3  # Repone HP
    MANA = 4  # Repone Mana
    CURA_VENENO = 5  # Cura Envenenamiento
    INVISIBLE = 6  # Invisibilidad (según obj.dat)
