#!/usr/bin/env python3
"""Script para verificar skills por clase en Redis.

Muestra las skills guardadas para un usuario específico.
"""

import asyncio
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.repositories.player_repository import PlayerRepository
from src.services.game.class_service import get_class_service
from src.utils.redis_client import RedisClient


async def check_user_skills(user_id: int) -> None:
    """Verifica las skills de un usuario."""
    # Conectar a Redis
    redis_client = await RedisClient.create()
    player_repo = PlayerRepository(redis_client)

    # Obtener skills del usuario
    skills = await player_repo.get_skills(user_id)

    if skills:
        print(f"\n📊 Skills del usuario {user_id}:")
        print("-" * 40)
        for skill_name, skill_value in sorted(skills.items()):
            if skill_value > 0:
                print(f"  {skill_name:15} = {skill_value}")
    else:
        print(f"\n⚠️  Usuario {user_id} no tiene skills guardadas")
        print("   (Puede ser que el personaje no se haya creado aún)")


async def show_class_skills() -> None:
    """Muestra las skills iniciales por clase."""
    class_service = get_class_service()

    print("\n🎭 Skills Iniciales por Clase:")
    print("=" * 60)

    for class_id in [1, 2, 3, 10]:  # Mago, Clérigo, Guerrero, Cazador
        character_class = class_service.get_class(class_id)
        if character_class:
            print(f"\n{class_icon(class_id)} {character_class.name} (ID: {class_id})")
            print("-" * 40)
            if character_class.initial_skills:
                for skill_name, skill_value in sorted(
                    character_class.initial_skills.items()
                ):
                    print(f"  {skill_name:15} = {skill_value}")
            else:
                print("  (Sin skills iniciales)")


def class_icon(class_id: int) -> str:
    """Retorna un icono para la clase."""
    icons = {1: "🔮", 2: "⚔️", 3: "🛡️", 10: "🏹"}
    return icons.get(class_id, "👤")


async def show_class_attributes() -> None:
    """Muestra los atributos base por clase."""
    class_service = get_class_service()

    print("\n📈 Atributos Base por Clase:")
    print("=" * 60)

    for class_id in [1, 2, 3, 10]:
        character_class = class_service.get_class(class_id)
        if character_class:
            attrs = character_class.base_attributes
            print(f"\n{class_icon(class_id)} {character_class.name} (ID: {class_id})")
            print("-" * 40)
            print(f"  STR: {attrs['strength']:2}  AGI: {attrs['agility']:2}  INT: {attrs['intelligence']:2}")
            print(f"  CHA: {attrs['charisma']:2}  CON: {attrs['constitution']:2}")


async def main() -> None:
    """Función principal."""
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
            await check_user_skills(user_id)
        except ValueError:
            print(f"❌ Error: '{sys.argv[1]}' no es un ID válido")
            sys.exit(1)
    else:
        # Mostrar información general
        await show_class_skills()
        await show_class_attributes()
        print("\n💡 Para ver skills de un usuario específico:")
        print("   python scripts/check_class_skills.py <user_id>")


if __name__ == "__main__":
    asyncio.run(main())

