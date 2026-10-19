# Transporte WSS optativo

El endpoint usa los mismos handlers, framer incremental, sesiones, límites de autenticación y limpieza que TCP/TLS. Los límites de mensaje son 64 KiB, ocho mensajes WebSocket en cola y 32 KiB de contrapresión de escritura. Texto, orígenes ajenos y mensajes excesivos se rechazan.

Activar en el TOML o entorno validado:

```toml
[server]
wss_host = "127.0.0.1"
wss_port = 7668
wss_origins = ["https://juego.example.org"]
wss_tls_proxy = false
```

Arrancar con los certificados TLS habituales del servidor. La configuración de entorno equivalente es `PYAO_SERVER__WSS_PORT`, `PYAO_SERVER__WSS_HOST` y `PYAO_SERVER__WSS_ORIGINS` como array JSON. El endpoint WSS tiene puerto propio; no se puede compartir con el listener AO TCP.

Para un proxy HTTPS que termina TLS, `wss_tls_proxy = true` sólo permite el backend sin TLS en loopback. El proxy debe pasar Upgrade/Connection y limitar el tamaño y plazo del handshake; la dirección se obtiene del socket, sin confiar en cabeceras IP aportadas por el navegador. Redis permanece privado. No hay fallback a WS público ni se transmiten credenciales antes de validar WSS.
