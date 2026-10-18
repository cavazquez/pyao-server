"""Saturación y cancelación sin bloquear el event loop ni desbordar el pool."""

import asyncio
from threading import Event, Lock

import pytest

from src.security.password_executor import PasswordExecutor, PasswordQueueFullError
from src.utils.password_utils import hash_password, verify_password


@pytest.mark.asyncio
async def test_heartbeat_capacity_and_cancelled_running_work():
    """Dos trabajos activos y uno pendiente conservan sus plazas al cancelar."""
    pool = PasswordExecutor(workers=2, max_pending=1)
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = Event()
    lock = Lock()
    active = 0
    peak = 0

    def blocked():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                loop.call_soon_threadsafe(entered.set)
        assert release.wait(timeout=5)
        with lock:
            active -= 1
        return True

    first = asyncio.create_task(pool.run(blocked))
    second = asyncio.create_task(pool.run(blocked))
    third = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        third = asyncio.create_task(pool.run(blocked))
        # Un heartbeat determinista progresa mientras ambos workers siguen bloqueados.
        heartbeats = 0
        for _ in range(5):
            await asyncio.sleep(0)
            heartbeats += 1
        assert heartbeats == 5
        assert not first.done()
        assert not second.done()
        assert pool.outstanding == 3
        first.cancel()
        third.cancel()
        await asyncio.gather(first, third, return_exceptions=True)
        assert pool.outstanding == 3
        with pytest.raises(PasswordQueueFullError):
            await pool.run(lambda: True)
        release.set()
        assert await second
    finally:
        release.set()
        await pool.aclose()
        await asyncio.gather(first, second, *([third] if third else []), return_exceptions=True)
    assert pool.outstanding == 0
    assert peak <= 2
    with pytest.raises(PasswordQueueFullError):
        await pool.run(lambda: True)


@pytest.mark.asyncio
async def test_real_hashes_and_invalid_credentials_keep_behavior():
    """Los parámetros Argon2, hashes existentes y rechazo de inválidos se preservan."""
    pool = PasswordExecutor(workers=1, max_pending=0)
    try:
        hashed = await pool.run(hash_password, "SyntheticPassword99")
        assert "$m=64000,t=3,p=4$" in hashed
        assert await pool.run(verify_password, "SyntheticPassword99", hashed)
        assert not await pool.run(verify_password, "Incorrect99", hashed)
        assert not await pool.run(verify_password, "SyntheticPassword99", "invalid-hash")
    finally:
        await pool.aclose()
