"""Redis descartable con nombre/volumen propios y publicación sólo en loopback."""

import json
import shutil
import subprocess  # noqa: S404 - CLI local de operación sin shell.
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Self
from uuid import uuid4

from redis import ConnectionError as RedisConnectionError
from redis import Redis
from src.operations.redis_secret import create_secret


def docker(*arguments: str) -> str:
    """Ejecuta un comando Docker sin shell y con plazo acotado.

    Returns:
        Salida estándar, sin datos de Redis.

    Raises:
        RuntimeError: Si Docker no está instalado.
    """
    executable = shutil.which("docker")
    if executable is None:
        msg = "Se requiere Docker para el ensayo aislado"
        raise RuntimeError(msg)
    return subprocess.run(  # noqa: S603 - argumentos separados, sin shell.
        [executable, *arguments], check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


class RedisSandbox:
    """Administra únicamente recursos aleatorios creados por esta instancia."""

    def __init__(self, *, appendonly: bool = True) -> None:
        """Prepara identidades nuevas, sin acceder a Redis del operador."""
        self.root = Path(__file__).resolve().parents[2]
        self.image = (
            (self.root / "redis/Dockerfile").read_text().splitlines()[0].removeprefix("FROM ")
        )
        identity = uuid4().hex
        self.name = f"pyao-validation-{identity}"
        self.volume = f"pyao-validation-data-{identity}"
        self.appendonly = appendonly
        self._secrets = TemporaryDirectory(prefix="pyao-redis-secret-")
        self.password_file = Path(self._secrets.name) / "redis-password"
        create_secret(self.password_file)
        self._password = self.password_file.read_text().strip()
        self._container_created = False
        self._volume_created = False

    def __enter__(self) -> Self:
        """Inicia Redis con un volumen nuevo y un puerto aleatorio local.

        Returns:
            Sandbox listo para recibir conexiones.
        """
        try:
            docker("volume", "create", "--label", "proyectoao=validation", self.volume)
            self._volume_created = True
            docker(
                "create",
                "--name",
                self.name,
                "--label",
                "proyectoao=validation",
                "-p",
                "127.0.0.1::6379",
                "--entrypoint",
                "/etc/pyao-entrypoint.sh",
                "--mount",
                f"type=bind,src={self.root / 'redis/entrypoint.sh'},"
                "dst=/etc/pyao-entrypoint.sh,readonly",
                "--mount",
                f"type=bind,src={self.password_file},dst=/run/secrets/redis_password,readonly",
                "--mount",
                f"type=volume,src={self.volume},dst=/data",
                "--mount",
                f"type=bind,src={self.root / 'redis/redis.conf'},dst=/etc/pyao-redis.conf,readonly",
                self.image,
                "redis-server",
                "/etc/pyao-redis.conf",
                "--aclfile",
                "/data/pyao-users.acl",
                "--appendonly",
                "yes" if self.appendonly else "no",
            )
            self._container_created = True
            docker("start", self.name)
            with self.client() as client:
                client.ping()
        except BaseException:
            try:
                if self._container_created:
                    print(docker("logs", self.name), file=sys.stderr)
            finally:
                self.close()
            raise
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Retira el contenedor y volumen propios incluso si falla la validación."""
        self.close()

    @property
    def port(self) -> int:
        """Puerto local asignado por Docker, nunca el Redis de desarrollo.

        Raises:
            RuntimeError: Si Docker publicó en una interfaz distinta de loopback.
        """
        bindings = json.loads(
            docker("inspect", self.name, "--format", "{{json .NetworkSettings.Ports}}")
        )
        published = bindings["6379/tcp"]
        if len(published) != 1 or published[0]["HostIp"] != "127.0.0.1":
            msg = "La validación requiere un único bind en loopback"
            raise RuntimeError(msg)
        return int(published[0]["HostPort"])

    def client(self) -> Redis:
        """Espera el arranque con plazo y crea un cliente contra el endpoint propio.

        Returns:
            Cliente listo; el llamador debe cerrarlo.

        Raises:
            TimeoutError: Si Redis no responde en diez segundos.
        """
        client = Redis(
            host="127.0.0.1",
            port=self.port,
            decode_responses=True,
            password=self._password,
            socket_connect_timeout=1,
            socket_timeout=10,
        )
        deadline = time.monotonic() + 10
        last_error: RedisConnectionError | None = None
        while time.monotonic() < deadline:
            try:
                if client.ping():
                    return client
            except RedisConnectionError as error:
                last_error = error
                time.sleep(0.1)
        client.close()
        msg = "Redis descartable no respondió al arranque"
        raise TimeoutError(msg) from last_error

    def close(self) -> None:
        """Elimina exclusivamente los recursos cuyo alta completó esta instancia."""
        try:
            if self._container_created:
                docker("rm", "-f", self.name)
                self._container_created = False
        finally:
            if self._volume_created:
                docker("volume", "rm", self.volume)
                self._volume_created = False
            self._secrets.cleanup()
