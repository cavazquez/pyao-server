"""Tests para SessionManager."""

from src.network.session_manager import SessionManager


def test_get_user_id_success():
    """Verifica que get_user_id devuelva el user_id correctamente."""
    session_data = {"user_id": 123, "username": "testuser"}

    user_id = SessionManager.get_user_id(session_data)

    assert user_id == 123


def test_get_user_id_none_session():
    """Verifica que get_user_id devuelva None si session_data es None."""
    user_id = SessionManager.get_user_id(None)

    assert user_id is None


def test_get_user_id_missing():
    """Verifica que get_user_id devuelva None si user_id no existe."""
    session_data = {"username": "testuser"}

    user_id = SessionManager.get_user_id(session_data)

    assert user_id is None


def test_get_user_id_invalid_type():
    """Verifica que get_user_id devuelva None si user_id no es int."""
    session_data = {"user_id": "not_an_int"}

    user_id = SessionManager.get_user_id(session_data)

    assert user_id is None


def test_get_username_success():
    """Verifica que get_username devuelva el username correctamente."""
    session_data = {"user_id": 123, "username": "testuser"}

    username = SessionManager.get_username(session_data)

    assert username == "testuser"


def test_get_username_none_session():
    """Verifica que get_username devuelva None si session_data es None."""
    username = SessionManager.get_username(None)

    assert username is None


def test_get_username_missing():
    """Verifica que get_username devuelva None si username no existe."""
    session_data = {"user_id": 123}

    username = SessionManager.get_username(session_data)

    assert username is None


def test_get_username_invalid_type():
    """Verifica que get_username devuelva None si username no es str."""
    session_data = {"username": 12345}

    username = SessionManager.get_username(session_data)

    assert username is None


def test_set_user_session():
    """Verifica que set_user_session guarde los datos correctamente."""
    session_data = {}

    SessionManager.set_user_session(session_data, 123, "testuser")

    assert session_data["user_id"] == 123
    assert session_data["username"] == "testuser"


def test_clear_session():
    """Verifica que clear_session limpie los datos."""
    session_data = {"user_id": 123, "username": "testuser", "other": "data"}

    SessionManager.clear_session(session_data)

    assert len(session_data) == 0


def test_clear_session_none():
    """Verifica que clear_session no falle con None."""
    SessionManager.clear_session(None)
    # No debe lanzar excepción


def test_is_logged_in_true():
    """Verifica que is_logged_in devuelva True si hay user_id."""
    session_data = {"user_id": 123, "username": "testuser"}

    assert SessionManager.is_logged_in(session_data) is True


def test_is_logged_in_false():
    """Verifica que is_logged_in devuelva False si no hay user_id."""
    session_data = {"username": "testuser"}

    assert SessionManager.is_logged_in(session_data) is False


def test_is_logged_in_none():
    """Verifica que is_logged_in devuelva False si session_data es None."""
    assert SessionManager.is_logged_in(None) is False
