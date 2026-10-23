# Mascotas y fogatas: índices acotados (#578 y #577)

Redis conserva las instancias y las fogatas autoritativas. Se eliminó el
descubrimiento global de las consultas habituales, no la persistencia.

## Mascotas

Antes, seguimiento, conteo, órdenes y desconexión llamaban a `get_all_npcs()`:
`KEYS npc:instance:*` y un `HGETALL` secuencial por cada NPC. La desconexión TCP
hacía ese recorrido dos veces; `/QUIT` podía repetirlo por cada mascota.

Ahora, `NPCRepository.get_player_pets(user)` lee `player:<user>:pets` y obtiene
sus instancias en un pipeline sin transacción. Valida propietario, vida y condición
de mascota antes de devolver datos; una referencia obsoleta se poda bajo `WATCH`
para no borrar una adopción concurrente. Las instancias vencidas sólo se incluyen
cuando se pide expresamente para retirarlas. Un NPC con `gm_follow_user` sigue
siendo un NPC administrativo.

Creación, cambio de dueño, muerte, liberación y eliminación confirman los cambios
de instancia y `SADD`/`SREM` en el mismo `EXEC`. `transact()` deriva esas membresías
de su snapshot protegido, junto con el recibo de operación: perder un ACK no crea
otra mascota. Las decisiones de doma/invocación que reemplazan el conjunto de
propietario también observan ese conjunto con `WATCH`.

El índice local del mundo conserva referencias por dueño e identidad estable.
Seguimiento y expiración recorren sólo mascotas; las órdenes y snapshots no
recorren los NPC del mundo. La doma vuelve a registrar el modelo mutable para
actualizar todos sus índices. Reingreso de mapa y eliminación retiran referencias
anteriores. Al arrancar, Redis reconstruye la vista y los índices, conserva las
mascotas domadas vivas y retira invocaciones temporales, como antes. No se cambió
la política de persistencia de invocaciones.

Las lecturas pasan de O(K + N) y N viajes secuenciales a O(P), con dos viajes normales
(conjunto y lote), donde K son claves Redis, N todos los NPC y P las mascotas del
dueño. El orden estable de IDs añade O(P log P) de CPU, con P limitado a tres por
las reglas actuales. El seguimiento local pasa de O(K + N) con I/O de NPC a O(Ptotal), sin
consultas Redis para descubrir mascotas; conserva las lecturas necesarias del dueño.
La memoria adicional es O(Ptotal) referencias, sin copiar modelos completos.

## Fogatas

Antes, cada sincronización ejecutaba `SCAN MATCH world:campfire:<mapa>:*` y una
lectura secuencial por fogata. `MATCH` no evita recorrer las demás claves Redis.

Ahora, `world:campfires:<mapa>` contiene sólo las claves de ese mapa. El hash de
cada fogata mantiene datos y TTL originales. Su creación, consumo de tres leños,
entrenamiento, índice y recibo se confirman juntos. La consulta usa `SMEMBERS` y
un pipeline, valida posición/vencimiento y poda referencias bajo `WATCH`. Una
referencia corrupta a otro mapa se retira del conjunto sin leer ni borrar ese dato.

La reconstrucción se hace una vez antes de abrir el listener; no renueva TTL ni
reescribe hashes. No requiere migrar el esquema persistido. Los recorridos globales
`SCAN` que quedan pertenecen al arranque/mantenimiento, nunca a sincronización por
jugador o tick. Las lecturas pasan de O(K + F) a O(Fmapa); ordenar las referencias
añade O(Fmapa log Fmapa) de CPU y el índice ocupa O(Fmapa).
Un lock por emisor evita paquetes duplicados de ticks concurrentes y volver al
mapa reconstruye la vista.

## Medición reproducible

```sh
uv run --locked python -m tools.analysis.world_index_study \
  --output /tmp/world-indexes.json
PYAO_RUN_SCOPED_INDEX_REDIS=1 uv run --locked pytest \
  tests/repositories/test_scoped_world_indexes.py
```

El [resultado completo](../benchmarks/world-indexes-2026-10-22.json) conserva hashes
de fuentes/datos, versión/GIL, 31 muestras después de tres calentamientos, p50/p95/p99,
desviación, CPU del cliente y Redis, comandos y memoria. Compara los métodos reales
del commit `fd3d819e75116ac6a4a6fcace7c6970e945425b9` con los nuevos sobre la misma
base aislada. Los escenarios usan 32/512/4.096 NPC, tres mascotas, dos fogatas en el
mapa, 200 en otros mapas y 0/10.000/50.000 claves ajenas.

En la muestra de 4.096 NPC y 50.000 claves ajenas:

- Consulta de dueño: p50 767,28 ms → 0,541 ms; un `KEYS` y 4.096 `HGETALL` → un
  `SMEMBERS` y tres `HGETALL` enviados juntos.
- Seguimiento: p50 767,96 ms → 0,478 ms; quedan las lecturas del dueño, sin descubrir
  NPC en Redis. La cantidad de esas lecturas no crece con NPC ajenos.
- Descubrimiento al desconectar: p50 1.541,02 ms → 0,565 ms. Se excluye la eliminación
  y el transporte en ambos métodos para comparar el mismo trabajo de selección.
- Fogatas: p50 24,11 ms → 0,176 ms; 543 `SCAN` → un `SMEMBERS`, con iguales fogatas
  y claves. Ambas versiones leen la posición del jugador.
- Redis informó 66 bytes para el conjunto de tres mascotas y 91 bytes para el
  conjunto de dos fogatas del mapa en esta fixture; no son un tamaño universal.

Se midió Linux x86_64, loopback y la carga acotada indicada. El pico RSS es
acumulado del proceso; `tracemalloc` excluye asignaciones nativas y de Redis.
Los tiempos de CPU Redis incluyen trabajo de fondo. No se purgó la caché del SO
ni se midió capacidad máxima. Las mejoras grandes se explican por comandos y
alcance; diferencias pequeñas requieren repetir en un host dedicado.

## Verificación

Las pruebas cubren índices vacíos/obsoletos, propiedad ajena, seguidores GM,
muerte, expiración, reasignación concurrente, órdenes, liberación y movimiento
del modelo entre mapas. El mismo módulo corre contra fake Redis y Redis real
con AOF y reinicio físico, usando siempre contenedor y volumen propios. CI ejecuta
también ese backend real. Fogatas verifica además competencia por una casilla,
ACK perdido, sincronización concurrente y volver al mapa.

La campaña gráfica adicional ejecuta dos Godot por TLS: creación visible en ambos,
descanso/regeneración, reconexión, dos reinicios, conservación de mascota domada,
órdenes y liberación autorizada, y vencimiento natural de la fogata a los 120 s.
Se puede repetir sin cambiar el cliente:

```sh
uv run --locked python -m tools.analysis.scoped_world_graphical \
  --client ../ArgentumOnlineGodot --godot /ruta/Godot \
  --output /tmp/scoped-indexes-graphical
```

Es prueba del proyecto gráfico instrumentado, no de un Snap publicado ni una
aceptación de distribución de 30 minutos. El estudio Nuitka reutiliza esta campaña
con un ejecutable experimental identificado por hash.
