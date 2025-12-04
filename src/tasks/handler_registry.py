"""Registry para creación de command handlers con inyección de dependencias."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.command_handlers.attack_handler import AttackCommandHandler
from src.command_handlers.ayuda_handler import AyudaCommandHandler
from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_end_handler import BankEndCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.command_handlers.change_heading_handler import ChangeHeadingCommandHandler
from src.command_handlers.commerce_buy_handler import CommerceBuyCommandHandler
from src.command_handlers.commerce_end_handler import CommerceEndCommandHandler
from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
from src.command_handlers.create_account_handler import CreateAccountCommandHandler
from src.command_handlers.dice_handler import DiceCommandHandler
from src.command_handlers.double_click_handler import DoubleClickCommandHandler
from src.command_handlers.drop_handler import DropCommandHandler
from src.command_handlers.equip_item_handler import EquipItemCommandHandler
from src.command_handlers.gm_command_handler import GMCommandHandler
from src.command_handlers.information_handler import InformationCommandHandler
from src.command_handlers.inventory_click_handler import InventoryClickCommandHandler
from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
from src.command_handlers.left_click_handler import LeftClickCommandHandler
from src.command_handlers.login_handler import LoginCommandHandler
from src.command_handlers.meditate_handler import MeditateCommandHandler
from src.command_handlers.motd_handler import MotdCommandHandler
from src.command_handlers.move_spell_handler import MoveSpellCommandHandler
from src.command_handlers.online_handler import OnlineCommandHandler
from src.command_handlers.party_accept_handler import PartyAcceptCommandHandler
from src.command_handlers.party_create_handler import PartyCreateCommandHandler
from src.command_handlers.party_join_handler import PartyJoinCommandHandler
from src.command_handlers.party_kick_handler import PartyKickCommandHandler
from src.command_handlers.party_leave_handler import PartyLeaveCommandHandler
from src.command_handlers.party_message_handler import PartyMessageCommandHandler
from src.command_handlers.party_set_leader_handler import PartySetLeaderCommandHandler
from src.command_handlers.pickup_handler import PickupCommandHandler
from src.command_handlers.ping_handler import PingCommandHandler
from src.command_handlers.quit_handler import QuitCommandHandler
from src.command_handlers.request_attributes_handler import RequestAttributesCommandHandler
from src.command_handlers.request_clan_details_handler import RequestClanDetailsCommandHandler
from src.command_handlers.request_position_update_handler import (
    RequestPositionUpdateCommandHandler,
)
from src.command_handlers.request_skills_handler import RequestSkillsCommandHandler
from src.command_handlers.request_stats_handler import RequestStatsCommandHandler
from src.command_handlers.spell_info_handler import SpellInfoCommandHandler
from src.command_handlers.talk_handler import TalkCommandHandler
from src.command_handlers.update_player_trade_handler import UpdatePlayerTradeCommandHandler
from src.command_handlers.update_trade_offer_handler import UpdateTradeOfferCommandHandler
from src.command_handlers.uptime_handler import UptimeCommandHandler
from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.command_handlers.walk_handler import WalkCommandHandler
from src.command_handlers.work_handler import WorkCommandHandler
from src.command_handlers.work_left_click_handler import WorkLeftClickCommandHandler
from src.commands.base import CommandHandler  # noqa: TC001 - usado en runtime

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.tasks.dependencies import TaskDependencies


@dataclass
class HandlerConfig:
    """Configuración para crear un handler."""

    handler_class: type[CommandHandler]
    deps_keys: list[str] = field(default_factory=list)
    needs_session_data: bool = False


# Mapeo de nombres de handler a su configuración
HANDLER_CONFIGS: dict[str, HandlerConfig] = {
    # Handlers simples (solo message_sender)
    "ping": HandlerConfig(PingCommandHandler),
    "ayuda": HandlerConfig(AyudaCommandHandler),
    "commerce_end": HandlerConfig(CommerceEndCommandHandler),
    "bank_end": HandlerConfig(BankEndCommandHandler),
    "motd": HandlerConfig(MotdCommandHandler),
    "uptime": HandlerConfig(UptimeCommandHandler),
    "quit": HandlerConfig(QuitCommandHandler),
    "dice": HandlerConfig(DiceCommandHandler),
    # Handlers con player_repo
    "meditate": HandlerConfig(
        MeditateCommandHandler,
        deps_keys=["player_repo"],
    ),
    "request_stats": HandlerConfig(
        RequestStatsCommandHandler,
        deps_keys=["player_repo"],
    ),
    "request_attributes": HandlerConfig(
        RequestAttributesCommandHandler,
        deps_keys=["player_repo"],
    ),
    "request_skills": HandlerConfig(
        RequestSkillsCommandHandler,
        deps_keys=["player_repo"],
    ),
    "request_position_update": HandlerConfig(
        RequestPositionUpdateCommandHandler,
        deps_keys=["player_repo"],
    ),
    "online": HandlerConfig(
        OnlineCommandHandler,
        deps_keys=["player_repo"],
    ),
    "information": HandlerConfig(
        InformationCommandHandler,
        deps_keys=["player_repo"],
    ),
    # Handlers de spellbook
    "spell_info": HandlerConfig(
        SpellInfoCommandHandler,
        deps_keys=["spellbook_repo", "spell_catalog"],
    ),
    "move_spell": HandlerConfig(
        MoveSpellCommandHandler,
        deps_keys=["spellbook_repo", "spell_catalog"],
    ),
    "cast_spell": HandlerConfig(
        CastSpellCommandHandler,
        deps_keys=["player_repo", "spell_service", "spellbook_repo", "stamina_service"],
    ),
    # Handlers de inventario
    "equip_item": HandlerConfig(
        EquipItemCommandHandler,
        deps_keys=["player_repo", "equipment_repo"],
    ),
    "inventory_click": HandlerConfig(
        InventoryClickCommandHandler,
        deps_keys=["player_repo", "equipment_repo"],
    ),
    "double_click": HandlerConfig(
        DoubleClickCommandHandler,
        deps_keys=["player_repo", "map_manager"],
    ),
    # Handlers de trabajo
    "work": HandlerConfig(
        WorkCommandHandler,
        deps_keys=["player_repo", "inventory_repo", "map_resources_service"],
    ),
    "work_left_click": HandlerConfig(
        WorkLeftClickCommandHandler,
        deps_keys=["player_repo", "inventory_repo", "map_resources_service"],
    ),
    # Handlers de banco
    "bank_deposit": HandlerConfig(
        BankDepositCommandHandler,
        deps_keys=["bank_repo", "inventory_repo", "player_repo"],
    ),
    "bank_extract": HandlerConfig(
        BankExtractCommandHandler,
        deps_keys=["bank_repo", "inventory_repo", "player_repo"],
    ),
    "bank_deposit_gold": HandlerConfig(
        BankDepositGoldCommandHandler,
        deps_keys=["player_repo", "bank_repo"],
    ),
    "bank_extract_gold": HandlerConfig(
        BankExtractGoldCommandHandler,
        deps_keys=["player_repo", "bank_repo"],
    ),
    # Handlers de comercio
    "commerce_buy": HandlerConfig(
        CommerceBuyCommandHandler,
        deps_keys=["commerce_service", "player_repo", "inventory_repo", "redis_client"],
    ),
    "commerce_sell": HandlerConfig(
        CommerceSellCommandHandler,
        deps_keys=["commerce_service", "player_repo", "inventory_repo", "redis_client"],
    ),
    # Handlers de items
    "drop": HandlerConfig(
        DropCommandHandler,
        deps_keys=[
            "player_repo",
            "inventory_repo",
            "map_manager",
            "broadcast_service",
            "item_catalog",
        ],
    ),
    "pickup": HandlerConfig(
        PickupCommandHandler,
        deps_keys=[
            "player_repo",
            "inventory_repo",
            "map_manager",
            "broadcast_service",
            "item_catalog",
            "party_service",
        ],
    ),
    "use_item": HandlerConfig(
        UseItemCommandHandler,
        deps_keys=[
            "player_repo",
            "map_resources_service",
            "account_repo",
            "item_catalog",
            "broadcast_service",
            "map_manager",
        ],
    ),
    # Handlers de movimiento/combate
    "walk": HandlerConfig(
        WalkCommandHandler,
        deps_keys=[
            "player_repo",
            "map_manager",
            "broadcast_service",
            "stamina_service",
            "player_map_service",
            "inventory_repo",
            "map_resources_service",
        ],
    ),
    "attack": HandlerConfig(
        AttackCommandHandler,
        deps_keys=[
            "player_repo",
            "combat_service",
            "map_manager",
            "npc_service",
            "broadcast_service",
            "npc_death_service",
            "npc_respawn_service",
            "loot_table_service",
            "item_catalog",
            "stamina_service",
        ],
    ),
    # Handlers de interacción
    "left_click": HandlerConfig(
        LeftClickCommandHandler,
        deps_keys=[
            "player_repo",
            "map_manager",
            "map_resources_service",
            "bank_repo",
            "merchant_repo",
            "door_service",
            "door_repo",
            "redis_client",
        ],
    ),
    # Handlers de party
    "party_create": HandlerConfig(
        PartyCreateCommandHandler,
        deps_keys=["party_service"],
    ),
    "party_join": HandlerConfig(
        PartyJoinCommandHandler,
        deps_keys=["party_service"],
    ),
    "party_accept": HandlerConfig(
        PartyAcceptCommandHandler,
        deps_keys=["party_service"],
    ),
    "party_leave": HandlerConfig(
        PartyLeaveCommandHandler,
        deps_keys=["party_service"],
    ),
    "party_message": HandlerConfig(
        PartyMessageCommandHandler,
        deps_keys=["party_service", "broadcast_service"],
    ),
    "party_kick": HandlerConfig(
        PartyKickCommandHandler,
        deps_keys=["party_service"],
    ),
    "party_set_leader": HandlerConfig(
        PartySetLeaderCommandHandler,
        deps_keys=["party_service"],
    ),
    # Handlers de clan
    "leave_clan": HandlerConfig(
        LeaveClanCommandHandler,
        deps_keys=["clan_service"],
    ),
    "request_clan_details": HandlerConfig(
        RequestClanDetailsCommandHandler,
        deps_keys=["clan_service"],
    ),
    # Handlers de trade
    "trade_update": HandlerConfig(
        UpdatePlayerTradeCommandHandler,
        deps_keys=["trade_service"],
    ),
    "trade_offer": HandlerConfig(
        UpdateTradeOfferCommandHandler,
        deps_keys=["trade_service"],
    ),
    # Handlers complejos con session_data
    "change_heading": HandlerConfig(
        ChangeHeadingCommandHandler,
        deps_keys=["player_repo", "account_repo", "map_manager"],
        needs_session_data=True,
    ),
    "talk": HandlerConfig(
        TalkCommandHandler,
        deps_keys=[
            "player_repo",
            "account_repo",
            "map_manager",
            "game_tick",
            "clan_service",
            "trade_service",
            "npc_service",
            "summon_service",
        ],
        needs_session_data=True,
    ),
    "login": HandlerConfig(
        LoginCommandHandler,
        deps_keys=[
            "player_repo",
            "account_repo",
            "map_manager",
            "server_repo",
            "spellbook_repo",
            "spell_catalog",
            "equipment_repo",
            "player_map_service",
        ],
        needs_session_data=True,
    ),
    "create_account": HandlerConfig(
        CreateAccountCommandHandler,
        deps_keys=[
            "player_repo",
            "account_repo",
            "map_manager",
            "npc_service",
            "server_repo",
            "spellbook_repo",
            "spell_catalog",
            "equipment_repo",
            "player_map_service",
        ],
        needs_session_data=True,
    ),
    "gm_command": HandlerConfig(
        GMCommandHandler,
        deps_keys=["player_repo", "account_repo", "player_map_service"],
    ),
}


class HandlerRegistry:
    """Registry para gestionar la creación y caché de command handlers."""

    def __init__(self, deps: TaskDependencies) -> None:
        """Inicializa el registry.

        Args:
            deps: Dependencias compartidas de la aplicación.
        """
        self.deps = deps
        self._cache: dict[str, CommandHandler] = {}

    def get(
        self,
        name: str,
        message_sender: MessageSender,
        session_data: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401 - retorna handler específico, tipo exacto no inferible
        """Obtiene o crea un handler por nombre.

        Args:
            name: Nombre del handler (ej: "attack", "walk").
            message_sender: Enviador de mensajes para el cliente.
            session_data: Datos de sesión (opcional, solo para algunos handlers).

        Returns:
            Instancia del handler solicitado.

        Raises:
            KeyError: Si el handler no está registrado.
        """
        config = HANDLER_CONFIGS.get(name)
        if config is None:
            msg = f"Handler '{name}' no registrado"
            raise KeyError(msg)

        handler = self._cache.get(name)

        if handler is None:
            # Construir kwargs de dependencias
            kwargs = self._build_kwargs(config, message_sender, session_data)
            handler = config.handler_class(**kwargs)
            self._cache[name] = handler
        else:
            # Actualizar message_sender y session_data si es necesario
            handler.message_sender = message_sender
            if config.needs_session_data and session_data is not None:
                handler.session_data = session_data  # type: ignore[attr-defined]

        return handler

    def _build_kwargs(
        self,
        config: HandlerConfig,
        message_sender: MessageSender,
        session_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Construye los kwargs para instanciar un handler.

        Args:
            config: Configuración del handler.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión.

        Returns:
            Diccionario de kwargs para el constructor.
        """
        kwargs: dict[str, Any] = {"message_sender": message_sender}

        # Agregar dependencias desde deps
        for key in config.deps_keys:
            value = getattr(self.deps, key, None)
            # Mapear nombres de atributo a nombres de parámetro si difieren
            param_name = self._get_param_name(key)
            kwargs[param_name] = value

        # Agregar session_data si es necesario
        if config.needs_session_data:
            kwargs["session_data"] = session_data

        return kwargs

    @staticmethod
    def _get_param_name(dep_key: str) -> str:
        """Mapea nombre de dependencia a nombre de parámetro del constructor.

        Args:
            dep_key: Nombre del atributo en TaskDependencies.

        Returns:
            Nombre del parámetro en el constructor del handler.
        """
        # Mapeos especiales donde el nombre difiere
        mappings = {
            "map_resources_service": "map_resources",
        }
        return mappings.get(dep_key, dep_key)

    def clear_cache(self) -> None:
        """Limpia la caché de handlers."""
        self._cache.clear()
