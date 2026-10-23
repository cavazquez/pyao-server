"""Ensayo de durabilidad con Redis real y recursos completamente descartables."""

import json
from typing import Any

from redis.exceptions import AuthenticationError

from redis import Redis
from src.operations.redis_sandbox import RedisSandbox, docker


def require(condition: bool, label: str) -> None:
    """Rechaza una comprobación fallida incluso al ejecutar Python con -O.

    Raises:
        RuntimeError: Si el resultado no coincide con la política esperada.
    """
    if not condition:
        msg = f"Falló la validación Redis: {label}"
        raise RuntimeError(msg)


def validate_persistence() -> dict[str, Any]:
    """Comprueba política efectiva, reinicio limpio y caída tras fsync confirmado.

    Returns:
        Evidencia sin credenciales ni datos de jugadores reales.

    Raises:
        RuntimeError: Si una política o comprobación de durabilidad falla.
    """
    with RedisSandbox() as sandbox:
        with sandbox.client() as client:
            policy = client.config_get("appendonly", "appendfsync", "dir", "save", "protected-mode")
            require(policy["protected-mode"] == "yes", "modo protegido")
            require(policy["appendonly"] == "yes", "política efectiva")
            require(policy["appendfsync"] == "always", "política efectiva")
            require(policy["dir"] == "/data", "política efectiva")
            require(policy["save"] == "900 1 300 10 60 10000", "política efectiva")
            version = client.info("server")["redis_version"]
            client.hset(
                "account:PersistenceTest:data",
                mapping={"user_id": "1", "username": "PersistenceTest"},
            )
            client.hset(
                "player:1:stats", mapping={"gold": "1234", "level": "7", "experience": "431"}
            )
            client.hset("inventory:1", mapping={"slot_30": "1:2"})
        with Redis(host="127.0.0.1", port=sandbox.port, socket_timeout=2) as anonymous:
            try:
                anonymous.ping()
            except AuthenticationError:
                pass
            else:
                msg = "El perfil persistente aceptó una conexión sin autenticación"
                raise RuntimeError(msg)
        docker("restart", "--time", "5", sandbox.name)
        with sandbox.client() as client:
            require(client.hget("player:1:stats", "gold") == "1234", "estado conservado")
            require(client.hget("inventory:1", "slot_30") == "1:2", "estado conservado")
            client.set("validation:confirmed-fsync", "preserved")
            fsync = client.execute_command("WAITAOF", 1, 0, 5000)
            require(fsync[0] == 1, "estado conservado")
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client() as client:
            require(client.get("validation:confirmed-fsync") == "preserved", "estado conservado")
            require(client.hget("player:1:stats", "gold") == "1234", "estado conservado")
            require(client.hget("inventory:1", "slot_30") == "1:2", "estado conservado")
        return {
            "image": sandbox.image,
            "redis_version": version,
            "policy": policy,
            "clean_restart": True,
            "process_crash_after_fsync": True,
            "unauthenticated_rejected": True,
            "production_data_used": False,
        }


if __name__ == "__main__":
    print(json.dumps(validate_persistence(), ensure_ascii=False, indent=2))
