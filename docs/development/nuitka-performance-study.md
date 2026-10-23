# Nuitka — estudio #564

**Decisión: conservar CPython y descartar la adopción de esta configuración de
Nuitka para la entrega actual.** Los prototipos funcionan, pero consumieron más
CPU y memoria y tuvieron peores latencias en la carga ensayada. No se reemplaza
el runtime publicado ni se publica un Snap experimental.

## Comparación controlada

Se midió el mismo código de juego, commit
`b9593f9b40309cb6593fec7b46f9462cd939952e`, después de los índices #577/#578.
Los manifests conservan los hashes del árbol que aún estaba sin commit al
construir; el HEAD registrado originalmente es `fd3d819...`. La equivalencia con
el commit de runtime se verifica por archivos, sin atribuirle código anterior.

Linux x86_64, Ubuntu 26.04.1, AMD Ryzen 5 9600X (12 CPU lógicas), 32 GB RAM.
Los tres modos utilizan **el mismo CPython 3.14.8 convencional**, de uv / Python
Build Standalone, Clang 23.1.3, GIL habilitado y JIT disponible pero desactivado.
Ese intérprete registra `-O3`, PGO/LTO/BOLT y tail-call interpreter en su build.
No se compara con el Python free-threaded 3.14.0 de desarrollo ni se habilita JIT.

Nuitka **4.3.1**, sdist SHA256
`b9c87a694acc424cfffa06abf149fddbdfa85f6daac998df67411b5f4269df0f`, GCC 15,
cuatro jobs, C11/`-O3`, `--lto=no`, `--static-libpython=no`, sin `-march=native`.
No se eliminaron asserts, docstrings ni controles de negocio. `accelerated`
compila `src` y las herramientas de compresión; conserva dependencias del mismo
entorno Python. `standalone` incorpora además intérprete, dependencias, protocolos,
catálogos, configuración y archive de mapas. Los paquetes de runtime se instalan
desde `uv.lock`; las herramientas del estudio tienen versiones y hashes fijados.

El [manual oficial](https://nuitka.net/user-documentation/user-manual.html) distingue
la compilación del empaquetado standalone y la inclusión explícita de datos.
El [changelog oficial](https://nuitka.net/changelog/Changelog.html) describe soporte
de Python 3.14; aquí se comprobó nuestra combinación concreta, no todas las variantes
de Python o de las plataformas anunciadas.

## Resultados del servidor completo

Nueve procesos independientes: tres por modo, orden rotado. Cada proceso utiliza
Redis 8.10.2/AOF propio, la misma configuración y mapas preextraídos, nueve cuentas
sintéticas idénticas, ocho clientes TCP de carga y un lector lento. Se observaron
1.602 NPC en los nueve ensayos. Calentamiento de cinco segundos y veinte segundos
medidos; las sesiones del calentamiento se liberan antes de volver a entrar.
Las muestras de red, servidor y Redis están en
[network.json](../benchmarks/nuitka-2026-10-22/network.json).

Medianas entre los tres ensayos; los JSON conservan todas las muestras y dispersión:

- **CPython:** arranque 10,72 s; login p50 38,71 ms; RTT p50/p95/p99
  0,703 / 1,994 / 2,914 ms; CPU 2,24 s en un intervalo observado de 19,53 s;
  pico RSS observado 111,47 MiB.
- **Nuitka accelerated:** arranque 14,16 s; login p50 41,23 ms; RTT p50/p95/p99
  0,805 / 2,514 / 3,830 ms; CPU 2,66 s; RSS 143,40 MiB.
- **Nuitka standalone:** arranque 14,02 s; login p50 43,97 ms; RTT p50/p95/p99
  0,850 / 3,612 / 8,712 ms; CPU 3,17 s; RSS 178,68 MiB.

El arranque corresponde al servidor completo con mapas/NPC, no al login sobre un
servidor abierto. Son procesos nuevos sobre archivos calientes: **no** se purgó
la caché del SO. Los tres modos reciben las mismas rutas de recursos, por lo que
la comparación de arranque excluye la extracción adicional del archive de mapas.

Accelerated consumió aproximadamente 19 % más CPU y 29 % más RSS; standalone,
42 % y 60 % más. El RTT p95 de CPython varió 1,574–2,043 ms, accelerated
2,321–2,693 ms y standalone 3,233–3,625 ms. El p99 de standalone varió mucho más:
4,386–11,909 ms; no convertir tres repeticiones cortas en significancia estadística.
El login de standalone también tuvo un ensayo p50 de 72 ms, registrado íntegro.

Se completaron unas 79 iteraciones de ping/movimiento por segundo en los tres
modos, bajo una demanda fijada por cadencia. **No es capacidad máxima.** Los
ticks, visibilidad y NPC se ejecutaron realmente, pero no se simularon miles de
jugadores ni sesiones de producción prolongadas. El RNG y los UUID del mundo
varían normalmente; catálogos, cantidad de NPC y datos lógicos del ensayo coinciden.
La CPU Redis acumulada y los comandos incluyen arranque y calentamiento; no se
presentan como costes exclusivos de la ventana estable.

La [carga física adicional](../benchmarks/nuitka-2026-10-22/combat.json) usa cuatro
parejas quietas, seguros apagados y ataques reales, con dos procesos independientes
por variante, tres segundos de calentamiento y diez medidos. En los seis ensayos
se redujo la vida persistida durante la ventana medida; no se acreditan rechazos
como golpes efectivos. El RNG cambia daño y aciertos, por lo que no se compara CPU
por punto de vida perdido. El RTT de PING mientras se ataca tuvo medianas del p95 de 1,94–1,99 s
en los tres modos. Es una espera importante que compilar no eliminó.

El [perfil de combate separado](../benchmarks/nuitka-2026-10-22/combat-profile.json)
observó `TaskAttack` hasta 2.224,8 ms y WAITAOF hasta 984,5 ms. El código solicita
una barrera antes y otra después del dispatch. Aislar y acotar esa espera sin
relajar durabilidad queda en el issue atómico [#596](https://github.com/cavazquez/pyao-server/issues/596).
No confundir RTT de control con confirmación exacta del golpe, ni atribuir todo el
tiempo al compilador o a AOF sin esa investigación. Esta carga agresiva tampoco
representa por sí sola la cadencia normal del cliente.

## Kernels y atribución

Se reutilizaron los siete kernels reales de #401: 101 muestras, lotes de 1.000
operaciones (50 para suelo), calentamiento previo y cinco procesos por variante,
rotando el orden. Se comprobó igualdad de versión/GIL/JIT/flags y de checksums
entre los 15 procesos. El resultado de
[kernels.json](../benchmarks/nuitka-2026-10-22/kernels.json) contiene p50/p95/p99,
CPU, operaciones/s, RSS y variación entre procesos. Verifica además que los módulos
del candidato son compilados y los de la referencia son Python.

Mediana de p50, CPython → accelerated:

- Bitmap: 161 → 142 ns por consulta; mejora local que no se trasladó al conjunto.
- Colisiones: 311 → 383 ns; búsqueda por nombre: 233 → 337 ns.
- Índice NPC: 101 → 162 ns; cálculo de apuñalamiento: 106 → 113 ns.
- Serialización: 356 → 583 ns; decodificar 30 stacks: 41,50 → 54,07 µs.

Standalone dio resultados similares en esos kernels. Las importaciones, arranque
del proceso y RSS se registran por separado de su ejecución. Compilar una consulta
a diccionario no elimina el tiempo de Redis, TLS o fsync; tampoco implica que cada
operación Python se vuelva más rápida. La comparación no aísla el efecto de un flag
C concreto: CPython ya usa optimizaciones de su proveedor y Nuitka tiene otro backend.

El diagnóstico adicional registra stacks del hilo principal con cProfile y reloj
`time.process_time_ns`, por separado de latencias de Redis, barreras AOF,
contraseñas y event loop.
Se ejecuta fuera de los nueve ensayos ordinarios: su instrumentación no se usa para
comparar las latencias anteriores. No sumar tiempos de etapas anidadas ni tratar
esperas de red/disco como CPU. Ese reloj cuenta CPU de todo el proceso: Argon2
corre en workers cuyos stacks no aparecen, y su CPU concurrente puede afectar
los deltas atribuidos. Este diagnóstico no sustituye la comparación de CPU total
tomada de `/proc`.

En ese perfil, el trabajo propio del arranque se concentró en validar NDJSON,
coordenadas y referencias y en convertir bloqueos/objetos de mapas. El perfil
incluye ese arranque y no acredita que esos métodos dominen el juego estable.
Los eventos de espera están filtrados por umbral y limitados a 4.096; los descartes
se registran en [profile.json](../benchmarks/nuitka-2026-10-22/profile.json).

## Compatibilidad funcional y datos

Las pruebas del prototipo usan dos procesos Godot 4.7.2 gráficos, PulseAudio,
TLS y Redis/AOF aislado. La evidencia en
[functional.json](../benchmarks/nuitka-2026-10-22/functional.json) distingue cada
ejecutable por SHA256 y conserva los resultados originales del runner:

- CPython, accelerated y standalone: fogata exacta en ambos clientes, descanso y
  energía, reconexión, dos reinicios, doma/órdenes/propiedad, liberación y
  vencimiento natural a los 120 segundos. Se validaron también región y textura
  de las ocho observaciones visibles de cada campaña.
- El smoke R10 comprueba alta/login, inventario, banco, comercio, chat, party,
  clan, combate, hechizos, meditación, recolección, mascotas, muerte y reconexión.
- Se observa cierre SIGTERM, drenaje de dos sesiones TLS, inventario y orden de
  hechizos conservados. Son proyectos Godot instrumentados; `native_export=false`.
  No se acredita una nueva aceptación de distribución de 30 minutos.

El wrapper sustituye exclusivamente el comando del servidor por el candidato
identificado por hash, también al reiniciar. El `source_checkout=true` del runner
original describe su fixture de desarrollo, no el modo del servidor compilado;
`study-server-commands.json` y el manifest del estudio registran el ejecutable real.

La primera prueba standalone encontró que faltaban los JSON de
`src/network/protocol`. Se corrigió la construcción para incluirlos explícitamente.
La validación posterior, desde otra carpeta y sin `PYTHONPATH`, encontró cero
errores, 290 mapas, 1.078 ítems, 336 plantillas NPC y 50 hechizos. Conserva cuatro
avisos conocidos del dataset (objetos deliberadamente invisibles y validación
audiovisual del cliente omitida en ese diagnóstico del servidor).

## Construcción, distribución y diagnóstico

Las primeras construcciones de accelerated/standalone tardaron 133/299 s. La
segunda de cada modo, con ccache caliente, tardó 22,75/58,55 s. Standalone ya
aprovechaba caché generada por accelerated: no son medidas de un CI completamente
vacío. El pico del hijo individual informado por `getrusage` fue 336/849 MiB en
las primeras construcciones; no equivale a memoria agregada de cuatro compiladores.

El ELF accelerated ocupa 31.902.360 bytes (30,42 MiB), **sin** incluir Python y
dependencias del entorno. El directorio standalone final ocupa 118.469.160 bytes
(112,98 MiB), con sus bibliotecas y datos. No comparar directamente esos tamaños
como si ambos contuvieran lo mismo. No se midió `onefile`: el servidor ya se entrega
como Snap/archivo instalado y no aparece una ventaja que compense agregar extracción
y otro ciclo de vida de proceso al arranque.

Los manifests de construcción y flags están en
[builds.json](../benchmarks/nuitka-2026-10-22/builds.json). Los logs y reports XML
completos quedan en el paquete local de evidencia, identificado por
[evidence.json](../benchmarks/nuitka-2026-10-22/evidence.json).
El prototipo mantiene trazas con archivo/línea, como mostró el fallo de recursos.
Diagnosticar funciones compiladas requiere conservar fuente exacta, reports y hashes;
el perfil Python por líneas no equivale a observar internamente todo el código C.

Sólo se midió **Linux AMD64**. Para CI/Snap AMD64 hay toolchain y prototipo viable,
pero se debe construir/verificar contra el base del Snap; un build en Ubuntu 26.04
no acredita confinamiento ni compatibilidad con core24. ARM64 necesitaría su propio
runner/toolchain y medición, preservando arquitectura mínima. Windows y macOS
requieren builds nativos, bibliotecas, firma y pruebas propias; no se ensayaron con
Nuitka. Tampoco se midió free-threaded, PGO/LTO de Nuitka ni un perfil de capacidad
máxima. No justificar su adopción en esas plataformas con resultados de AMD64.

## Reproducir

Usar el checkout que contiene este informe y sus herramientas, con el mismo
runtime señalado, uv y un entorno convencional nuevo:

```sh
uv venv --python 3.14.8 /tmp/pyao-nuitka-env
uv export --locked --no-dev --no-emit-project --output-file /tmp/pyao-runtime.txt
uv pip install --python /tmp/pyao-nuitka-env/bin/python --require-hashes -r /tmp/pyao-runtime.txt
uv pip install --python /tmp/pyao-nuitka-env/bin/python --no-deps -e .
uv pip install --python /tmp/pyao-nuitka-env/bin/python --require-hashes -r tools/analysis/nuitka-requirements.txt

/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_study build --mode accelerated --output /tmp/pyao-accelerated
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_study build --mode standalone --output /tmp/pyao-standalone
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_study compare \
  --build /tmp/pyao-accelerated/build.json --build /tmp/pyao-standalone/build.json \
  --output /tmp/pyao-kernels.json
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_network_study \
  --build /tmp/pyao-accelerated/build.json --build /tmp/pyao-standalone/build.json \
  --output /tmp/pyao-network
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_network_study \
  --profile --repeats 1 --seconds 10 --warmup 3 --output /tmp/pyao-cpu-profile
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.nuitka_network_study \
  --combat --repeats 2 --seconds 10 --warmup 3 \
  --build /tmp/pyao-accelerated/build.json --build /tmp/pyao-standalone/build.json \
  --output /tmp/pyao-combat
/tmp/pyao-nuitka-env/bin/python -m tools.analysis.scoped_world_graphical \
  --client ../ArgentumOnlineGodot --godot /ruta/Godot \
  --build /tmp/pyao-standalone/build.json --output /tmp/pyao-graphical
```

Los directorios de salida deben ser nuevos. Se necesitan GCC/patchelf, Docker y
acceso al display para Godot; las sondas nunca aceptan un Redis de producción.
Para R10, repetir el último comando con `--scenario r10`. Se conserva CPython:
no hay beneficio medido que justifique abrir una integración de Nuitka a los
paquetes. Si se reevalúa otra configuración, repetir carga y plataformas antes
de crear el issue separado de adopción solicitado por #564.
