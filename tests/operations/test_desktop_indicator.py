"""El indicador sólo controla su hijo; cerrar la bandeja no mata el servidor."""

import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - disposable test children
import sys
import time
from pathlib import Path
from unittest.mock import patch

from src.desktop.indicator import ServerProcess, linux_indicator


def wait_ready(process, log):
    """Espera al hijo de ensayo sin acceder a una partida.

    Raises:
        TimeoutError: Si el proceso temporal no publica READY.
    """
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if log.exists() and "READY" in log.read_text():
            return
        time.sleep(0.02)
    process.kill()
    message = "El proceso de ensayo no inició a tiempo"
    raise TimeoutError(message)


def test_stop_is_graceful_and_only_signals_own_process(tmp_path, monkeypatch):
    """La señal de parada ejecuta el cierre del hijo y conserva al otro proceso."""
    monkeypatch.setenv("PYAO_STATE_DIR", str(tmp_path))
    done = tmp_path / "closed"
    script = (
        "import signal,time,pathlib,sys; "
        "signal.signal(signal.SIGINT, lambda *_: "
        f"(pathlib.Path({str(done)!r}).write_text('closed'), sys.exit(0))); "
        "print('READY',flush=True); time.sleep(30)"
    )
    original = subprocess.Popen
    supervisor = ServerProcess([])

    def start_owned(_command, **kwargs: object):
        return original([sys.executable, "-c", script], **kwargs)

    with original([sys.executable, "-c", "import time; time.sleep(30)"]) as unrelated:
        try:
            with patch("src.desktop.indicator.subprocess.Popen", side_effect=start_owned):
                supervisor.start()
            wait_ready(supervisor.process, supervisor.log)
            assert supervisor.log.stat().st_mode & 0o777 == 0o600
            supervisor.stop()
            supervisor.process.wait(timeout=5)
            assert done.read_text() == "closed"
            assert unrelated.poll() is None
            assert "detenido (0)" in supervisor.title()
            supervisor.stop()  # Repetir tras terminar no señaliza otro PID.
        finally:
            if supervisor.process.poll() is None:
                supervisor.process.kill()
                supervisor.process.wait()
            unrelated.terminate()
            unrelated.wait()


def test_closing_indicator_detaches_instead_of_stopping_own_server(tmp_path, monkeypatch):
    """Un bridge que cierra su menú conserva el hijo que ya había iniciado."""
    monkeypatch.setenv("PYAO_STATE_DIR", str(tmp_path))
    bridge = tmp_path / "tray"
    bridge.write_text(
        f"#!{sys.executable}\nimport time\nprint('READY',flush=True)\n"
        "time.sleep(0.1)\nprint('DETACH',flush=True)\n"
    )
    bridge.chmod(0o755)
    original = subprocess.Popen
    supervisor = ServerProcess([])

    def start(command, **kwargs: object):
        if command[:3] == [sys.executable, "-m", "src.run_server"]:
            command = [
                sys.executable,
                "-c",
                "import time; print('READY',flush=True); time.sleep(30)",
            ]
        return original(command, **kwargs)

    try:
        with (
            patch("src.desktop.indicator.shutil.which", return_value=str(bridge)),
            patch("src.desktop.indicator.subprocess.Popen", side_effect=start),
        ):
            assert linux_indicator(supervisor, Path("icon.png")) == 0
        assert supervisor.process.poll() is None
    finally:
        supervisor.process.send_signal(signal.SIGINT)
        supervisor.process.wait(timeout=5)
