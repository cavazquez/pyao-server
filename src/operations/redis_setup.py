"""Orientación opcional y comprobaciones de sólo lectura para operadores de PyAO."""

import asyncio
import json
import shlex
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig

INSTALL = "https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/apt/"
INSIGHT = "https://redis.io/docs/latest/operate/redisinsight/install/install-on-desktop/"
STORE = "https://snapcraft.io/redisinsight"


def guide(config: RedisConfig | None = None) -> str:
    """Construye instrucciones sin leer archivos de secretos ni necesitar Redis.

    Returns:
        Guía local/remota, autenticación interactiva y GUI opcional.
    """
    host, port, db = (config.host, config.port, config.db) if config else ("localhost", 6379, 0)
    local = host in {"localhost", "127.0.0.1", "::1"}
    cli = f"redis-cli -h {shlex.quote(host)} -p {port} -n {db} --askpass"
    return f"""Puesta en marcha de Redis para el operador del servidor PyAO
Endpoint configurado: {json.dumps(host)}; puerto {port}; base {db}.
Modo: {"local" if local else "remoto"}. Una instancia ya configurada se conserva.
El cliente Godot no necesita instalar Redis ni Redis Insight.

Redis: usar Redis >= 7.2 con WAITAOF y AOF activado; la campaña del proyecto usa
Redis 8.10.2. Un servicio remoto debe soportar estas funciones y sus permisos.
Si ya tenés una instancia, no instales otra ni cambies sus datos.
Linux: seguir el repositorio APT oficial (paquete redis, origen packages.redis.io):
{INSTALL}
Alternativa Snap: revisar primero `snap info redis` y la versión/canal ofrecidos;
si cumple los requisitos, usar `sudo snap install redis --channel=latest/stable`.
Paquete oficial publicado por Redis/redislabs: https://snapcraft.io/redis
Documentación: https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/snap/
La instalación puede iniciar un servicio; revisá puertos y configuración antes.

Configurar [redis] host, port, db y password_file en el TOML de PyAO (o
PYAO_REDIS__HOST, PYAO_REDIS__PORT, PYAO_REDIS__DB, PYAO_REDIS__PASSWORD_FILE).
Guardar la contraseña en un archivo privado de una línea, legible por el servidor.
No pegarla en argumentos, URLs, historial ni reportes. En Snap usar una ruta dentro
de $SNAP_USER_COMMON y permisos 0600. Para instancias remotas usar red privada o
túnel seguro; PyAO no agrega TLS al enlace Redis por esta opción.

Verificar con autenticación interactiva, sin contraseña en la línea de comandos:
{cli} PING
{cli} INFO server
{cli} CONFIG GET appendonly appendfsync
Se espera PONG, Redis >= 7.2, appendonly=yes y appendfsync=everysec o always.
Habilitar AOF en el archivo persistente de configuración del servicio Redis y
respaldar su volumen; un PONG por sí solo no acredita persistencia.
Si un ACL impide INFO/CONFIG, pedir al administrador la comprobación; no ampliar
permisos automáticamente. --check-redis sólo lee PING/INFO/CONFIG, nunca escribe
barreras, semillas ni datos de la partida. PyAO exige WAITAOF antes de confirmar oro.

Redis Insight (GUI oficial opcional, no bloquea el juego ni el servidor sin GUI):
{INSIGHT}
Snap publicado por Redis (redislabs): {STORE}
Instalación opcional: sudo snap install redisinsight --channel=latest/stable
Almacén de credenciales opcional: sudo snap connect redisinsight:password-manager-service
Abrir Redis Insight y agregar una conexión con host {json.dumps(host)}, puerto {port}
y base {db}; introducir la contraseña en su campo privado, nunca en una URL.
Para acceso remoto usar el endpoint/túnel aprobado por el administrador.
Los programas externos los instala y configura el operador; PyAO no lo hace.
"""


async def check(config: RedisConfig) -> dict[str, Any]:
    """Consulta versión y política sin modificar la instancia ni mostrar secretos.

    Returns:
        Estado acotado, incluidas instrucciones accionables ante fallos.
    """
    client = None
    report: dict[str, Any] = {
        "ok": False,
        "mode": "local" if config.host in {"localhost", "127.0.0.1", "::1"} else "remote",
        "host": config.host,
        "port": config.port,
        "db": config.db,
        "read_only": True,
        "insight_required": False,
    }
    try:
        client = Redis(
            host=config.host,
            port=config.port,
            db=config.db,
            password=config.read_password(),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        async with asyncio.timeout(5):
            ping = await client.ping()
            server = await client.info("server")
            policy = await client.config_get("appendonly", "appendfsync")
        version = str(server.get("redis_version", "0.0"))
        compatible = tuple(int(v) for v in version.split(".")[:2]) >= (7, 2)
        report.update(
            version=version,
            appendonly=policy.get("appendonly"),
            appendfsync=policy.get("appendfsync"),
            authenticated=config.password_file is not None,
            ok=bool(ping)
            and compatible
            and policy.get("appendonly") == "yes"
            and policy.get("appendfsync") in {"everysec", "always"},
        )
        if not report["ok"]:
            report["message"] = (
                "Revisar versión y persistencia AOF con el administrador; ejecutar --redis-guide."
            )
    except RedisError, TimeoutError, OSError, ValueError:
        report["message"] = "Revisar endpoint, secreto y permisos; ejecutar --redis-guide."
    finally:
        if client:
            await client.aclose()
    return report
