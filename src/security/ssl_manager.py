"""Gestión de configuración TLS/SSL para el servidor."""

from __future__ import annotations

import logging
import ssl
import subprocess  # noqa: S404
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class SSLConfigurationError(RuntimeError):
    """Error al preparar o inicializar la configuración SSL."""


CertificateGenerator = Callable[[Path, Path], None]


class SSLManager:
    """Encapsula la preparación de certificados y construcción de contextos SSL."""

    def __init__(
        self,
        *,
        enabled: bool,
        cert_path: Path | None,
        key_path: Path | None,
        default_cert_path: Path | None = None,
        default_key_path: Path | None = None,
        auto_generate: bool = True,
        certificate_generator: CertificateGenerator | None = None,
    ) -> None:
        """Inicializa el administrador de SSL con rutas y opciones de generación."""
        self._enabled = enabled
        self._input_cert_path = cert_path
        self._input_key_path = key_path
        self._default_cert_path = default_cert_path
        self._default_key_path = default_key_path
        self._auto_generate = auto_generate
        self._certificate_generator = certificate_generator or self._generate_self_signed

        self._resolved_cert_path: Path | None = None
        self._resolved_key_path: Path | None = None

    @classmethod
    def disabled(cls) -> SSLManager:
        """Retorna un manager deshabilitado (sin SSL).

        Returns:
            SSLManager: Instancia con SSL deshabilitado.
        """
        return cls(
            enabled=False,
            cert_path=None,
            key_path=None,
            auto_generate=False,
        )

    @property
    def enabled(self) -> bool:
        """Indica si SSL está habilitado."""
        return self._enabled

    @property
    def cert_path(self) -> Path | None:
        """Ruta final del certificado SSL."""
        return self._resolved_cert_path

    @property
    def key_path(self) -> Path | None:
        """Ruta a la clave privada SSL resuelta."""
        return self._resolved_key_path

    def prepare(self) -> None:
        """Resuelve rutas y genera certificados si es necesario.

        Raises:
            SSLConfigurationError: Si la configuración es inconsistente o faltan archivos.
        """
        if not self._enabled:
            return

        if (self._input_cert_path is None) != (self._input_key_path is None):
            message = (
                "Debes proporcionar tanto --ssl-cert como --ssl-key cuando usas rutas "
                "personalizadas."
            )
            raise SSLConfigurationError(message)

        resolved_cert = self._input_cert_path or self._default_cert_path
        resolved_key = self._input_key_path or self._default_key_path

        if resolved_cert is None or resolved_key is None:
            message = (
                "No se especificaron rutas de certificado/clave y no hay valores por "
                "defecto configurados."
            )
            raise SSLConfigurationError(message)

        resolved_cert = resolved_cert.expanduser().resolve()
        resolved_key = resolved_key.expanduser().resolve()

        self._resolved_cert_path = resolved_cert
        self._resolved_key_path = resolved_key

        if self._input_cert_path is None and self._auto_generate:
            if not resolved_cert.exists() or not resolved_key.exists():
                logger.info(
                    "Generando certificado autofirmado (cert: %s, key: %s)",
                    resolved_cert,
                    resolved_key,
                )
                resolved_cert.parent.mkdir(parents=True, exist_ok=True)
                self._certificate_generator(resolved_cert, resolved_key)
        elif not resolved_cert.exists() or not resolved_key.exists():
            message = (
                "No se encontraron los archivos SSL proporcionados: "
                f"{resolved_cert} o {resolved_key}"
            )
            raise SSLConfigurationError(message)

    def build_context(self) -> ssl.SSLContext | None:
        """Construye un contexto SSL listo para usarse.

        Returns:
            ssl.SSLContext | None: Contexto configurado si SSL está habilitado, o None.

        Raises:
            SSLConfigurationError: Si `prepare()` no fue ejecutado, o si ocurren errores al cargar
                el certificado y la clave.
        """
        if not self._enabled:
            return None

        if self._resolved_cert_path is None or self._resolved_key_path is None:
            message = "SSLManager.prepare() debe ejecutarse antes de build_context()."
            raise SSLConfigurationError(message)

        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(self._resolved_cert_path), str(self._resolved_key_path))
        except FileNotFoundError as exc:
            message = "No se encontró el archivo de certificado o clave privada"
            raise SSLConfigurationError(message) from exc
        except ssl.SSLError as exc:  # pragma: no cover - depende del entorno SSL
            message = "Error inicializando el contexto SSL"
            raise SSLConfigurationError(message) from exc
        else:
            return context

    @staticmethod
    def _generate_self_signed(cert_path: Path, key_path: Path) -> None:
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
        except FileNotFoundError as exc:
            message = (
                "No se encontró 'openssl'. Instálalo o proporciona tus propios certificados SSL."
            )
            raise SSLConfigurationError(message) from exc
        except subprocess.CalledProcessError as exc:  # pragma: no cover - error externo
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            message = f"Falló la generación del certificado SSL: {stderr}"
            raise SSLConfigurationError(message) from exc
