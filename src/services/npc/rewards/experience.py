"""Publicación de experiencia ya confirmada; nunca acredita saldos o puntos desde la UI."""

from typing import TYPE_CHECKING, Any

from src.services.player_progression import publish_progress

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.services.npc.npc_death_service import NPCDeathService


class ExperienceComponent:
    """Notifica a receptores presentes sin cambiar el resultado durable del commit."""

    def __init__(self, owner: NPCDeathService) -> None:
        """Conserva el acceso al mapa y a repositorios para publicar snapshots actuales."""
        self.owner = owner

    async def publish(
        self,
        npc: NPC,
        killer: int,
        result: dict[str, Any],
        direct_sender: MessageSender | None,
    ) -> None:
        """Un receptor offline conserva la experiencia y verá su estado al reconectar."""
        for user_string, level in result["levels"].items():
            user = int(user_string)
            sender = self.owner.map_manager.get_player_message_sender(user)
            if sender is None and user == killer:
                sender = direct_sender
            if sender is None:
                continue
            await sender.send_update_exp(level["experience"])
            await publish_progress(self.owner.player_repo, user, sender)
            prefix = (
                f"¡Has matado a {npc.name}!" if user == killer else f"Tu party mató a {npc.name}."
            )
            await sender.send_console_msg(f"{prefix} Ganaste {level['awarded']} EXP.")
            if level["level"] > level["previous_level"]:
                await sender.play_sound_level_up()
                await sender.send_console_msg(
                    f"¡Felicidades! Has subido al nivel {level['level']}!"
                )
