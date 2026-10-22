"""Contexto autenticado y utilidades comunes de comandos clásicos."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.security.account_bans import is_blocked
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

SELECTION_RANGE = 10

if TYPE_CHECKING:
    from collections.abc import Callable

    from redis.asyncio import Redis

    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC


class ChatCommandError(ValueError):
    """Error público redactado por el servidor, sin reflejar argumentos sensibles."""


@dataclass(slots=True)
class ChatContext:
    """Identidad de sesión, emisor y servicios; el texto nunca elige al actor."""

    deps: DependencyContainer
    user: int
    sender: MessageSender
    command: str
    arguments: str
    gm: bool = False

    @property
    def redis(self) -> Redis:
        """Devuelve la conexión Redis de la partida.

        Returns:
            Redis compartido, nunca una conexión elegida por el cliente.
        """
        return self.deps.redis_client.redis

    @property
    def key(self) -> str:
        """Devuelve la clave de estado del personaje autenticado.

        Returns:
            Clave de estadísticas del actor.
        """
        return RedisKeys.player_user_stats(self.user)

    async def tell(self, text: str) -> None:
        """Responde exclusivamente a la conexión que ejecutó el comando."""
        await self.sender.send_multiline_console_msg(text)

    async def stats(self) -> dict[str, str]:
        """Lee el estado actual para validar la operación.

        Returns:
            Campos persistidos del actor.
        """
        return cast("dict[str, str]", await self.redis.hgetall(self.key))

    async def read_hash(self, key: str) -> dict[str, str]:
        """Lee un hash con decode_responses, como los repositorios de la partida.

        Returns:
            Campos de texto de Redis.
        """
        return cast("dict[str, str]", await self.redis.hgetall(key))

    async def alive(self) -> None:
        """Exige que el personaje esté vivo.

        Raises:
            ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
        """
        if int((await self.stats()).get("min_hp", 0)) <= 0:
            message = "¡Estás muerto!"
            raise ChatCommandError(message)

    async def position(self) -> dict[str, int]:
        """Lee la posición autoritativa del personaje.

        Returns:
            Mapa y coordenadas del actor.

        Raises:
            ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
        """
        position = await self.deps.player_repo.get_position(self.user)
        if not position:
            message = "No se encontró tu posición."
            raise ChatCommandError(message)
        return position

    async def npc(self) -> NPC:
        """Resuelve la selección por instancia y comprueba mapa y distancia actuales.

        Returns:
            NPC seleccionado actualmente dentro de alcance.

        Raises:
            ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
        """
        target = cast("dict[str, str]", await self.redis.hgetall(f"chat:target:{self.user}"))
        position = await self.position()
        npc = self.deps.map_manager.get_npc_by_char_index(
            position["map"], int(target.get("index", 0))
        )
        if npc is None or npc.instance_id != target.get("npc"):
            message = "Primero selecciona un NPC del mapa."
            raise ChatCommandError(message)
        if max(abs(npc.x - position["x"]), abs(npc.y - position["y"])) > SELECTION_RANGE:
            message = "Estás demasiado lejos."
            raise ChatCommandError(message)
        return npc

    async def selected_user(self) -> int:
        """Resuelve un jugador seleccionado y vuelve a validar su posición.

        Returns:
            Identidad del jugador objetivo próximo.

        Raises:
            ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
        """
        target = cast("dict[str, str]", await self.redis.hgetall(f"chat:target:{self.user}"))
        user = int(target.get("user", 0))
        position = await self.position()
        other = await self.deps.player_repo.get_position(user) if user else None
        if (
            not other
            or other["map"] != position["map"]
            or max(abs(other["x"] - position["x"]), abs(other["y"] - position["y"]))
            > SELECTION_RANGE
            or self.deps.map_manager.get_player_message_sender(user) is None
        ):
            message = "Primero selecciona un jugador cercano."
            raise ChatCommandError(message)
        return user

    async def account(self, name: str) -> dict[str, str]:
        """Resuelve una cuenta por nombre, sin enumerar ni confiar en un ID recibido.

        Returns:
            Cuenta existente del objetivo.

        Raises:
            ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
        """
        account = await self.deps.account_repo.get_account(name)
        if not account:
            message = "Jugador no encontrado."
            raise ChatCommandError(message)
        return account

    async def commit(
        self,
        resources: tuple[Resource, ...],
        request: dict[str, Any],
        decide: Callable[[Snapshot], Decision],
        *,
        identity: str | None = None,
    ) -> dict[str, Any]:
        """Confirma recursos y recibo; una operación GM revalida el rol bajo WATCH.

        Returns:
            Resultado confirmado sin repetir el cambio ante respuesta incierta.
        """
        actor = await self.deps.account_repo.get_account_by_user_id(self.user) if self.gm else None
        actor_key = RedisKeys.account_data(actor["username"]) if actor else ""
        if self.gm and not actor_key:
            return {"applied": False, "message": "No tienes permisos de Game Master."}
        if actor_key and actor_key not in {resource.key for resource in resources}:
            resources = (*resources, Resource(actor_key, "hash"))

        def guarded(snapshot: Snapshot) -> Decision:
            if actor_key:
                fields = cast("dict[str, str]", snapshot[actor_key])
                if (
                    fields.get("is_gm") != "1"
                    or int(fields.get("user_id", 0)) != self.user
                    or is_blocked(fields, prefix="ban_")
                ):
                    return Decision({"applied": False, "message": "Los permisos cambiaron."}, {})
            return decide(snapshot)

        await require_durable(self.redis)
        result = await transact(
            self.redis,
            resources,
            identity or operation_id(),
            {"chat": self.command, "actor": self.user, **request},
            guarded,
        )
        await require_durable(self.redis)
        return result

    async def commit_near(
        self,
        npc: NPC,
        resources: tuple[Resource, ...],
        request: dict[str, Any],
        decide: Callable[[Snapshot], Decision],
        *,
        distance: int = 3,
    ) -> dict[str, Any]:
        """Revalida selección, instancia y distancia junto con el cambio de recursos.

        Returns:
            Resultado confirmado o rechazo sin cobro ni curación remota.
        """
        position_key = RedisKeys.player_position(self.user)
        npc_key = RedisKeys.npc_instance(npc.instance_id)
        selection_key = f"chat:target:{self.user}"
        watched = tuple(
            {
                resource.key: resource
                for resource in (
                    *resources,
                    Resource(position_key, "hash"),
                    Resource(npc_key, "hash"),
                    Resource(selection_key, "hash"),
                )
            }.values()
        )

        def guarded(snapshot: Snapshot) -> Decision:
            pos = cast("dict[str, str]", snapshot[position_key])
            current = cast("dict[str, str]", snapshot[npc_key])
            selection = cast("dict[str, str]", snapshot[selection_key])
            valid = (
                current.get("instance_id") == npc.instance_id
                and selection.get("npc") == npc.instance_id
                and int(current.get("npc_id", 0)) == npc.npc_id
                and int(current.get("map_id", 0)) == int(pos.get("map", -1))
                and max(
                    abs(int(current.get("x", 0)) - int(pos.get("x", -100))),
                    abs(int(current.get("y", 0)) - int(pos.get("y", -100))),
                )
                <= distance
                and (int(current.get("max_hp", 0)) == 0 or int(current.get("hp", 0)) > 0)
            )
            if not valid:
                return Decision(
                    {
                        "applied": False,
                        "message": "El NPC seleccionado cambió o está fuera de alcance.",
                    },
                    {},
                )
            return decide(snapshot)

        return await self.commit(watched, {**request, "npc": npc.instance_id}, guarded)


def integer(value: str, minimum: int, maximum: int) -> int:
    """Valida un entero acotado antes de usarlo en Redis o serializarlo.

    Returns:
        Entero válido.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    number = int(value)
    if not minimum <= number <= maximum:
        message = f"El valor debe estar entre {minimum} y {maximum}."
        raise ChatCommandError(message)
    return number
