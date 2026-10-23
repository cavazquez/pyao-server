"""Repositorio para operaciones de NPCs usando Redis."""

import logging
import time
import uuid
from typing import TYPE_CHECKING, cast

from redis.exceptions import WatchError

from src.models.npc import NPC
from src.utils.pet_index import enqueue_pet_index, owner_key, pet_owner
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.typing import EncodableT

    from src.utils.redis_client import RedisClient
else:
    RedisClient = object

logger = logging.getLogger(__name__)


class NPCRepository:
    """Repositorio para operaciones de datos de NPCs en Redis."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente Redis para operaciones de bajo nivel.
        """
        self.redis = redis_client

    async def create_npc_instance(
        self,
        npc_id: int,
        char_index: int,
        map_id: int,
        x: int,
        y: int,
        heading: int,
        name: str,
        description: str,
        body_id: int,
        head_id: int,
        hp: int,
        max_hp: int,
        level: int,
        is_hostile: bool,
        is_attackable: bool,
        respawn_time: int,
        respawn_time_max: int,
        gold_min: int,
        gold_max: int,
        is_merchant: bool = False,
        is_banker: bool = False,
        movement_type: str = "static",
        attack_damage: int = 10,
        attack_cooldown: float = 3.0,
        aggro_range: int = 8,
        summoned_by_user_id: int = 0,
        summoned_until: float = 0.0,
        snd1: int = 0,
        snd2: int = 0,
        snd3: int = 0,
        domable: int = 0,
        is_tamed: bool = False,
        role: str = "inhabitant",
        guard_faction: str = "neutral",
        loot_profile: str = "none",
        loot_material: int = 0,
        stable_instance: str = "",
    ) -> NPC:
        """Crea una nueva instancia de NPC en Redis.

        Args:
            npc_id: ID del tipo de NPC (del catálogo).
            role: Rol explícito de comportamiento.
            guard_faction: Facción defendida por un guardia.
            loot_profile: Política de botín, independiente del nivel del jugador.
            loot_material: Piel específica de la especie, si corresponde.
            stable_instance: Identidad fija de un servicio del mundo, nunca entrada de red.
            char_index: CharIndex único en el mapa.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).
            name: Nombre del NPC.
            description: Descripción del NPC.
            body_id: ID del sprite del cuerpo.
            head_id: ID del sprite de la cabeza.
            hp: HP actual.
            max_hp: HP máximo.
            level: Nivel del NPC.
            is_hostile: ¿Ataca a jugadores?
            is_attackable: ¿Puede ser atacado?
            is_merchant: ¿Es un mercader?
            is_banker: ¿Es un banquero?
            movement_type: Tipo de movimiento.
            respawn_time: Tiempo mínimo de respawn en segundos.
            respawn_time_max: Tiempo máximo de respawn en segundos.
            gold_min: Oro mínimo al morir.
            gold_max: Oro máximo al morir.
            attack_damage: Daño base del NPC.
            attack_cooldown: Segundos entre ataques.
            aggro_range: Rango de detección/agresión en tiles.
            summoned_by_user_id: ID del jugador que invocó al NPC (0 = no invocado).
            summoned_until: Timestamp hasta cuando existe (0 = permanente/no invocado).
            snd1: Sonido de ataque (cuando el NPC ataca).
            snd2: Sonido de daño recibido (cuando el NPC recibe daño).
            snd3: Sonido de muerte (cuando el NPC muere).
            domable: Umbral de Carisma por habilidad para domar.
            is_tamed: Indica una mascota permanente.

        Returns:
            Instancia de NPC creada.

        """
        instance_id = stable_instance or str(uuid.uuid4())
        if stable_instance:
            existing = await self.get_npc(stable_instance)
            if existing is not None:
                return existing

        npc = NPC(
            npc_id=npc_id,
            char_index=char_index,
            instance_id=instance_id,
            map_id=map_id,
            x=x,
            y=y,
            heading=heading,
            name=name,
            description=description,
            body_id=body_id,
            head_id=head_id,
            hp=hp,
            max_hp=max_hp,
            level=level,
            is_hostile=is_hostile,
            is_attackable=is_attackable,
            is_merchant=is_merchant,
            is_banker=is_banker,
            movement_type=movement_type,
            respawn_time=respawn_time,
            respawn_time_max=respawn_time_max,
            gold_min=gold_min,
            gold_max=gold_max,
            attack_damage=attack_damage,
            attack_cooldown=attack_cooldown,
            aggro_range=aggro_range,
            summoned_by_user_id=summoned_by_user_id,
            summoned_until=summoned_until,
            snd1=snd1,
            snd2=snd2,
            snd3=snd3,
            domable=domable,
            is_tamed=is_tamed,
            role=role,
            guard_faction=guard_faction,
            home_x=x,
            home_y=y,
            loot_profile=loot_profile,
            loot_material=loot_material,
        )

        # Guardar en Redis
        key = RedisKeys.npc_instance(instance_id)
        npc_data = {
            "loot_profile": loot_profile,
            "loot_material": str(loot_material),
            "npc_id": str(npc_id),
            "char_index": str(char_index),
            "instance_id": instance_id,
            "map_id": str(map_id),
            "x": str(x),
            "y": str(y),
            "heading": str(heading),
            "name": name,
            "description": description,
            "body_id": str(body_id),
            "head_id": str(head_id),
            "hp": str(hp),
            "max_hp": str(max_hp),
            "level": str(level),
            "is_hostile": str(is_hostile),
            "is_attackable": str(is_attackable),
            "is_merchant": str(is_merchant),
            "is_banker": str(is_banker),
            "movement_type": movement_type,
            "respawn_time": str(respawn_time),
            "respawn_time_max": str(respawn_time_max),
            "gold_min": str(gold_min),
            "gold_max": str(gold_max),
            "attack_damage": str(attack_damage),
            "attack_cooldown": str(attack_cooldown),
            "aggro_range": str(aggro_range),
            "paralyzed_until": "0.0",
            "poisoned_until": "0.0",
            "poisoned_by_user_id": "0",
            "summoned_by_user_id": str(summoned_by_user_id),
            "summoned_until": str(summoned_until),
            "domable": str(domable),
            "is_tamed": str(is_tamed),
            "pet_order": "follow",
            "snd1": str(snd1),
            "snd2": str(snd2),
            "snd3": str(snd3),
            "role": role,
            "guard_faction": guard_faction,
            "home_x": str(x),
            "home_y": str(y),
            "random_spawn_area": "",
        }

        async with self.redis.redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", npc_data))
            pipe.sadd(RedisKeys.npc_map_index(map_id), instance_id)
            enqueue_pet_index(pipe, instance_id, {}, npc_data)
            await pipe.execute()

        logger.debug(
            "NPC creado: %s (ID: %d, CharIndex: %d) en mapa %d (%d, %d)",
            name,
            npc_id,
            char_index,
            map_id,
            x,
            y,
        )

        return npc

    async def get_npc(self, instance_id: str) -> NPC | None:
        """Obtiene un NPC por su instance_id.

        Args:
            instance_id: ID único de la instancia del NPC.

        Returns:
            Instancia de NPC o None si no existe.
        """
        key = RedisKeys.npc_instance(instance_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        return self._from_data(result)

    @staticmethod
    def _from_data(result: dict[str, str]) -> NPC:
        """Decodifica una instancia, tanto individual como obtenida por lote.

        Returns:
            Modelo del NPC persistido.
        """
        return NPC(
            npc_id=int(result["npc_id"]),
            char_index=int(result["char_index"]),
            instance_id=result["instance_id"],
            map_id=int(result["map_id"]),
            x=int(result["x"]),
            y=int(result["y"]),
            heading=int(result["heading"]),
            name=result["name"],
            description=result["description"],
            body_id=int(result["body_id"]),
            head_id=int(result["head_id"]),
            hp=int(result["hp"]),
            max_hp=int(result["max_hp"]),
            level=int(result["level"]),
            is_hostile=result["is_hostile"].lower() == "true",
            is_attackable=result["is_attackable"].lower() == "true",
            is_merchant=result.get("is_merchant", "False").lower() == "true",
            is_banker=result.get("is_banker", "False").lower() == "true",
            movement_type=result["movement_type"],
            respawn_time=int(result["respawn_time"]),
            respawn_time_max=int(result.get("respawn_time_max", result["respawn_time"])),
            gold_min=int(result["gold_min"]),
            gold_max=int(result["gold_max"]),
            attack_damage=int(result.get("attack_damage", "10")),
            attack_cooldown=float(result.get("attack_cooldown", "3.0")),
            aggro_range=int(result.get("aggro_range", "8")),
            paralyzed_until=float(result.get("paralyzed_until", "0.0")),
            poisoned_until=float(result.get("poisoned_until", "0.0")),
            poisoned_by_user_id=int(result.get("poisoned_by_user_id", "0")),
            summoned_by_user_id=int(result.get("summoned_by_user_id", "0")),
            summoned_until=float(result.get("summoned_until", "0.0")),
            snd1=int(result.get("snd1", "0")),
            snd2=int(result.get("snd2", "0")),
            snd3=int(result.get("snd3", "0")),
            domable=int(result.get("domable", "0")),
            is_tamed=result.get("is_tamed", "False").lower() == "true",
            pet_order=result.get("pet_order", "follow"),
            role=result.get("role", "inhabitant"),
            guard_faction=result.get("guard_faction", "neutral"),
            home_x=int(result.get("home_x", result["x"])),
            home_y=int(result.get("home_y", result["y"])),
            random_spawn_area=result.get("random_spawn_area", ""),
            loot_profile=result.get("loot_profile", "none"),
            loot_material=int(result.get("loot_material", "0")),
            gm_follow_user=int(result.get("gm_follow_user", "0")),
        )

    async def get_player_pets(self, user_id: int, *, include_expired: bool = False) -> list[NPC]:
        """Consulta sólo el propietario y valida las instancias con una lectura por lote.

        Returns:
            Mascotas vivas del dueño; opcionalmente incluye invocaciones vencidas.
        """
        members: list[str] = sorted(await self.redis.smembers(owner_key(user_id)))
        rows = await self._read_many(members)
        stale = [
            instance
            for instance, row in zip(members, rows, strict=True)
            if pet_owner(row) != user_id
        ]
        if stale:
            await self._prune_owner_index(user_id, stale)
        now = time.time()
        return [
            self._from_data(row)
            for row in rows
            if pet_owner(row) == user_id
            and (
                include_expired
                or row.get("is_tamed", "False").lower() == "true"
                or float(row.get("summoned_until", 0)) > now
            )
        ]

    async def _read_many(self, instances: list[str]) -> list[dict[str, str]]:
        if not instances:
            return []
        async with self.redis.redis.pipeline(transaction=False) as pipe:
            for instance in instances:
                pipe.hgetall(RedisKeys.npc_instance(instance))
            return cast("list[dict[str, str]]", await pipe.execute())

    async def _prune_owner_index(self, user_id: int, instances: list[str]) -> None:
        # WATCH evita borrar una membresía que acaba de volver a ser válida.
        keys = [RedisKeys.npc_instance(instance) for instance in instances]
        for _ in range(3):
            async with self.redis.redis.pipeline() as pipe:
                try:
                    await pipe.watch(*keys)
                    stale = []
                    for instance, key in zip(instances, keys, strict=True):
                        row = cast("dict[str, str]", await pipe.hgetall(key))
                        if pet_owner(row) != user_id:
                            stale.append(instance)
                    pipe.multi()  # type: ignore[no-untyped-call]
                    if stale:
                        pipe.srem(owner_key(user_id), *stale)
                    await pipe.execute()
                except WatchError:
                    continue
                else:
                    return

    async def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Obtiene todos los NPCs de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        map_key = RedisKeys.npc_map_index(map_id)
        instance_ids: set[str] = await self.redis.smembers(map_key)

        npcs: list[NPC] = []
        for instance_id in instance_ids:
            npc = await self.get_npc(instance_id)
            if npc:
                npcs.append(npc)

        return npcs

    async def get_all_npcs(self) -> list[NPC]:
        """Obtiene todos los NPCs del mundo.

        Returns:
            Lista de todos los NPCs.
        """
        # Sólo inicialización/mantenimiento: nunca usar esta ruta en un tick.
        instances = [
            str(key).removeprefix("npc:instance:")
            async for key in self.redis.redis.scan_iter(match="npc:instance:*", count=256)
        ]
        npcs: list[NPC] = []
        for offset in range(0, len(instances), 256):
            rows = await self._read_many(instances[offset : offset + 256])
            npcs.extend(self._from_data(row) for row in rows if row)
        return npcs

    async def update_npc_position(self, instance_id: str, x: int, y: int, heading: int) -> None:
        """Actualiza la posición de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            x: Nueva posición X.
            y: Nueva posición Y.
            heading: Nueva dirección.
        """
        key = RedisKeys.npc_instance(instance_id)
        position_data = {
            "x": str(x),
            "y": str(y),
            "heading": str(heading),
        }
        await self.redis.hset(key, mapping=position_data)
        logger.debug("Posición actualizada para NPC %s: (%d, %d)", instance_id, x, y)

    async def update_npc_hp(self, instance_id: str, hp: int) -> None:
        """Actualiza el HP de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            hp: Nuevo HP.
        """
        await self._write_membership(instance_id, {"hp": str(hp)})
        logger.debug("HP actualizado para NPC %s: %d", instance_id, hp)

    async def update_npc_paralyzed_until(self, instance_id: str, paralyzed_until: float) -> None:
        """Actualiza el estado de parálisis de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            paralyzed_until: Timestamp hasta cuando está paralizado (0.0 = no paralizado).
        """
        key = RedisKeys.npc_instance(instance_id)
        await self.redis.hset(key, "paralyzed_until", str(paralyzed_until))
        logger.debug(
            "Estado de parálisis actualizado para NPC %s: hasta %.2f", instance_id, paralyzed_until
        )

    async def update_npc_poisoned_until(
        self, instance_id: str, poisoned_until: float, poisoned_by_user_id: int = 0
    ) -> None:
        """Actualiza el estado de envenenamiento de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            poisoned_until: Timestamp hasta cuando está envenenado (0.0 = no envenenado).
            poisoned_by_user_id: ID del jugador que envenenó al NPC (0 = sistema/desconocido).
        """
        key = RedisKeys.npc_instance(instance_id)
        await self.redis.hset(
            key,
            mapping={
                "poisoned_until": str(poisoned_until),
                "poisoned_by_user_id": str(poisoned_by_user_id),
            },
        )
        logger.debug(
            "Estado de envenenamiento actualizado para NPC %s: hasta %.2f "
            "(envenenado por user_id %d)",
            instance_id,
            poisoned_until,
            poisoned_by_user_id,
        )

    async def update_npc_summoned(
        self, instance_id: str, summoned_by_user_id: int, summoned_until: float
    ) -> None:
        """Actualiza los campos de invocación de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            summoned_by_user_id: ID del jugador que invocó al NPC (0 = no invocado).
            summoned_until: Timestamp hasta cuando existe (0.0 = permanente/no invocado).
        """
        await self._write_membership(
            instance_id,
            {
                "summoned_by_user_id": str(summoned_by_user_id),
                "summoned_until": str(summoned_until),
            },
        )
        logger.debug(
            "Campos de invocación actualizados para NPC %s: owner=%d, hasta %.2f",
            instance_id,
            summoned_by_user_id,
            summoned_until,
        )

    async def remove_npc(self, instance_id: str) -> None:
        """Elimina un NPC del mundo.

        Args:
            instance_id: ID único de la instancia del NPC.
        """
        await self._write_membership(instance_id, None)

    async def _write_membership(self, instance: str, changes: dict[str, str] | None) -> None:
        """Confirma instancia e índices sin carreras de muerte, dueño o cambio de mapa.

        Raises:
            RuntimeError: Si la instancia permanece en contención tras 16 intentos.
        """
        key = RedisKeys.npc_instance(instance)
        for _ in range(16):
            async with self.redis.redis.pipeline() as pipe:
                try:
                    await pipe.watch(key)
                    before = cast("dict[str, str]", await pipe.hgetall(key))
                    if not before:
                        return
                    pipe.multi()  # type: ignore[no-untyped-call]
                    if changes is None:
                        pipe.delete(key)
                        pipe.srem(RedisKeys.npc_map_index(int(before["map_id"])), instance)
                        user = int(before.get("summoned_by_user_id", 0))
                        if user:
                            pipe.srem(owner_key(user), instance)
                    else:
                        pipe.hset(key, mapping=cast("Mapping[EncodableT, EncodableT]", changes))
                    enqueue_pet_index(
                        pipe, instance, before, {} if changes is None else {**before, **changes}
                    )
                    await pipe.execute()
                except WatchError:
                    continue
                else:
                    return
        message = "La instancia NPC cambió durante todos los intentos de actualización"
        raise RuntimeError(message)

    async def clear_all_npcs(self, *, preserve_tamed: bool = False) -> None:
        """Elimina todos los NPCs del mundo (útil para reiniciar).

        ADVERTENCIA: Esta operación es destructiva.
        """
        kept = []
        for npc in await self.get_all_npcs():
            pending = await self.redis.hget(RedisKeys.npc_instance(npc.instance_id), "death_state")
            if preserve_tamed and (pending == "pending" or (npc.is_tamed and npc.hp > 0)):
                kept.append(npc)
            else:
                await self.remove_npc(npc.instance_id)
        # Reconstrucción exclusivamente al arrancar, antes de aceptar jugadores.
        for pattern in ("npc:map:*", "player:*:pets"):
            async for key in self.redis.redis.scan_iter(match=pattern, count=256):
                await self.redis.delete(str(key))
        async with self.redis.redis.pipeline() as pipe:
            for npc in kept:
                pipe.sadd(RedisKeys.npc_map_index(npc.map_id), npc.instance_id)
                if npc.summoned_by_user_id > 0 and npc.is_tamed and npc.hp > 0:
                    pipe.sadd(owner_key(npc.summoned_by_user_id), npc.instance_id)
            await pipe.execute()

        logger.info("Todos los NPCs han sido eliminados de Redis")
