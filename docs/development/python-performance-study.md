# Rendimiento de CPython — estudio #401

Recomendación para esta versión: conservar el runtime y las validaciones actuales.
Las pruebas no muestran una mejora general con `-O`, `-OO` o el JIT ensayado. Antes
de mantener una compilación propia de CPython, medir la carga esperada de jugadores
y corregir los recorridos Redis que crecen con toda la base. Nuitka se estudia por
separado en [#564](https://github.com/cavazquez/pyao-server/issues/564).

Actualización del 22 de octubre: los [índices #577/#578](world-index-performance.md)
ya eliminan esos recorridos globales de juego. El [estudio Nuitka #564](nuitka-performance-study.md)
conserva CPython tras comparar prototipos accelerated/standalone, red y dos clientes
gráficos. Las mediciones de esta página se conservan como baseline histórico de #401.

## Qué se midió

Host Linux x86_64, Ryzen 5 9600X, 12 CPU lógicas y 32 GB de RAM. Siete kernels reales:
bitmap de mapas, colisiones, nombre entre 1.024 jugadores, índice de 256 NPC,
apuñalamiento, serialización de movimiento y decodificación de 30 stacks del suelo.
Fixture determinista; 101 muestras por caso, lotes de 1.000 operaciones (50 para
suelo), calentamiento previo y cinco procesos independientes por modo. Se rota el
orden de ejecución y se publican CPU, pared, p50/p95/p99, dispersión y pico RSS.

Los [resultados de desarrollo](../benchmarks/cpython-dev-final-2026-10-22.json)
identifican versión, flags, estado del GIL, ejecutable y hashes de cada fuente. Se
ejecutaron sobre el árbol de trabajo de esta tanda, antes del commit; los hashes
permiten identificar el código medido. El HEAD indicado es la base del trabajo.
El [ensayo del intérprete instalado en Snap](../benchmarks/cpython-snap-2026-10-22.json)
usa exactamente los mismos kernels desde el checkout, con las dependencias del
Snap: **no es una prueba del confinamiento de Snap ni del servidor completo con JIT**.

Reproducir en el checkout con el entorno bloqueado:

```sh
python -m tools.analysis.interpreter_study --output /tmp/cpython-study.json
# Sólo cuando sys._jit.is_available() sea verdadero:
python -m tools.analysis.interpreter_study --include-jit --output /tmp/cpython-jit.json
```

No se purga el caché del sistema operativo: los procesos son nuevos y el sistema
de archivos está caliente. Los tiempos de importación y del proceso de la sonda
no equivalen al arranque en frío del servidor, que también carga mapas, configura
Redis y abre TLS. Algunas muestras se tomaron mientras corrían otras fixtures de
desarrollo; diferencias pequeñas requieren repetición en un host dedicado.

## Compilaciones comprobadas

- Desarrollo: CPython 3.14.0 free-threaded de uv, Clang 20.1.4; `PY_CFLAGS` incluye
  `-O3`. CONFIG_ARGS registra `--enable-optimizations`, `--with-lto`,
  `--enable-bolt`, `--with-tail-call-interp` y `--disable-gil`; los flags del build
  incluyen `-flto=thin` y `-fprofile-instr-use`. Ya incorpora PGO/LTO en ese build.
  JIT no disponible. El informe guarda el estado efectivo del GIL tras importar
  los kernels; no se asume que todas las extensiones se comporten igual.
- Snap instalado: CPython 3.14.4, GCC 15.2.0, GIL habilitado. Los flags expuestos
  incluyen `-O2`; CONFIG_ARGS incluye `--enable-experimental-jit=yes-off`. Se midió
  tanto su valor predeterminado desactivado como `PYTHON_JIT=1`, comprobando
  `is_available()` e `is_enabled()`. Eso no demuestra que todo el servidor o cada
  función haya sido compilada por el JIT.
- No se recompiló CPython con otro conjunto de flags. Comparar directamente esos
  dos ejecutables no aísla `-O3` frente a `-O2`: difieren versión, compilador, GIL,
  intérprete de llamadas y dependencias. No atribuir sus diferencias sólo a PGO.

`-O3` corresponde al compilador C/C++ que construye el intérprete. Las
[opciones de Python](https://docs.python.org/3.14/using/cmdline.html#cmdoption-O)
`-O`/`-OO` eliminan asserts y código de depuración; `-OO` elimina además docstrings.
Los [flags de construcción](https://docs.python.org/3.14/using/configure.html#performance-options)
son otra decisión. Activar una variable de entorno no reconstruye el intérprete.

## Resultados y decisión

- `-O`/`-OO` en desarrollo: la mediana de p50 de los cinco procesos varió entre
  −0,2 % y +1,5 % respecto del modo predeterminado, según el kernel. No hay una
  mejora general. No adoptarlos por rendimiento.
- En el intérprete de Snap, `-O`/`-OO` mejoraron algunos kernels pequeños y empeoraron
  otros. Por ejemplo, índice NPC varió de 168,8 ns a 152,2 ns con `-OO`, mientras
  colisiones pasó de 477,9 ns a 502,9 ns. No extrapolar un acceso a diccionario al
  rendimiento completo del juego ni convertir estas diferencias en capacidad de
  jugadores. Conservar los modos predeterminados.
- JIT del build Snap: suelo 57,33 a 56,94 µs por decodificación (−0,7 %), pero
  búsqueda de jugador 349,4 a 393,1 ns (+12,5 %) e índice NPC 168,8 a 195,2 ns
  (+15,6 %). El calentamiento es limitado y esto no descarta futuras versiones del
  JIT; no justifica habilitarlo globalmente en esta versión.
- PGO/LTO: el entorno de desarrollo ya los registra. Mantener una compilación
  propia para Snap o portables exige fuentes/hashes, toolchain, arquitecturas
  mínimas, tiempo/tamaño de construcción, símbolos, parches y CI por plataforma.
  Investigar sólo si un perfil de carga objetivo demuestra un límite de CPU que
  compense ese coste. No hay ganancia medida de una compilación propia en este estudio.
- Extensiones selectivas y Nuitka: pendientes de estudio, no incorporadas como
  cambios de runtime. Elegir un kernel por su coste acumulado antes de compilarlo;
  Redis, red y fsync siguen existiendo aunque se compile Python.

La revisión de `src` encontró asserts principalmente en diagnósticos de distribución,
herramientas y comprobaciones de invariantes ya validadas; los controles de dinero,
vida y permisos usan condiciones y errores explícitos. Aun así, `-OO` modifica la
introspección y descripciones CLI basadas en `__doc__`. No ejecutar pytest con asserts
eliminados como si fuese una verificación funcional equivalente. Las variantes
experimentales aquí medidas son sondas; no se publican como distribuciones aprobadas.

## Integración y prioridades

La [campaña local del servidor predeterminado](../benchmarks/cpython-gameplay-2026-10-22.json)
usó dos clientes Godot gráficos por TLS, Redis 8.10.2 aislado y un lector lento. En
la muestra final de 30 segundos: login p50 67,17 ms y p95 69,68 ms, RTT p50 0,750 ms,
p95 1,292 ms y p99 1,534 ms, sin errores. El proceso consumió unos 2,05 segundos de
CPU en 29,56 segundos observados y alcanzó unos 130 MB RSS. Eso describe esta fixture
pequeña y sus mapas; **no es una medición de capacidad máxima ni de carga masiva**.

La campaña funcional completa duró unos 19 minutos e incluyó 22 habilidades, magia
en ambos sentidos, PvP, navegación, recolección, economía, reconexión y reinicio.
Es validación del comportamiento del runtime recomendado, no una comparación
funcional de JIT contra CPython. La aceptación prolongada del binario y las pruebas
del Snap instalado deben ejecutarse además durante la publicación.

El perfil acotado separó etapas de Redis, barreras AOF, ejecutor de contraseñas,
envío, login y espera del loop. Tras un reinicio se registraron 14.230 SCAN y 155
KEYS durante esa vida del proceso. Son contadores, no prueba de causalidad; las
duraciones de etapas anidadas no se suman como CPU. Los picos de inicialización
tampoco representan la latencia habitual de comandos. La revisión identificó
descubrimiento de fogatas con SCAN global y consultas de mascotas mediante KEYS
y lecturas por cada NPC: perfilar y acotar esas rutas antes de cambiar el compilador.
Las tareas derivadas son [#577, índice de fogatas por mapa](https://github.com/cavazquez/pyao-server/issues/577)
y [#578, consultas de mascotas por propietario](https://github.com/cavazquez/pyao-server/issues/578).

Sólo se midió Linux x86_64. Windows, macOS y ARM64 requieren sus propios perfiles;
que un paquete compile o pase un smoke funcional no demuestra una mejora cuantitativa
de rendimiento en esas plataformas. La recomendación no introduce instrucciones
específicas de la CPU del desarrollador ni cambia los requisitos mínimos publicados.
