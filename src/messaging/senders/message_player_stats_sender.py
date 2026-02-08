"""Componente para enviar estadísticas del jugador al cliente."""

import logging
from typing import TYPE_CHECKING

from src.network.msg_player_stats import (
    build_update_bank_gold_response,
    build_update_dexterity_response,
    build_update_exp_response,
    build_update_gold_response,
    build_update_hp_response,
    build_update_hunger_and_thirst_response,
    build_update_mana_response,
    build_update_sta_response,
    build_update_strength_and_dexterity_response,
    build_update_strength_response,
    build_update_user_stats_response,
)
from src.network.msg_skills import build_update_skills_response

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class PlayerStatsMessageSender:
    """Maneja el envío de estadísticas del jugador al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de stats del jugador.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_update_hp(self, hp: int) -> None:
        """Envía paquete UpdateHP del protocolo AO estándar.

        Args:
            hp: Puntos de vida actuales (int16).
        """
        response = build_update_hp_response(hp=hp)
        logger.info("[%s] Enviando UPDATE_HP: %d", self.connection.address, hp)
        await self.connection.send(response)

    async def send_update_strength_and_dexterity(self, strength: int, dexterity: int) -> None:
        """Envía paquete UpdateStrengthAndDexterity del protocolo AO estándar."""
        from src.network.packet_id import ServerPacketID  # noqa: PLC0415

        response = build_update_strength_and_dexterity_response(
            strength=strength, dexterity=dexterity
        )
        logger.info(
            "[%s] Enviando UPDATE_STRENGTH_AND_DEXTERITY (packet_id=%d, bytes=%s): STR=%d DEX=%d",
            self.connection.address,
            ServerPacketID.UPDATE_STRENGTH_AND_DEXTERITY,
            response.hex(),
            strength,
            dexterity,
        )
        await self.connection.send(response)

    async def send_update_strength(self, strength: int) -> None:
        """Envía paquete UpdateStrength del protocolo AO estándar."""
        response = build_update_strength_response(strength=strength)
        logger.info("[%s] Enviando UPDATE_STRENGTH: %d", self.connection.address, strength)
        await self.connection.send(response)

    async def send_update_dexterity(self, dexterity: int) -> None:
        """Envía paquete UpdateDexterity del protocolo AO estándar."""
        response = build_update_dexterity_response(dexterity=dexterity)
        logger.info("[%s] Enviando UPDATE_DEXTERITY: %d", self.connection.address, dexterity)
        await self.connection.send(response)

    async def send_update_mana(self, mana: int) -> None:
        """Envía paquete UpdateMana del protocolo AO estándar.

        Args:
            mana: Puntos de mana actuales (int16).
        """
        response = build_update_mana_response(mana=mana)
        logger.info("[%s] Enviando UPDATE_MANA: %d", self.connection.address, mana)
        await self.connection.send(response)

    async def send_update_sta(self, stamina: int) -> None:
        """Envía paquete UpdateSta del protocolo AO estándar.

        Args:
            stamina: Puntos de stamina actuales (int16).
        """
        response = build_update_sta_response(stamina=stamina)
        logger.info("[%s] Enviando UPDATE_STA: %d", self.connection.address, stamina)
        await self.connection.send(response)

    async def send_update_exp(self, experience: int) -> None:
        """Envía paquete UpdateExp del protocolo AO estándar.

        Args:
            experience: Puntos de experiencia actuales (int32).
        """
        response = build_update_exp_response(experience=experience)
        logger.info("[%s] Enviando UPDATE_EXP: %d", self.connection.address, experience)
        await self.connection.send(response)

    async def send_update_gold(self, gold: int) -> None:
        """Envía paquete UpdateGold del protocolo AO estándar.

        Args:
            gold: Cantidad total de oro del jugador (int32).
        """
        response = build_update_gold_response(gold=gold)
        logger.info("[%s] Enviando UPDATE_GOLD: %d", self.connection.address, gold)
        await self.connection.send(response)

    async def send_update_bank_gold(self, bank_gold: int) -> None:
        """Envía paquete UpdateBankGold del protocolo AO estándar.

        Args:
            bank_gold: Cantidad de oro en el banco (int32).
        """
        response = build_update_bank_gold_response(bank_gold=bank_gold)
        logger.info(
            "[%s] Enviando UPDATE_BANK_GOLD: %d | Bytes (hex): %s",
            self.connection.address,
            bank_gold,
            response.hex(),
        )
        await self.connection.send(response)

    async def send_update_hunger_and_thirst(
        self, max_water: int, min_water: int, max_hunger: int, min_hunger: int
    ) -> None:
        """Envía paquete UpdateHungerAndThirst del protocolo AO estándar.

        Args:
            max_water: Sed máxima (u8).
            min_water: Sed actual (u8).
            max_hunger: Hambre máxima (u8).
            min_hunger: Hambre actual (u8).
        """
        response = build_update_hunger_and_thirst_response(
            max_water=max_water,
            min_water=min_water,
            max_hunger=max_hunger,
            min_hunger=min_hunger,
        )
        logger.info(
            "[%s] Enviando UPDATE_HUNGER_AND_THIRST: water=%d/%d hunger=%d/%d",
            self.connection.address,
            min_water,
            max_water,
            min_hunger,
            max_hunger,
        )
        await self.connection.send(response)

    async def send_update_user_stats(
        self,
        max_hp: int,
        min_hp: int,
        max_mana: int,
        min_mana: int,
        max_sta: int,
        min_sta: int,
        gold: int,
        level: int,
        elu: int,
        experience: int,
    ) -> None:
        """Envía paquete UpdateUserStats del protocolo AO estándar.

        Args:
            max_hp: HP máximo (int16).
            min_hp: HP actual (int16).
            max_mana: Mana máximo (int16).
            min_mana: Mana actual (int16).
            max_sta: Stamina máxima (int16).
            min_sta: Stamina actual (int16).
            gold: Oro del jugador (int32).
            level: Nivel del jugador (byte).
            elu: Experiencia para subir de nivel (int32).
            experience: Experiencia total (int32).
        """
        response = build_update_user_stats_response(
            max_hp=max_hp,
            min_hp=min_hp,
            max_mana=max_mana,
            min_mana=min_mana,
            max_sta=max_sta,
            min_sta=min_sta,
            gold=gold,
            level=level,
            elu=elu,
            experience=experience,
        )
        logger.info(
            "[%s] Enviando UPDATE_USER_STATS: HP=%d/%d MANA=%d/%d STA=%d/%d "
            "GOLD=%d LVL=%d ELU=%d EXP=%d",
            self.connection.address,
            min_hp,
            max_hp,
            min_mana,
            max_mana,
            min_sta,
            max_sta,
            gold,
            level,
            elu,
            experience,
        )
        await self.connection.send(response)

    async def send_update_user_stats_from_repo(
        self,
        user_id: int,
        player_repo: "PlayerRepository",  # noqa: UP037
        *,
        min_hp: int | None = None,
        min_mana: int | None = None,
        min_sta: int | None = None,
    ) -> None:
        """Envía UPDATE_USER_STATS obteniendo datos del repositorio.

        Este helper simplifica el patrón común de obtener stats del repositorio
        y enviarlos al cliente. Permite sobrescribir valores específicos si es necesario.

        Args:
            user_id: ID del jugador.
            player_repo: Repositorio de jugadores.
            min_hp: HP actual a sobrescribir (opcional).
            min_mana: Mana actual a sobrescribir (opcional).
            min_sta: Stamina actual a sobrescribir (opcional).

        Example:
            # Enviar stats completos del repositorio
            await sender.send_update_user_stats_from_repo(user_id, player_repo)

            # Enviar stats con HP modificado
            await sender.send_update_user_stats_from_repo(
                user_id, player_repo, min_hp=new_hp
            )
        """
        stats = await player_repo.get_player_stats(user_id)
        if not stats:
            logger.warning(
                "No se encontraron stats para user_id %d al enviar UPDATE_USER_STATS",
                user_id,
            )
            return

        await self.send_update_user_stats(
            max_hp=stats.max_hp,
            min_hp=min_hp if min_hp is not None else stats.min_hp,
            max_mana=stats.max_mana,
            min_mana=min_mana if min_mana is not None else stats.min_mana,
            max_sta=stats.max_sta,
            min_sta=min_sta if min_sta is not None else stats.min_sta,
            gold=stats.gold,
            level=stats.level,
            elu=stats.elu,
            experience=stats.experience,
        )

    async def send_update_skills(
        self,
        magic: int,
        robustness: int,
        agility: int,
        woodcutting: int,
        fishing: int,
        mining: int,
        blacksmithing: int,
        carpentry: int,
        survival: int,
    ) -> None:
        """Envía paquete SEND_SKILLS con todas las habilidades del jugador.

        Args:
            magic: Nivel de magia.
            robustness: Nivel de robustez.
            agility: Nivel de agilidad.
            woodcutting: Nivel de tala.
            fishing: Nivel de pesca.
            mining: Nivel de minería.
            blacksmithing: Nivel de herrería.
            carpentry: Nivel de carpintería.
            survival: Nivel de supervivencia.
        """
        response = build_update_skills_response(
            magic=magic,
            robustness=robustness,
            agility=agility,
            woodcutting=woodcutting,
            fishing=fishing,
            mining=mining,
            blacksmithing=blacksmithing,
            carpentry=carpentry,
            survival=survival,
        )
        logger.info(
            "[%s] Enviando SEND_SKILLS: MAG=%d ROB=%d AGI=%d TAL=%d PES=%d MIN=%d "
            "HERR=%d CARP=%d SUP=%d",
            self.connection.address,
            magic,
            robustness,
            agility,
            woodcutting,
            fishing,
            mining,
            blacksmithing,
            carpentry,
            survival,
        )
        await self.connection.send(response)
