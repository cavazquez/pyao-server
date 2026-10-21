"""Acredita el backend nativo opcional sin conectar el servidor a Redis."""

import argparse
from contextlib import chdir
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if sys.platform not in {"win32", "darwin"}:
        parser.error("Este backend nativo se verifica en Windows/macOS; Linux usa el puente GTK")
    import pystray
    from PIL import ImageGrab
    from src.desktop.indicator import ServerProcess, native_indicator
    from src.runtime_paths import data_dir

    args.output.mkdir(parents=True, exist_ok=True)
    proof = {
        "platform": sys.platform,
        "visible": False,
        "version_without_redis": False,
        "closed": False,
    }
    errors = []
    original = pystray.Icon
    with tempfile.TemporaryDirectory(prefix="pyao-desktop-native-") as temporary, chdir(temporary):
        os.environ["PYAO_STATE_DIR"] = temporary
        supervisor = ServerProcess(["--version"])

        def factory(*values, **kwargs):
            icon = original(*values, **kwargs)

            def inspect():
                try:
                    proof["visible"] = bool(icon.visible)
                    proof["version_without_redis"] = (
                        supervisor.process is not None and supervisor.process.poll() == 0
                    )
                    proof["status"] = supervisor.title()
                    if args.capture:
                        ImageGrab.grab().save(args.output / "desktop.png")
                    proof["closed"] = True
                except Exception as error:
                    errors.append(str(error))
                finally:
                    icon.stop()

            timer = threading.Timer(3.0, inspect)
            timer.daemon = True
            timer.start()
            return icon

        with patch.object(pystray, "Icon", factory):
            status = native_indicator(supervisor, data_dir() / "desktop/icons/pyao-server-128.png")
        proof["errors"] = errors
        proof["passed"] = (
            status == 0
            and all(proof[k] for k in ("visible", "version_without_redis", "closed"))
            and not errors
        )
        if supervisor.log.exists():
            (args.output / "server-version.log").write_bytes(supervisor.log.read_bytes())
    (args.output / "result.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))
    if not proof["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
