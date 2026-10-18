# Redis para PyAO Server

El perfil de desarrollo utiliza Redis **8.10.2 Alpine**, fijado también por digest,
con autenticación, modo protegido y persistencia. Los comandos siguientes se
usan desde la raíz del servidor con uv.

## Preparar e iniciar

Generar la credencial sólo la primera vez; un archivo existente se reutiliza:

```bash
uv sync --locked
uv run --locked python -m src.operations.redis_secret --output .local/redis-password
export PYAO_REDIS_PASSWORD_FILE="$PWD/.local/redis-password"
docker compose up -d --build redis
uv run --locked pyao-server
```

El generador usa creación exclusiva y permisos 0600. El contenido no se imprime,
no se pasa en argumentos y `.local/` está excluido de Git. El servidor reconoce
`PYAO_REDIS_PASSWORD_FILE`, `PYAO_REDIS__PASSWORD_FILE` o `redis.password_file`
en TOML. El entrypoint prepara un hash ACL privado en `/data/pyao-users.acl` y
conserva `protected-mode yes`. Para una instancia externa sin autenticación se
puede dejar `password_file` sin definir.

Compose publica Redis únicamente en `127.0.0.1:6379`. Para otro puerto local,
exportar `PYAO_REDIS_PORT`; el servidor reconoce el mismo nombre legado.
La red de Compose conserva el servicio interno `redis:6379`. Para acceso remoto
administrativo, utilizar un túnel SSH hacia loopback.

Comprobar disponibilidad sin imprimir la credencial:

```bash
docker compose exec -T redis sh -c 'REDISCLI_AUTH=$(cat /run/secrets/redis_password) redis-cli PING'
docker compose logs redis
docker compose down
```

`down` conserva el volumen. La configuración usa `noeviction` para el progreso;
una política de caché que expulse claves puede borrar cuentas o economía.

## Redis Insight

```bash
docker compose --profile tools up -d
```

La UI queda en [localhost:5540](http://127.0.0.1:5540). Configurar host `redis`,
puerto `6379`, usuario `default` y la credencial del archivo privado. El puerto
local admite `PYAO_REDIS_INSIGHT_PORT`. El perfil es optativo y publica sólo en
loopback.

## Durabilidad

`redis/redis.conf` habilita AOF con `appendfsync everysec`, sin desactivar fsync
al reescribir, y RDB a los 900 s/1 cambio, 300 s/10 cambios o 60 s/10000 cambios.
Se persiste **todo `/data`**, incluido `appendonlydir` y su manifiesto. Un cierre
limpio guarda escrituras pendientes. Ante caída abrupta, everysec puede perder
aproximadamente el último segundo; el almacenamiento debe cumplir fsync. Un
reinicio de proceso no equivale a un corte eléctrico. Los snapshots agregan
puntos de recuperación; el volumen local sigue necesitando un backup externo.

Ensayo con datos sintéticos, contenedor/volumen UUID y puerto local aleatorio:

```bash
uv run --locked python -m src.operations.redis_persistence
```

Comprueba CONFIG GET, autenticación obligatoria, reinicio limpio y SIGKILL después
de WAITAOF confirmado. Retira sólo sus recursos y nunca conecta al Redis activo.
Este último caso demuestra persistencia sincronizada; no promete conservar
escrituras que todavía no llegaron a fsync.

## Backup consistente y privado

Se requieren Docker y `redis-cli`. La instancia debe estar dedicada a pyao: el
RDB contiene **todos los DBs**, no sólo el seleccionado por el servidor, además
de cuentas, hashes de contraseña, oro, inventario, progreso y configuración.

```bash
uv run --locked python -m src.operations.redis_backup backup --output .backups/pyao-2026-10-18.rdb
uv run --locked python -m src.operations.redis_backup verify .backups/pyao-2026-10-18.rdb
```

`backup` lee un RDB consistente por el protocolo de replicación y lo restaura en
un volumen descartable antes de publicar el archivo y su recibo `.rdb.json`, ambos
0600 y sin sobrescribir archivos existentes. El recibo registra versión, fecha,
SHA256 y un digest canónico por DB de las claves persistentes. Los valores y
nombres de claves no se imprimen. Para otro origen, usar `--host`, `--port` y
`--password-file`; la contraseña sigue fuera de los argumentos.

`verify` comprueba el SHA256 antes de iniciar un destino, carga el RDB con AOF
inicialmente deshabilitado, activa AOF, confirma su fsync y recrea el contenedor
sobre el mismo volumen para verificar la recarga. Compara contenido y cantidades
de strings, hashes, listas, sets y zsets. Las claves con TTL mantienen su fecha
absoluta y pueden vencer durante la recuperación; no forman parte del digest
persistente. Se rechazan tipos ajenos al contrato de pyao. Al finalizar se retiran
los recursos descartables.

Política inicial de operación: backup diario, 14 copias diarias y 8 semanales,
con una copia cifrada fuera del host. Verificar semanalmente una restauración y
antes/después de una migración. Registrar fecha, digest y resultado sin datos de
jugadores. La rotación elimina una copia sólo después de verificar una más nueva;
la herramienta conserva la decisión de retención en el operador. `.backups/`
está excluido de Git y debe restringirse también el acceso a las copias externas.

## Recuperar sin sobrescribir la instancia activa

Conservar el origen y detener el juego antes de cambiarlo de destino. Para
mantener la restauración en un volumen y contenedor nuevos:

```bash
uv run --locked python -m src.operations.redis_backup restore .backups/pyao-2026-10-18.rdb --password-file "$PYAO_REDIS_PASSWORD_FILE"
```

El comando exige un archivo de credencial permanente, realiza la misma validación
y entrega nombre de contenedor, volumen y puerto loopback del destino. Conserva
esos recursos sólo después de la comprobación completa. No modifica ni detiene la
instancia de origen. El operador actualiza host/puerto del servidor al endpoint
entregado y comprueba el ingreso antes de retirar el origen. La contraseña del
nuevo destino es la del archivo seleccionado; su contenido no aparece en el
resultado. Un error de integridad o de restauración retira sólo el destino nuevo.

Activar AOF directamente sobre una restauración RDB sin convertirla primero puede
seleccionar un AOF vacío; la herramienta aplica la secuencia RDB → AOF → recarga.
Para volver a una versión anterior se conserva el backup y se restaura otro
volumen, en lugar de ejecutar una migración inversa destructiva.

Ensayo reproducible de backup, restauración, varios DBs, conservación de cuenta,
oro, inventario y habilidades, y rechazo de un archivo alterado:

```bash
uv run --locked python -m src.operations.redis_backup selftest
```

Referencias: [persistencia de Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
y [release 8.10.2](https://github.com/redis/redis/releases/tag/8.10.2).
