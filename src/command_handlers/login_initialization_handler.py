"""Handler especializado para inicialización de datos del jugador durante login."""

import logging
from typing import TYPE_CHECKING

from src.services.player.player_service import PlayerService

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.spellbook_repository import SpellbookRepository

logger = logging.getLogger(__name__)


class LoginInitializationHandler:
    """Handler especializado para inicialización de datos del jugador durante login."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        spellbook_repo: SpellbookRepository | None,
        spell_catalog: SpellCatalog | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de inicialización.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            spellbook_repo: Repositorio de libro de hechizos.
            spell_catalog: Catálogo de hechizos.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.message_sender = message_sender

    async def send_login_packets(self, user_id: int, user_class: int) -> dict[str, int]:
        """Envía los paquetes iniciales de login.

        IMPORTANTE: Orden de envío de paquetes durante el login.
        Este orden es crítico para evitar problemas de parsing en el cliente.

        Orden correcto:
        1. LOGGED (ID: 0)
        2. USER_CHAR_INDEX_IN_SERVER (ID: 28)
        3. CHANGE_MAP (ID: 21)
        4. UPDATE_STRENGTH_AND_DEXTERITY (ID: 102)
        5. UPDATE_USER_STATS (ID: 45)

        Args:
            user_id: ID del usuario.
            user_class: Clase del personaje.

        Returns:
            Diccionario con la posición del jugador.
        """
        logger.info("[LOGIN-PACKETS] user_id=%d Iniciando envío de paquetes de login", user_id)

        # Enviar paquete Logged con la clase del personaje
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Enviando LOGGED (ID=0) class=%d", user_id, user_class
        )
        await self.message_sender.send_logged(user_class)

        # Enviar índice del personaje en el servidor
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Enviando USER_CHAR_INDEX_IN_SERVER (ID=28)", user_id
        )
        await self.message_sender.send_user_char_index_in_server(user_id)

        # Crear servicio de jugador
        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)

        # Obtener/crear y enviar posición (envía CHANGE_MAP)
        logger.info("[LOGIN-PACKETS] user_id=%d Enviando CHANGE_MAP (ID=21)", user_id)
        position = await player_service.send_position(user_id)
        logger.info(
            "[LOGIN-PACKETS] user_id=%d Posición: map=%d x=%d y=%d",
            user_id,
            position["map"],
            position["x"],
            position["y"],
        )

        # Crear atributos por defecto si no existen
        attributes = await player_service.send_attributes(user_id)
        logger.info("[LOGIN-PACKETS] user_id=%d Atributos obtenidos: %s", user_id, attributes)

        if attributes:
            str_val = await self.player_repo.get_strength(user_id)
            agi_val = await self.player_repo.get_agility(user_id)
            logger.info(
                "[LOGIN-PACKETS] user_id=%d UPDATE_STRENGTH_AND_DEXTERITY str=%d agi=%d",
                user_id,
                str_val,
                agi_val,
            )
            await self.message_sender.send_update_strength_and_dexterity(
                strength=str_val,
                dexterity=agi_val,
            )

        # Obtener/crear y enviar stats
        logger.info("[LOGIN-PACKETS] user_id=%d Enviando UPDATE_USER_STATS (ID=45)", user_id)
        await player_service.send_stats(user_id)

        logger.info("[LOGIN-PACKETS] user_id=%d Paquetes de login enviados correctamente", user_id)
        return position

    async def initialize_player_data(self, user_id: int) -> None:
        """Inicializa los datos del jugador.

        Args:
            user_id: ID del usuario.
        """
        # Resetear estado de meditación al hacer login
        await self.player_repo.set_meditating(user_id, is_meditating=False)
        logger.debug("Estado de meditación reseteado para user_id %d al hacer login", user_id)

        # Enviar hambre/sed (stats ya se enviaron en _send_login_packets)
        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
        await player_service.send_hunger_thirst(user_id)

    async def send_spellbook(self, user_id: int) -> None:
        """Envía el libro de hechizos al jugador.

        Args:
            user_id: ID del usuario.
        """
        if not self.spellbook_repo or not self.spell_catalog:
            return

        # Inicializar libro de hechizos con hechizos por defecto si es necesario
        # Pasar spell_catalog para agregar TODOS los hechizos disponibles
        await self.spellbook_repo.initialize_default_spells(
            user_id, spell_catalog=self.spell_catalog
        )

        # Cargar y enviar todos los hechizos del jugador
        logger.info("Cargando libro de hechizos para user_id %d desde Redis", user_id)
        spells = await self.spellbook_repo.get_all_spells(user_id)

        if spells:
            logger.info(
                "user_id %d tiene %d hechizo(s) en su libro: %s",
                user_id,
                len(spells),
                dict(sorted(spells.items())),
            )

            for slot, spell_id in sorted(spells.items()):
                spell_data = self.spell_catalog.get_spell_data(spell_id)
                if spell_data:
                    spell_name = spell_data.get("name", f"Spell {spell_id}")
                    await self.message_sender.send_change_spell_slot(slot, spell_id, spell_name)
                    logger.info(
                        "Hechizo enviado al cliente: slot=%d, spell_id=%d (%s)",
                        slot,
                        spell_id,
                        spell_name,
                    )
        else:
            logger.info("user_id %d no tiene hechizos en su libro", user_id)
