#!/usr/bin/env python3
"""Script de utilidad para establecer y verificar el estado GM de usuarios."""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.repositories.account_repository import AccountRepository
from src.utils.redis_client import RedisClient


async def set_gm(username: str, is_gm: bool) -> None:
    """Establece el estado de GM de un usuario."""
    redis_client = await RedisClient.create()
    account_repo = AccountRepository(redis_client)

    # Verificar que el usuario existe
    account_data = await account_repo.get_account(username)
    if not account_data:
        print(f"❌ Error: El usuario '{username}' no existe")
        return

    user_id = account_data.get("user_id")
    current_gm = account_data.get("is_gm", "0")

    print(f"📋 Usuario: {username}")
    print(f"   User ID: {user_id}")
    print(f"   Estado GM actual: {'Sí' if current_gm == '1' else 'No'}")

    # Establecer nuevo estado
    await account_repo.set_gm_status(username, is_gm)

    # Verificar
    new_gm = await account_repo.is_gm(username)
    status = "GM ✅" if new_gm else "No GM ❌"
    print(f"   Estado GM nuevo: {status}")

    # Verificar también por user_id
    if user_id:
        new_gm_by_id = await account_repo.is_gm_by_user_id(int(user_id))
        print(f"   Verificación por user_id ({user_id}): {'GM ✅' if new_gm_by_id else 'No GM ❌'}")


async def check_gm(username: str | None = None, user_id: int | None = None) -> None:
    """Verifica el estado GM de un usuario."""
    redis_client = await RedisClient.create()
    account_repo = AccountRepository(redis_client)

    if username:
        account_data = await account_repo.get_account(username)
        if not account_data:
            print(f"❌ Error: El usuario '{username}' no existe")
            return

        user_id_from_username = account_data.get("user_id")
        is_gm = await account_repo.is_gm(username)
        print(f"📋 Usuario: {username}")
        print(f"   User ID: {user_id_from_username}")
        print(f"   Estado GM: {'Sí ✅' if is_gm else 'No ❌'}")

        # Verificar también por user_id
        if user_id_from_username:
            is_gm_by_id = await account_repo.is_gm_by_user_id(int(user_id_from_username))
            print(f"   Verificación por user_id: {'GM ✅' if is_gm_by_id else 'No GM ❌'}")

    elif user_id:
        account_data = await account_repo.get_account_by_user_id(user_id)
        if not account_data:
            print(f"❌ Error: No se encontró cuenta para user_id={user_id}")
            return

        username_from_id = account_data.get("username")
        is_gm = await account_repo.is_gm_by_user_id(user_id)
        print(f"📋 User ID: {user_id}")
        print(f"   Usuario: {username_from_id}")
        print(f"   Estado GM: {'Sí ✅' if is_gm else 'No ❌'}")
    else:
        print("❌ Error: Debes especificar --username o --user-id")


async def list_gms() -> None:
    """Lista todos los usuarios que son GM."""
    redis_client = await RedisClient.create()
    account_repo = AccountRepository(redis_client)

    # Buscar todas las cuentas
    pattern = "account:*:data"
    keys = await redis_client.redis.keys(pattern)

    gms = []
    for key in keys:
        account_data: dict[str, str] = await redis_client.redis.hgetall(key)  # type: ignore[misc]
        if account_data.get("is_gm") == "1":
            username = account_data.get("username", "Unknown")
            user_id = account_data.get("user_id", "Unknown")
            gms.append((username, user_id))

    if gms:
        print("👑 Usuarios GM:")
        for username, user_id in sorted(gms):
            print(f"   - {username} (ID: {user_id})")
    else:
        print("ℹ️  No hay usuarios GM configurados")


def main() -> None:
    """Función principal."""
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python tools/set_gm.py set <username> <1|0>    # Establecer GM")
        print("  python tools/set_gm.py check --username <user>  # Verificar por username")
        print("  python tools/set_gm.py check --user-id <id>    # Verificar por user_id")
        print("  python tools/set_gm.py list                     # Listar todos los GMs")
        sys.exit(1)

    command = sys.argv[1]

    if command == "set":
        if len(sys.argv) < 4:
            print("❌ Error: Uso: python tools/set_gm.py set <username> <1|0>")
            sys.exit(1)
        username = sys.argv[2]
        is_gm = sys.argv[3] == "1"
        asyncio.run(set_gm(username, is_gm))

    elif command == "check":
        if len(sys.argv) < 3:
            print("❌ Error: Uso: python tools/set_gm.py check --username <user> | --user-id <id>")
            sys.exit(1)

        if sys.argv[2] == "--username":
            if len(sys.argv) < 4:
                print("❌ Error: Debes especificar el username")
                sys.exit(1)
            username = sys.argv[3]
            asyncio.run(check_gm(username=username))
        elif sys.argv[2] == "--user-id":
            if len(sys.argv) < 4:
                print("❌ Error: Debes especificar el user_id")
                sys.exit(1)
            try:
                user_id = int(sys.argv[3])
                asyncio.run(check_gm(user_id=user_id))
            except ValueError:
                print("❌ Error: user_id debe ser un número")
                sys.exit(1)
        else:
            print("❌ Error: Debes usar --username o --user-id")
            sys.exit(1)

    elif command == "list":
        asyncio.run(list_gms())

    else:
        print(f"❌ Error: Comando desconocido '{command}'")
        sys.exit(1)


if __name__ == "__main__":
    main()

