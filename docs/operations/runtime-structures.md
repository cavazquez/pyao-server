# Estructuras del mundo: diagnóstico medido del 20/10/2026

Se revisaron servidor y cliente para el issue #333. Se corrigió la enumeración
cuadrática de jugadores conectados y se dejaron tareas independientes para las
optimizaciones que requieren mantener índices o cambiar representaciones.
Redis continúa siendo la autoridad durable; los índices de memoria son derivados.

## Reproducción y límites

Servidor: `uv run --locked python scripts/benchmark_structures.py --redis --output artifacts/structures.json`.
`--quick` ejecuta 100 y 1.000 entidades; la corrida completa agrega 5.000, en un
mapa y repartidas en 50 mapas. El Redis opcional es autenticado, descartable y
creado por `RedisSandbox`; no se acepta una URL de una base existente.

Cliente: abrir `tests/structure_benchmark.tscn` con Godot 4.7.2 y definir
`PYAO_STRUCTURE_OUTPUT` con la ruta del JSON. La ejecución gráfica mide 16 cambios
de mapa; en headless sólo se miden búsquedas. Para el perfil real:
`python tools/integration-world.py --scenario structure-profile --source --server-project ../pyao-server --godot /ruta/al/Godot --output /ruta/nueva --seconds 30`.
El runner crea sus cuentas, dos Godot, un servidor TLS y Redis propio; los procesos
y volúmenes se retiran al finalizar. La CLI de CI permite ejecutar la regresión
seleccionada sin construir Snaps ni distribuciones de las otras plataformas.

Hardware local: Ryzen 5 9600X, 6 núcleos/12 hilos, Linux x86_64, Python 3.14.0
free-threaded, Redis 8.10.2, Godot 4.7.2, Xvfb y renderizador software llvmpipe.
Los JSON de [medición inicial](../benchmarks/structures-before-2026-10-20.json),
[medición posterior](../benchmarks/structures-after-2026-10-20.json),
[Godot](../benchmarks/client-structures-2026-10-20.json) y sus
[metadatos](../benchmarks/client-structures-meta-2026-10-20.json) conservan
versiones, tamaños, repeticiones, percentiles y hashes de los archivos efectivos.
Las corridas locales sobre fuentes incluyen cambios todavía sin commit; los
hashes efectivos y manifiestos describen el código medido, además del HEAD base.

Cada microbenchmark tiene 21 o 31 muestras, con calentamiento y número de
iteraciones explícito. Con tan pocas muestras, p99 representa prácticamente el
máximo observado. El tiempo de un runner compartido no es una prueba estable de
regresión: CI conserva resultados y verifica invariantes, sin umbrales de tiempo
arbitrarios. No se certifica una capacidad de 5.000 conexiones: se construyeron
5.000 registros sintéticos. El perfil de red sí usa conexiones reales.

`deep_bytes` cuenta contenedores Python y referentes una sola vez. Los índices
adicionales descuentan objetos ya poseídos por la estructura original. No es RSS
del asignador, ni se pueden sumar tamaños que comparten referentes. Los NPCs
sintéticos de los índices tampoco representan todo el modelo: 1.000 instancias
del dataclass real requieren 1.756.778 bytes, unos 1.757 por registro en esa
fixture, excluyendo Redis, red y mapas. En Redis, 1.000 hashes mínimos de tres
campos aumentaron `used_memory` unos 131 KB; no representan cuentas completas.

## Complejidades verificadas en el código

Se usan M mapas, A tiles por mapa (10.000), P jugadores, N NPCs, E posiciones
ocupadas, T posiciones con objetos, S stacks por tile (máximo 10), B_m bytes del
documento durable de un mapa y V receptores visibles. El subíndice m indica sólo
un mapa. Los diccionarios/conjuntos tienen acceso medio amortizado O(1); su peor
caso por colisiones es lineal. Las cotas de abajo asumen hashing normal y separan
el tamaño de la salida del costo de localizarla.

- `PlayerIndex`: diccionario mapa → ID → (sender, nombre), espacio O(M+P).
  Consultar ID con mapa es O(1); sin mapa es O(M); buscar nombre es O(P).
  Listar jugadores de un mapa es O(P_m) en tiempo y salida. Antes, listar IDs o
  nombres únicos hacía pertenencia en una lista: O(P²), salida O(P). Ahora usa
  hashing ordenado, O(P) medio y espacio transitorio O(P), preservando el orden,
  nombres vacíos omitidos y duplicados transitorios entre mapas.
- `NpcIndex`: mapa → UUID → NPC, espacio O(M+N). Consultar UUID es O(1), pero
  `get_npc_by_char_index` y localizarlo en `move_npc` son O(N_m). Agregar un índice
  por (mapa, CharIndex) permite O(1) medio con O(N) referencias adicionales; exige
  invalidarlo en respawn, retirada y cambio de mapa.
- `TileOccupation`: (mapa,x,y) → identificador, espacio O(E). Punto y movimiento
  son O(1) medio. Retirar por identidad y limpiar un mapa recorren E globales,
  incluso si sólo interesan unas pocas posiciones. Un índice inverso o buckets
  por mapa evitarían ese recorrido, pero deben conservar colisiones/reservas.
- `GroundItemIndex`: (mapa,x,y) → lista de stacks, espacio O(T + stacks). Punto
  O(1) medio y recorrer un tile O(S). Contar, limpiar, reemplazar o emitir un
  snapshot de un mapa inspecciona T globales, con salida O(T_m). Los buckets
  propuestos reducen esa inspección a T_m; no alteran el formato durable.
- `GroundState`/`GroundItemsRepository`/`resource_transaction`: una recogida o un
  drop lee, valida y escribe el JSON de todo el mapa. Tiempo y memoria temporal
  O(B_m); con R intentos por contención, O(R·B_m). La comprobación de identidad
  de un nuevo stack también recorre el mapa. Es incorrecto describir este commit
  como O(1) porque la consulta inicial del tile sea O(1).
- Terreno de `MapResourcesService`/`MapBinaryCache`: conjuntos de coordenadas por
  mapa/capa, espacio O(coordenadas marcadas), consulta media O(1). El archivo
  binario reduce I/O; al cargarlo todavía se materializan conjuntos Python.
  `TileBitmap` es una alternativa, no la representación que usa ese servicio.
- IA `find_nearest_player`: recorre P_m y espera vida/posición por candidato.
  Para N_m NPCs que busquen, el trabajo puede ser O(N_m·P_m), además de los viajes
  a Redis. La frecuencia real depende del tipo de NPC y del tick. El broadcast
  de movimiento recorre P_m, consulta posiciones y puede releer la apariencia
  del emisor para cada receptor. Enviar V mensajes siempre tiene costo Ω(V).
- `NPCRepository.get_all_npcs`: `KEYS npc:instance:*` inspecciona el espacio de
  claves; después hay lecturas secuenciales. `SCAN` evita un bloqueo largo de
  `KEYS`, pero sigue teniendo costo total lineal. Pipeline reduce viajes de red,
  no el número de hashes ni la complejidad total de una lectura completa.
- Cliente `MapContainer`: arrays de personajes y objetos, espacio O(C+O).
  `GetCharacter`, `GetCharacterAt`, localizar/borrar un objeto y `Array.erase`
  son lineales. Índices por identidad/posición aceleran consultas, pero una
  posición interpolada no debe confundirse con la posición lógica del actor.
- Cliente `MapData`: dos `PackedInt32Array` y un `PackedByteArray`: 90.000 bytes
  de payload por mapa, más capas altas y objetos. Consultar flags es O(1).
  `MapViewCache` guarda hasta tres vistas y un presupuesto estimado de 64 MiB.
  Esa estimación no es un límite medido de RSS ni de VRAM. Buscar vecinos recorre
  aristas de topología; la lista LRU de longitud máxima tres no es un cuello.
- Pathfinding: la cola con prioridad cuesta O(L log L) para L expansiones y
  espacio O(L), con cuatro vecinos por tile y presupuesto de búsqueda acotado.
  Se deben medir expansiones/frecuencia, no sólo la operación de una celda.

## Resultados y cambio aplicado

Con 5.000 jugadores, enumerar IDs pasó de 39,60 ms a 0,094 ms en un mapa y de
44,63 ms a 0,113 ms repartidos en 50 mapas: aproximadamente 394–422 veces más
rápido en esa corrida. No se agregan índices persistentes ni una migración. Las
regresiones verifican orden, nombres y un jugador temporalmente en dos mapas.

Buscar el último nombre con 5.000 jugadores costó 191–223 µs; un diccionario
prototipo, alrededor de 0,1 µs. Buscar CharIndex entre 5.000 NPCs concentrados
costó 130 µs frente a 0,05 µs del prototipo. Los índices adicionales cuestan
aproximadamente 0,44–0,47 MB cada uno para 5.000 entidades en estas fixtures.
Es una comparación de consultas; todavía falta implementar/medir su mantenimiento.

En el suelo, contar un mapa entre 50 con 5.000 posiciones globales costó unos
72 µs frente a 1,6 µs agrupándolo por mapa. Un JSON de 5.000 posiciones mide
433.701 bytes: cambiar un objeto implica como mínimo unos 867 KB leídos/escritos.
Validar/modificar/serializar cuesta unos 7,9 ms; con Redis local, WATCH/GET/SET/EXEC
unos 8,4 ms. No incluye recibos, tributación, contención ni confirmación AOF del
commit de juego: es una cota inferior del recorrido durable.

Leer 50 hashes tomó 1,20 ms secuencial y 0,29 ms mediante pipeline. Ambos ejecutan
50 comandos; los viajes de aplicación pasan de 50 a uno. En una red remota la
diferencia puede ser mayor, pero aquí sólo se midió loopback.

Los 290 mapas contienen 2.486.941 coordenadas en las seis capas y ocupan
292.671.468 bytes en contenedores Python (279,1 MiB). Seis planos compactos por
mapa necesitan 2.175.000 bytes de payload y unos 2,32 MB como bytearrays/lista;
un byte de flags por tile necesita 2,90 MB de payload. El encabezado antiguo que
prometía menos de 1 MB era incorrecto y fue corregido. La alternativa compacta
requiere adaptar 1..100 del mundo a 0..99: pasar `(100,100)` directamente al
`TileBitmap` actual pierde ese borde. No se activó esa representación sin la
migración funcional/pruebas del terreno.

En Godot, buscar el último personaje entre 5.000 nodos sintéticos costó 124 µs
y buscar por posición 147 µs; los diccionarios prototipo, 0,06–0,07 µs. Los nodos
sin hijos de render más esos prototipos aumentaron el monitor de memoria unos
18,4 MB. Eso no mide renderizar 5.000 personajes. En 16 cambios gráficos de mapa
el presupuesto de caché se respetó; se observaron unos 2–61 ms dentro de LoadMap y
30–113 ms hasta el siguiente draw, según mapa y caché. Los recursos/texturas
compartidos y el renderer deben medirse aparte del payload de `MapData`.

## Perfil real y prioridades

El [perfil de ticks/frames](../benchmarks/live-structure-profile-2026-10-20.json)
y el [ensayo TLS](../benchmarks/live-tls-benchmark-2026-10-20.json) complementan
los microbenchmarks con dos clientes, un lector lento, cuentas reales y Redis
aislado. El reporte conserva RTT, login, muestras de CPU/RSS y ticks. La latencia
de arranque del servidor se registra aparte del login; no se deben mezclar ambas.
Los intervalos de publicación de tick incluyen pausas sin sesiones y la resolución
de sondeo de 10 ms: no son una medición pura de jitter del planificador. Los frames
se miden entre señales `process_frame`; incluyen renderizado y planificación,
no CPU aislada por frame. La cantidad de muestras y las condiciones acompañan
cada percentil. La cola p99 de RTT es mucho mayor que p95 y necesita investigación.

En la corrida final: login TCP/TLS p50 48,1 ms, RTT p50 0,49 ms, p95 0,93 ms y
p99 512,6 ms (168 muestras); máximo 586,8 ms. Los 68 ticks observados tuvieron
duración p50 17,0 ms, p95 20,2 ms y p99 21,0 ms. Cada Godot aportó 180 intervalos
entre frames: p50 5,15 ms, p95 5,96/6,14 ms y p99 6,56/7,51 ms. Se midió un
escenario pequeño, renderizado software y lector lento: estos resultados no se
extrapolan a miles de clientes ni justifican ocultar la cola de latencia.
La duración del tick incluye esperas a Redis y no representa CPU aislada.

Orden propuesto, con tareas atómicas derivadas:

1. [#338: terreno compacto](https://github.com/cavazquez/pyao-server/issues/338),
   verificando también si se duplican instancias inmutables de recursos.
2. [#342: lecturas por lotes de IA/broadcast](https://github.com/cavazquez/pyao-server/issues/342).
   [#344: investigar los picos p99](https://github.com/cavazquez/pyao-server/issues/344)
   antes de atribuirlos a una etapa concreta.
3. [#339: jugadores por ID/nombre](https://github.com/cavazquez/pyao-server/issues/339)
   y [#340: NPC por CharIndex](https://github.com/cavazquez/pyao-server/issues/340).
4. [#164 del cliente: índices de personajes](https://github.com/cavazquez/ArgentumOnlineGodot/issues/164).
5. [#341: buckets del suelo en memoria](https://github.com/cavazquez/pyao-server/issues/341).
6. [#343: segmentar el suelo durable](https://github.com/cavazquez/pyao-server/issues/343),
   sólo con migración explícita y la misma atomicidad y recuperación actuales.

Para un mundo de grilla 100×100 conviene comparar primero índices hash por ID,
buckets por mapa/celda y máscaras densas. No hay evidencia suficiente para
introducir quadtree, ECS completo ni cambiar Redis. Un índice espacial debe
acotar candidatos a área visible sin dejar obsoletos posiciones, colisiones o
permisos; los commits siguen revalidando contra Redis.

Toda optimización posterior debe conservar los bordes 1/100 y 0/99 del cliente,
reservas, visibilidad, IA, barcos/recolección, identidad única de stacks y oro,
devaluación del 1% diario, recibos de replay, TTL y recuperación tras caída. Los
índices derivados se reconstruyen al iniciar/reconectar. Cambiar el formato
durable del suelo es una migración versionada, no un cambio de caché. El bootstrap
de #332 debe seguir completando ausencias sin sobrescribir datos confirmados.
