# Interfaz de Línea de Comandos (CLI)

PyAO Server incluye una interfaz de línea de comandos completa para facilitar la configuración y el uso del servidor.

## Uso Básico

```bash
pyao-server [opciones]
```

## Opciones Disponibles

### --help
Muestra la ayuda con todas las opciones disponibles.

```bash
pyao-server --help
```

**Salida:**
```
usage: pyao-server [-h] [--debug] [--host HOST] [--port PORT] [--ssl]
                   [--ssl-cert SSL_CERT] [--ssl-key SSL_KEY] [--version]

PyAO Server - Servidor de Argentum Online en Python

options:
  -h, --help            show this help message and exit
  --debug               Habilitar logs de debug (muestra información detallada)
  --host HOST           Host donde escuchar (default: 0.0.0.0)
  --port PORT           Puerto donde escuchar (default: 7666)
  --ssl                 Habilita TLS/SSL para el socket del servidor. Si no se proporcionan rutas personalizadas, el servidor generará automáticamente un certificado y clave autofirmados en `certs/server.{crt,key}` (requiere `openssl`).
  --ssl-cert SSL_CERT   Ruta al certificado PEM del servidor (default: certs/server.crt)
  --ssl-key SSL_KEY     Ruta a la clave privada PEM del servidor (default: certs/server.key)
  --version             show program's version number and exit

Ejemplos:
  pyao-server                    # Iniciar servidor en modo normal
  pyao-server --debug            # Iniciar con logs de debug
  pyao-server --host 127.0.0.1   # Iniciar en localhost
  pyao-server --port 8000        # Usar puerto personalizado
  pyao-server --ssl              # Iniciar con TLS (usar certificados en certs/)
```

### --debug
Habilita logs de nivel DEBUG, mostrando información detallada de todas las operaciones del servidor.

```bash
pyao-server --debug
```

**Logs de debug incluyen:**
- Packets enviados y recibidos (bytes hexadecimales)
- Operaciones de Redis
- Movimiento de NPCs y detección de jugadores
- Ejecución de efectos del GameTick
- Broadcast de mensajes
- Validaciones y errores detallados

**Ejemplo de salida:**
```
2025-10-16 22:00:00,123 - src.client_connection - DEBUG - Recibidos 17 bytes de ('127.0.0.1', 12345): 00 03 00 61 73 64...
2025-10-16 22:00:00,124 - src.effect_npc_movement - DEBUG - NPC Lobo en mapa 1 buscando jugadores - 1 jugadores en el mapa
2025-10-16 22:00:00,125 - src.effect_npc_movement - DEBUG - Jugador 1 en (66,72) - NPC Lobo en (72,70) - distancia=8
2025-10-16 22:00:00,126 - src.effect_npc_movement - DEBUG - NPC Lobo (ID:7) detectó jugador en (66,72), distancia=8 - PERSIGUIENDO
```

### --host
Especifica la dirección IP donde el servidor escuchará conexiones.

```bash
pyao-server --host 127.0.0.1  # Solo localhost
pyao-server --host 0.0.0.0    # Todas las interfaces (default)
pyao-server --host 192.168.1.100  # IP específica
```

**Valores comunes:**
- `0.0.0.0` - Escucha en todas las interfaces (default)
- `127.0.0.1` - Solo conexiones locales
- `192.168.x.x` - IP específica de la red local

### --port
Especifica el puerto TCP donde el servidor escuchará conexiones.

```bash
pyao-server --port 7666  # Puerto default
pyao-server --port 8000  # Puerto personalizado
```

**Notas:**
- Puerto default: 7666 (puerto tradicional de Argentum Online)
- Puertos < 1024 requieren permisos de administrador
- Asegúrate de que el puerto no esté en uso

### --version
Muestra la versión del servidor.

```bash
pyao-server --version
```

**Salida:**
```
PyAO Server 0.1.0
```

## Ejemplos de Uso

### Desarrollo Local
```bash
# Servidor en localhost con logs de debug
pyao-server --host 127.0.0.1 --debug
```

### Producción
```bash
# Servidor en todas las interfaces, puerto default, logs normales
pyao-server
```

### Testing
```bash
# Puerto alternativo para no interferir con servidor principal
pyao-server --port 8000 --debug
```

### Red Local
```bash
# Servidor accesible desde la red local
pyao-server --host 192.168.1.100 --port 7666
```

## Arquitectura de la CLI

### ServerCLI (src/server_cli.py)
Clase que maneja el parsing de argumentos y configuración del servidor.

```python
class ServerCLI:
    """Interfaz de línea de comandos para el servidor."""
    
    VERSION = "0.1.0"
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Crea el parser de argumentos."""
        # Configura argparse con todas las opciones
    
    def _configure_logging(self, debug: bool):
        """Configura el nivel de logging."""
        # DEBUG o INFO según la opción
    
    def parse_args(self) -> argparse.Namespace:
        """Parsea los argumentos de línea de comandos."""
        return self.parser.parse_args()
    
    def configure_logging(self, debug: bool):
        """Configura el sistema de logging."""
        self._configure_logging(debug)
```

### run_server.py
Script principal que usa ServerCLI para iniciar el servidor.

```python
def main():
    cli = ServerCLI()
    args = cli.parse_args()
    
    # Configurar logging
    cli.configure_logging(args.debug)
    
    # Crear y ejecutar servidor
    server = ArgentumServer(host=args.host, port=args.port)
    asyncio.run(server.start())
```

## Logs del Servidor

### Nivel INFO (Default)
Muestra información importante de operaciones del servidor:

```
2025-10-16 21:00:00,123 - src.run_server - INFO - Iniciando PyAO Server v0.1.0...
2025-10-16 21:00:00,124 - src.run_server - INFO - Host: 0.0.0.0 | Puerto: 7666
2025-10-16 21:00:00,125 - src.redis_client - INFO - Conectado a Redis en localhost:6379
2025-10-16 21:00:00,126 - src.server - INFO - Servidor escuchando en ('0.0.0.0', 7666)
2025-10-16 21:00:05,234 - src.server - INFO - Nueva conexión desde ('127.0.0.1', 12345)
2025-10-16 21:00:05,235 - src.authentication_service - INFO - Autenticación exitosa para usuario (ID: 1)
```

### Nivel DEBUG (--debug)
Incluye toda la información de INFO más detalles técnicos:

```
2025-10-16 21:00:05,236 - src.client_connection - DEBUG - Recibidos 17 bytes: 00 03 00 61 73 64...
2025-10-16 21:00:05,237 - src.player_repository - DEBUG - Hambre y sed guardadas para user_id 1
2025-10-16 21:00:05,238 - src.map_manager - DEBUG - Jugador 1 (usuario) agregado al mapa 1
2025-10-16 21:00:05,239 - src.npc_service - DEBUG - Enviados 7 NPCs al jugador en mapa 1
```

## Variables de Entorno

El servidor también puede configurarse mediante variables de entorno:

```bash
# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Servidor
export SERVER_HOST=0.0.0.0
export SERVER_PORT=7666
```

## Integración con Systemd

Para ejecutar el servidor como servicio en Linux:

```ini
[Unit]
Description=PyAO Server
After=network.target redis.service

[Service]
Type=simple
User=pyao
WorkingDirectory=/opt/pyao-server
ExecStart=/opt/pyao-server/.venv/bin/pyao-server --host 0.0.0.0 --port 7666
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Puerto en uso
```bash
# Error: Address already in use
# Solución: Usar otro puerto o matar el proceso
lsof -i :7666
kill -9 <PID>
```

### Permisos insuficientes
```bash
# Error: Permission denied (puerto < 1024)
# Solución: Usar sudo o puerto > 1024
sudo pyao-server --port 80
# O
pyao-server --port 8080
```

### Redis no disponible
```bash
# Error: Connection refused (Redis)
# Solución: Iniciar Redis
sudo systemctl start redis
# O
redis-server
```

## Referencias

- [SERVICES_ARCHITECTURE.md](SERVICES_ARCHITECTURE.md) - Arquitectura del servidor
- [GAME_TICK_SYSTEM.md](GAME_TICK_SYSTEM.md) - Sistema de efectos y tick
- [NPC_SYSTEM.md](NPC_SYSTEM.md) - Sistema de NPCs
