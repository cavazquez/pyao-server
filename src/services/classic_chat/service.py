"""Despacho exacto del catálogo clásico, con identidad y permisos de servidor."""

from typing import TYPE_CHECKING

from src.config.config_manager import config_manager
from src.security.account_bans import is_blocked
from src.services.classic_chat.admin_accounts import HANDLERS as ACCOUNT_HANDLERS
from src.services.classic_chat.admin_character import HANDLERS as CHARACTER_HANDLERS
from src.services.classic_chat.admin_moderation import HANDLERS as MODERATION_HANDLERS
from src.services.classic_chat.admin_npcs import HANDLERS as NPC_HANDLERS
from src.services.classic_chat.admin_operations import HANDLERS as OPERATION_HANDLERS
from src.services.classic_chat.admin_presentation import HANDLERS as PRESENTATION_HANDLERS
from src.services.classic_chat.admin_queries import HANDLERS as QUERY_HANDLERS
from src.services.classic_chat.admin_social import HANDLERS as ADMIN_SOCIAL_HANDLERS
from src.services.classic_chat.admin_tools import HANDLERS as TOOL_HANDLERS
from src.services.classic_chat.admin_world import HANDLERS as WORLD_HANDLERS
from src.services.classic_chat.catalog import COMMANDS, command_token, help_text
from src.services.classic_chat.collective import HANDLERS as COLLECTIVE_HANDLERS
from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.services.classic_chat.factions import HANDLERS as FACTION_HANDLERS
from src.services.classic_chat.native import NATIVE_NAMES, native
from src.services.classic_chat.player import HANDLERS as PLAYER_HANDLERS
from src.services.classic_chat.social import HANDLERS as SOCIAL_HANDLERS

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender


HANDLERS = {
    **PLAYER_HANDLERS,
    **SOCIAL_HANDLERS,
    **CHARACTER_HANDLERS,
    **QUERY_HANDLERS,
    **ACCOUNT_HANDLERS,
    **FACTION_HANDLERS,
    **COLLECTIVE_HANDLERS,
    **TOOL_HANDLERS,
    **PRESENTATION_HANDLERS,
    **WORLD_HANDLERS,
    **NPC_HANDLERS,
    **MODERATION_HANDLERS,
    **OPERATION_HANDLERS,
    **ADMIN_SOCIAL_HANDLERS,
}

MAP_EDITS = frozenset({"/BLOQ", "/TRIGGER", "/CT", "/DT", "/MODMAPINFO"})


class ClassicChatService:
    """No interpreta prefijos, evalúa código ni usa argumentos como identidad."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte los servicios reales y mantiene todo el progreso en Redis."""
        self.deps = deps

    async def execute(self, user: int, text: str, sender: MessageSender) -> None:
        """Valida autorización antes de acceder a datos o ejecutar una acción."""
        name = command_token(text)
        if name in MAP_EDITS:
            account = await self.deps.account_repo.get_account_by_user_id(user) or {}
            if account.get("is_gm") != "1" or is_blocked(account, prefix="ban_"):
                await sender.send_console_msg("No tienes permisos de Game Master.")
                return
            async with self.deps.map_manager.map_edit_lock:
                # _execute vuelve a validar el rol después de cualquier espera.
                await self._execute(user, text, sender)
            return
        social = self.deps.world_state
        if social is not None and name in {
            "/FUNDARCLANGM",
            "/RAJARCLAN",
            "/BANCLAN",
            "/VOTO",
            "/ELECCIONES",
            "/ANAME",
        }:
            async with social.lock:
                await self._execute(user, text, sender)
        else:
            await self._execute(user, text, sender)

    async def _execute(self, user: int, text: str, sender: MessageSender) -> None:
        name = command_token(text)
        definition = COMMANDS.get(name)
        if definition is None:
            await sender.send_console_msg("Comando desconocido. Usa /AYUDA.")
            return
        account = await self.deps.account_repo.get_account_by_user_id(user) or {}
        gm = account.get("is_gm") == "1" and not is_blocked(account, prefix="ban_")
        if definition.role == "gm" and not gm:
            await sender.send_console_msg("No tienes permisos de Game Master.")
            return
        pieces = text.strip().split(maxsplit=1)
        ctx = ChatContext(self.deps, user, sender, name, pieces[1] if len(pieces) > 1 else "", gm)
        try:
            handler = HANDLERS.get(name)
            if name == "/AYUDA":
                await ctx.tell(
                    help_text(
                        gm=gm,
                        page=int(ctx.arguments or "1"),
                        autoupdate=bool(config_manager.get("server.autoupdate_hook", "")),
                    )
                )
            elif handler:
                await handler(ctx)
            elif name in NATIVE_NAMES:
                await native(ctx)
            elif definition.transport == "form":
                await ctx.tell(
                    f"Abre {definition.description.lower()} desde la interfaz del cliente."
                )
            else:
                # Administrative/collective services are registered explicitly;
                # unimplemented entries are never advertised as successful actions.
                await sender.send_console_msg(f"El comando {name} aún no está habilitado.")
        except ChatCommandError as error:
            await sender.send_console_msg(str(error))
        except ValueError, KeyError, IndexError:
            await sender.send_console_msg(f"No se pudo completar {name}. Uso: {definition.syntax}")
