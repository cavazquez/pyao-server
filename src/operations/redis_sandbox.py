"""Redis descartable con nombre/volumen propios y publicación sólo en loopback."""

import json
import shutil
import subprocess  # noqa: S404 - CLI local de operación sin shell.
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Literal, Self
from uuid import uuid4

from redis import ConnectionError as RedisConnectionError
from redis import Redis
from src.config.game_config import RedisConfig
from src.operations.redis_secret import create_secret
from src.runtime_paths import resource_root


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

    def __init__(
        self,
        *,
        appendonly: bool = True,
        password_file: Path | None = None,
        purpose: Literal["validation", "recovery"] = "validation",
    ) -> None:
        """Prepara identidades nuevas, sin acceder a Redis del operador."""
        self.root = resource_root()
        self.image = (
            (self.root / "redis/Dockerfile").read_text().splitlines()[0].removeprefix("FROM ")
        )
        identity = uuid4().hex
        self.name = f"pyao-{purpose}-{identity}"
        self.volume = f"pyao-{purpose}-data-{identity}"
        self.purpose = purpose
        self.appendonly = appendonly
        self._secrets: TemporaryDirectory[str] | None = None
        if password_file is None:
            self._secrets = TemporaryDirectory(prefix="pyao-redis-secret-")
            password_file = Path(self._secrets.name) / "redis-password"
            create_secret(password_file)
        self.password_file = password_file.resolve()
        self._password = RedisConfig(password_file=self.password_file).read_password()
        self._container_created = False
        self._volume_created = False

    def __enter__(self) -> Self:
        """Inicia Redis con un volumen nuevo y un puerto aleatorio local.

        Returns:
            Sandbox listo para recibir conexiones.
        """
        try:
            docker("volume", "create", "--label", f"proyectoao={self.purpose}", self.volume)
            self._volume_created = True
            self._start_container()
        except BaseException:
            try:
                if self._container_created:
                    print(docker("logs", self.name), file=sys.stderr)
            finally:
                self.close()
            raise
        return self

    def _start_container(self) -> None:
        """Crea el contenedor propio sobre su volumen y espera Redis."""
        docker(
            "create",
            "--name",
            self.name,
            "--label",
            f"proyectoao={self.purpose}",
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

    def client(self, *, decode_responses: bool = True) -> Redis:
        """Espera el arranque con plazo y crea un cliente contra el endpoint propio.

        Returns:
            Cliente listo; el llamador debe cerrarlo.

        Raises:
            TimeoutError: Si Redis no responde en diez segundos.
        """
        client = Redis(
            host="127.0.0.1",
            port=self.port,
            decode_responses=decode_responses,
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

    def recreate(self, *, appendonly: bool) -> None:
        """Recrea sólo el contenedor propio conservando su volumen y secreto."""
        docker("stop", "--time", "5", self.name)
        docker("rm", self.name)
        self._container_created = False
        self.appendonly = appendonly
        self._start_container()

    def retain(self) -> None:
        """Entrega una restauración verificada al operador sin eliminar sus recursos.

        Raises:
            RuntimeError: Si el secreto pertenece a un directorio temporal.
        """
        if self._secrets is not None:
            msg = "Conservar una restauración requiere un archivo de secreto permanente"
            raise RuntimeError(msg)
        self._container_created = False
        self._volume_created = False

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
            if self._secrets is not None:
                self._secrets.cleanup()
