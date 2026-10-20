# Suelo por casilla: esquema Redis 6

Implementa [#343](https://github.com/cavazquez/pyao-server/issues/343).
El esquema 5 guardaba un documento JSON completo en `ground_items:<mapa>`.
El esquema 6 conserva la clave y cambia su tipo a hash: cada campo canónico
`x,y` contiene la lista JSON completa de stacks de esa casilla. No hay una segunda
copia persistida ni escrituras de inventario/suelo en segundo plano.

## Operaciones y complejidad

`Resource(kind="ground", fields=(...))` declara las casillas antes de WATCH.
El snapshot de negocio conserva la interfaz de `GroundState`, pero sólo contiene
ese alcance. HMGET lee los campos solicitados; HSET/HDEL escriben o retiran las
listas correspondientes. La decisión no puede escribir casillas ajenas al alcance.
Se conservan orden, IDs, cantidades, campos opcionales y fracciones de devaluación.

Drop, pickup y muerte de jugador usan una casilla. El botín de NPC declara los
destinos candidatos del radio de caída, congelados antes del commit. Un rechazo
por falta de capacidad conserva el plan pendiente y no paga XP ni botín parcial.
El refresco del índice local también lee sólo esas casillas. La selección previa
de pickup dejó de cargar el mapa entero.

Para K casillas solicitadas, el trabajo y los bytes dependen de sus stacks, con
un máximo de diez por casilla. No dependen de las otras P posiciones del mapa.
Los metadatos variables siguen contando en el tamaño de cada stack. Cargar un
mapa completo para login, inspección o reemplazo administrativo sigue costando
O(P); esas operaciones reservan HGETALL. El reemplazo administrativo exige que
no haya sesiones activas y que el servidor esté detenido.

WATCH continúa protegiendo el hash completo del mapa: dos escrituras en casillas
distintas pueden provocar un reintento. Esta implementación reduce los bytes y
la serialización; no promete transacciones independientes por campo ni elimina
la contención bajo carga ilimitada.

## Atomicidad, recibos y devaluación

La misma transacción incluye suelo, inventario, equipo, saldos, estado fiscal y
recibo. Se conservan los límites WATCH/EXEC y las barreras WAITAOF en una conexión
dedicada antes de anunciar resultados. El alcance forma parte del fingerprint de
los recibos nuevos. Los recibos previos al cambio de esquema se reconocen por su
fingerprint anterior y devuelven su resultado sin aplicar otra vez el negocio.

Cada montón conserva `devaluation_day` y `devaluation_remainder`. La operación
liquida sus casillas antes de mover oro y conserva las fracciones al transferirlo
entre suelo, personaje y banco. El mantenimiento sin jugadores recorre campos con
HSCAN NOVALUES y procesa hasta 64 casillas por transacción. HSCAN usa COUNT como
orientación, por eso cada respuesta se divide además en lotes de 64 antes de leer
valores y planificar cambios. Las iteraciones duplicadas son idempotentes por día.

Una acción que modificaba suelo renueva el vencimiento del mapa a una hora, como
antes. El mantenimiento conserva el vencimiento existente: HSET/HDEL no lo
renuevan. Al retirar el último campo Redis elimina el hash vacío. Una expiración
entre lectura y EXEC fuerza la revalidación y no acredita objetos vencidos.

Las casillas que desaparecen durante la proyección fiscal también se publican a
los clientes. Los envíos fallidos quedan pendientes aunque el índice local ya se
haya refrescado, para que un reintento no deje oro visible después de agotarse.

## Migración explícita y recuperación

Una base nueva adopta el esquema 6. Una base existente en 5 requiere una migración
con el servidor detenido; el arranque no cambia tipos ni sobrescribe datos.
Usar la configuración del endpoint elegido, sin poner contraseñas en argumentos:

```sh
uv run --locked python -m src.operations.redis_schema status
uv run --locked python -m src.operations.redis_backup backup --output /ruta/privada/antes-v6.rdb
uv run --locked python -m src.operations.redis_backup verify /ruta/privada/antes-v6.rdb
uv run --locked python -m src.operations.redis_schema migrate --backup /ruta/privada/antes-v6.rdb
```

El respaldo se restaura en un Redis descartable para comprobarlo. La comparación
previa a migrar incluye también contenido y vencimientos absolutos del suelo con
TTL, además del estado persistente ya verificado. Cambiar suelo después de crear
el respaldo impide migrar y exige respaldar nuevamente.

La migración valida todos los mapas antes de escribir. Conserva las identidades
existentes y deriva una sola vez las identidades legadas. Rechaza datos corruptos,
coordenadas no canónicas y casillas que exceden su capacidad, sin truncarlas.
Bajo WATCH reemplaza los strings por hashes y aplica PEXPIREAT con el vencimiento
original, en el mismo EXEC que publica el esquema y su journal. Los mapas sin TTL
siguen sin TTL; las casillas vacías no requieren campos persistidos. Una respuesta
perdida se resuelve consultando la versión y repitiendo sin reconvertir ni renovar
vencimientos. La preparación offline puede requerir memoria proporcional al suelo
completo; no es una operación del tick del juego.

La reversión comprobada usa el RDB previo en un volumen nuevo y el código previo,
antes de volver a admitir jugadores. El volumen migrado se conserva. Restaurar
ese respaldo devuelve el estado de ese instante; no incorpora partidas posteriores.
La herramienta de recuperación no reemplaza el volumen de origen:

```sh
uv run --locked python -m src.operations.redis_backup restore /ruta/privada/antes-v6.rdb --password-file /ruta/privada/redis-password
```

Configurar el servidor anterior contra el destino devuelto y comprobar su estado.
Los ensayos de esta implementación usaron únicamente datos sintéticos y Redis
descartables; no se migró una base del operador.

## Medición y regresiones

[Evidencia antes/después](../benchmarks/redis-ground-2026-10-20.json): Redis 8.10.2
propio, mismo intérprete y 51 muestras por operación/tamaño después del calentamiento.
El código de referencia es `4b1cef2d34a17700593724f17edb12745b72238a`.
El microbenchmark usa `appendfsync always` en ambos casos y mantiene las barreras
de durabilidad; así la cadencia de un segundo de `everysec` no domina la medición.
La configuración distribuida continúa usando `everysec`.

Con 5.000 posiciones sintéticas, incluyendo commit durable y refresco local:

- Drop: p50 37,15 → 4,18 ms; p95 40,10 → 4,64 ms; p99 40,99 → 8,11 ms.
- Pickup: p50 36,73 → 4,19 ms; p95 39,22 → 4,69 ms; p99 39,51 → 5,22 ms.
- Payload JSON de suelo leído/escrito durante un drop: aproximadamente 1,30 MB
  → 258 bytes. No cuenta framing RESP, nombres de campos ni otros recursos.
- MEMORY USAGE del suelo: 458.793 → 589.333 bytes. El hash usa aproximadamente
  28% más memoria en esta fixture a cambio de evitar serializaciones completas.

No son 5.000 clientes, un ensayo de capacidad ni una predicción de latencia de
producción. El WATCH por mapa y la cadencia AOF del despliegue siguen influyendo.
El script reproduce también 100 y 1.000 posiciones:

```sh
uv run --locked python scripts/benchmark_ground_transactions.py --baseline /ruta/fuentes-previas --output /ruta/resultado.json
uv run --locked python -m src.operations.ground_atomic_smoke
uv run --locked python -m src.operations.npc_loot_smoke
uv run --locked python -m src.operations.economy_smoke
uv run --locked python -m src.operations.redis_schema selftest
```

Las regresiones cubren competencia por un stack, replay/ACK incierto, expiración
durante EXEC, alcance de escritura, muerte, botín pendiente, banco/comercio,
fracciones diarias, ausencia de jugadores, límites de lote y recuperación AOF tras
SIGKILL. El selftest de migración comprueba además el rollback de suelo con TTL.

Contratos de Redis: [HMGET](https://redis.io/docs/latest/commands/hmget/),
[HSET](https://redis.io/docs/latest/commands/hset/),
[PEXPIRETIME](https://redis.io/docs/latest/commands/pexpiretime/) y
[transacciones](https://redis.io/docs/latest/develop/using-commands/transactions/).
