"""Broadcast service for sending messages to multiple users."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for broadcasting messages to multiple users."""
    
    def __init__(self):
        """Initialize broadcast service."""
        self.user_connections: dict[int, "MessageSender"] = {}
    
    def register_user(self, user_id: int, message_sender: "MessageSender") -> None:
        """Register a user's message sender for broadcasting.
        
        Args:
            user_id: User ID
            message_sender: MessageSender instance for this user
        """
        self.user_connections[user_id] = message_sender
        logger.debug(f"Registered user {user_id} for broadcasting")
    
    def unregister_user(self, user_id: int) -> None:
        """Unregister a user from broadcasting.
        
        Args:
            user_id: User ID to unregister
        """
        if user_id in self.user_connections:
            del self.user_connections[user_id]
            logger.debug(f"Unregistered user {user_id} from broadcasting")
    
    async def send_to_user(self, user_id: int, message: str, font_color: int = 7) -> bool:
        """Send a message to a specific user.
        
        Args:
            user_id: Target user ID
            message: Message to send
            font_color: Font color for the message
            
        Returns:
            True if message was sent, False if user not connected
        """
        message_sender = self.user_connections.get(user_id)
        if not message_sender:
            logger.warning(f"Cannot send message to user {user_id}: not connected")
            return False
        
        try:
            await message_sender.send_console_msg(message, font_color=font_color)
            return True
        except Exception:
            logger.exception(f"Error sending message to user {user_id}")
            return False
    
    async def send_to_users(self, user_ids: list[int], message: str, font_color: int = 7) -> int:
        """Send a message to multiple users.
        
        Args:
            user_ids: List of user IDs to send to
            message: Message to send
            font_color: Font color for the message
            
        Returns:
            Number of users who received the message
        """
        sent_count = 0
        for user_id in user_ids:
            if await self.send_to_user(user_id, message, font_color):
                sent_count += 1
        
        logger.debug(f"Broadcast message to {sent_count}/{len(user_ids)} users")
        return sent_count
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if a user is online.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user is online, False otherwise
        """
        return user_id in self.user_connections
