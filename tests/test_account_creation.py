"""Tests para la funcionalidad de creación de cuentas."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_id import ClientPacketID, ServerPacketID
from src.redis_client import RedisClient
from src.task import TaskCreateAccount


@pytest.mark.asyncio
async def test_task_create_account_success() -> None:  # noqa: PLR0914
    """Verifica que TaskCreateAccount cree una cuenta exitosamente."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del RedisClient
    redis_client = MagicMock(spec=RedisClient)
    redis_client.create_account = AsyncMock(return_value=1)
    redis_client.set_player_position = AsyncMock()

    # Crear conexión y message sender
    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Construir paquete de creación de cuenta con formato real del cliente
    username = "testuser"
    password = "password123"  # noqa: S105
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

    # Crear y ejecutar tarea
    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
    await task.execute()

    # Verificar que se llamó a create_account
    redis_client.create_account.assert_called_once()
    call_args = redis_client.create_account.call_args
    assert call_args.kwargs["username"] == username
    assert call_args.kwargs["email"] == email
    # Verificar que la contraseña fue hasheada (no es la original)
    assert call_args.kwargs["password_hash"] != password
    assert len(call_args.kwargs["password_hash"]) == 64  # SHA-256 hex

    # Verificar que se enviaron 6 paquetes:
    # Logged, UserCharIndex, ChangeMap, PosUpdate, UpdateUserStats, UpdateHungerAndThirst
    assert writer.write.call_count == 6

    # Primer paquete: Logged
    first_call = writer.write.call_args_list[0][0][0]
    assert first_call[0] == ServerPacketID.LOGGED

    # Segundo paquete: UserCharIndexInServer
    second_call = writer.write.call_args_list[1][0][0]
    assert second_call[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER

    # Tercer paquete: ChangeMap
    third_call = writer.write.call_args_list[2][0][0]
    assert third_call[0] == ServerPacketID.CHANGE_MAP

    # Cuarto paquete: PosUpdate
    fourth_call = writer.write.call_args_list[3][0][0]
    assert fourth_call[0] == ServerPacketID.POS_UPDATE

    # Quinto paquete: UpdateUserStats
    fifth_call = writer.write.call_args_list[4][0][0]
    assert fifth_call[0] == ServerPacketID.UPDATE_USER_STATS

    # Sexto paquete: UpdateHungerAndThirst
    sixth_call = writer.write.call_args_list[5][0][0]
    assert sixth_call[0] == ServerPacketID.UPDATE_HUNGER_AND_THIRST


@pytest.mark.asyncio
async def test_task_create_account_duplicate_username() -> None:
    """Verifica que TaskCreateAccount maneje usuarios duplicados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del RedisClient que lanza ValueError
    redis_client = MagicMock(spec=RedisClient)
    redis_client.create_account = AsyncMock(
        side_effect=ValueError("La cuenta 'testuser' ya existe")
    )

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Construir paquete
    username = "testuser"
    password = "password123"  # noqa: S105
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    # Ejecutar tarea
    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
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

    redis_client = MagicMock(spec=RedisClient)
    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Username muy corto (menos de 3 caracteres)
    username = "ab"
    password = "password123"  # noqa: S105
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
    await task.execute()

    # Verificar que se envió error sin llamar a Redis
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    redis_client.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_invalid_password() -> None:
    """Verifica validación de contraseña corta."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    redis_client = MagicMock(spec=RedisClient)
    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Password muy corto (menos de 6 caracteres)
    username = "testuser"
    password = "12345"  # noqa: S105
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    redis_client.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_invalid_email() -> None:
    """Verifica validación de email inválido."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    redis_client = MagicMock(spec=RedisClient)
    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Email sin @
    username = "testuser"
    password = "password123"  # noqa: S105
    email = "invalidemail"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    redis_client.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_no_redis() -> None:
    """Verifica manejo cuando Redis no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Construir paquete válido
    username = "testuser"
    password = "password123"  # noqa: S105
    email = "test@example.com"

    data = bytearray([ClientPacketID.CREATE_ACCOUNT])
    data.extend(len(username).to_bytes(2, byteorder="little"))
    data.extend(username.encode("utf-8"))
    data.extend(len(password).to_bytes(2, byteorder="little"))
    data.extend(password.encode("utf-8"))
    data.extend(len(email).to_bytes(2, byteorder="little"))
    data.extend(email.encode("utf-8"))

    # Crear tarea sin redis_client (None)
    task = TaskCreateAccount(bytes(data), message_sender, None)
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

    redis_client = MagicMock(spec=RedisClient)
    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Paquete incompleto (solo PacketID)
    data = bytes([ClientPacketID.CREATE_ACCOUNT])

    task = TaskCreateAccount(data, message_sender, redis_client)
    await task.execute()

    # Verificar que se envió error
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ERROR_MSG
    redis_client.create_account.assert_not_called()


@pytest.mark.asyncio
async def test_task_create_account_unicode_username() -> None:
    """Verifica que funcione con username unicode."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    redis_client = MagicMock(spec=RedisClient)
    redis_client.create_account = AsyncMock(return_value=1)

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    # Username con caracteres unicode
    username = "usuario_ñ"
    password = "password123"  # noqa: S105
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

    task = TaskCreateAccount(bytes(data), message_sender, redis_client)
    await task.execute()

    # Verificar que se creó la cuenta
    redis_client.create_account.assert_called_once()
    call_args = redis_client.create_account.call_args
    assert call_args.kwargs["username"] == username


def test_task_create_account_password_hashing() -> None:
    """Verifica que las contraseñas se hasheen correctamente."""
    password1 = "password123"
    password2 = "password123"
    password3 = "different"

    hash1 = TaskCreateAccount._hash_password(password1)  # noqa: SLF001
    hash2 = TaskCreateAccount._hash_password(password2)  # noqa: SLF001
    hash3 = TaskCreateAccount._hash_password(password3)  # noqa: SLF001

    # Misma contraseña debe generar mismo hash
    assert hash1 == hash2

    # Contraseña diferente debe generar hash diferente
    assert hash1 != hash3

    # Hash debe ser hexadecimal de 64 caracteres (SHA-256)
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)
