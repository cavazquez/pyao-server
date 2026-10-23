"""Anuncios persistidos con TTL y solicitudes que terminan en invitaciones normales."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from redis.exceptions import WatchError

from src.constants.gameplay import MAX_PARTY_MEMBERS
from src.services.expansion.pages import bounded_pages
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

ACTIVITIES = frozenset({"caza", "recoleccion", "misiones", "social"})
INDEX = "finder:index"
PAGE_SIZE = 4
MAX_ANNOUNCEMENTS = 2000
MAX_LEVEL = 100
MAX_PAGE = 1000
MAX_MAP = 10000
MAX_REQUESTS = 10
REQUEST_SECONDS = 120
MIN_AD_SECONDS = 30
MAX_AD_SECONDS = 1800
MAX_AD_TEXT = 120


def live_requests(raw: str | bytes | None) -> dict[str, dict[str, Any]]:
    """Conserva sólo las solicitudes vigentes del documento acotado del grupo.

    Returns:
        Solicitudes por usuario, con vencimientos independientes del TTL del documento.
    """
    now = time.time()
    requests: dict[str, dict[str, Any]] = json.loads(raw or "{}")
    return {user: row for user, row in requests.items() if float(row["expires"]) > now}


class PartyFinder:
    """Un anuncio no crea grupos ni permite omitir consentimiento o cupos."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte PartyService para emitir las invitaciones autorizadas."""
        self.deps = deps

    async def active(self, party_id: int) -> dict[str, Any] | None:
        """Revalida liderazgo y cupo incluso si el TTL del anuncio no terminó.

        Returns:
            Anuncio vigente o None después de retirar un índice obsoleto.
        """
        redis = self.deps.redis_client.redis
        raw, party_raw = await redis.mget(f"finder:ad:{party_id}", f"party:{party_id}")
        ad = json.loads(raw) if raw else {}
        party = json.loads(party_raw) if party_raw else {}
        count = await redis.hlen(f"party:{party_id}:members") if party else 0
        if (
            not ad
            or not party
            or int(party.get("leader_id", 0)) != int(ad.get("leader", 0))
            or count >= MAX_PARTY_MEMBERS
            or float(ad.get("expires", 0)) <= time.time()
        ):
            async with redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(
                        f"finder:ad:{party_id}", f"party:{party_id}", f"party:{party_id}:members"
                    )
                    if (
                        await pipe.get(f"finder:ad:{party_id}") == raw
                        and await pipe.get(f"party:{party_id}") == party_raw
                        and await pipe.hlen(f"party:{party_id}:members") == count
                    ):
                        pipe.multi()  # type: ignore[no-untyped-call]
                        pipe.delete(f"finder:ad:{party_id}")
                        pipe.srem(INDEX, str(party_id))
                        await pipe.execute()
                except WatchError:
                    pass  # Un anuncio recién publicado pertenece a la consulta siguiente.
            return None
        return {**ad, "free": MAX_PARTY_MEMBERS - count}

    async def snapshot(self, user: int, params: dict[str, Any]) -> dict[str, Any]:
        """Filtra un índice acotado, sin KEYS ni perfiles privados.

        Returns:
            Página estable de anuncios válidos y solicitudes del líder autenticado.

        Raises:
            ValueError: Por filtros inválidos o un índice fuera del límite.
        """
        minimum, maximum, page = (
            int(params.get("min_level", 1)),
            int(params.get("max_level", 100)),
            int(params.get("page", 0)),
        )
        activity, map_id = str(params.get("activity", "")), int(params.get("map", 0))
        if (
            not 1 <= minimum <= maximum <= MAX_LEVEL
            or not 0 <= page <= MAX_PAGE
            or (activity and activity not in ACTIVITIES)
            or not 0 <= map_id <= MAX_MAP
        ):
            message = "Filtros de búsqueda inválidos"
            raise ValueError(message)
        redis = self.deps.redis_client.redis
        ids = []
        async for value in redis.sscan_iter(INDEX, count=100):
            ids.append(int(value))
            if len(ids) > MAX_ANNOUNCEMENTS:
                message = "El índice supera el límite de anuncios"
                raise ValueError(message)
        rows = []
        for party_id in sorted(ids):
            ad = await self.active(party_id)
            if ad is None:
                continue
            if activity and ad["activity"] != activity:
                continue
            if map_id and ad["map"] != map_id:
                continue
            if ad["max_level"] >= minimum and ad["min_level"] <= maximum:
                rows.append(ad)
        own = await self.deps.party_repo.get_user_party(user)
        requests = []
        if own and own.leader_id == user:
            raw = await redis.get(f"finder:requests:{own.party_id}")
            requests = list(live_requests(raw).values())
        chunks = bounded_pages(rows, PAGE_SIZE, 2000)
        pages = len(chunks)
        page = min(page, pages - 1)
        return {
            "rows": chunks[page],
            "page": page,
            "pages": pages,
            "party": own.party_id if own else 0,
            "leader": bool(own and own.leader_id == user),
            "requests": bounded_pages(requests, MAX_REQUESTS, 900)[0],
            "activities": sorted(ACTIVITIES),
        }

    async def command(
        self, user: int, action: str, params: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        """Publica, cierra o solicita ingreso sin crear membresías directamente.

        Returns:
            Resultado confirmado y mensaje de interfaz.
        """
        own = await self.deps.party_repo.get_user_party(user)
        party_id = int(params.get("party", own.party_id if own else 0))
        if party_id < 1:
            return {"applied": False, "message": "Primero debes crear o seleccionar un grupo."}
        if action == "invite":
            if (
                not own
                or own.party_id != party_id
                or own.leader_id != user
                or await self.active(party_id) is None
            ):
                return {
                    "applied": False,
                    "message": "Sólo el líder del anuncio vigente puede invitar.",
                }
            raw = await self.deps.redis_client.redis.get(f"finder:requests:{party_id}")
            request = live_requests(raw).get(str(int(params["user"])))
            if request is None:
                return {"applied": False, "message": "La solicitud venció."}
            message = await self.deps.party_service.invite_to_party(user, request["name"])
            invitation = await self.deps.party_repo.get_invitation(int(params["user"]), party_id)
            return {
                "applied": bool(invitation and invitation.inviter_id == user),
                "message": message,
            }
        ad_key, group_key, members_key, user_key = (
            f"finder:ad:{party_id}",
            f"party:{party_id}",
            f"party:{party_id}:members",
            f"user:{user}:party",
        )
        stats_key, position_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
        request_key = f"finder:requests:{party_id}"
        seconds = int(params.get("seconds", 600))
        if action == "publish" and not MIN_AD_SECONDS <= seconds <= MAX_AD_SECONDS:
            return {"applied": False, "message": "El anuncio debe durar entre 30 y 1800 segundos."}
        resources = (
            Resource(
                ad_key,
                "string",
                ttl_seconds=seconds if action == "publish" else 1 if action == "close" else None,
                keep_ttl=action not in {"publish", "close"},
            ),
            Resource(group_key, "string"),
            Resource(members_key, "hash"),
            Resource(user_key, "string"),
            Resource(stats_key, "hash"),
            Resource(position_key, "hash"),
            Resource(INDEX, "set"),
            Resource(
                request_key, "string", ttl_seconds=REQUEST_SECONDS, deletable=action == "close"
            ),
        )

        def decide(snapshot: Snapshot) -> Decision:
            party = json.loads(str(snapshot[group_key] or "{}"))
            members = cast("dict[str, str]", snapshot[members_key])
            ad = json.loads(str(snapshot[ad_key] or "{}"))
            stats = cast("dict[str, str]", snapshot[stats_key])
            pos = cast("dict[str, str]", snapshot[position_key])
            if not party or int(stats.get("min_hp", 0)) <= 0:
                return Decision(
                    {"applied": False, "message": "Grupo inexistente o personaje muerto."}, {}
                )
            ids = cast("set[str]", snapshot[INDEX]).copy()
            if action in {"publish", "close"}:
                if int(party["leader_id"]) != user or str(snapshot[user_key]) != str(party_id):
                    return Decision(
                        {
                            "applied": False,
                            "message": "Sólo el líder puede administrar el anuncio.",
                        },
                        {},
                    )
                if action == "close":
                    ids.discard(str(party_id))
                    return Decision(
                        {"applied": True, "message": "Anuncio cerrado."},
                        {ad_key: "", INDEX: ids, request_key: None},
                    )
                lo, hi = int(params["min_level"]), int(params["max_level"])
                has_capacity = len(members) < MAX_PARTY_MEMBERS and (
                    len(ids) < MAX_ANNOUNCEMENTS or str(party_id) in ids
                )
                if (
                    not 1 <= lo <= hi <= MAX_LEVEL
                    or params["activity"] not in ACTIVITIES
                    or not MIN_AD_SECONDS <= seconds <= MAX_AD_SECONDS
                    or len(str(params["text"])) > MAX_AD_TEXT
                    or not has_capacity
                ):
                    return Decision(
                        {"applied": False, "message": "Anuncio inválido o grupo completo."}, {}
                    )
                ad = {
                    "id": party_id,
                    "leader": user,
                    "name": party["leader_username"],
                    "map": int(pos.get("map", 0)),
                    "min_level": lo,
                    "max_level": hi,
                    "activity": params["activity"],
                    "text": params["text"],
                    "expires": int(time.time()) + seconds,
                }
                ids.add(str(party_id))
                return Decision(
                    {"applied": True, "message": "Anuncio publicado."},
                    {ad_key: json.dumps(ad), INDEX: ids},
                )
            if action != "request" or snapshot[user_key] or not ad:
                return Decision(
                    {"applied": False, "message": "La solicitud no está permitida."}, {}
                )
            if (
                int(ad.get("leader", 0)) != int(party["leader_id"])
                or len(members) >= MAX_PARTY_MEMBERS
                or float(ad.get("expires", 0)) <= time.time()
                or not int(ad["min_level"]) <= int(stats.get("level", 0)) <= int(ad["max_level"])
            ):
                return Decision(
                    {"applied": False, "message": "El anuncio cambió o no cumples los requisitos."},
                    {},
                )
            requests = live_requests(str(snapshot[request_key] or "{}"))
            if str(user) not in requests and len(requests) >= MAX_REQUESTS:
                return Decision(
                    {"applied": False, "message": "El grupo ya tiene diez solicitudes pendientes."},
                    {},
                )
            requests[str(user)] = {
                "id": user,
                "name": self.deps.map_manager.get_player_username(user) or "",
                "level": int(stats["level"]),
                "expires": int(time.time()) + REQUEST_SECONDS,
            }
            return Decision(
                {"applied": True, "message": "Solicitud enviada; el líder puede invitarte."},
                {request_key: json.dumps(requests)},
            )

        return await transact(
            self.deps.redis_client.redis,
            resources,
            identity,
            {"finder": action, "params": params, "user": user},
            decide,
        )
