"""El diagnóstico opcional conserva tiempos y nombres públicos, nunca argumentos."""

import json

import pytest

from tools.profile_runtime import RuntimeProfile


@pytest.mark.asyncio
async def test_profile_is_bounded_and_never_retains_command_arguments() -> None:
    """Aunque el comando sea desconocido, ni claves ni credenciales llegan al reporte."""
    profile = RuntimeProfile(limit=2, threshold_ms=0)

    async def command(*_args: object) -> bool:
        return True

    measured = profile.wrap(command, "redis", command=True)
    for _ in range(5):
        assert await measured(object(), "PRIVATE_CANARY", "password-canary", "account-canary")
    assert await measured(object(), "GET", "account-canary")
    report = profile.report()
    assert len(report["events"]) == 2
    assert report["dropped_events"] == 4
    assert report["counts"] == {"redis:other": 5, "redis:GET": 1}
    encoded = json.dumps(report)
    assert "PRIVATE_CANARY" not in encoded
    assert "password-canary" not in encoded
    assert "account-canary" not in encoded
