"""Configuración y constantes para Redis."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RedisConfig:
    """Configuración de conexión a Redis."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    decode_responses: bool = True
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0


class RedisKeys:
    """Constantes para las claves de Redis."""

    # Configuración del servidor
    CONFIG_SERVER_HOST = "config:server:host"
    CONFIG_SERVER_PORT = "config:server:port"
    CONFIG_SERVER_MAX_CONNECTIONS = "config:server:max_connections"

    # Configuración de efectos del juego
    CONFIG_HUNGER_THIRST_ENABLED = "config:effects:hunger_thirst:enabled"
    CONFIG_HUNGER_THIRST_INTERVAL_SED = "config:effects:hunger_thirst:interval_sed"
    CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE = "config:effects:hunger_thirst:interval_hambre"
    CONFIG_HUNGER_THIRST_REDUCCION_AGUA = "config:effects:hunger_thirst:reduccion_agua"
    CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE = "config:effects:hunger_thirst:reduccion_hambre"

    CONFIG_GOLD_DECAY_ENABLED = "config:effects:gold_decay:enabled"
    CONFIG_GOLD_DECAY_PERCENTAGE = "config:effects:gold_decay:percentage"
    CONFIG_GOLD_DECAY_INTERVAL = "config:effects:gold_decay:interval_seconds"

    # Estado del servidor
    SERVER_UPTIME = "server:uptime"
    SERVER_CONNECTIONS_COUNT = "server:connections:count"
    SERVER_CONNECTIONS_ACTIVE = "server:connections:active"

    # Ground items (items en el suelo)
    @staticmethod
    def ground_items(map_id: int) -> str:
        """Clave para ground items de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Clave de Redis para los ground items del mapa.
        """
        return f"ground_items:{map_id}"

    # Sesiones de jugadores
    @staticmethod
    def session_active(user_id: int) -> str:
        """Clave para sesión activa de un jugador.

        Returns:
            Clave de Redis para la sesión activa.
        """
        return f"session:{user_id}:active"

    @staticmethod
    def session_last_seen(user_id: int) -> str:
        """Clave para último acceso de un jugador.

        Returns:
            Clave de Redis para el último acceso.
        """
        return f"session:{user_id}:last_seen"

    # Estado del jugador
    @staticmethod
    def player_position(user_id: int) -> str:
        """Clave para posición del jugador.

        Returns:
            Clave de Redis para la posición.
        """
        return f"player:{user_id}:position"

    @staticmethod
    def player_character(user_id: int) -> str:
        """Clave para datos del personaje (race, gender, job, head, home).

        Returns:
            Clave de Redis para los datos del personaje.
        """
        return f"player:{user_id}:character"

    @staticmethod
    def player_stats(user_id: int) -> str:
        """Clave para estadísticas/atributos del jugador (strength, agility, etc).

        Returns:
            Clave de Redis para las estadísticas.
        """
        return f"player:{user_id}:stats"

    @staticmethod
    def player_inventory(user_id: int) -> str:
        """Clave para inventario del jugador.

        Returns:
            Clave de Redis para el inventario.
        """
        return f"player:{user_id}:inventory"

    @staticmethod
    def player_user_stats(user_id: int) -> str:
        """Clave para estadísticas completas del jugador (HP, mana, stamina, oro, nivel, exp).

        Returns:
            Clave de Redis para las estadísticas completas.
        """
        return f"player:{user_id}:user_stats"

    @staticmethod
    def player_hunger_thirst(user_id: int) -> str:
        """Clave para hambre y sed del jugador.

        Returns:
            Clave de Redis para hambre y sed.
        """
        return f"player:{user_id}:hunger_thirst"

    @staticmethod
    def player_spellbook(user_id: int) -> str:
        """Clave para libro de hechizos del jugador.

        Returns:
            Clave de Redis para el libro de hechizos.
        """
        return f"player:{user_id}:spellbook"

    @staticmethod
    def player_equipment(user_id: int) -> str:
        """Clave para equipamiento del jugador.

        Returns:
            Clave de Redis para el equipamiento.
        """
        return f"player:{user_id}:equipment"

    # Cuentas de usuario
    ACCOUNTS_COUNTER = "accounts:counter"

    @staticmethod
    def account_data(username: str) -> str:
        """Clave para datos de cuenta de usuario.

        Returns:
            Clave de Redis para los datos de la cuenta.
        """
        return f"account:{username}:data"

    @staticmethod
    def account_id_by_username(username: str) -> str:
        """Clave para mapear username a user_id.

        Returns:
            Clave de Redis para el mapeo username -> user_id.
        """
        return f"account:username:{username}"

    # NPCs
    @staticmethod
    def npc_instance(instance_id: str) -> str:
        """Clave para datos de una instancia de NPC.

        Returns:
            Clave de Redis para la instancia del NPC.
        """
        return f"npc:instance:{instance_id}"

    @staticmethod
    def npc_map_index(map_id: int) -> str:
        """Clave para índice de NPCs en un mapa.

        Returns:
            Clave de Redis para el índice de NPCs del mapa.
        """
        return f"npc:map:{map_id}"

    # Mercaderes
    @staticmethod
    def merchant_inventory(npc_id: int) -> str:
        """Clave para inventario de un mercader.

        Returns:
            Clave de Redis para el inventario del mercader.
        """
        return f"merchant:{npc_id}:inventory"

    @staticmethod
    def session_active_merchant(user_id: int) -> str:
        """Clave para mercader activo en sesión de comercio.

        Returns:
            Clave de Redis para el mercader activo.
        """
        return f"session:{user_id}:active_merchant"

    # Banco
    @staticmethod
    def bank(user_id: int) -> str:
        """Clave para bóveda bancaria del jugador.

        Returns:
            Clave de Redis para la bóveda bancaria.
        """
        return f"bank:{user_id}:vault"


# Valores por defecto para configuración del servidor
DEFAULT_SERVER_CONFIG = {
    RedisKeys.CONFIG_SERVER_HOST: "0.0.0.0",
    RedisKeys.CONFIG_SERVER_PORT: "7666",
    RedisKeys.CONFIG_SERVER_MAX_CONNECTIONS: "1000",
}

# Valores por defecto para efectos del juego
DEFAULT_EFFECTS_CONFIG = {
    # Hambre y Sed
    RedisKeys.CONFIG_HUNGER_THIRST_ENABLED: "1",
    RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED: "180",  # 180 segundos = 3 minutos
    RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE: "180",  # 180 segundos = 3 minutos
    RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA: "10",  # puntos
    RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE: "10",  # puntos
    # Reducción de Oro
    RedisKeys.CONFIG_GOLD_DECAY_ENABLED: "1",
    RedisKeys.CONFIG_GOLD_DECAY_PERCENTAGE: "1.0",  # porcentaje
    RedisKeys.CONFIG_GOLD_DECAY_INTERVAL: "60.0",  # segundos
}
