"""Tests para la funcionalidad de creación de cuentas."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.msg import build_account_created_response, build_account_error_response
from src.packet_id import ClientPacketID, ServerPacketID
from src.redis_client import RedisClient
from src.task import TaskCreateAccount


def test_build_account_created_response() -> None:
    """Verifica que el paquete de cuenta creada tenga la estructura correcta."""
    user_id = 12345
    response = build_account_created_response(user_id)

    # Verificar que el primer byte sea el PacketID correcto
    assert response[0] == ServerPacketID.ACCOUNT_CREATED

    # Verificar que el user_id esté codificado como int32 (4 bytes, little-endian)
    assert len(response) == 5  # 1 byte PacketID + 4 bytes int32
    decoded_user_id = int.from_bytes(response[1:5], byteorder="little", signed=True)
    assert decoded_user_id == user_id


def test_build_account_error_response() -> None:
    """Verifica que el paquete de error tenga la estructura correcta."""
    error_message = "Usuario ya existe"
    response = build_account_error_response(error_message)

    # Verificar que el primer byte sea el PacketID correcto
    assert response[0] == ServerPacketID.ACCOUNT_ERROR

    # Verificar longitud del mensaje
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    assert msg_length == len(error_message.encode("utf-8"))

    # Verificar que el mensaje esté codificado correctamente
    decoded_message = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_message == error_message


def test_build_account_error_response_empty_message() -> None:
    """Verifica que funcione con mensaje vacío."""
    response = build_account_error_response("")

    assert response[0] == ServerPacketID.ACCOUNT_ERROR
    assert len(response) == 3  # PacketID + int16 length


def test_build_account_error_response_unicode() -> None:
    """Verifica que funcione con caracteres unicode."""
    error_message = "Error: contraseña inválida 🔒"
    response = build_account_error_response(error_message)

    assert response[0] == ServerPacketID.ACCOUNT_ERROR
    msg_length = int.from_bytes(response[1:3], byteorder="little", signed=True)
    decoded_message = response[3 : 3 + msg_length].decode("utf-8")
    assert decoded_message == error_message


@pytest.mark.asyncio
async def test_task_create_account_success() -> None:
    """Verifica que TaskCreateAccount cree una cuenta exitosamente."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del RedisClient
    redis_client = MagicMock(spec=RedisClient)
    redis_client.create_account = AsyncMock(return_value=1)

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

    # Verificar que se envió respuesta de éxito
    assert writer.write.called
    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.ACCOUNT_CREATED


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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR


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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR
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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR
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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR
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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR


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
    assert written_data[0] == ServerPacketID.ACCOUNT_ERROR
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
