"""Handler especializado para ejecución de ataque y efectos."""

import logging
from typing import TYPE_CHECKING, Any

from src.utils.sounds import SoundID
from src.utils.visual_effects import VisualEffectID

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.services.combat.combat_service import CombatService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
else:
    NPC = object  # Para type hints en runtime

logger = logging.getLogger(__name__)


class AttackExecutionHandler:
    """Handler especializado para ejecución de ataque y efectos."""

    def __init__(
        self,
        combat_service: CombatService,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de ejecución.

        Args:
            combat_service: Servicio de combate.
            broadcast_service: Servicio de broadcast.
            message_sender: Enviador de mensajes.
        """
        self.combat_service = combat_service
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender

    async def execute_attack(
        self, user_id: int, target_npc: NPC, target_x: int, target_y: int
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Ejecuta el ataque y maneja los efectos.

        Args:
            user_id: ID del usuario.
            target_npc: NPC objetivo.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.

        Returns:
            Tupla (success, error_message, result_data).
        """
        # Realizar el ataque
        result = await self.combat_service.player_attack_npc(
            user_id, target_npc, self.message_sender
        )

        if not result:
            await self.message_sender.send_console_msg("No puedes atacar en este momento.")
            return False, "No puedes atacar en este momento.", None

        damage = result["damage"]
        is_critical = result["critical"]
        is_dodged = result.get("dodged", False)
        npc_died = result["npc_died"]

        # Si el NPC esquivó, mostrar mensaje y salir
        if is_dodged:
            await self.message_sender.send_console_msg(f"¡{target_npc.name} esquivó tu ataque!")
            await self.message_sender.send_create_fx(
                target_npc.char_index,
                VisualEffectID.MEDITATION,
                loops=1,  # Efecto de esquive
            )
            return True, None, {"dodged": True}

        # Reproducir sonido de golpe (sonido del atacante)
        await self.message_sender.send_play_wave(SoundID.SWORD_HIT, target_x, target_y)

        # Reproducir sonido de daño recibido del NPC (Snd2) si está disponible
        if target_npc.snd2 > 0 and self.broadcast_service:
            # Broadcast sonido a todos los jugadores en el mapa
            await self.broadcast_service.broadcast_play_wave(
                map_id=target_npc.map_id,
                wave_id=target_npc.snd2,
                x=target_npc.x,
                y=target_npc.y,
            )

        # Mostrar efecto visual
        if is_critical:
            await self.message_sender.send_create_fx(
                target_npc.char_index, VisualEffectID.CRITICAL_HIT, loops=1
            )
            await self.message_sender.send_console_msg(
                f"¡Golpe crítico! Le hiciste {damage} de daño a {target_npc.name}."
            )
        else:
            await self.message_sender.send_create_fx(
                target_npc.char_index, VisualEffectID.BLOOD, loops=1
            )
            await self.message_sender.send_console_msg(
                f"Le hiciste {damage} de daño a {target_npc.name}."
            )

        # Si el NPC murió
        if npc_died:
            experience = result.get("experience", 0)
            return (
                True,
                None,
                {
                    "npc_died": True,
                    "damage": damage,
                    "experience": experience,
                    "npc_name": target_npc.name,
                    "target_npc": target_npc,
                },
            )

        # Mostrar HP restante del NPC
        hp_percent = int((target_npc.hp / target_npc.max_hp) * 100)
        await self.message_sender.send_console_msg(
            f"{target_npc.name} tiene {target_npc.hp}/{target_npc.max_hp} HP ({hp_percent}%)."
        )

        return (
            True,
            None,
            {
                "npc_died": False,
                "damage": damage,
                "npc_name": target_npc.name,
                "npc_hp": target_npc.hp,
                "npc_max_hp": target_npc.max_hp,
            },
        )
