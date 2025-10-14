#!/usr/bin/env python3
"""Parser para convertir obj.dat a formato TOML.

Lee los objetos desde [OBJ1] hasta [OBJ1052] y los convierte a TOML.
"""

import re
from pathlib import Path
from typing import TextIO


def parse_obj_dat_to_toml(input_file: str, output_file: str) -> int:
    """Convierte obj.dat a formato TOML.

    Args:
        input_file: Ruta al archivo obj.dat
        output_file: Ruta al archivo TOML de salida

    Returns:
        Número de objetos convertidos.
    """
    # Leer archivo con encoding latin-1 (usado en VB6)
    with Path(input_file).open("rb") as f:
        content = f.read().decode("latin-1", errors="ignore")

    lines = content.split("\n")

    with Path(output_file).open("w", encoding="utf-8") as out:
        # Escribir encabezado
        out.write("# Catálogo de Items de Argentum Online\n")
        out.write("# Convertido desde obj.dat del cliente VB6\n")
        out.write("# Formato: TOML\n\n")

        current_obj_id: int | None = None
        current_obj_data: dict[str, int | str | list[str]] = {}
        obj_count = 0

        in_objects_section = False

        for raw_line in lines:
            line = raw_line.strip()

            # Detectar inicio de sección de objetos
            if line.startswith("[OBJ"):
                in_objects_section = True

                # Guardar objeto anterior si existe
                if current_obj_id is not None and current_obj_data:
                    write_object_toml(out, current_obj_id, current_obj_data)
                    obj_count += 1

                # Extraer ID del objeto
                match = re.match(r"\[OBJ(\d+)\]", line)
                if match:
                    current_obj_id = int(match.group(1))
                    current_obj_data = {}
                continue

            # Si no estamos en la sección de objetos, continuar
            if not in_objects_section:
                continue

            # Parsear propiedades del objeto
            if "=" in line and current_obj_id is not None:
                # Ignorar comentarios
                if line.startswith("'"):
                    continue

                parts = line.split("=", 1)
                if len(parts) == 2:  # noqa: PLR2004
                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Manejar clases prohibidas (CP1, CP2, etc.)
                    if key.startswith("CP"):
                        if "ClasesProhibidas" not in current_obj_data:
                            current_obj_data["ClasesProhibidas"] = []
                        clases = current_obj_data["ClasesProhibidas"]
                        if isinstance(clases, list):
                            clases.append(value)
                    # Convertir números
                    elif value.isdigit() or value.lstrip("-").isdigit():
                        current_obj_data[key] = int(value)
                    else:
                        current_obj_data[key] = value

        # Escribir último objeto
        if current_obj_id is not None and current_obj_data:
            write_object_toml(out, current_obj_id, current_obj_data)
            obj_count += 1

    print(f"✓ Convertidos {obj_count} objetos a {output_file}")
    return obj_count


def write_object_toml(out: TextIO, obj_id: int, obj_data: dict[str, int | str | list[str]]) -> None:
    """Escribe un objeto en formato TOML.

    Args:
        out: File handle de salida
        obj_id: ID del objeto
        obj_data: Diccionario con las propiedades del objeto
    """
    out.write("[[item]]\n")
    out.write(f"id = {obj_id}\n")

    for key, value in obj_data.items():
        if isinstance(value, list):
            # Array de strings
            formatted_list = "[" + ", ".join(f'"{v}"' for v in value) + "]"
            out.write(f"{key} = {formatted_list}\n")
        elif isinstance(value, int):
            # Número entero
            out.write(f"{key} = {value}\n")
        else:
            # String - escapar caracteres especiales
            escaped = (
                str(value)
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "")
            )
            out.write(f'{key} = "{escaped}"\n')

    out.write("\n")


if __name__ == "__main__":
    base_path = Path(__file__).parent.parent
    input_file = (
        base_path
        / "clientes"
        / "ArgentumOnline0.13.3-Cliente-Servidor"
        / "server"
        / "Dat"
        / "obj.dat"
    )
    output_file = base_path / "data" / "items.toml"

    parse_obj_dat_to_toml(str(input_file), str(output_file))
