"""Presupuestos de autenticación previos al trabajo Argon2."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.game_config import SecurityConfig


@dataclass
class ConnectionAttempts:
    """Contador privado de una conexión; no se comparte con otra sesión."""

    window: int = -1
    count: int = 0


class AuthLimiter:
    """Ventanas fijas compartidas por IP/cuenta con memoria máxima explícita."""

    def __init__(self, config: SecurityConfig, clock: Callable[[], float] = time.monotonic) -> None:
        """Configura límites y un reloj monotónico inyectable para pruebas."""
        self.config = config
        self.clock = clock
        self._window = -1
        self._ips: dict[str, int] = {}
        self._accounts: dict[str, int] = {}

    def allow(self, ip: str, username: str, connection: ConnectionAttempts) -> bool:
        """Consume un intento conjunto sin consultar si la cuenta existe.

        Returns:
            True si los tres presupuestos permiten el intento.
        """
        window = int(self.clock() // self.config.auth_window_seconds)
        if window != self._window:
            self._window = window
            self._ips.clear()
            self._accounts.clear()
        if connection.window != window:
            connection.window = window
            connection.count = 0
        # No conservar nombres de cuenta arbitrarios en el presupuesto global.
        account = sha256(username.casefold().encode("utf-8")).hexdigest()
        ip_count = self._ips.get(ip, 0)
        account_count = self._accounts.get(account, 0)
        if (
            connection.count >= self.config.auth_attempts_per_connection
            or ip_count >= self.config.auth_attempts_per_ip
            or account_count >= self.config.auth_attempts_per_account
        ):
            return False
        additional = int(ip not in self._ips) + int(account not in self._accounts)
        if len(self._ips) + len(self._accounts) + additional > self.config.auth_max_keys:
            # No desalojar contadores vivos: eso permitiría eludir el límite rotando nombres.
            return False
        connection.count += 1
        self._ips[ip] = ip_count + 1
        self._accounts[account] = account_count + 1
        return True
