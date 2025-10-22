"""Repositorio para operaciones de NPCs usando Redis."""

import logging
import uuid
from typing import TYPE_CHECKING

from src.npc import NPC
from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient
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
    ) -> NPC:
        """Crea una nueva instancia de NPC en Redis.

        Args:
            npc_id: ID del tipo de NPC (del catálogo).
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

        Returns:
            Instancia de NPC creada.
        """
        instance_id = str(uuid.uuid4())

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
        )

        # Guardar en Redis
        key = RedisKeys.npc_instance(instance_id)
        npc_data = {
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
        }

        await self.redis.redis.hset(key, mapping=npc_data)  # type: ignore[misc]

        # Agregar a índice de mapa
        map_key = RedisKeys.npc_map_index(map_id)
        await self.redis.redis.sadd(map_key, instance_id)  # type: ignore[misc]

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
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

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
        )

    async def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Obtiene todos los NPCs de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        map_key = RedisKeys.npc_map_index(map_id)
        instance_ids: set[str] = await self.redis.redis.smembers(map_key)  # type: ignore[misc]

        npcs = []
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
        # Obtener todas las claves de NPCs
        pattern = "npc:instance:*"
        keys = await self.redis.redis.keys(pattern)

        npcs = []
        for key in keys:
            # Extraer instance_id de la clave
            instance_id = key.split(":")[-1]
            npc = await self.get_npc(instance_id)
            if npc:
                npcs.append(npc)

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
        await self.redis.redis.hset(key, mapping=position_data)  # type: ignore[misc]
        logger.debug("Posición actualizada para NPC %s: (%d, %d)", instance_id, x, y)

    async def update_npc_hp(self, instance_id: str, hp: int) -> None:
        """Actualiza el HP de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            hp: Nuevo HP.
        """
        key = RedisKeys.npc_instance(instance_id)
        await self.redis.redis.hset(key, "hp", str(hp))  # type: ignore[misc]
        logger.debug("HP actualizado para NPC %s: %d", instance_id, hp)

    async def remove_npc(self, instance_id: str) -> None:
        """Elimina un NPC del mundo.

        Args:
            instance_id: ID único de la instancia del NPC.
        """
        # Obtener el NPC para saber su mapa
        npc = await self.get_npc(instance_id)
        if not npc:
            logger.warning("Intento de eliminar NPC inexistente: %s", instance_id)
            return

        # Eliminar de índice de mapa
        map_key = RedisKeys.npc_map_index(npc.map_id)
        await self.redis.redis.srem(map_key, instance_id)  # type: ignore[misc]

        # Eliminar datos del NPC
        key = RedisKeys.npc_instance(instance_id)
        await self.redis.redis.delete(key)

        logger.debug("NPC eliminado: %s (%s)", npc.name, instance_id)

    async def clear_all_npcs(self) -> None:
        """Elimina todos los NPCs del mundo (útil para reiniciar).

        ADVERTENCIA: Esta operación es destructiva.
        """
        # Eliminar todas las instancias de NPCs
        pattern = "npc:instance:*"
        keys = await self.redis.redis.keys(pattern)
        if keys:
            await self.redis.redis.delete(*keys)

        # Eliminar todos los índices de mapas
        pattern = "npc:map:*"
        keys = await self.redis.redis.keys(pattern)
        if keys:
            await self.redis.redis.delete(*keys)

        logger.info("Todos los NPCs han sido eliminados de Redis")
