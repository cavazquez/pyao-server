"""Lanzamiento de área: objetivos congelados y un único coste/commit."""

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from src.services.combat.spell_plan import MAX_RANGE, CastRequest, SpellPlan
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from src.services.combat.pvp_policy import PvpPolicy


class AreaSpellPlan(SpellPlan):
    """Compone efectos individuales sin repetir materiales ni entrenamiento."""

    def __init__(
        self,
        request: CastRequest,
        spell: dict[str, Any],
        policy: PvpPolicy,
        targets: list[CastRequest],
    ) -> None:
        """Congela una lista ordenada y única; el snapshot filtra blancos inválidos."""
        super().__init__(request, spell, policy)
        self.targets = [SpellPlan(target, spell, policy) for target in targets]
        for target in self.targets:
            target.charge_cost = False
            target.train = False
        self.resources = tuple(
            {
                r.key: r
                for r in (
                    *self.resources,
                    *(resource for target in self.targets for resource in target.resources),
                )
            }.values()
        )

    async def prepare_relations(self, redis: Redis) -> None:
        """Observa las relaciones de todos los posibles jugadores afectados."""
        for target in self.targets:
            target.staff_items = self.staff_items
            target.event_id = self.event_id
            await target.prepare_relations(redis)
        self.resources = tuple(
            {
                r.key: r
                for r in (
                    *self.resources,
                    *(resource for target in self.targets for resource in target.resources),
                )
            }.values()
        )

    def decide(self, snapshot: Snapshot) -> Decision:
        """Filtra estados/PvP y paga sólo cuando existe un efecto ejecutable.

        Returns:
            Un resultado por objetivo bajo un solo recibo durable.
        """
        position = cast("dict[str, str]", snapshot[RedisKeys.player_position(self.request.user_id)])
        if self.world_guard and not self.world_guard():
            return Decision({"applied": False, "message": "La sesión cambió."}, {})
        if (
            abs(self.request.x - int(position.get("x", 0)))
            + abs(self.request.y - int(position.get("y", 0)))
            > MAX_RANGE
        ):
            return Decision(
                {"applied": False, "message": "El centro del área está fuera de alcance."}, {}
            )
        selected: list[tuple[SpellPlan, Decision]] = []
        for target in self.targets:
            target.charge_cost, target.train = False, False
            result = target.decide(snapshot)
            if result.result.get("applied"):
                selected.append((target, result))
                if len(selected) >= int(self.spell["area"]["max_targets"]):
                    break
        if not selected:
            return Decision(
                {"applied": False, "message": "No hay objetivos válidos en el área."}, {}
            )
        first = selected[0][0]
        first.charge_cost, first.train = True, True
        first_result = first.decide(snapshot)
        if not first_result.result.get("applied"):
            return first_result
        selected[0] = first, first_result
        writes: dict[str, str | dict[str, str] | set[str]] = {}
        outcomes = []
        for target, decision in selected:
            for key, value in decision.writes.items():
                if isinstance(value, dict):
                    writes[key] = {**cast("dict[str, str]", writes.get(key, {})), **value}
                else:
                    writes[key] = value
            outcomes.append({"request": asdict(target.request), "result": decision.result})
        return Decision(
            {"applied": True, "message": "Hechizo de área confirmado.", "area_results": outcomes},
            writes,
        )
