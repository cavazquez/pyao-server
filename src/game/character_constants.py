"""Constantes de IDs ↔ nombres para personajes.

Este módulo centraliza los mapeos entre IDs usados en el protocolo/cliente
(Godot / enums) y los nombres de raza/clase/género/ciudad que usa el
servidor.

Los IDs de clase y raza provienen de los enums definidos en el cliente
Godot (ver `clientes/ArgentumOnlineGodot/common/enums/enums.gd` y
`clientes/ArgentumOnlineGodot/engine/autoload/consts.gd`).

NOTA: Este módulo no tiene lógica, solo constantes reutilizables.
"""

# Mapping de IDs de clase (cliente Godot / protocolo AO) a nombres de clase
# usados en el archivo data/classes_balance.toml.
JOB_ID_TO_CLASS_NAME: dict[int, str] = {
    1: "Mago",
    2: "Clerigo",
    3: "Guerrero",
    4: "Asesino",
    5: "Ladron",
    6: "Bardo",
    7: "Druida",
    8: "Bandido",
    9: "Paladin",
    10: "Cazador",
    11: "Trabajador",
    12: "Pirata",
}

# Mapping de IDs de raza a nombres legibles (coinciden con classes_balance.toml)
RACE_ID_TO_NAME: dict[int, str] = {
    1: "Humano",
    2: "Elfo",
    3: "Drow",
    4: "Gnomo",
    5: "Enano",
}

# Género es un valor entero que el cliente envía (1 = Hombre, 2 = Mujer)
GENDER_ID_TO_NAME: dict[int, str] = {
    1: "Hombre",
    2: "Mujer",
}

# Mapping de IDs de ciudad inicial (home) a nombres
HOME_ID_TO_NAME: dict[int, str] = {
    1: "Ullathorpe",
    2: "Nix",
    3: "Banderbill",
    4: "Lindos",
    5: "Arghal",
    6: "Arkhein",
}
