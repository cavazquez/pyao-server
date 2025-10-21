"""Script para parsear archivos .map de AO VB6 y extraer recursos (agua, árboles, minas).

Formato de archivo .map de Argentum Online 0.13.3:
- Cada mapa es 100x100 tiles
- Cada tile tiene múltiples capas gráficas y propiedades
- Los archivos .map son binarios con estructura específica de VB6

Recursos a detectar:
- Agua: Graphic(1) en rangos [1505-1520, 5665-5680, 13547-13562]
- Árboles: ObjGrh específicos (por ahora detectamos por coordenadas conocidas)
- Yacimientos: ObjGrh específicos
"""

import json
import struct
from pathlib import Path
from typing import ClassVar

from src.constants.graphics import WATER_GRAPHIC_RANGES
from src.constants.map import MAP_SIZE


class AOMapParser:
    """Parser para archivos .map de Argentum Online."""

    # Rangos de GrhIndex que representan agua
    WATER_GRAPHIC_RANGES: ClassVar[list[tuple[int, int]]] = WATER_GRAPHIC_RANGES

    # Tamaño del mapa
    MAP_SIZE: ClassVar[int] = MAP_SIZE

    def __init__(self, map_file_path: str | Path) -> None:
        """Inicializa el parser.

        Args:
            map_file_path: Ruta al archivo .map
        """
        self.map_path = Path(map_file_path)
        self.map_data: dict[str, list[tuple[int, int]]] = {
            "water": [],
            "trees": [],
            "mines": [],
        }

    def parse(self) -> dict[str, list[tuple[int, int]]]:
        """Parsea el archivo .map y extrae los recursos.

        Returns:
            Diccionario con listas de coordenadas por tipo de recurso.
        """
        print(f"Parseando {self.map_path.name}...")

        try:
            with Path(self.map_path).open("rb") as f:
                # Leer todo el archivo
                data = f.read()

            # Parsear tiles
            self._parse_tiles(data)

            print(f"  ✓ Agua: {len(self.map_data['water'])} tiles")
            print(f"  ✓ Árboles: {len(self.map_data['trees'])} tiles")
            print(f"  ✓ Minas: {len(self.map_data['mines'])} tiles")

        except Exception as e:  # noqa: BLE001 - Catch all errors in map parsing
            print(f"  ✗ Error parseando {self.map_path.name}: {e}")

        return self.map_data

    def _parse_tiles(self, data: bytes) -> None:
        """Parsea los tiles del mapa según formato de AO WorldEditor.

        Formato del archivo .map (basado en modMapIO.bas):

        HEADER:
        - 2 bytes: MapVersion (Int16)
        - Variable: MiCabecera (string, típicamente 100 bytes)
        - 2 bytes: Llueve
        - 2 bytes: Nieba
        - 4 x 2 bytes: TempInt (8 bytes total)

        TILES (100x100, de Y=1 to 100, X=1 to 100):
        Para cada tile:
        - 1 byte: ByFlags (bits que indican qué campos están presentes)
        - 2 bytes: Graphic(1).grhindex (SIEMPRE presente - capa base)
        - 2 bytes: Graphic(2).grhindex (solo si ByFlags And 2)
        - 2 bytes: Graphic(3).grhindex (solo si ByFlags And 4)
        - 2 bytes: Graphic(4).grhindex (solo si ByFlags And 8)
        - 1 byte: Trigger (solo si ByFlags And 16)
        - ...otros campos opcionales...

        ByFlags bits:
        - Bit 0 (1): Blocked
        - Bit 1 (2): Tiene Graphic(2)
        - Bit 2 (4): Tiene Graphic(3)
        - Bit 3 (8): Tiene Graphic(4)
        - Bit 4 (16): Tiene Trigger
        """
        # Skip header (aproximadamente 120 bytes)
        # MapVersion (2) + Cabecera (~100) + Llueve (2) + Nieba (2) + TempInts (8) = ~114 bytes
        offset = 120

        # Parsear tiles: 100x100 tiles
        for y in range(1, self.MAP_SIZE + 1):
            for x in range(1, self.MAP_SIZE + 1):
                try:
                    if offset >= len(data):
                        return

                    # Leer ByFlags
                    by_flags = data[offset]
                    offset += 1

                    # Leer Graphic(1) - SIEMPRE presente (2 bytes, Little Endian)
                    if offset + 2 > len(data):
                        return

                    graphic1 = struct.unpack("<H", data[offset : offset + 2])[0]
                    offset += 2

                    # Verificar si es agua
                    if self._is_water_graphic(graphic1):
                        self.map_data["water"].append((x, y))

                    # Leer capas opcionales según ByFlags
                    if by_flags & 2:  # Graphic(2)
                        offset += 2
                    if by_flags & 4:  # Graphic(3)
                        offset += 2
                    if by_flags & 8:  # Graphic(4)
                        offset += 2
                    if by_flags & 16:  # Trigger
                        offset += 1
                    # Ignoramos particle_group y luz por ahora

                except (struct.error, IndexError):
                    return

    def _is_water_graphic(self, graphic: int) -> bool:
        """Verifica si un GrhIndex corresponde a agua.

        Args:
            graphic: Valor del GrhIndex.

        Returns:
            True si es agua, False si no.
        """
        return any(min_val <= graphic <= max_val for min_val, max_val in self.WATER_GRAPHIC_RANGES)


def parse_all_maps(maps_dir: str | Path, output_dir: str | Path) -> None:
    """Parsea todos los mapas y genera archivos JSON individuales.

    Args:
        maps_dir: Directorio con los archivos .map
        output_dir: Directorio de salida para los JSON
    """
    maps_dir = Path(maps_dir)
    output_dir = Path(output_dir)

    # Crear directorio de salida
    output_dir.mkdir(parents=True, exist_ok=True)

    # Buscar todos los archivos .map
    map_files = sorted(maps_dir.glob("Mapa*.map"))

    if not map_files:
        print(f"❌ No se encontraron archivos .map en {maps_dir}")
        return

    print(f"📂 Encontrados {len(map_files)} archivos .map")
    print(f"📁 Guardando en {output_dir}\n")

    processed = 0
    errors = 0

    for map_file in map_files:
        # Extraer número del mapa (Mapa1.map -> 1)
        try:
            map_number = int(map_file.stem.replace("Mapa", ""))
        except ValueError:
            print(f"⚠️  Ignorando archivo: {map_file.name}")
            continue

        try:
            # Parsear mapa
            parser = AOMapParser(map_file)
            resources = parser.parse()

            # Guardar en archivo individual (formato: 1.json, 2.json, etc.)
            output_file = output_dir / f"{map_number}.json"
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "water": resources["water"],
                        "trees": resources["trees"],
                        "mines": resources["mines"],
                    },
                    f,
                    indent=2,
                )

            processed += 1
            if processed % 50 == 0:
                print(f"✓ Procesados {processed}/{len(map_files)} mapas...")

        except Exception as e:  # noqa: BLE001 - Continue processing on errors
            errors += 1
            print(f"❌ Error en {map_file.name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"✓ Procesados: {processed}/{len(map_files)} mapas")
    print(f"❌ Errores: {errors}")
    print(f"📁 Recursos guardados en {output_dir}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    # Rutas
    MAPS_DIR = (
        Path(__file__).parent.parent
        / "clientes"
        / "ArgentumOnline0.13.3-Cliente-Servidor"
        / "server"
        / "Maps"
    )
    OUTPUT_DIR = Path(__file__).parent.parent / "resources"

    print("=== Parser de Recursos de Mapas AO ===\n")
    parse_all_maps(MAPS_DIR, OUTPUT_DIR)
    print("\n✓ Proceso completado")
