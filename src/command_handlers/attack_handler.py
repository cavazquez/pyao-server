"""Handler para comando de ataque."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.attack_execution_handler import AttackExecutionHandler
from src.command_handlers.attack_loot_handler import AttackLootHandler
from src.command_handlers.attack_validation_handler import AttackValidationHandler
from src.commands.attack_command import AttackCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.player_repository import PlayerRepository
    from src.services.combat.combat_service import CombatService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.loot_table_service import LootTableService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.services.npc.npc_service import NPCService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class AttackCommandHandler(CommandHandler):
    """Handler para comando de ataque (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        combat_service: CombatService,
        map_manager: MapManager,
        npc_service: NPCService,
        broadcast_service: MultiplayerBroadcastService | None,
        npc_death_service: NPCDeathService | None,
        npc_respawn_service: NPCRespawnService | None,
        loot_table_service: LootTableService | None,
        item_catalog: ItemCatalog | None,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            combat_service: Servicio de combate.
            map_manager: Gestor de mapas.
            npc_service: Servicio de NPCs.
            broadcast_service: Servicio de broadcast.
            npc_death_service: Servicio de muerte de NPCs.
            npc_respawn_service: Servicio de respawn de NPCs.
            loot_table_service: Servicio de loot tables.
            item_catalog: Catálogo de items.
            stamina_service: Servicio de stamina.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.npc_service = npc_service
        self.npc_death_service = npc_death_service
        self.npc_respawn_service = npc_respawn_service
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.validation_handler = AttackValidationHandler(
            player_repo=player_repo,
            map_manager=map_manager,
            stamina_service=stamina_service,
            message_sender=message_sender,
        )

        self.execution_handler = AttackExecutionHandler(
            combat_service=combat_service,
            broadcast_service=broadcast_service,
            message_sender=message_sender,
        )

        self.loot_handler = AttackLootHandler(
            map_manager=map_manager,
            loot_table_service=loot_table_service,
            item_catalog=item_catalog,
            broadcast_service=broadcast_service,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de ataque (solo lógica de negocio).

        Args:
            command: Comando de ataque.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, AttackCommand):
            return CommandResult.error("Comando inválido: se esperaba AttackCommand")

        user_id = command.user_id
        target_x = command.target_x
        target_y = command.target_y
        map_id = command.map_id

        # Validar ataque y encontrar NPC objetivo
        (
            can_attack,
            error_msg,
            _position,
            target_npc,
        ) = await self.validation_handler.validate_attack(user_id, target_x, target_y, map_id)
        if not can_attack or target_npc is None:
            return CommandResult.error(error_msg or "No se puede atacar")

        # Ejecutar ataque
        success, error_msg, result_data = await self.execution_handler.execute_attack(
            user_id, target_npc, target_x, target_y
        )
        if not success:
            return CommandResult.error(error_msg or "Error al ejecutar ataque")

        # Si el NPC murió, manejar muerte y loot
        if result_data and result_data.get("npc_died"):
            experience = result_data.get("experience", 0)

            # Usar NPCDeathService si está disponible
            if self.npc_death_service:
                await self.npc_death_service.handle_npc_death(
                    npc=target_npc,
                    killer_user_id=user_id,
                    experience=experience,
                    message_sender=self.message_sender,
                    death_reason="combate",
                )
            else:
                # Fallback: lógica antigua (para tests que no tienen el servicio)
                await self.message_sender.send_console_msg(
                    f"¡Has matado a {target_npc.name}! Ganaste {experience} EXP."
                )

                # Dropear items según loot table
                await self.loot_handler.handle_loot_drop(target_npc)

                # Remover NPC del mapa
                await self.npc_service.remove_npc(target_npc)

                # Programar respawn del NPC
                if self.npc_respawn_service:
                    await self.npc_respawn_service.schedule_respawn(target_npc)

            return CommandResult.ok(
                {
                    "npc_died": True,
                    "damage": result_data.get("damage", 0),
                    "experience": experience,
                    "npc_name": result_data.get("npc_name", ""),
                }
            )

        return CommandResult.ok(result_data or {})
