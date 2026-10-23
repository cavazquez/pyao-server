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

Las cuentas y el progreso mutable de la partida (posición, inventario, banco,
oro, habilidades, hechizos y relaciones sociales) se guardan en Redis. Los
catálogos y recursos versionados aportan los datos iniciales; AOF/RDB y los
procedimientos de backup de esta guía protegen el estado persistido.

El pool async conserva el límite `redis.max_connections` (20 por defecto).
Cuando todas están ocupadas, las tareas esperan una conexión libre durante
`redis.pool_timeout` segundos (5 por defecto), sin bloquear el event loop.
`PYAO_REDIS__POOL_TIMEOUT` permite ajustar ese plazo positivo. Es independiente
de los timeouts de conexión y lectura de red; al vencer devuelve un error en
vez de esperar indefinidamente. Cerrar el cliente cierra también su pool.

## Redis Insight

```bash
docker compose --profile tools up -d
```

La UI queda en [localhost:5540](http://127.0.0.1:5540). Configurar host `redis`,
puerto `6379`, usuario `default` y la credencial del archivo privado. El puerto
local admite `PYAO_REDIS_INSIGHT_PORT`. El perfil es optativo y publica sólo en
loopback.

## Durabilidad

`redis/redis.conf` habilita AOF con `appendfsync always`, sin desactivar fsync
al reescribir, y RDB a los 900 s/1 cambio, 300 s/10 cambios o 60 s/10000 cambios.
Se persiste **todo `/data`**, incluido `appendonlydir` y su manifiesto. Un cierre
limpio guarda escrituras pendientes. El perfil `always` confirma fsync en cada lote de escrituras; el almacenamiento debe cumplir fsync. Si una instalación existente conserva `everysec`, puede perder aproximadamente el último segundo de escrituras no confirmadas y cada barrera puede esperar ese intervalo. Un
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

## Esquema y migraciones

`schema:state` conserva la versión y un journal por paso. La versión 1 adopta
explícitamente el layout legado de cuentas/economía/progreso, sin reemplazar
datos por seeds. Una base nueva se inicializa en la versión actual. Una base con
estado legado exige migración explícita antes de abrir el juego, y una versión
futura se rechaza antes de escribir defaults o cargar datos iniciales.

Con el perfil AOF configurado, el juego detenido y sin sesiones activas:

```bash
uv run --locked python -m src.operations.redis_schema status
uv run --locked python -m src.operations.redis_backup backup --output .backups/antes-de-migrar.rdb
uv run --locked python -m src.operations.redis_schema migrate --backup .backups/antes-de-migrar.rdb
uv run --locked python -m src.operations.redis_schema status
```

La migración vuelve a verificar una restauración del backup y comprueba que el
origen siga igual a ese snapshot. Rechaza sesiones de jugadores y otra migración
activa. Cada paso confirma versión y journal con un HSET dentro de WATCH/MULTI;
repetir tras perder la respuesta de EXEC no duplica el paso. La reserva tiene
propietario y vence a los cinco minutos si el proceso cae; sólo el dueño puede
liberarla. El arranque también rechaza una reserva activa. Se confirma fsync antes
de anunciar éxito. Una interrupción previa a la confirmación permite reintentar;
una posterior conserva versión y journal. La recuperación usa otro volumen
restaurado desde el backup verificado, conservando el origen para revisión.

Las transformaciones de formatos posteriores deben agregar su paso ordenado y
su fixture de conservación; cambiar los seeds no migra jugadores existentes.

```bash
uv run --locked python -m src.operations.redis_schema selftest
```

Referencias: [persistencia de Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
y [release 8.10.2](https://github.com/redis/redis/releases/tag/8.10.2).

### Migración v2: maná dentro de int16

El balance incluido usa `mana_per_int = 10`: inteligencia 10 genera 100 de maná.
Los cálculos de alta/subida de nivel saturan a 32767 antes de persistir. Los setters
rechazan maná negativo, mayor al máximo o mayor a 32767; no se repara al enviar.

`uv run python -m src.operations.redis_schema status` muestra `mana_out_of_range`
sin escribir. Para reparar estado histórico, detener el servidor, crear y verificar
el backup como arriba y ejecutar `uv run python -m src.operations.redis_schema
migrate --backup <archivo.rdb>`. La migración v2 limita máximo a 0–32767 y actual
a 0–máximo; conserva originales en `migration:mana:current_before` y
`migration:mana:maximum_before` del hash del personaje. Conserva oro, experiencia,
inventario y todos los demás campos. El backup preserva el estado original completo.

Los cambios pendientes y sus journals se confirman en una sola transacción; ante
una respuesta perdida se puede repetir sin duplicar pasos ni auditoría. Un dato no
numérico requiere inspección y aborta antes del commit. El arranque rechaza esquema
v1 hasta completar esta migración explícita. La autoverificación descartable sigue
siendo `uv run python -m src.operations.redis_schema selftest`.

### Migración v3: progreso de habilidades

La versión v3 agrega niveles y XP separados según `src/network/protocol/skills.json`.
Conserva todos los campos originales, los puntos disponibles y las claves desconocidas.
Por ejemplo, `magia=10` conserva nivel 10; `talar=275` conserva XP 275 y representa
nivel 2 con 75% usando el umbral 100. Robustez y agilidad mantienen sus IDs propios.
El umbral efectivo se guarda en cada perfil. No se repara ni se migra durante envíos.

Usar el procedimiento anterior con el servidor detenido y backup verificado;
`redis_schema migrate` aplica los pasos pendientes hasta la versión actual en una transacción.
Repetir no convierte otra vez los valores históricos. `redis_schema selftest`
comprueba también que XP, niveles, puntos, oro e inventario sobreviven a la migración.

### Migración v4: entrenamiento clásico y puntos por nivel

El formato `progress_version=2` conserva los niveles, la XP total y los campos
históricos. Agrega `partial:<habilidad>` para el avance hacia el siguiente nivel
con umbral creciente `round(200 * 1.05 ** nivel)`. La conversión conserva el
porcentaje previo; no vuelve a interpretar XP total como nivel ni elimina las
habilidades propias Robustez y Agilidad, IDs 21 y 22.

El personaje nace con diez puntos. El nivel 2 concede diez nuevos y cada nivel
posterior concede cinco. `points_granted_through` registra hasta qué nivel fueron
otorgados; la migración recupera los puntos de niveles históricos que no los
habían concedido. Repetir la migración, una acción o el chequeo de nivel no los
duplica. No se alteran oro, inventario, atributos iniciales ni grupos existentes.

Usar el mismo procedimiento de backup verificado y migración con el servidor
detenido. El arranque rechaza un esquema v3 pendiente de migrar. Las reglas y
recetas se cargan a `config:skills:rules` y `config:crafting:recipes` al iniciar;
durante una partida las acciones leen esos datos desde Redis. Los hashes
`player:<id>:skills`, `player:<id>:user_stats`, inventario, propiedad de mascotas
y `world:campfire:<mapa>:<x>:<y>` contienen el estado guardado. Las fogatas tienen
vencimiento y las mascotas domadas no se eliminan al desconectar o reiniciar.
