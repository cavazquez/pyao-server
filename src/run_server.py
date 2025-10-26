"""Script para ejecutar el servidor de Argentum Online."""

import asyncio
import logging
import subprocess  # noqa: S404
import sys
from pathlib import Path

from src.server import ArgentumServer
from src.server_cli import ServerCLI

logger = logging.getLogger(__name__)

DEFAULT_CERT_PATH = Path("certs/server.crt")
DEFAULT_KEY_PATH = Path("certs/server.key")


def ensure_self_signed_cert(cert_path: Path, key_path: Path) -> None:
    """Genera un certificado autofirmado si no existe."""
    if cert_path.exists() and key_path.exists():
        return

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Generando certificado autofirmado (cert: %s, key: %s)",
        cert_path,
        key_path,
    )

    command = [
        "openssl",
        "req",
        "-x509",
        "-nodes",
        "-days",
        "365",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(key_path),
        "-out",
        str(cert_path),
        "-subj",
        "/CN=localhost",
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)  # noqa: S603
    except FileNotFoundError:
        logger.exception(
            "No se encontró 'openssl'. Instálalo o proporciona tus propios certificados SSL."
        )
        sys.exit(1)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - error externo
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        logger.exception("Falló la generación del certificado SSL: %s", stderr)
        sys.exit(1)


def main() -> None:
    """Punto de entrada principal del servidor."""
    cli = ServerCLI()
    args = cli.parse_args()

    # Configurar logging
    cli.configure_logging(args.debug)

    ssl_cert_path = Path(args.ssl_cert) if args.ssl_cert else DEFAULT_CERT_PATH
    ssl_key_path = Path(args.ssl_key) if args.ssl_key else DEFAULT_KEY_PATH

    if args.ssl:
        if (args.ssl_cert is None) != (args.ssl_key is None):
            logger.error(
                "Debes proporcionar tanto --ssl-cert como --ssl-key "
                "cuando usas rutas personalizadas."
            )
            sys.exit(1)

        if args.ssl_cert is None:
            ensure_self_signed_cert(ssl_cert_path, ssl_key_path)
        elif not ssl_cert_path.exists() or not ssl_key_path.exists():
            logger.error(
                "No se encontraron los archivos SSL proporcionados: %s o %s",
                ssl_cert_path,
                ssl_key_path,
            )
            sys.exit(1)

    # Mostrar información de inicio
    logger.info("Iniciando PyAO Server v%s...", cli.VERSION)
    logger.info("Host: %s | Puerto: %d", args.host, args.port)
    if args.ssl:
        logger.info(
            "SSL habilitado | Certificado: %s | Clave: %s",
            ssl_cert_path,
            ssl_key_path,
        )

    # Crear y ejecutar servidor
    server = ArgentumServer(
        host=args.host,
        port=args.port,
        enable_ssl=args.ssl,
        ssl_cert_path=str(ssl_cert_path),
        ssl_key_path=str(ssl_key_path),
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception:
        logger.exception("Error fatal")
        raise


if __name__ == "__main__":
    main()
