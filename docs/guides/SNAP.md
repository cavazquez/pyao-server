# Publicación del servidor en Snap

`pyao` es el servidor; `pyao-client` es el cliente. Ambos usan `1.0.0rc1`.
La distribución de desarrollo se publica en `latest/edge`. Publicar un paquete
no instala ni migra una partida de producción.

## Construcción y validación

Desde un commit limpio, con Snapcraft 9.1.4 (revisión 19274 en amd64,
19281 en arm64) y LXD:

```bash
python3 scripts/build_snap.py --arch amd64
# En un host arm64:
python3 scripts/build_snap.py --arch arm64
```

La receta usa core26 estable, incluye Python 3.14 y el plugin uv con versión
0.13.1 verificada por SHA256 para instalar el runtime de `uv.lock`, sin grupos
de desarrollo ni edición del lock. El wheel incluye los catálogos y el archive
de mapas; no se requiere una copia local de `map_data/`. uv queda fuera del Snap.
La [guía oficial de core26](https://ubuntu.com/docs/snapcraft/9/how-to/change-bases/change-from-core24-to-core26/)
documenta el runtime Python incluido.

Se normalizan `bin/python`, `bin/python3` y `bin/python3.14` a enlaces relativos
al intérprete incluido. El plugin uv puede conservar alias a `/root/stage`;
CI resuelve y ejecuta los tres desde el Snap instalado antes de publicar.

`Server Snap` construye en runners nativos amd64/arm64, instala el paquete y
verifica versión, recursos, PING/PONG con TLS, esquema 4, catálogos de habilidades
y recetas, cierre SIGTERM y reinicio con estado Redis y configuración intactos.
Redis es descartable y autenticado. Se guardan Snap, hashes, procedencia y logs.
El release de servidor reutiliza ese mismo workflow, sin credenciales Launchpad.

## Publicación e instalación

Servidor y cliente se entregan juntos, con la misma versión pública. Después
de fusionar ambos commits, construir y probar sus paquetes, el mantenedor usa
`tools/release-pair.py` del repositorio del cliente, siguiendo su
[procedimiento conjunto](https://github.com/cavazquez/ArgentumOnlineGodot/blob/main/docs/SNAP.md).
Exige CI, R01–R09, R10 de dos clientes nativos durante 30 minutos y el ensayo
descartable de actualización. Primero carga **los tres paquetes sin `--release`**
(servidor amd64/arm64 y cliente amd64); sólo después promueve el par revisado.
El recibo conserva los hashes y las revisiones anteriores para recuperación.

La Store cambia cada revisión por separado. El publicador registra el intervalo
real y, si falla una promoción, recupera todas las revisiones anteriores y verifica
el resultado. No hay una transacción atómica entre ambos nombres de Snap.

Instalación de la entrega ya publicada:

```bash
snapcraft status pyao
sudo snap install pyao --edge
pyao.pyao-server --version
pyao.pyao-server --check-resources
```

La procedencia está en `share/doc/pyao/provenance.json`. Descargar nuevamente
desde la Store y comparar SHA256 antes de declarar publicada la revisión.

El servidor se inicia con `pyao.pyao-server`; el Snap no crea un servicio ni
se conecta a una partida automáticamente. Usa `PYAO_REDIS__HOST`,
`PYAO_REDIS__PORT` y `PYAO_REDIS__PASSWORD_FILE` para la instancia elegida.
El archivo de secreto y los respaldos deben estar en `$HOME/snap/pyao/common/`,
accesible desde el confinamiento estricto.

## Actualización y partidas existentes

Se conserva `common/config/server.toml`. Los catálogos predeterminados vienen
del wheel actual; no se borran ni sobrescriben `common/data` y `common/map_data`
de versiones anteriores. Para elegir un dataset personalizado, indicar
explícitamente `PYAO_DATA_DIR`/`PYAO_MAPS_DIR`; debe incluir el esquema actual.
Las cachés de mapas se regeneran por hash del archive.

`--version` y `--help` funcionan sin Redis y sin cargar el TOML del operador.
El arranque normal valida la configuración conservada. Si un archivo antiguo
contiene `game.character.mana_per_int = 50000`, respaldar
`common/config/server.toml` y reemplazar ese valor por el predeterminado actual
`10`; el protocolo admite hasta `32767`. La actualización no cambia ese archivo
automáticamente ni sustituye los valores personalizados del operador.

Todo lo guardado de la partida permanece en Redis. Una base antigua requiere
detener el servidor, crear y verificar un respaldo y migrar al esquema 4 antes
de iniciar; la actualización del Snap no ejecuta la migración por su cuenta.
El respaldo, su verificación mediante restauración y la migración se ejecutan
con uv fuera del Snap, en el host del operador con Docker y `redis-cli`, según
el [procedimiento Redis](REDIS.md). Usar el checkout del tag `v1.0.0rc1` o la
distribución de esa misma versión y el endpoint elegido para la partida.
El paquete de juego conserva su confinamiento estricto y acceso de red.

El ensayo repetible `uv run python -m src.operations.redis_schema selftest`
usa `data/validation/redis_upgrade.toml`, Redis propio autenticado y un RDB
restaurado realmente en otro volumen. Comprueba cuenta/contraseña, oro, banco,
inventario, orden de hechizos, habilidades, migración idempotente, reinicio y
recuperación al estado anterior. También ensaya el TOML inválido y su ajuste
explícito con respaldo previo. El fixture representa el esquema legado; no
acredita ejecutar el binario 0.9.4 ni usar una partida real. CI guarda los
recibos en `redis-recovery-results/schema.json`.
