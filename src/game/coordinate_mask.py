"""Conjunto mutable de coordenadas 1..100: 1.250 bytes por capa de terreno."""

from collections.abc import Iterable, Iterator, MutableSet
from collections.abc import Set as AbstractSet
from typing import Any, Self

type Coordinates = MutableSet[tuple[int, int]]
type ResourcesMap = dict[str, dict[str, Coordinates]]
TERRAIN_LAYERS = ("blocked", "water", "trees", "mines", "anvils", "forges")
MAP_SIDE = 100
MASK_BYTES = MAP_SIDE * MAP_SIDE // 8
COORDINATE_DIMENSIONS = 2


def coordinates_for[K](layers: dict[K, Coordinates], key: K) -> Coordinates:
    """Inicializa una capa sólo al necesitarla.

    Returns:
        Conjunto existente o máscara compacta nueva.
    """
    layer = layers.get(key)
    if layer is None:
        layer = CoordinateMask()
        layers[key] = layer
    return layer


class CoordinateMask(MutableSet[tuple[int, int]]):
    """Guarda los flags compactos sin retener tuplas por cada casilla marcada."""

    def __init__(self, values: Iterable[tuple[int, int]] = ()) -> None:
        """Construye una capa vacía o a partir de coordenadas del mundo."""
        self._bits = bytearray(MASK_BYTES)
        self._count = 0
        self.update(values)

    def __contains__(self, value: object) -> bool:
        """Comprueba pertenencia, rechazando coordenadas fuera del mundo.

        Returns:
            Si existe la pareja de enteros en el dominio 1..100.
        """
        if not isinstance(value, tuple) or len(value) != COORDINATE_DIMENSIONS:
            return False
        x, y = value
        return type(x) is int and type(y) is int and self.contains_xy(x, y)

    def contains_xy(self, x: int, y: int) -> bool:
        """Consulta directa sin materializar una tupla.

        Returns:
            El bit de esa casilla o False si está fuera de 1..100.
        """
        if (
            type(x) is not int
            or type(y) is not int
            or not 1 <= x <= MAP_SIDE
            or not 1 <= y <= MAP_SIDE
        ):
            return False
        index = (y - 1) * MAP_SIDE + x - 1
        return bool(self._bits[index >> 3] & (1 << (index & 7)))

    def __len__(self) -> int:
        """Obtiene el número de casillas marcadas.

        Returns:
            Cantidad de bits activos, mantenida al mutar la capa.
        """
        return self._count

    def __iter__(self) -> Iterator[tuple[int, int]]:
        """Materializa coordenadas sólo al recorrer explícitamente una capa.

        Yields:
            Parejas (x, y) del mundo, en orden por fila y columna.
        """
        for byte_index, stored in enumerate(self._bits):
            remaining = stored
            while remaining:
                first = remaining & -remaining
                index = byte_index * 8 + first.bit_length() - 1
                y, x = divmod(index, MAP_SIDE)
                yield x + 1, y + 1
                remaining &= remaining - 1

    def add(self, value: tuple[int, int]) -> None:
        """Marca una casilla sin duplicarla.

        Raises:
            ValueError: Si la coordenada no pertenece al mundo 1..100.
        """
        x, y = value
        if (
            type(x) is not int
            or type(y) is not int
            or not 1 <= x <= MAP_SIDE
            or not 1 <= y <= MAP_SIDE
        ):
            message = f"Coordenada fuera de 1..100: {value!r}"
            raise ValueError(message)
        index = (y - 1) * MAP_SIDE + x - 1
        byte, bit = index >> 3, 1 << (index & 7)
        if not self._bits[byte] & bit:
            self._bits[byte] |= bit
            self._count += 1

    def discard(self, value: tuple[int, int]) -> None:
        """Desmarca una casilla; una coordenada ausente no modifica la capa."""
        if value in self:
            x, y = value
            index = (y - 1) * MAP_SIDE + x - 1
            self._bits[index >> 3] &= ~(1 << (index & 7))
            self._count -= 1

    def update(self, values: Iterable[tuple[int, int]]) -> None:
        """Añade coordenadas sin retener el iterable ni sus tuplas."""
        for value in values:
            self.add(value)

    def __or__(self, other: AbstractSet[Any]) -> Self:
        """Une máscaras en C; no materializa sus miles de coordenadas.

        Returns:
            Máscara independiente con la unión de ambos conjuntos.
        """
        if isinstance(other, CoordinateMask):
            bits = int.from_bytes(self._bits, "little") | int.from_bytes(other._bits, "little")
            return self.from_bytes(bits.to_bytes(MASK_BYTES, "little"))
        result = self.copy()
        result.update(other)
        return result

    def __and__(self, other: AbstractSet[Any]) -> Self:
        """Interseca planos directamente cuando ambos son máscaras.

        Returns:
            Máscara independiente con las coordenadas compartidas.
        """
        if isinstance(other, CoordinateMask):
            bits = int.from_bytes(self._bits, "little") & int.from_bytes(other._bits, "little")
            return self.from_bytes(bits.to_bytes(MASK_BYTES, "little"))
        return type(self)(coordinate for coordinate in other if coordinate in self)

    def __sub__(self, other: AbstractSet[Any]) -> Self:
        """Resta planos o sólo las pocas coordenadas de un conjunto disperso.

        Returns:
            Máscara independiente con las casillas restantes.
        """
        if isinstance(other, CoordinateMask):
            bits = int.from_bytes(self._bits, "little") & ~int.from_bytes(other._bits, "little")
            return self.from_bytes(bits.to_bytes(MASK_BYTES, "little"))
        result = self.copy()
        for coordinate in other:
            result.discard(coordinate)
        return result

    def __xor__(self, other: AbstractSet[Any]) -> Self:
        """Calcula diferencia simétrica sin recorrer el mapa denso.

        Returns:
            Máscara independiente con las casillas exclusivas de cada conjunto.
        """
        if isinstance(other, CoordinateMask):
            bits = int.from_bytes(self._bits, "little") ^ int.from_bytes(other._bits, "little")
            return self.from_bytes(bits.to_bytes(MASK_BYTES, "little"))
        return (self | other) - (self & other)

    __ror__ = __or__
    __rand__ = __and__
    __rxor__ = __xor__

    def copy(self) -> Self:
        """Copia una capa para permitir bloqueos dinámicos independientes.

        Returns:
            Máscara con datos propios y los mismos flags.
        """
        return self.from_bytes(self.to_bytes())

    def to_bytes(self) -> bytes:
        """Exporta el payload compacto para la caché descartable.

        Returns:
            Exactamente 1.250 bytes.
        """
        return bytes(self._bits)

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Restaura una capa sin construir coordenadas intermedias.

        Returns:
            Máscara mutable con todos los flags del payload.

        Raises:
            ValueError: Si el tamaño del payload no es válido.
        """
        if len(data) != MASK_BYTES:
            message = f"Máscara de terreno inválida: {len(data)} bytes"
            raise ValueError(message)
        result = cls()
        result._bits[:] = data
        result._count = int.from_bytes(data).bit_count()
        return result
