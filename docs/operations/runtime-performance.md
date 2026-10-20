# Optimización aplicada de las estructuras del mundo

Implementación posterior al [diagnóstico #333](runtime-structures.md), sobre
servidor `f8261ad56163f569f62a4fdd3ee7054c445b4698` y cliente
`4d4c74e214cbed1aa76398ffd12021bc9d9d846d`. La versión del par sigue siendo
`1.0.0rc3`. Las mediciones y hashes efectivos están en
[runtime-optimizations-2026-10-20.json](../benchmarks/runtime-optimizations-2026-10-20.json).

## Terreno y carga (#338)

Las seis capas usan `CoordinateMask`: 1.250 bytes de payload por capa, coordenadas
externas 1..100 y consultas fuera de ese dominio rechazadas. Incluye bloqueos,
agua, árboles, minas, yunques y fraguas. Las operaciones entre máscaras usan
operaciones de bits sin reconstruir miles de tuplas. Puertas y carteles conservan
sus datos dispersos; los talleres siguen publicando sus objetos y colisiones.

La caché `terrain-v1.msgpack` guarda los planos directamente y valida versión,
directorio y SHA256 de los archivos fuente. Se reemplaza atómicamente; una caché
vieja, corrupta o de otro catálogo se reconstruye. Es estado descartable. Redis
no cambia de esquema. El cargador de colisiones lee NDJSON en streaming y libera
las copias de fuentes al terminar; los bloqueos dinámicos tienen una copia propia.

Comparación con **los mismos archivos de los 290 mapas**, verificados por hash:

- Las 2.486.941 coordenadas, las seis capas de cada mapa, colisiones y salidas
  coinciden con la referencia. Se prueban también los bordes 1/100 y 0/101.
- Heap del catálogo de recursos: 292.671.468 → 2.669.205 bytes, una reducción del
  99,1%. Los 2.175.000 bytes de payload no incluyen contenedores ni metadatos.
- Heap del `MapManager` sin jugadores: 384.078.387 → aproximadamente 18.585.242
  bytes. Estos tamaños se miden por separado, sin sumar referentes compartidos.
- RSS retenido del proceso de carga tras GC: 728,5 → 114,2 MiB. Es una prueba de
  carga de recursos/colisiones, no el consumo completo de un servidor productivo.
- Cargar recursos desde caché: 435 → 43 ms. Cargar colisiones: 1,24 → 1,45 s.
  Consulta puntual del catálogo: p50 0,163 → 0,271 µs. La consulta cuesta unos
  0,11 µs adicionales; el beneficio principal es memoria y carga del catálogo.

Los conjuntos anteriores costaban O(coordenadas marcadas) en espacio. Ahora son
O(mapas × 6 × 10.000 bits), con acceso puntual O(1) dentro del dominio fijo.

## Jugadores, NPCs y suelo en memoria (#339–#341)

`PlayerIndex` mantiene `user_id → sesión` y `nombre normalizado → usuarios`,
además de los buckets ordenados por mapa. ID, nombre y sender se localizan en
O(1) medio; antes requerían recorrer mapas o jugadores. Una transición conserva
la identidad hasta retirar la última pertenencia. Una conexión nueva reemplaza
las referencias anteriores; la limpieza tardía valida el sender esperado. Cambiar
el nombre elimina su alias anterior. Se conserva `lower().strip()` y el orden de
las listas públicas. El conjunto de mapas de cada sesión admite altas/bajas;
por eso es mutable.

`NpcIndex` agrega `(mapa, CharIndex) → NPC` y bindings por UUID. Buscar o mover
por CharIndex pasa de O(NPCs del mapa) a O(1) medio. Rechaza un CharIndex activo
duplicado y retira los bindings y tiles al mover, volver a registrar o eliminar
la instancia, incluso si el modelo ya fue mutado. Un respawn puede reutilizar el
CharIndex sin que una retirada vieja borre al reemplazo.

`GroundItemIndex` almacena `mapa → (x,y) → stacks`. Consultar un tile sigue siendo
O(1) medio; contar, limpiar, reemplazar y publicar un mapa recorre sus posiciones,
en lugar de todo el mundo. Los stacks conservan orden, identidades y metadatos.
No hay una copia global y otra por mapa: `MapTileIndex` ofrece la vista compatible
sobre un único almacenamiento agrupado.

Con 5.000 registros sintéticos, p50 en microsegundos por consulta:

- Último nombre en un mapa: 190,08 → 0,21; distribuido en 50 mapas: 222,43 → 0,33.
- NPC por CharIndex entre 5.000 en un mapa: 130,83 → 0,062.
- Contar suelo de un mapa entre 50: 71,41 → 1,60. Contar 5.000 posiciones del
  mismo mapa todavía recorre esas posiciones: 118,64 → 72,05.

Los índices consumen memoria adicional: para esos 5.000 registros el índice de
jugadores pasa de 1,87 a 4,94 MB y el de NPCs de 2,94 a 4,04 MB. Incluye el
mantenimiento real; los prototipos del diagnóstico inicial subestimaban ese costo.
Las cotas de hashing son medias amortizadas, no una garantía de peor caso O(1).

## IA y broadcast (#342)

`get_positions` lee posiciones y, opcionalmente, HP en pipelines de hasta 256
usuarios. Conserva defaults y HP legacy; excluye ausentes y muertos. Elegir un
candidato no liquida ni consulta saldos. Las operaciones monetarias siguen
materializando la devaluación diaria en su límite durable.

La IA obtiene un snapshot por mapa y por ejecución del tick, compartido por todos
sus NPCs y descartado al terminar. La IA global se agenda una vez, en lugar de
repetirla por cada jugador. Un fallo de lectura de un mapa no impide procesar los
demás. El ataque relee vida, mapa y distancia y conserva su commit autoritativo;
el snapshot nunca autoriza daño. Los tests cubren muerte y cambio de mapa después
de seleccionar el candidato.

Se elimina la multiplicación de lecturas por NPC/jugador: las lecturas de
candidatos son O(jugadores de mapas activos), con pipelines acotados. Buscar el
más cercano todavía compara las distancias O(N_m × P_m); no se introdujo un
quadtree sin evidencia de necesidad. Para 50 candidatos vivos con su día ya
liquidado, la ruta anterior hacía 150 comandos secuenciales; ahora hace 100 en
un pipeline. El benchmark adicional registra comandos y percentiles reales.
Sin carga gráfica concurrente, esa lectura de 50 candidatos pasó de 5,33 a
1,12 ms p50 y de 6,41 a 1,17 ms p99. Para 500 candidatos, acotados a dos pipelines:
55,44 → 10,92 ms p50. La fixture usa saldos ya liquidados y HP vivo; no incluye
ataques ni una simulación de 500 conexiones.

El broadcast de movimiento lee las posiciones en lotes y calcula apariencia una
sola vez si cambió la orientación y hay receptores. Conserva el rango visible y
descarta receptores que ya cambiaron de mapa. Emitir V mensajes sigue costando
O(V); no hay una caché de apariencia entre movimientos.

## Login y cola de RTT (#344)

Los dos outliers de unos 517/586 ms eran la **iteración 0 de cada peer**. El
benchmark consideraba listo el login al recibir `UPDATE_USER_STATS`, que se envía
antes del spawn. El primer ping quedaba detrás del resto del handler de login.
Las trazas acotadas mostraron un login de unos 596 ms: aproximadamente 101 ms de
espera fija, 124 ms en el primer spawn y otros 425 ms al volver a publicar el mapa,
incluido el desbloqueo de salidas con espera por tile. No era un pico de CPU o
Redis durante el juego. Las pausas de carga fría del event loop se registran
aparte y ocurren antes de admitir sesiones.

El login ahora usa un único `spawn_in_map`, después de cargar el suelo, incluyendo
NPCs aleatorios, talleres, portales y estado. Las transiciones conservan el orden
TCP de `CHANGE_MAP` y entidades. Se eliminaron las esperas temporales fijas;
el envío cede el event loop cada 16 entidades para permitir drenar la cola
acotada. Los límites, validaciones, durabilidad y aislamiento de lectores lentos
siguen activos.

El benchmark espera un PONG enviado detrás del LOGIN para medir ingreso completo
y publica la latencia de las primeras estadísticas por separado. La primera
corrida dio login completo 56–57 ms; p99 durante el juego 2,78 ms y máximo 3,40 ms.
La matriz posterior compara concentración, ausencia de lector lento y distribución
en dos mapas, manteniendo los presupuestos existentes. Es un escenario pequeño
de dos conexiones activas, no una certificación de capacidad masiva. La mejora
del p99 incluye corregir la clasificación del tiempo de ingreso; el tiempo real
del handler también disminuye de unos 596 a menos de 70 ms en esa prueba.
En la matriz verificada, las tres condiciones dieron p99 entre 1,42 y 2,27 ms,
máximos de hasta 2,57 ms y sin errores de transporte. El ingreso completo queda
en el reporte separado de RTT; no se aumentaron sus presupuestos para aprobar.

## Cliente Godot (#164)

`MapContainer` mantiene índices por ID y posición lógica para personajes y por
posición para objetos. Las bajas intercambian el último slot del array, evitando
`Array.erase` global. Mover/teletransportar actualiza la celda mediante el setter
de `gridPosition`; interpolar el sprite no modifica el índice. Si se superponen
personajes se conserva la selección del primero creado. El costo de mantener ese
orden depende de los ocupantes de esa celda, no de todos los actores del mapa.

Los índices se limpian al cambiar de mapa, liberar nodos y reutilizar un ID.
`GameWorld` asigna ID/celda antes de registrar el personaje. El test incluye
borrados diferidos, liberación externa, solapamientos y 1.000 altas/bajas.

Con 5.000 nodos sintéticos, localizar el último ID pasó de 122,96 a 0,15 µs p50;
por posición, de 143,87 a 0,25 µs. Mover a otra celda y volver cuesta 1,58 µs;
retirar y volver a registrar, 3,46 µs. El monitor de memoria de esa fixture,
incluyendo diccionarios de referencia, pasa de 18,35 a 35,34 MB. No incluye hijos
del renderer, texturas ni tráfico de 5.000 clientes. Es un intercambio explícito
de memoria por consultas y bajas rápidas, independiente del gran ahorro del
terreno del servidor.

## Reproducción y validación

Servidor:

```sh
uv run --locked python scripts/benchmark_structures.py --redis --output artifacts/structures.json
uv run --locked python scripts/benchmark_candidate_reads.py --output artifacts/candidates.json
PYAO_STATE_DIR=/tmp/pyao-world-measure uv run --locked python scripts/benchmark_world_load.py --output artifacts/world.json
```

Para comparar otro checkout, ejecutar `benchmark_world_load.py` con `PYTHONPATH`
apuntando al checkout de referencia, `PYAO_MAPS_DIR` al mismo catálogo y un
`PYAO_STATE_DIR` propio. Comparar hashes de fuentes, capas, colisiones y salidas
antes de comparar tamaños. Repetir con la misma caché para medir carga caliente.

Cliente: `tests/entity_indexes.tscn` y `tests/structure_benchmark.tscn`, con
`PYAO_STRUCTURE_OUTPUT` apuntando al JSON. El smoke habitual incluye la regresión
de índices. Para el perfil nativo usar `tools/integration-world.py --source
--scenario structure-profile --server-profile ...`. La opción de perfil sólo
activa `tools.profile_runtime` en la fixture fuente; limita a 4.096 eventos de
al menos 5 ms y registra nombres de comandos/clases y tiempos, sin argumentos.
La matriz corre con/sin lector lento y jugadores en uno/dos mapas.

Se verificaron Ruff, formato, mypy, la suite completa con cobertura, escenas
Godot, herramientas del cliente, TLS con dos clientes gráficos, reconexión,
combate y navegación. Las pruebas de suelo/botín con Redis real conservan
recibos, carreras y recuperación tras SIGKILL/AOF.

El suelo durable todavía usa el documento JSON por mapa. Su segmentación
[#343](https://github.com/cavazquez/pyao-server/issues/343) continúa como migración
independiente: la optimización de buckets de memoria no cambia las garantías ni
la complejidad del commit persistido.
