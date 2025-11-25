"""Servicio para gestionar comercio entre jugadores."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TradeState(StrEnum):
    """Posibles estados de una sesión de comercio."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TradeOfferItem:
    """Item ofrecido en la sesión."""

    slot: int
    item_id: int
    quantity: int


@dataclass
class TradeOffer:
    """Oferta actual de un jugador."""

    items: dict[int, TradeOfferItem] = field(default_factory=dict)
    gold: int = 0


@dataclass
class TradeSession:
    """Representa una sesión de comercio entre dos jugadores."""

    initiator_id: int
    initiator_username: str
    target_id: int
    target_username: str
    state: TradeState
    created_at: float
    last_update: float
    initiator_confirmed: bool = False
    target_confirmed: bool = False
    initiator_offer: TradeOffer = field(default_factory=TradeOffer)
    target_offer: TradeOffer = field(default_factory=TradeOffer)


class TradeService:
    """Gestiona la vida de las sesiones de comercio jugador-jugador."""

    GOLD_SLOT = 0

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_manager: MapManager,
    ) -> None:
        """Inicializa TradeService con dependencias necesarias."""
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self._sessions_by_user: dict[int, TradeSession] = {}

    async def request_trade(self, initiator_id: int, target_username: str) -> tuple[bool, str]:
        """Inicia una solicitud de comercio entre jugadores.

        Returns:
            Tupla (éxito, mensaje descriptivo).
        """
        target_id = self._find_player_by_username(target_username)
        if target_id is None:
            return False, f"El usuario '{target_username}' no está conectado."

        if target_id == initiator_id:
            return False, "No puedes comerciar contigo mismo."

        if self.is_user_in_trade(initiator_id):
            return False, "Ya tienes una sesión de comercio abierta."

        if self.is_user_in_trade(target_id):
            target_name = self._resolve_username(target_id)
            return False, f"{target_name} ya está comerciando."

        initiator_username = self._resolve_username(initiator_id)
        resolved_target_username = self._resolve_username(target_id)

        session = TradeSession(
            initiator_id=initiator_id,
            initiator_username=initiator_username,
            target_id=target_id,
            target_username=resolved_target_username,
            state=TradeState.PENDING,
            created_at=time.time(),
            last_update=time.time(),
        )
        self._store_session(session)

        await self._notify_trade_init(session)

        logger.info(
            "Solicitud de comercio creada: %s (%d) -> %s (%d)",
            initiator_username,
            initiator_id,
            resolved_target_username,
            target_id,
        )

        return True, f"Solicitud de comercio enviada a {resolved_target_username}."

    async def cancel_trade(self, user_id: int, reason: str | None = None) -> tuple[bool, str]:
        """Cancela la sesión de comercio del usuario.

        Returns:
            Tupla (éxito, mensaje) describiendo la operación.
        """
        session = self.get_session(user_id)
        if not session:
            return False, "No tienes una sesión de comercio activa."

        message = reason or "La sesión de comercio fue cancelada."
        await self._send_trade_end(session, message)
        self.clear_session(user_id)
        return True, message

    async def confirm_trade(self, user_id: int) -> tuple[bool, str]:
        """Marca al usuario como listo para comerciar.

        Returns:
            Tupla (éxito, mensaje) describiendo la operación.
        """
        session = self.get_session(user_id)
        if not session:
            return False, "No tienes una sesión de comercio activa."

        if user_id == session.initiator_id:
            session.initiator_confirmed = True
        else:
            session.target_confirmed = True

        session.last_update = time.time()
        await self._notify_console(user_id, "Marcaste listo para el intercambio.", font_color=7)

        if session.initiator_confirmed and session.target_confirmed:
            success, message = await self._perform_trade(session)
            if success:
                await self._notify_console(
                    session.initiator_id, "Intercambio completado.", font_color=7
                )
                await self._notify_console(
                    session.target_id, "Intercambio completado.", font_color=7
                )
                self.clear_session(user_id)
                return True, "Intercambio completado."

            session.initiator_confirmed = False
            session.target_confirmed = False
            await self._notify_console(session.initiator_id, message, font_color=1)
            await self._notify_console(session.target_id, message, font_color=1)
            return False, message

        return True, "Confirmación registrada."

    async def ready_trade(self, user_id: int) -> tuple[bool, str]:
        """Alias de confirm_trade para paquetes USER_COMMERCE_OK.

        Returns:
            Tupla (éxito, mensaje) describiendo la operación.
        """
        return await self.confirm_trade(user_id)

    async def reject_trade(self, user_id: int) -> tuple[bool, str]:
        """Rechaza la sesión de comercio actual.

        Returns:
            Tupla (éxito, mensaje) describiendo la operación.
        """
        return await self.cancel_trade(user_id, "Comercio rechazado.")

    async def update_offer(self, user_id: int, slot: int, quantity: int) -> tuple[bool, str]:
        """Actualiza la oferta (items o oro) de un jugador.

        Returns:
            Tupla (éxito, mensaje) describiendo la operación.
        """
        session = self.get_session(user_id)
        if not session:
            return False, "No tienes una sesión de comercio activa."

        if quantity < 0:
            return False, "La cantidad debe ser positiva."

        if slot == self.GOLD_SLOT:
            return await self._update_offer_gold(session, user_id, quantity)

        return await self._update_offer_item(session, user_id, slot, quantity)

    def get_session(self, user_id: int) -> TradeSession | None:
        """Obtiene la sesión asociada a un usuario.

        Returns:
            TradeSession si existe, None en caso contrario.
        """
        return self._sessions_by_user.get(user_id)

    def is_user_in_trade(self, user_id: int) -> bool:
        """Indica si el usuario ya participa de una sesión.

        Returns:
            True si el usuario tiene una sesión registrada.
        """
        return user_id in self._sessions_by_user

    def clear_session(self, user_id: int) -> None:
        """Elimina la sesión asociada al usuario."""
        session = self._sessions_by_user.get(user_id)
        if not session:
            return

        for participant_id in {session.initiator_id, session.target_id}:
            self._sessions_by_user.pop(participant_id, None)

    def _store_session(self, session: TradeSession) -> None:
        """Almacena la sesión para ambos jugadores."""
        self._sessions_by_user[session.initiator_id] = session
        self._sessions_by_user[session.target_id] = session

    @staticmethod
    def _get_offer(session: TradeSession, user_id: int) -> TradeOffer:
        if user_id == session.initiator_id:
            return session.initiator_offer
        return session.target_offer

    @staticmethod
    def _get_partner_id(session: TradeSession, user_id: int) -> int:
        return session.target_id if user_id == session.initiator_id else session.initiator_id

    @staticmethod
    def _reset_confirmations(session: TradeSession) -> None:
        session.initiator_confirmed = False
        session.target_confirmed = False
        session.state = TradeState.PENDING

    async def _notify_trade_init(self, session: TradeSession) -> None:
        """Envía USER_COMMERCE_INIT y mensajes de consola a ambos jugadores."""
        initiator_sender = self._get_sender(session.initiator_id)
        target_sender = self._get_sender(session.target_id)

        if initiator_sender:
            await initiator_sender.send_user_commerce_init(session.target_username)
            await initiator_sender.send_console_msg(
                f"Iniciaste comercio con {session.target_username}.",
                font_color=7,
            )

        if target_sender:
            await target_sender.send_user_commerce_init(session.initiator_username)
            await target_sender.send_console_msg(
                f"{session.initiator_username} quiere comerciar contigo.",
                font_color=7,
            )

    async def _send_trade_end(self, session: TradeSession, message: str) -> None:
        """Envía USER_COMMERCE_END y un mensaje de consola a ambos jugadores."""
        for participant in (session.initiator_id, session.target_id):
            sender = self._get_sender(participant)
            if sender:
                await sender.send_user_commerce_end()
                await sender.send_console_msg(message, font_color=1)

    async def _notify_console(self, user_id: int, message: str, font_color: int = 7) -> None:
        """Envía un mensaje de consola si el jugador está conectado."""
        sender = self._get_sender(user_id)
        if sender:
            await sender.send_console_msg(message, font_color=font_color)

    def _get_sender(self, user_id: int) -> MessageSender | None:
        """Obtiene el MessageSender asociado a un jugador.

        Returns:
            Instancia de MessageSender si el jugador está conectado, None en caso contrario.
        """
        return self.map_manager.get_player_message_sender(user_id)

    def _find_player_by_username(self, username: str) -> int | None:
        """Busca un jugador conectado por nombre.

        Returns:
            user_id si se encuentra, None en caso contrario.
        """
        return self.map_manager.find_player_by_username(username)

    def _resolve_username(self, user_id: int) -> str:
        """Obtiene el username desde el map manager o genera uno por defecto.

        Returns:
            Username conocido o un nombre genérico.
        """
        username = self.map_manager.get_player_username(user_id)
        if username:
            return username
        return f"Jugador{user_id}"

    async def _update_offer_item(
        self, session: TradeSession, user_id: int, slot: int, quantity: int
    ) -> tuple[bool, str]:
        if slot <= 0:
            return False, "Slot inválido."

        offer = self._get_offer(session, user_id)

        if quantity == 0:
            offer.items.pop(slot, None)
            self._reset_confirmations(session)
            await self._notify_console(user_id, f"Quitaste la oferta del slot {slot}.")
            partner_id = self._get_partner_id(session, user_id)
            await self._notify_console(
                partner_id, f"{self._resolve_username(user_id)} actualizó su oferta."
            )
            return True, "Oferta actualizada."

        slot_content = await self.inventory_repo.get_slot(user_id, slot)
        if not slot_content:
            return False, "El slot seleccionado está vacío."

        item_id, slot_quantity = slot_content

        if quantity > slot_quantity:
            return False, "No tienes esa cantidad en el slot."

        existing = offer.items.get(slot)
        if existing and existing.item_id != item_id:
            return False, "Ese slot ya contiene otra oferta."

        offer.items[slot] = TradeOfferItem(slot=slot, item_id=item_id, quantity=quantity)
        await self._notify_console(
            user_id, f"Ofreces {quantity} unidad(es) del item en slot {slot}."
        )
        partner_id = self._get_partner_id(session, user_id)
        self._reset_confirmations(session)
        await self._notify_console(
            partner_id, f"{self._resolve_username(user_id)} actualizó su oferta."
        )
        return True, "Oferta actualizada."

    async def _update_offer_gold(
        self, session: TradeSession, user_id: int, quantity: int
    ) -> tuple[bool, str]:
        current_gold = await self.player_repo.get_gold(user_id)
        if quantity > current_gold:
            return False, "No tienes tanto oro."

        offer = self._get_offer(session, user_id)
        offer.gold = quantity

        partner_id = self._get_partner_id(session, user_id)
        self._reset_confirmations(session)
        if quantity == 0:
            await self._notify_console(user_id, "Quitaste la oferta de oro.")
        else:
            await self._notify_console(user_id, f"Ofreces {quantity} monedas de oro.")
        await self._notify_console(
            partner_id, f"{self._resolve_username(user_id)} cambió su oferta de oro."
        )
        return True, "Oferta de oro actualizada."

    async def _perform_trade(self, session: TradeSession) -> tuple[bool, str]:
        participants = [
            (session.initiator_id, session.initiator_offer, session.target_id),
            (session.target_id, session.target_offer, session.initiator_id),
        ]

        validation = await self._validate_offers(participants)
        if validation is not None:
            return False, validation

        removed_items: list[tuple[int, TradeOfferItem]] = []
        removed_gold: list[tuple[int, int]] = []

        for user_id, offer, _ in participants:
            for item in offer.items.values():
                success = await self.inventory_repo.remove_item(user_id, item.slot, item.quantity)
                if not success:
                    await self._refund_removed_resources(removed_items, removed_gold)
                    return False, "No se pudo reservar un item del comercio."
                removed_items.append((user_id, item))

            if offer.gold:
                success = await self.player_repo.remove_gold(user_id, offer.gold)
                if not success:
                    await self._refund_removed_resources(removed_items, removed_gold)
                    return False, "No tienes suficiente oro para completar el intercambio."
                removed_gold.append((user_id, offer.gold))

        delivered_items: list[tuple[int, int, int]] = []
        delivered_gold: list[tuple[int, int]] = []

        for _source_id, offer, target_id in participants:
            for item in offer.items.values():
                slots_modified = await self.inventory_repo.add_item(
                    target_id, item.item_id, item.quantity
                )
                if not slots_modified:
                    await self._rollback_trade(
                        removed_items, removed_gold, delivered_items, delivered_gold
                    )
                    return (
                        False,
                        f"{self._resolve_username(target_id)} no tiene espacio suficiente.",
                    )
                delivered_items.append((target_id, item.item_id, item.quantity))

            if offer.gold:
                await self.player_repo.add_gold(target_id, offer.gold)
                delivered_gold.append((target_id, offer.gold))

        return True, "Intercambio completado."

    async def _validate_offers(self, participants: list[tuple[int, TradeOffer, int]]) -> str | None:
        for user_id, offer, _ in participants:
            for item in offer.items.values():
                slot_content = await self.inventory_repo.get_slot(user_id, item.slot)
                if not slot_content:
                    username = self._resolve_username(user_id)
                    return f"{username} ya no tiene el item del slot {item.slot}."
                item_id, quantity = slot_content
                if item_id != item.item_id or quantity < item.quantity:
                    return f"{self._resolve_username(user_id)} modificó el slot {item.slot}."

            gold_available = await self.player_repo.get_gold(user_id)
            if offer.gold > gold_available:
                return f"{self._resolve_username(user_id)} ya no tiene ese oro disponible."
        return None

    async def _refund_removed_resources(
        self, removed_items: list[tuple[int, TradeOfferItem]], removed_gold: list[tuple[int, int]]
    ) -> None:
        for user_id, item in removed_items:
            added = await self.inventory_repo.add_item(user_id, item.item_id, item.quantity)
            if not added:
                logger.error("No se pudo devolver item %s al jugador %d", item, user_id)

        for user_id, amount in removed_gold:
            await self.player_repo.add_gold(user_id, amount)

    async def _rollback_trade(
        self,
        removed_items: list[tuple[int, TradeOfferItem]],
        removed_gold: list[tuple[int, int]],
        delivered_items: list[tuple[int, int, int]],
        delivered_gold: list[tuple[int, int]],
    ) -> None:
        for user_id, item_id, quantity in delivered_items:
            success = await self.inventory_repo.remove_item_by_item_id(user_id, item_id, quantity)
            if not success:
                logger.error("No se pudo revertir item %d en inventario de %d", item_id, user_id)

        for user_id, amount in delivered_gold:
            removed = await self.player_repo.remove_gold(user_id, amount)
            if not removed:
                logger.error("No se pudo revertir oro entregado a %d", user_id)

        await self._refund_removed_resources(removed_items, removed_gold)
