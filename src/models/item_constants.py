"""Constantes de items del juego."""

# IDs de items especiales
GOLD_ITEM_ID = 12  # ID del item oro en el catálogo
GOLD_GRH_INDEX = 511  # Índice gráfico del oro en el suelo
BOAT_ITEM_ID = 474  # ID del item Barca

# Tope duro del oro que un jugador puede acumular. Coincide con el rango
# aceptado por el validador de banco (999_999_999) para mantener un único
# invariante en todo el sistema.
MAX_PLAYER_GOLD = 999_999_999

# TODO: Mover a un catálogo de items JSON
