"""Factory para crear instancias de Tasks con sus dependencias.

Usa introspección del constructor para inyectar automáticamente las dependencias
necesarias, eliminando el mapeo manual entre task classes y sus dependencias.

Las dependencias se resuelven en este orden de prioridad:
1. Parámetros fijos: data, message_sender, session_data
2. Handlers: parámetros que terminan en '_handler' se resuelven via HandlerRegistry
3. Datos pre-validados: parámetros que coinciden con claves en parsed_data (slot, amount)
4. Dependencias del contenedor: parámetros que coinciden con atributos de DependencyContainer
"""

import logging
from functools import cache
from typing import TYPE_CHECKING, Any

from src.network.packet_handlers import TASK_HANDLERS
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.handler_registry import HandlerRegistry
from src.tasks.task_null import TaskNull
from src.tasks.task_tls_handshake import TaskTLSHandshake

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender
    from src.tasks.task import Task

logger = logging.getLogger(__name__)

TLS_HEADER_MIN_LENGTH = 3
TLS_CONTENT_TYPE_HANDSHAKE = 0x16
TLS_PROTOCOL_MAJOR_VERSION = 0x03
TLS_CLIENT_HELLO_MINOR_VERSIONS = {0x00, 0x01, 0x02, 0x03, 0x04}


class TaskFactory:
    """Factory para crear instancias de Tasks con sus dependencias inyectadas.

    Usa introspección del constructor para resolver automáticamente qué
    dependencias necesita cada Task, basándose en los nombres de parámetros:

    - ``data``, ``message_sender``, ``session_data``: valores directos del contexto.
    - ``*_handler``: se resuelve via HandlerRegistry (ej: ``walk_handler`` → ``h.get("walk")``).
    - Claves de ``parsed_data`` (``slot``, ``amount``): datos pre-validados del packet.
    - Atributos de ``DependencyContainer``: repos, services, managers, catálogos.
    """

    def __init__(self, deps: DependencyContainer, enable_prevalidation: bool = True) -> None:
        """Inicializa el factory con el contenedor de dependencias.

        Args:
            deps: Contenedor con todas las dependencias del servidor.
            enable_prevalidation: Si True, pre-valida packets antes de crear tasks.
        """
        self.deps = deps
        self.enable_prevalidation = enable_prevalidation
        self.handlers = HandlerRegistry(deps)

    def create_task(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> Task:
        """Crea una Task apropiada basada en el packet_id.

        Args:
            data: Datos del packet recibido.
            message_sender: Enviador de mensajes para el cliente.
            session_data: Datos de sesión compartidos entre tasks.

        Returns:
            Instancia de Task correspondiente al packet_id.
        """
        # Detectar TLS handshake antes de leer packet_id
        if self._looks_like_tls_handshake(data, message_sender):
            return TaskTLSHandshake(data, message_sender)

        # Leer packet_id del primer byte
        packet_id = data[0] if data else 0

        # Buscar la clase de task en el mapa
        task_class = TASK_HANDLERS.get(packet_id)
        if task_class is None:
            client_address = message_sender.connection.address
            logger.warning(
                "Packet_id=%d no implementado desde %s. Retornando TaskNull.",
                packet_id,
                client_address,
            )
            return TaskNull(data, message_sender)

        # Pre-validar packet si está habilitado
        parsed_data: dict[str, Any] = {}
        if self.enable_prevalidation:
            validation_result = self._prevalidate_packet(data, packet_id, message_sender)
            if validation_result is not None:
                if not validation_result.success:
                    # Packet inválido, retornar TaskNull para ignorarlo
                    return TaskNull(data, message_sender)
                # Si validación fue exitosa, extraer datos parseados
                parsed_data = validation_result.data or {}

        # Crear la task con las dependencias apropiadas
        return self._create_task_with_deps(
            task_class, data, message_sender, session_data, parsed_data
        )

    @staticmethod
    @cache
    def _get_init_params(task_class: type) -> tuple[str, ...]:
        """Retorna los nombres de parámetros del constructor (sin self), cacheados.

        Usa ``__code__.co_varnames`` en lugar de ``inspect.signature()`` para
        evitar la evaluación de anotaciones diferidas (PEP 749), que fallaría
        con tipos importados bajo ``TYPE_CHECKING``.

        Args:
            task_class: Clase de la task.

        Returns:
            Tupla con los nombres de los parámetros.
        """
        code = task_class.__init__.__code__
        nparams = code.co_argcount + code.co_kwonlyargcount
        return tuple(code.co_varnames[1:nparams])  # Skip 'self'

    def _create_task_with_deps(
        self,
        task_class: type[Task],
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None,
        parsed_data: dict[str, Any],
    ) -> Task:
        """Crea una task inyectando dependencias via introspección del constructor.

        Resuelve cada parámetro del ``__init__`` de la task automáticamente:

        - ``data``, ``message_sender``, ``session_data``: valores directos.
        - ``*_handler``: se resuelve via HandlerRegistry.
        - Claves de ``parsed_data`` (``slot``, ``amount``): datos pre-validados.
        - Atributos de DependencyContainer: repos, services, managers, catálogos.

        Args:
            task_class: Clase de la task a crear.
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión.
            parsed_data: Datos pre-validados del packet.

        Returns:
            Instancia de la task con dependencias inyectadas.
        """
        h = self.handlers
        params = self._get_init_params(task_class)

        kwargs: dict[str, Any] = {}
        for name in params:
            if name == "data":
                kwargs["data"] = data
            elif name == "message_sender":
                kwargs["message_sender"] = message_sender
            elif name == "session_data":
                kwargs["session_data"] = session_data
            elif name.endswith("_handler"):
                handler_key = name.removesuffix("_handler")
                kwargs[name] = h.get(handler_key, message_sender, session_data)
            elif name in parsed_data:
                kwargs[name] = parsed_data[name]
            elif hasattr(self.deps, name):
                kwargs[name] = getattr(self.deps, name)

        return task_class(**kwargs)

    @staticmethod
    def _prevalidate_packet(data: bytes, packet_id: int, message_sender: MessageSender) -> Any:  # noqa: ANN401 - ValidationResult es genérico, Any es apropiado aquí
        """Pre-valida un packet antes de crear la task.

        Args:
            data: Datos del packet.
            packet_id: ID del packet.
            message_sender: MessageSender para enviar errores al cliente.

        Returns:
            ValidationResult si hay validador para este packet, None si no existe.
        """
        try:
            # Crear reader y validator
            reader = PacketReader(data)
            validator = PacketValidator(reader)

            # Intentar validar según el packet_id
            validation_result = validator.validate_packet_by_id(packet_id)

            # Si no hay validador para este packet, retornar None (no validar)
            if validation_result is None:
                return None

            # Obtener nombre del packet para logging
            from src.network.packet_id import ClientPacketID  # noqa: PLC0415

            try:
                packet_name = ClientPacketID(packet_id).name
            except ValueError:
                packet_name = f"UNKNOWN_{packet_id}"

            # Log del resultado
            client_address = message_sender.connection.address
            validation_result.log_validation(packet_name, packet_id, client_address)

            # Si la validación falló, enviar error al cliente
            if not validation_result.success and validation_result.error_message:
                # Crear una tarea asíncrona para enviar el mensaje
                # (no podemos await aquí porque create_task no es async)
                import asyncio  # noqa: PLC0415

                task = asyncio.create_task(
                    message_sender.send_console_msg(validation_result.error_message)
                )
                # Guardar referencia para evitar que sea garbage collected
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

            # Validación exitosa o fallida, retornar resultado
            return validation_result  # noqa: TRY300 - Return necesario aquí para claridad

        except Exception:
            # Si hay algún error en la validación, loguear y continuar sin validar
            logger.exception("Error inesperado en pre-validación de packet_id=%d", packet_id)
            return None

    @staticmethod
    def _looks_like_tls_handshake(data: bytes, message_sender: MessageSender) -> bool:
        """Detecta si el paquete parece ser un ClientHello TLS y SSL está deshabilitado.

        Returns:
            bool: True si el paquete coincide con la cabecera de un ClientHello TLS.
        """
        if len(data) < TLS_HEADER_MIN_LENGTH:
            return False

        connection = getattr(message_sender, "connection", None)
        if connection is None:
            return False

        if getattr(connection, "is_ssl_enabled", False):
            return False

        return (
            data[0] == TLS_CONTENT_TYPE_HANDSHAKE
            and data[1] == TLS_PROTOCOL_MAJOR_VERSION
            and data[2] in TLS_CLIENT_HELLO_MINOR_VERSIONS
        )
