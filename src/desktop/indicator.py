"""Indicador opcional: supervisa exclusivamente el proceso que inicia."""

from __future__ import annotations

import argparse
import os
import selectors
import shutil
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed argv; no shell
import sys
import threading
from contextlib import ExitStack, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.runtime_paths import data_dir, resource_root, state_dir

if TYPE_CHECKING:
    from collections.abc import Callable


class ServerProcess:
    """Proceso propio, con registros privados y parada gradual."""

    def __init__(self, arguments: list[str]) -> None:
        """Prepara el supervisor sin iniciar Redis ni el servidor."""
        self.arguments = arguments
        self.process: subprocess.Popen[bytes] | None = None
        self.log = state_dir() / "logs" / f"indicator-{os.getpid()}.log"
        self._stopping = False

    def start(self) -> None:
        """Arranca el CLI normal en un grupo independiente del indicador."""
        self.log.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            self.process = subprocess.Popen(  # noqa: S603 - arguments are forwarded as argv
                [sys.executable, "-m", "src.run_server", *self.arguments],
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                if os.name == "nt"
                else 0,
            )
        print(f"PyAO PID {self.process.pid}; registros: {self.log}", flush=True)

    def title(self) -> str:
        """Describe el proceso real, sin confundirlo con disponibilidad de red.

        Returns:
            Estado breve del proceso que inició este indicador.
        """
        if self.process is None:
            return "PyAO Server · sin iniciar"
        status = self.process.poll()
        if status is not None:
            return f"PyAO Server · detenido ({status})"
        status_label = "deteniendo" if self._stopping else "proceso activo"
        return f"PyAO Server · {status_label} · PID {self.process.pid}"

    def stop(self) -> None:
        """Solicita el cierre gradual una sola vez; nunca mata Redis."""
        if self.process is None or self.process.poll() is not None or self._stopping:
            return
        self._stopping = True
        with suppress(ProcessLookupError):
            self.process.send_signal(
                getattr(signal, "CTRL_BREAK_EVENT", signal.SIGINT)
                if os.name == "nt"
                else signal.SIGINT
            )

    def open_logs(self) -> None:
        """Abre el archivo del proceso propio con el visor del escritorio."""
        if os.name == "nt":
            os.startfile(self.log)  # type: ignore[attr-defined]  # ruff: ignore[start-process-with-no-shell] - desktop opener
            return
        opener = shutil.which("open" if sys.platform == "darwin" else "xdg-open")
        if opener:
            subprocess.Popen([opener, str(self.log)])  # noqa: S603 - no shell


def quit_bridge(process: subprocess.Popen[str]) -> None:
    """El cierre del menú puede haber cerrado ya el otro extremo de la tubería."""
    if process.stdin is not None:
        with suppress(BrokenPipeError):
            process.stdin.write("QUIT\n")
            process.stdin.flush()


def close_bridge_input(process: subprocess.Popen[str]) -> None:
    """Cierra el buffer antes de que Popen repita un flush con el lector terminado."""
    if process.stdin is not None:
        with suppress(BrokenPipeError):
            process.stdin.close()


def linux_indicator(supervisor: ServerProcess, icon: Path) -> int:
    """Inicia el servidor sólo después de confirmar una bandeja disponible.

    Returns:
        Código de salida del indicador; cerrar éste conserva el servidor.
    """
    bridge = shutil.which("pyao-tray")
    local = resource_root() / "build/desktop/pyao-tray"
    if bridge is None and local.is_file():
        bridge = str(local)
    if bridge is None:
        print(
            "Falta pyao-tray; ejecutar tools/build_tray.py o usar el CLI pyao-server.",
            file=sys.stderr,
        )
        return 2
    with (
        subprocess.Popen(  # noqa: S603 - a resolved executable with fixed protocol
            [bridge, "server", str(icon), "PyAO Server · esperando bandeja"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as process,
        ExitStack() as cleanup,
    ):
        assert process.stdout is not None  # noqa: S101 - pipes created above
        assert process.stdin is not None  # noqa: S101
        cleanup.callback(close_bridge_input, process)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            title = ""
            while process.poll() is None:
                if selector.select(timeout=0.5):
                    event = process.stdout.readline().strip()
                    if event == "READY" and supervisor.process is None:
                        supervisor.start()
                    elif event == "STOP":
                        supervisor.stop()
                    elif event == "LOGS" and supervisor.process is not None:
                        supervisor.open_logs()
                    elif event in {"DETACH", "UNAVAILABLE", ""}:
                        quit_bridge(process)
                        break
                current = supervisor.title()
                if current != title:
                    title = current
                    try:
                        process.stdin.write("TITLE " + title + "\n")
                        stopped = (
                            supervisor.process is not None and supervisor.process.poll() is not None
                        )
                        process.stdin.write("STOPPED\n" if stopped else "")
                        process.stdin.flush()
                    except BrokenPipeError:
                        break
        return 0 if supervisor.process is not None else 2


def native_indicator(supervisor: ServerProcess, image: Path) -> int:
    """Usa las bibliotecas opcionales de escritorio en Windows y macOS.

    Returns:
        Código de salida, sin detener el servidor al cerrar el indicador.
    """
    try:
        import pystray  # type: ignore[import-not-found]  # noqa: PLC0415 - optional desktop dependencies
        from PIL import Image  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError:
        print(
            "Instalar pyao-server[desktop] para el indicador en esta plataforma.", file=sys.stderr
        )
        return 2

    def action(callback: Callable[[], None]) -> Callable[..., None]:
        def run(*_args: object) -> None:
            callback()

        return run

    with Image.open(image) as bitmap:
        indicator: Any = pystray.Icon("pyao-server", bitmap.copy(), "PyAO Server")
    indicator.menu = pystray.Menu(
        pystray.MenuItem("Ver registros", action(supervisor.open_logs)),
        pystray.MenuItem("Detener servidor", action(supervisor.stop)),
        pystray.MenuItem("Cerrar indicador (servidor continúa)", action(indicator.stop)),
    )
    finished = threading.Event()

    def setup(icon: Any) -> None:  # ruff: ignore[any-type] - optional pystray has no type stubs
        supervisor.start()
        icon.visible = True
        while not finished.wait(0.5):
            icon.title = supervisor.title()

    try:
        indicator.run(setup=setup)
    finally:
        finished.set()
    return 0


def main() -> int:
    """Expone el indicador separado de la CLI que funciona sin escritorio.

    Returns:
        Estado de la integración de escritorio.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-arg",
        action="append",
        default=[],
        help="Argumento para pyao-server; usar --server-arg=--ssl",
    )
    args = parser.parse_args()
    supervisor = ServerProcess(args.server_arg)
    icon = data_dir() / "desktop/icons/pyao-server-128.png"
    if sys.platform.startswith("linux"):
        return linux_indicator(supervisor, icon)
    return native_indicator(supervisor, icon)


if __name__ == "__main__":
    raise SystemExit(main())
