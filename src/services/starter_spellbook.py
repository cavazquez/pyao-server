"""Entrega única y explícita del libro inicial al crear un personaje."""

from typing import TYPE_CHECKING, cast

from src.config.config_manager import ConfigManager, config_manager
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import SpellbookRepository


async def initialize_starter_spellbook(
    repository: SpellbookRepository, user_id: int, class_id: int, catalog: SpellCatalog
) -> None:
    """Nunca rellena ni reordena libros existentes, incluso con dos inicializaciones.

    Raises:
        ValueError: Si la configuración contiene un hechizo inexistente o duplicado.
    """
    configured = config_manager.get_section("game.spells.starter_by_class").get(
        str(class_id), [2, 3]
    )
    if not isinstance(configured, list) or any(type(value) is not int for value in configured):
        message = "Lista de hechizos iniciales inválida"
        raise ValueError(message)
    spells = configured
    if len(set(spells)) != len(spells) or any(
        not catalog.get_spell_data(value) for value in spells
    ):
        message = "Hechizo inicial inexistente o duplicado"
        raise ValueError(message)
    book, stats = RedisKeys.player_spellbook(user_id), RedisKeys.player_user_stats(user_id)
    skills_key = RedisKeys.player_skills(user_id)
    initial_points = ConfigManager.as_int(
        config_manager.get("game.character.initial_skill_points", 10)
    )

    def decide(snapshot: Snapshot) -> Decision:
        saved = cast("dict[str, str]", snapshot[stats])
        existing = cast("dict[str, str]", snapshot[book])
        if saved.get("spellbook_seeded") or existing:
            return Decision({"applied": False}, {})
        skills = cast("dict[str, str]", snapshot[skills_key])
        return Decision(
            {"applied": True},
            {
                book: {str(slot): str(spell) for slot, spell in enumerate(spells, 1)},
                stats: {"spellbook_seeded": "1"},
                skills_key: {} if "points" in skills else {"points": str(initial_points)},
            },
        )

    await transact(
        repository.redis_client.redis,
        (Resource(book, "hash"), Resource(stats, "hash"), Resource(skills_key, "hash")),
        operation_id(),
        {"starter": user_id, "class_id": class_id, "spells": spells},
        decide,
    )
