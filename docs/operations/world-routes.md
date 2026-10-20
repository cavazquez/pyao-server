# Auditoría de mapas y salidas

El inventario de `docs/catalogs/world-routes.json` cubre los 290 mapas, las
59.918 coordenadas de salida y sus 852 pares dirigidos. De esos pares, 847
cambian de mapa y cinco son teletransportes dentro del mismo mapa (10 casillas).
Una coordenada define un destino; no se generan retornos artificiales.

## Reproducir sin Redis

Desde el repositorio y con los datos descomprimidos:

```sh
uv run --locked python -m tools.compression.decompress_map_data --target map_data
uv run --locked python -m src.validation.dataset
uv run --locked python -m tools.analysis.audit_world_routes --output artifacts/world-routes \
  --check docs/catalogs/world-routes.json
uv run --locked pytest tests/tools/test_world_routes.py
```

El directorio de salida contiene el informe, un registro por casilla en
`exits.jsonl` y la matriz de los 84.100 pares ordenados en `map-pair-matrix.csv`.
La matriz distingue enlaces directos y la cantidad mínima de saltos del grafo;
no implica que un personaje pueda caminar entre dos puntos dentro de un mapa.
Hay 76.741 pares alcanzables contando la diagonal (permanecer en el mismo mapa).
Los hashes identifican todos los archivos de entrada. El comando no escribe en
Redis ni modifica los mapas.

Los tests usan el cálculo real de `WalkMovementHandler` y `MapManager` para las
239.672 posiciones de aproximación cardinal dentro de límites a las 59.918 salidas. Esto prueba el
destino calculado; no sustituye transacciones Redis, colisiones, navegación,
paquetes TCP ni el renderizado del cliente.

## Hallazgos pendientes

No hay fuentes duplicadas, destinos ausentes ni coordenadas fuera de los
límites 1..100. Eso no certifica que todas las salidas sean jugables:

- [#348](https://github.com/cavazquez/pyao-server/issues/348): la salida se ejecuta
  antes de validar colisiones. Un control con el handler real aceptó llegadas
  sólidas y ocupadas por jugador, NPC o reserva, además de un cambio tierra/agua
  sin comprobar navegación. La transición de ese control usa un receptor en
  memoria; no se atribuye una prueba TCP a esa reproducción.
- [#349](https://github.com/cavazquez/pyao-server/issues/349): el desbloqueo de
  portales se envía durante login y falta al cambiar de mapa. Hay 94 fuentes
  sólidas que requieren la política de portal.
- [#350](https://github.com/cavazquez/pyao-server/issues/350): 131 llegadas apuntan
  a obstáculos sólidos, excluyendo el agua. Cada coordenada figura en el informe.
- [#351](https://github.com/cavazquez/pyao-server/issues/351): 420 salidas cambian
  entre agua y tierra. Se requiere distinguir puertos y teleports deliberados de
  errores, y probar el estado de navegación al llegar.
- [#352](https://github.com/cavazquez/pyao-server/issues/352): once mapas no tienen
  salida y diez carecen también de entrada. Desde el mapa 1 se alcanzan 275 mapas
  en el grafo. Los 15 restantes necesitan un rol explícito: mapa reservado,
  evento con acceso especial o parte del mundo jugable. Hay 33 pares sin regreso
  directo (966 casillas); no todos son errores.
- Hay 137 llegadas sobre otra salida y 137 fuentes sin una aproximación cardinal
  ordinaria en el análisis estático. Los bordes contiguos y portales especiales
  requieren revisión; estas cifras no se presentan como 137 errores confirmados.

La verificación del inventario en CI detecta cambios de datos y errores de
referencias. Conserva los hallazgos abiertos: **un inventario actualizado no
significa que se hayan corregido esos problemas**. Al modificar mapas hay que
revisar y regenerar el informe con el mismo comando y actualizar las pruebas.

## Contraste gráfico

El cliente tiene `tools/smoke-world-routes.py`. Carga y renderiza todos los mapas,
y para cada par dirigido renderiza ambos extremos en las coordenadas de una
salida representativa. Se ejecuta con OpenGL real y también sobre el ejecutable
exportado; comprueba máscaras completas, caché acotada y cierre sin errores.
El resultado indica `network_crossings: false`: no acredita 59.918 cruces TCP.

El primer contraste de 2.900.000 casillas coincidió en toda la máscara acuática.
Detectó 348 diferencias de bloqueo sólido entre escenas base y recursos del
servidor, antes de superponer objetos dinámicos: 308 carteles y una puerta
bloqueados sólo en el cliente, y 39 árboles bloqueados sólo en el servidor.
Se registran en [#353](https://github.com/cavazquez/pyao-server/issues/353).
Requieren sincronizar políticas; las puertas y talleres no se deben tratar como
paredes estáticas por una mera comparación de bits.

La clasificación del mapa del mundo también necesita revisión en el cliente:
28.201 salidas con el patrón horizontal X=9→91 o X=92→10 están marcadas como
`teleport` (364 pares). Eso altera la disposición geográfica y la selección de
vecinos para precarga, aunque la coordenada de destino siga presente. Véase
[#169 del cliente](https://github.com/cavazquez/ArgentumOnlineGodot/issues/169).

El recorrido de dos clientes y las reglas de llegada deben cerrarse junto con
los issues anteriores antes de afirmar que todos los portales funcionan.
