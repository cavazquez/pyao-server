"""Efecto de reducción de hambre y sed."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.effects.tick_effect import TickEffect
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class HungerThirstEffect(TickEffect):
    """Efecto de reducción de hambre y sed basado en General.bas del servidor original.

    Las constantes se leen desde Redis y pueden ser modificadas sin reiniciar el servidor.
    """

    def __init__(self, server_repo: ServerRepository) -> None:
        """Inicializa el efecto de hambre/sed.

        Args:
            server_repo: Repositorio del servidor para leer configuración.
        """
        self.server_repo = server_repo
        # Contadores por jugador: {user_id: {"water": int, "hunger": int}}
        self._counters: dict[int, dict[str, int]] = {}
        # Cache de configuración (se recarga en cada apply)
        self._config_cache: dict[str, int] = {}

    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica la reducción de hambre y sed."""
        # Leer configuración desde Redis, usando defaults desde ConfigManager
        default_intervalo_sed = ConfigManager.as_int(
            config_manager.get("game.effects.hunger_thirst.interval_sed", 180)
        )
        default_intervalo_hambre = ConfigManager.as_int(
            config_manager.get("game.effects.hunger_thirst.interval_hambre", 180)
        )
        default_reduccion_agua = ConfigManager.as_int(
            config_manager.get("game.effects.hunger_thirst.reduccion_agua", 10)
        )
        default_reduccion_hambre = ConfigManager.as_int(
            config_manager.get("game.effects.hunger_thirst.reduccion_hambre", 10)
        )

        intervalo_sed = await self.server_repo.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED,
            default_intervalo_sed,
        )
        intervalo_hambre = await self.server_repo.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE,
            default_intervalo_hambre,
        )
        reduccion_agua = await self.server_repo.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA,
            default_reduccion_agua,
        )
        reduccion_hambre = await self.server_repo.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE,
            default_reduccion_hambre,
        )

        # Obtener datos actuales
        hunger_thirst = await player_repo.get_hunger_thirst(user_id)
        if not hunger_thirst:
            logger.warning("No se encontraron datos de hambre/sed para user_id %d", user_id)
            return

        # Inicializar contadores si no existen
        if user_id not in self._counters:
            self._counters[user_id] = {
                "water": hunger_thirst["water_counter"],
                "hunger": hunger_thirst["hunger_counter"],
            }

        # Extraer valores actuales
        min_water = hunger_thirst["min_water"]
        min_hunger = hunger_thirst["min_hunger"]
        thirst_flag = hunger_thirst["thirst_flag"]
        hunger_flag = hunger_thirst["hunger_flag"]

        # Variables para detectar cambios
        changed = False

        # Procesar sed (agua)
        self._counters[user_id]["water"] += 1
        if self._counters[user_id]["water"] >= intervalo_sed:
            self._counters[user_id]["water"] = 0
            min_water = max(0, min_water - reduccion_agua)
            changed = True

            # Activar/desactivar flag de sed
            if min_water <= 0:
                if thirst_flag == 0:
                    thirst_flag = 1
                    logger.info("user_id %d tiene sed (agua = 0)", user_id)
            elif thirst_flag == 1:
                thirst_flag = 0

        # Procesar hambre (comida)
        self._counters[user_id]["hunger"] += 1
        if self._counters[user_id]["hunger"] >= intervalo_hambre:
            self._counters[user_id]["hunger"] = 0
            min_hunger = max(0, min_hunger - reduccion_hambre)
            changed = True

            # Activar/desactivar flag de hambre
            if min_hunger <= 0:
                if hunger_flag == 0:
                    hunger_flag = 1
                    logger.info("user_id %d tiene hambre (comida = 0)", user_id)
            elif hunger_flag == 1:
                hunger_flag = 0

        # Guardar cambios
        if changed or (
            self._counters[user_id]["water"] != hunger_thirst["water_counter"]
            or self._counters[user_id]["hunger"] != hunger_thirst["hunger_counter"]
        ):
            await player_repo.set_hunger_thirst(
                user_id=user_id,
                max_water=hunger_thirst["max_water"],
                min_water=min_water,
                max_hunger=hunger_thirst["max_hunger"],
                min_hunger=min_hunger,
                thirst_flag=thirst_flag,
                hunger_flag=hunger_flag,
                water_counter=self._counters[user_id]["water"],
                hunger_counter=self._counters[user_id]["hunger"],
            )

            # Notificar al cliente si cambió el valor visible
            if changed and message_sender:
                await message_sender.send_update_hunger_and_thirst(
                    max_water=hunger_thirst["max_water"],
                    min_water=min_water,
                    max_hunger=hunger_thirst["max_hunger"],
                    min_hunger=min_hunger,
                )

    def get_interval_seconds(self) -> float:
        """Retorna 1 segundo (se ejecuta cada segundo para contar intervalos).

        Returns:
            Intervalo en segundos.
        """
        return 1.0

    def get_name(self) -> str:
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "HungerThirst"

    def cleanup_player(self, user_id: int) -> None:
        """Limpia los contadores de un jugador desconectado."""
        if user_id in self._counters:
            del self._counters[user_id]
