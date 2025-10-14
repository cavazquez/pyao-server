"""Sistema de tick periódico genérico para efectos del juego.

Sistema configurable que permite aplicar diferentes efectos periódicos
a los jugadores conectados (hambre, sed, reducción de oro, etc.).
"""

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class TickEffect(ABC):
    """Clase base abstracta para efectos de tick."""

    @abstractmethod
    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica el efecto a un jugador.

        Args:
            user_id: ID del usuario.
            player_repo: Repositorio de jugadores.
            message_sender: MessageSender del jugador (puede ser None).
        """

    @abstractmethod
    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto."""

    @abstractmethod
    def get_name(self) -> str:
        """Retorna el nombre del efecto para logging."""


class HungerThirstEffect(TickEffect):
    """Efecto de reducción de hambre y sed basado en General.bas del servidor original.

    Las constantes se leen desde Redis y pueden ser modificadas sin reiniciar el servidor.
    """

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el efecto de hambre/sed.

        Args:
            redis_client: Cliente Redis para leer configuración.
        """
        self.redis_client = redis_client
        # Contadores por jugador: {user_id: {"water": int, "hunger": int}}
        self._counters: dict[int, dict[str, int]] = {}
        # Cache de configuración (se recarga en cada apply)
        self._config_cache: dict[str, int] = {}

    async def apply(  # noqa: C901
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica la reducción de hambre y sed."""
        # Leer configuración desde Redis
        intervalo_sed = await self.redis_client.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, 4
        )
        intervalo_hambre = await self.redis_client.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE, 6
        )
        reduccion_agua = await self.redis_client.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA, 10
        )
        reduccion_hambre = await self.redis_client.get_effect_config_int(
            RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE, 10
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

    def get_interval_seconds(self) -> float:  # noqa: PLR6301
        """Retorna 1 segundo (se ejecuta cada segundo para contar intervalos).

        Returns:
            Intervalo en segundos.
        """
        return 1.0

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "HungerThirst"

    def cleanup_player(self, user_id: int) -> None:
        """Limpia los contadores de un jugador desconectado."""
        if user_id in self._counters:
            del self._counters[user_id]


class GoldDecayEffect(TickEffect):
    """Efecto de reducción de oro.

    Las constantes se leen desde Redis y pueden ser modificadas sin reiniciar el servidor.
    """

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el efecto de reducción de oro.

        Args:
            redis_client: Cliente Redis para leer configuración.
        """
        self.redis_client = redis_client
        # Contadores por jugador: {user_id: ticks_elapsed}
        self._counters: dict[int, int] = {}

    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica la reducción de oro."""
        # Leer configuración desde Redis
        percentage = await self.redis_client.get_effect_config_float(
            RedisKeys.CONFIG_GOLD_DECAY_PERCENTAGE, 1.0
        )
        interval_seconds = await self.redis_client.get_effect_config_float(
            RedisKeys.CONFIG_GOLD_DECAY_INTERVAL, 60.0
        )

        # Inicializar contador si no existe
        if user_id not in self._counters:
            self._counters[user_id] = 0

        # Incrementar contador
        self._counters[user_id] += 1

        # Verificar si se cumplió el intervalo
        ticks_needed = int(interval_seconds / 1.0)  # Asumiendo tick de 1 segundo
        if self._counters[user_id] >= ticks_needed:
            self._counters[user_id] = 0

            # Obtener estadísticas actuales
            stats = await player_repo.get_stats(user_id)
            if not stats:
                logger.warning("No se encontraron stats para user_id %d", user_id)
                return

            current_gold = stats["gold"]
            if current_gold <= 0:
                return  # No hay oro para reducir

            # Calcular reducción
            reduction = max(1, int(current_gold * (percentage / 100.0)))
            new_gold = max(0, current_gold - reduction)

            # Actualizar estadísticas
            stats["gold"] = new_gold
            await player_repo.set_stats(user_id=user_id, **stats)

            logger.info(
                "user_id %d: oro reducido de %d a %d (-%d, %.1f%%)",
                user_id,
                current_gold,
                new_gold,
                reduction,
                percentage,
            )

            # Notificar al cliente
            if message_sender:
                await message_sender.send_update_user_stats(**stats)
                await message_sender.send_console_msg(
                    f"Has perdido {reduction} monedas de oro ({percentage}%)"
                )

    def get_interval_seconds(self) -> float:  # noqa: PLR6301
        """Retorna 1 segundo (se ejecuta cada segundo para contar intervalos).

        Returns:
            Intervalo en segundos.
        """
        return 1.0

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "GoldDecay"

    def cleanup_player(self, user_id: int) -> None:
        """Limpia los contadores de un jugador desconectado."""
        if user_id in self._counters:
            del self._counters[user_id]


class GameTick:
    """Sistema de tick genérico que aplica efectos periódicos a jugadores conectados."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        effects: list[TickEffect] | None = None,
        tick_interval: float = 1.0,
    ) -> None:
        """Inicializa el sistema de tick.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener jugadores conectados.
            effects: Lista de efectos a aplicar (por defecto vacía).
            tick_interval: Intervalo del tick en segundos (por defecto 1 segundo).
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.effects = effects or []
        self.tick_interval = tick_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def add_effect(self, effect: TickEffect) -> None:
        """Agrega un efecto al sistema de tick.

        Args:
            effect: Efecto a agregar.
        """
        self.effects.append(effect)
        logger.info("Efecto agregado: %s", effect.get_name())

    async def _tick_loop(self) -> None:
        """Loop principal del tick que procesa todos los jugadores conectados."""
        logger.info(
            "Sistema de tick iniciado (intervalo: %.1fs, efectos: %d)",
            self.tick_interval,
            len(self.effects),
        )

        while self._running:
            try:
                # Obtener todos los user_ids conectados
                connected_user_ids = self.map_manager.get_all_connected_user_ids()

                # Aplicar cada efecto a cada jugador
                for effect in self.effects:
                    for user_id in connected_user_ids:
                        try:
                            message_sender = self.map_manager.get_message_sender(user_id)
                            await effect.apply(user_id, self.player_repo, message_sender)
                        except Exception:
                            logger.exception(
                                "Error aplicando efecto %s a user_id %d",
                                effect.get_name(),
                                user_id,
                            )

                # Esperar hasta el próximo tick
                await asyncio.sleep(self.tick_interval)

            except asyncio.CancelledError:
                logger.info("Tick del juego cancelado")
                break
            except Exception:
                logger.exception("Error en el loop de tick del juego")
                await asyncio.sleep(self.tick_interval)

    def start(self) -> None:
        """Inicia el sistema de tick."""
        if self._running:
            logger.warning("El sistema de tick ya está ejecutándose")
            return

        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info("Sistema de tick iniciado con %d efectos", len(self.effects))

    async def stop(self) -> None:
        """Detiene el sistema de tick."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("Sistema de tick detenido")
