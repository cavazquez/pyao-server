"""Servicios relacionados con jugadores.

Ejemplo de uso:
    from src.services.player import PlayerService, AuthenticationService, SpellService
"""

from src.services.player.authentication_service import AuthenticationService
from src.services.player.equipment_service import EquipmentService
from src.services.player.player_service import PlayerService
from src.services.player.spell_service import SpellService
from src.services.player.stamina_service import StaminaService

__all__ = [
    "AuthenticationService",
    "EquipmentService",
    "PlayerService",
    "SpellService",
    "StaminaService",
]
