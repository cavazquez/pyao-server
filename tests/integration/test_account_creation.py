"""Tests para la funcionalidad de creación de cuentas."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.create_account_handler import CreateAccountCommandHandler
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ClientPacketID, ServerPacketID
from src.repositories.account_repository import AccountRepository
from src.repositories.player_repository import PlayerRepository
from src.tasks.player.task_account import TaskCreateAccount
from src.utils.password_utils import hash_password


@pytest.mark.asyncio
async def test_task_create_account_success() -> None:  # noqa: PLR0914, PLR0915
    """Verifica que TaskCreateAccount cree una cuenta exitosamente."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock de los repositorios
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_position = AsyncMock()
    player_repo.set_stats = AsyncMock()
    player_repo.set_hunger_thirst = AsyncMock()
    player_repo.set_attributes = AsyncMock()
    # Para que cree valores por defecto y luego los devuelva
    player_repo.get_position = AsyncMock(return_value=None)
    player_repo.get_stats = AsyncMock(return_value=None)
    player_repo.get_hunger_thirst = AsyncMock(
        side_effect=[
            None,  # Primera llamada: no existen
            {  # Segunda llamada: devolver valores creados
                "max_water": 100,
                "min_water": 100,
                "max_hunger": 100,
                "min_hunger": 100,
            },
        ]
    )
    player_repo.get_attributes = AsyncMock(return_value=None)
    player_repo.get_strength = AsyncMock(return_value=10)
    player_repo.get_agility = AsyncMock(return_value=10)
    # Mock de redis para InventoryRepository
    redis_client_mock = MagicMock()
    redis_client_mock.redis = AsyncMock()
    redis_client_mock.redis.hgetall = AsyncMock(return_value={})
    redis_client_mock.redis.hset = AsyncMock()
    player_repo.redis = redis_client_mock

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.create_account = AsyncMock(return_value=1)
    # Mocks necesarios para TaskLogin que se ejecuta después de crear la cuenta
    account_repo.get_account = AsyncMock(return_value={"user_id": 1, "char_job": 1})
    account_repo.verify_password = AsyncMock(return_value=True)

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Construir paquete de creación de cuenta con formato real del cliente
    username = "testuser"
    password = "password123"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    # Username
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    # Password
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    # Char data (race, unknown int16, gender, job, unknown byte, head int16)
    data.append(1)  # race
    data.extend((0).to_bytes(2, byteorder="little"))  # unknown int16
    data.append(1)  # gender
    data.append(1)  # job
    data.append(1)  # unknown byte
    data.extend((18).to_bytes(2, byteorder="little"))  # head
    # Email
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))
    # Home
    data.append(1)  # home

    # Crear handler con todas las dependencias necesarias
    create_account_handler = CreateAccountCommandHandler(
        player_repo=player_repo,
        account_repo=account_repo,
        map_manager=None,
        npc_service=None,
        server_repo=None,
        spellbook_repo=None,
        spell_catalog=None,
        equipment_repo=None,
        player_map_service=None,
        message_sender=message_sender,
        session_data=None,
    )

    # Crear y ejecutar tarea
    task = TaskCreateAccount(
        bytes(data),
        message_sender,
        create_account_handler=create_account_handler,
        session_data=None,
    )
    await task.execute()

    # Verificar que se llamó a create_account
    account_repo.create_account.assert_called_once()
    call_args = account_repo.create_account.call_args
    assert call_args.kwargs["username"] == username
    assert call_args.kwargs["email"] == email
    # Verificar que la contraseña fue hasheada (no es la original) y usa Argon2id
    password_hash = call_args.kwargs["password_hash"]
    assert password_hash != password
    assert password_hash.startswith("$argon2id$")

    # Verificar que se enviaron los paquetes esperados:
    # 1. Logged
    # 2. UserCharIndex
    # 3. ChangeMap
    # 4. UpdateStrengthAndDexterity
    # 5. UpdateUserStats
    # 6. UpdateHungerAndThirst
    # 6. PlayWave (sonido de login)
    # 7. CharacterCreate
    # 8. CreateFX (efecto visual de spawn)
    # Nota: MOTD se envía con delay asíncrono (no se verifica en este test)
    # Nota: Attributes no se envía automáticamente (el cliente lo solicita con /EST)
    # Nota: Inventario no se envía al login (se carga on-demand con clicks)
    # Nota: ChangeSpellSlot no se envía porque spellbook_repo es None en este test
    assert writer.write.call_count >= 6  # Al menos 6 paquetes base (MOTD es asíncrono)

    # Primer paquete: Logged
    first_call = writer.write.call_args_list[0][0][0]
    assert first_call[0] == ServerPacketID.LOGGED

    # Segundo paquete: UserCharIndexInServer
    second_call = writer.write.call_args_list[1][0][0]
    assert second_call[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER

    # Tercer paquete: ChangeMap
    third_call = writer.write.call_args_list[2][0][0]
    assert third_call[0] == ServerPacketID.CHANGE_MAP

    # Cuarto paquete: UpdateStrengthAndDexterity (agregado por send_attributes)
    fourth_call = writer.write.call_args_list[3][0][0]
    assert fourth_call[0] == ServerPacketID.UPDATE_STRENGTH_AND_DEXTERITY

    # Quinto paquete: UpdateUserStats (agregado por send_stats)
    fifth_call = writer.write.call_args_list[4][0][0]
    assert fifth_call[0] == ServerPacketID.UPDATE_USER_STATS

    # Verificar paquetes básicos que sí se envían
    # Los paquetes de NPCs (CHARACTER_CREATE, CREATE_FX) no se envían si npc_world_manager es None
    assert writer.write.call_count >= 5  # Logged, UserCharIndex, ChangeMap, StrengthDex, UserStats

    # MOTD se envía con delay asíncrono, no se verifica aquí
    # TODO: Agregar verificación de PLAY_MIDI cuando el cliente lo soporte


@pytest.mark.asyncio
async def test_task_create_account_duplicate_username() -> None:
    """Verifica que TaskCreateAccount maneje usuarios duplicados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del RedisClient que lanza ValueError
    player_repo = MagicMock(spec=PlayerRepository)
    account_repo = MagicMock(spec=AccountRepository)
    account_repo.create_account = AsyncMock(
        side_effect=ValueError("La cuenta 'testuser' ya existe")
    )

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Construir paquete
    username = "testuser"
    password = "password123"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    # Crear handler
    create_account_handler = CreateAccountCommandHandler(
        player_repo=player_repo,
        account_repo=account_repo,
        map_manager=None,
        npc_service=None,
        server_repo=None,
        spellbook_repo=None,
        spell_catalog=None,
        equipment_repo=None,
        player_map_service=None,
        message_sender=message_sender,
        session_data=None,
    )

    # Ejecutar tarea
    task = TaskCreateAccount(
        bytes(data), message_sender, create_account_handler=create_account_handler
    )
    await task.execute()

    # Verificar que se envió mensaje de error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG


@pytest.mark.asyncio
async def test_task_create_account_invalid_username() -> None:
    """Verifica validación de username corto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    account_repo = MagicMock(spec=AccountRepository)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Username muy corto (menos de 3 caracteres)
    username = "ab"
    password = "password123"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    task = TaskCreateAccount(bytes(data), message_sender, player_repo, account_repo)
    await task.execute()

    # Verificar que se envió error sin llamar a Redis
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    account_repo.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_invalid_password() -> None:
    """Verifica validación de contraseña corta."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    account_repo = MagicMock(spec=AccountRepository)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Password muy corto (menos de 6 caracteres)
    username = "testuser"
    password = "12345"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    task = TaskCreateAccount(bytes(data), message_sender, player_repo, account_repo)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    account_repo.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_invalid_email() -> None:
    """Verifica validación de email inválido."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    account_repo = MagicMock(spec=AccountRepository)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Email sin @
    username = "testuser"
    password = "password123"
    email = "invalidemail"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    # Crear handler
    create_account_handler = CreateAccountCommandHandler(
        player_repo=player_repo,
        account_repo=account_repo,
        map_manager=None,
        npc_service=None,
        server_repo=None,
        spellbook_repo=None,
        spell_catalog=None,
        equipment_repo=None,
        player_map_service=None,
        message_sender=message_sender,
        session_data=None,
    )

    task = TaskCreateAccount(
        bytes(data), message_sender, create_account_handler=create_account_handler
    )
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    account_repo.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_no_redis() -> None:
    """Verifica manejo cuando Redis no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Construir paquete válido
    username = "testuser"
    password = "password123"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    # Crear tarea sin handler (None)
    task = TaskCreateAccount(bytes(data), message_sender, create_account_handler=None)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG


@pytest.mark.asyncio
async def test_task_create_account_invalid_packet() -> None:
    """Verifica manejo de paquete malformado."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    account_repo = MagicMock(spec=AccountRepository)
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Paquete incompleto (solo PacketID)
    data = bytes([ClientPacketID.CREATE_ACCOUNT])

    task = TaskCreateAccount(data, message_sender, player_repo, account_repo)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    account_repo.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_unicode_username() -> None:
    """Verifica que funcione con username unicode."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.set_position = AsyncMock()
    player_repo.set_stats = AsyncMock()
    player_repo.set_hunger_thirst = AsyncMock()
    player_repo.get_position = AsyncMock(return_value=None)
    player_repo.get_stats = AsyncMock(return_value=None)
    player_repo.get_hunger_thirst = AsyncMock(return_value=None)

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.create_account = AsyncMock(return_value=1)
    # Mocks necesarios para TaskLogin
    account_repo.get_account = AsyncMock(return_value={"user_id": 1, "char_job": 1})
    account_repo.verify_password = AsyncMock(return_value=True)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Username con caracteres unicode
    username = "usuario_ñ"
    password = "password123"
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    # Username
    data.extend(len(username.encode("utf-8")).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    # Password
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    # Char data
    data.append(1)  # race
    data.extend((0).to_bytes(2, byteorder="little"))  # unknown int16
    data.append(1)  # gender
    data.append(1)  # job
    data.append(1)  # unknown byte
    data.extend((18).to_bytes(2, byteorder="little"))  # head
    # Email
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))
    # Home
    data.append(1)  # home

    # Crear handler
    create_account_handler = CreateAccountCommandHandler(
        player_repo=player_repo,
        account_repo=account_repo,
        map_manager=None,
        npc_service=None,
        server_repo=None,
        spellbook_repo=None,
        spell_catalog=None,
        equipment_repo=None,
        player_map_service=None,
        message_sender=message_sender,
        session_data=None,
    )

    task = TaskCreateAccount(
        bytes(data), message_sender, create_account_handler=create_account_handler
    )
    await task.execute()

    # Verificar que se creó la cuenta
    account_repo.create_account.assert_called_once()
    call_args = account_repo.create_account.call_args
    assert call_args.kwargs["username"] == username


def test_task_create_account_password_hashing() -> None:
    """Verifica que el hash de contraseñas utilice Argon2id con salt aleatorio."""
    password1 = "password123"
    password2 = "password123"
    password3 = "different"

    hash1 = hash_password(password1)
    hash2 = hash_password(password2)
    hash3 = hash_password(password3)

    # Misma contraseña debe generar hashes distintos (salt aleatorio)
    assert hash1 != hash2

    # Contraseña diferente debe generar hash diferente
    assert hash1 != hash3

    # Hash debe incluir el prefijo Argon2id y no contener la contraseña en texto plano
    assert hash1.startswith("$argon2id$")
    assert password1 not in hash1
