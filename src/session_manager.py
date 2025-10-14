"""Gestor de sesiones de usuario."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SessionManager:
    """Gestor estático para operaciones de sesión de usuario."""

    @staticmethod
    def get_user_id(session_data: dict[str, Any] | None) -> int | None:
        """Obtiene el user_id de la sesión.

        Args:
            session_data: Diccionario de datos de sesión.

        Returns:
            user_id si existe y es válido, None en caso contrario.
        """
        if not session_data:
            return None

        user_id = session_data.get("user_id")
        if not user_id or not isinstance(user_id, int):
            return None

        return int(user_id)

    @staticmethod
    def get_username(session_data: dict[str, Any] | None) -> str | None:
        """Obtiene el username de la sesión.

        Args:
            session_data: Diccionario de datos de sesión.

        Returns:
            username si existe, None en caso contrario.
        """
        if not session_data:
            return None

        username = session_data.get("username")
        if not username or not isinstance(username, str):
            return None

        return str(username)

    @staticmethod
    def set_user_session(
        session_data: dict[str, Any],
        user_id: int,
        username: str,
    ) -> None:
        """Guarda los datos del usuario en la sesión.

        Args:
            session_data: Diccionario de datos de sesión.
            user_id: ID del usuario.
            username: Nombre del usuario.
        """
        session_data["user_id"] = user_id
        session_data["username"] = username
        logger.info("User ID %d y username %s guardados en sesión", user_id, username)

    @staticmethod
    def clear_session(session_data: dict[str, Any] | None) -> None:
        """Limpia los datos de la sesión.

        Args:
            session_data: Diccionario de datos de sesión.
        """
        if not session_data:
            return

        user_id = session_data.get("user_id")
        session_data.clear()
        logger.info("Sesión limpiada para user_id %s", user_id)

    @staticmethod
    def is_logged_in(session_data: dict[str, Any] | None) -> bool:
        """Verifica si hay un usuario logueado en la sesión.

        Args:
            session_data: Diccionario de datos de sesión.

        Returns:
            True si hay un usuario logueado, False en caso contrario.
        """
        return SessionManager.get_user_id(session_data) is not None
