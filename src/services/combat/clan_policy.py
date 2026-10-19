"""Relación entre clanes observada junto con el golpe o hechizo."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from src.utils.resource_transaction import Resource, Snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True)
class ClanCombat:
    """Congela identidades; un cambio de afiliación invalida esta intención."""

    users: tuple[int, int]
    clans: tuple[int, int]

    @classmethod
    async def prepare(cls, redis: Redis, source: int, target: int) -> ClanCombat:
        """Obtiene las claves que el commit deberá observar.

        Returns:
            Contexto cuya autoridad se comprueba nuevamente bajo WATCH.
        """
        values = await redis.mget(f"user:{source}:clan", f"user:{target}:clan")
        return cls((source, target), (int(values[0] or 0), int(values[1] or 0)))

    @property
    def pair_key(self) -> str:
        """Devuelve la clave única de ambos sentidos.

        Returns:
            Relación bilateral ordenada por clan.
        """
        return f"clan:relation:{min(self.clans)}:{max(self.clans)}"

    @property
    def resources(self) -> tuple[Resource, ...]:
        """Define afiliaciones, miembros, existencia y relación observados juntos.

        Returns:
            Recursos adicionales de sólo lectura del plan de combate.
        """
        return tuple(
            {
                r.key: r
                for r in (
                    *(Resource(f"user:{user}:clan", "string") for user in self.users),
                    *(
                        r
                        for clan in set(self.clans) - {0}
                        for r in (
                            Resource(f"clan:{clan}", "string"),
                            Resource(f"clan:{clan}:members", "hash"),
                        )
                    ),
                    Resource(self.pair_key, "hash"),
                )
            }.values()
        )

    def relationship(self, snapshot: Snapshot) -> str:
        """Revalida las identidades antes de interpretar una guerra.

        Returns:
            same, alliance, war, neutral o changed para rechazar el intento.
        """
        for user, clan in zip(self.users, self.clans, strict=True):
            if int(cast("str | None", snapshot[f"user:{user}:clan"]) or 0) != clan:
                return "changed"
            if clan and (
                not snapshot[f"clan:{clan}"]
                or str(user) not in cast("dict[str, str]", snapshot[f"clan:{clan}:members"])
            ):
                return "changed"
        if self.clans[0] and self.clans[0] == self.clans[1]:
            return "same"
        if not all(self.clans):
            return "neutral"
        return cast("dict[str, str]", snapshot[self.pair_key]).get("state", "neutral")
