"""Tests for the SSLManager utility."""

from __future__ import annotations

import re
import ssl
from pathlib import Path

import pytest

from src.security.ssl_manager import SSLConfigurationError, SSLManager


def test_disabled_manager_returns_none_context() -> None:
    """Ensure disabled manager returns None and does not resolve paths."""
    manager = SSLManager.disabled()

    manager.prepare()

    assert not manager.enabled
    assert manager.cert_path is None
    assert manager.key_path is None
    assert manager.build_context() is None


def test_prepare_requires_cert_and_key(tmp_path: Path) -> None:
    """Validate that both certificate and key must be provided together."""
    manager = SSLManager(
        enabled=True,
        cert_path=tmp_path / "cert.pem",
        key_path=None,
        auto_generate=False,
    )

    message = "Debes proporcionar tanto --ssl-cert como --ssl-key"
    with pytest.raises(SSLConfigurationError, match=message):
        manager.prepare()


def test_prepare_generates_self_signed_when_missing(tmp_path: Path) -> None:
    """Check that missing files trigger automatic certificate generation."""
    generated: list[tuple[Path, Path]] = []

    def fake_generator(cert_path: Path, key_path: Path) -> None:
        generated.append((cert_path, key_path))
        cert_path.parent.mkdir(parents=True, exist_ok=True)
        cert_path.write_text("certificate", encoding="utf-8")
        key_path.write_text("key", encoding="utf-8")

    cert_path = tmp_path / "ssl" / "server.crt"
    key_path = tmp_path / "ssl" / "server.key"

    manager = SSLManager(
        enabled=True,
        cert_path=None,
        key_path=None,
        default_cert_path=cert_path,
        default_key_path=key_path,
        auto_generate=True,
        certificate_generator=fake_generator,
    )

    manager.prepare()

    assert manager.cert_path == cert_path.resolve()
    assert manager.key_path == key_path.resolve()
    assert generated == [(cert_path.resolve(), key_path.resolve())]
    assert cert_path.exists()
    assert key_path.exists()


def test_prepare_with_input_paths_skips_generation(tmp_path: Path) -> None:
    """Confirm that providing custom paths skips generator invocation."""
    cert_path = tmp_path / "provided.crt"
    key_path = tmp_path / "provided.key"
    cert_path.write_text("certificate", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")

    def failing_generator(cert_path: Path, key_path: Path) -> None:  # noqa: ARG001
        message = "Generator should not be invoked when paths are provided"
        raise AssertionError(message)

    manager = SSLManager(
        enabled=True,
        cert_path=cert_path,
        key_path=key_path,
        auto_generate=True,
        certificate_generator=failing_generator,
    )

    manager.prepare()

    assert manager.cert_path == cert_path.resolve()
    assert manager.key_path == key_path.resolve()


def test_prepare_missing_files_without_autogen_raises(tmp_path: Path) -> None:
    """Ensure missing files raise when auto generation is disabled."""
    cert_path = tmp_path / "missing.crt"
    key_path = tmp_path / "missing.key"

    manager = SSLManager(
        enabled=True,
        cert_path=None,
        key_path=None,
        default_cert_path=cert_path,
        default_key_path=key_path,
        auto_generate=False,
    )

    message = "No se encontraron los archivos SSL proporcionados"
    with pytest.raises(SSLConfigurationError, match=message):
        manager.prepare()


def test_build_context_loads_cert_chain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify build_context loads certificate chain into SSL context."""
    created_contexts: list[DummyContext] = []

    class DummyContext:
        def __init__(self, protocol: int) -> None:
            self.protocol = protocol
            self.loaded: tuple[str, str] | None = None

        def load_cert_chain(self, certfile: str, keyfile: str) -> None:
            self.loaded = (certfile, keyfile)

    def fake_ssl_context(protocol: int) -> DummyContext:
        context = DummyContext(protocol)
        created_contexts.append(context)
        return context

    monkeypatch.setattr(ssl, "SSLContext", fake_ssl_context)

    cert_path = tmp_path / "context.crt"
    key_path = tmp_path / "context.key"

    def generator(cert_dest: Path, key_dest: Path) -> None:
        cert_dest.parent.mkdir(parents=True, exist_ok=True)
        cert_dest.write_text("certificate", encoding="utf-8")
        key_dest.write_text("key", encoding="utf-8")

    manager = SSLManager(
        enabled=True,
        cert_path=None,
        key_path=None,
        default_cert_path=cert_path,
        default_key_path=key_path,
        auto_generate=True,
        certificate_generator=generator,
    )

    manager.prepare()
    context = manager.build_context()

    assert isinstance(context, DummyContext)
    assert context.protocol == ssl.PROTOCOL_TLS_SERVER
    assert context.loaded == (str(cert_path.resolve()), str(key_path.resolve()))
    assert created_contexts == [context]


def test_build_context_requires_prepare(tmp_path: Path) -> None:
    """Check that build_context fails if prepare has not been executed."""
    cert_path = tmp_path / "missing.crt"
    key_path = tmp_path / "missing.key"

    manager = SSLManager(
        enabled=True,
        cert_path=cert_path,
        key_path=key_path,
        auto_generate=False,
    )

    message = "SSLManager.prepare() debe ejecutarse antes de build_context()."
    with pytest.raises(SSLConfigurationError, match=re.escape(message)):
        manager.build_context()
