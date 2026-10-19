"""Invocación y traslado de mascotas confirmados con el coste del mismo cast."""

from dataclasses import asdict
from typing import TYPE_CHECKING, cast
from uuid import NAMESPACE_URL, uuid5

from src.constants.gameplay import MAX_PETS
from src.models.npc import NPC
from src.services.combat.spell_plan import SpellPlan
from src.services.skill_training import trained_decision
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

if TYPE_CHECKING:
    from src.models.npc_catalog import NPCCatalog

SUMMON_LIFETIME = 300


class SummonPlan(SpellPlan):
    """El recibo incluye los IDs estables de mascotas y sus índices de mapa."""

    def prepare(
        self,
        identity: str,
        map_id: int,
        pets: list[NPC],
        template_id: int,
        catalog: NPCCatalog | None,
        positions: list[tuple[int, int]],
        character_indices: tuple[int, ...],
        occupants: list[NPC],
        players: list[int],
    ) -> None:
        """Congela instancias/posiciones y declara todos sus recursos antes del commit."""
        self.occupants = occupants
        self.players = players
        self.pets = pets
        self.map_id = map_id
        self.positions = positions
        self.reservation_id = identity
        self.spawned: list[NPC] = []
        template = catalog.get_npc_data(template_id) if catalog else None
        for index, ((x, y), char_index) in enumerate(
            zip(positions, character_indices, strict=True)
        ):
            if not template:
                break
            self.spawned.append(
                NPC(
                    npc_id=template_id,
                    char_index=char_index,
                    instance_id=str(uuid5(NAMESPACE_URL, f"pyao:cast:{identity}:{index}")),
                    map_id=map_id,
                    x=x,
                    y=y,
                    heading=3,
                    name=str(template.get("nombre", "Mascota")),
                    description=str(template.get("descripcion", "")),
                    body_id=int(str(template.get("body_id", 1))),
                    head_id=int(str(template.get("head_id", 0))),
                    hp=int(str(template.get("hp_max", 100))),
                    max_hp=int(str(template.get("hp_max", 100))),
                    level=int(str(template.get("nivel", 1))),
                    is_hostile=False,
                    is_attackable=True,
                    summoned_by_user_id=self.request.user_id,
                    summoned_until=self.now + SUMMON_LIFETIME,
                )
            )
        extra = [
            Resource(f"player:{self.request.user_id}:pets", "set"),
            *(
                Resource(RedisKeys.npc_instance(npc.instance_id), "hash")
                for npc in pets + self.spawned + occupants
            ),
        ]
        extra.extend(
            Resource(RedisKeys.npc_map_index(number), "set")
            for number in {map_id, *(pet.map_id for pet in pets)}
        )
        extra.extend(Resource(RedisKeys.player_position(player), "hash") for player in players)
        self.resources = tuple(
            {resource.key: resource for resource in (*self.resources, *extra)}.values()
        )

    def decide(self, snapshot: Snapshot) -> Decision:  # ruff: ignore[too-many-locals] - recursos del único commit de invocación
        """No publica criaturas ni cobra hasta confirmar juntas sus instancias e índices.

        Returns:
            Peticiones de publicación derivadas exclusivamente del commit confirmado.
        """
        request = self.request
        if self.world_guard is not None and not self.world_guard():
            return Decision({"applied": False, "message": "La sesión o el terreno cambió."}, {})
        stats_key = RedisKeys.player_user_stats(request.user_id)
        stats = cast("dict[str, str]", snapshot[stats_key])
        position = cast("dict[str, str]", snapshot[RedisKeys.player_position(request.user_id)])
        values = {key: value for key, value in snapshot.items() if isinstance(value, dict)}
        error = self._validate_caster(
            values, stats, position, values[RedisKeys.player_spellbook(request.user_id)]
        )
        if error:
            return Decision({"applied": False, "message": error}, {})
        if int(position.get("map", 0)) != self.map_id:
            return Decision({"applied": False, "message": "El mapa cambió."}, {})
        pets = [
            pet
            for pet in self.pets
            if self._active(
                cast("dict[str, str]", snapshot[RedisKeys.npc_instance(pet.instance_id)])
            )
        ]
        members = set(cast("set[str]", snapshot[f"player:{request.user_id}:pets"]))
        if members - {pet.instance_id for pet in self.pets}:
            return Decision(
                {"applied": False, "message": "Tus mascotas cambiaron; vuelve a intentarlo."}, {}
            )
        writes: dict[str, str | dict[str, str] | set[str]] = {}
        spawned: list[str] = []
        if self.spell.get("warps_pet"):
            if not pets:
                return Decision({"applied": False, "message": "No tienes mascotas invocadas."}, {})
            pet = pets[0]
            occupied = {
                (int(row.get("x", -1)), int(row.get("y", -1)))
                for row in (
                    cast("dict[str, str]", snapshot[RedisKeys.player_position(player)])
                    for player in self.players
                )
                if int(row.get("map", 0)) == self.map_id
            }
            occupied.update(
                (int(row.get("x", -1)), int(row.get("y", -1)))
                for row in (
                    cast("dict[str, str]", snapshot[RedisKeys.npc_instance(npc.instance_id)])
                    for npc in self.occupants
                )
                if int(row.get("map_id", 0)) == self.map_id
            )
            available = [
                (x, y)
                for x, y in self.positions
                if (x, y) not in occupied
                and max(abs(x - int(position["x"])), abs(y - int(position["y"]))) == 1
            ]
            if not available:
                return Decision(
                    {"applied": False, "message": "No hay una casilla libre junto al dueño."}, {}
                )
            x, y = available[0]
            source_key, target_key = (
                RedisKeys.npc_map_index(pet.map_id),
                RedisKeys.npc_map_index(self.map_id),
            )
            source_index, target_index = (
                set(cast("set[str]", snapshot[source_key])),
                set(cast("set[str]", snapshot[target_key])),
            )
            source_index.discard(pet.instance_id)
            target_index.add(pet.instance_id)
            writes.update(
                {
                    source_key: source_index,
                    target_key: target_index,
                    RedisKeys.npc_instance(pet.instance_id): {
                        "map_id": str(self.map_id),
                        "x": str(x),
                        "y": str(y),
                        "heading": position.get("heading", "3"),
                    },
                }
            )
            spawned.append(pet.instance_id)
        else:
            if not self.spawned or len(pets) + len(self.spawned) > MAX_PETS:
                return Decision(
                    {"applied": False, "message": "No hay espacio o capacidad para invocar."}, {}
                )
            index_key = RedisKeys.npc_map_index(self.map_id)
            members = set(cast("set[str]", snapshot[index_key]))
            occupied = {
                (int(row.get("x", -1)), int(row.get("y", -1)))
                for row in (
                    cast("dict[str, str]", snapshot[RedisKeys.npc_instance(npc.instance_id)])
                    for npc in self.occupants
                )
                if int(row.get("map_id", 0)) == self.map_id
            }
            occupied.update(
                (int(row.get("x", -1)), int(row.get("y", -1)))
                for row in (
                    cast("dict[str,str]", snapshot[RedisKeys.player_position(player)])
                    for player in self.players
                )
                if int(row.get("map", 0)) == self.map_id
            )
            if any((npc.x, npc.y) in occupied for npc in self.spawned):
                return Decision(
                    {"applied": False, "message": "El lugar de invocación está ocupado."}, {}
                )
            for npc in self.spawned:
                key = RedisKeys.npc_instance(npc.instance_id)
                if snapshot[key]:
                    return Decision({"applied": False, "message": "La invocación ya existe."}, {})
                writes[key] = {field: str(value) for field, value in asdict(npc).items()}
                members.add(npc.instance_id)
                spawned.append(npc.instance_id)
            writes[index_key] = members
        writes[f"player:{request.user_id}:pets"] = {pet.instance_id for pet in pets} | set(spawned)
        writes[stats_key] = {
            "hidden_until": "0",
            "meditating": "0",
            "min_mana": str(int(stats.get("min_mana", 0)) - int(self.spell.get("mana_cost", 0))),
            "min_sta": str(int(stats.get("min_sta", 0)) - int(self.spell.get("stamina_cost", 3))),
        }
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "message": "Invocación confirmada.",
                    "pets": spawned,
                    "warped": bool(self.spell.get("warps_pet")),
                    "old_maps": {pet.instance_id: pet.map_id for pet in pets},
                },
                writes,
            ),
            snapshot,
            request.user_id,
            (("magia", True),),
        )

    def _active(self, npc: dict[str, str]) -> bool:
        return (
            int(npc.get("summoned_by_user_id", 0)) == self.request.user_id
            and (
                float(npc.get("summoned_until", 0)) > self.now
                or npc.get("is_tamed", "False").lower() == "true"
            )
            and int(npc.get("hp", 0)) > 0
        )
