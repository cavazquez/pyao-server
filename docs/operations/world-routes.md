# Auditoría de mapas y salidas

El inventario vigente de `docs/catalogs/world-routes.json` cubre 290 mapas,
59.855 coordenadas de salida y 852 pares dirigidos: 847 entre mapas y cinco
teletransportes dentro del mismo mapa. Después de corregir las llegadas sólidas
se retiraron 63 coordenadas inválidas del inventario anterior de 59.918 salidas.
Las 239.420 aproximaciones cardinales dentro de límites tienen un destino
explícito; no se generan retornos artificiales.

## Inventario estático

```sh
uv run --locked python -m tools.compression.decompress_map_data --target map_data
uv run --locked python -m src.validation.dataset
uv run --locked python -m tools.analysis.audit_world_routes --output artifacts/world-routes \
  --check docs/catalogs/world-routes.json --roles data/world/map_roles.json \
  --water-routes data/world/water_routes.json
uv run --locked pytest tests/tools/test_world_routes.py
```

La salida incluye `audit.json`, `exits.jsonl` y `map-pair-matrix.csv`: los 84.100
pares ordenados, enlaces directos y saltos mínimos del grafo. Hay 76.741 pares
alcanzables contando la diagonal. El grafo no acredita caminos transitables
entre dos portales dentro de un mapa. Los hashes identifican todos los archivos.

## Cruces por TCP con Redis real

```sh
uv run --locked python -m tools.analysis.audit_world_routes_network \
  --output artifacts/world-routes-tcp
```

El comprobador inicia una instancia Redis autenticada y descartable y un listener
TCP en loopback con `ArgentumServer.handle_client`, framing, autenticación,
`TaskFactory`, handlers, repositorios, transacciones e índices concretos. No
reemplaza el handler ni el commit con mocks. Carga el dataset vigente y envía
WALK seguido de PING en la misma conexión; PONG confirma que terminó el comando.

Para cada salida y aproximación cardinal verifica posición persistida, paquetes
CHANGE_MAP/POS_UPDATE, pertenencia al mapa, índice espacial y navegación al
llegar. Usa un personaje vivo con embarcación válida y Navegación suficiente.
En cada uno de los 852 pares dirigidos agrega trece controles: jugador, NPC
amistoso, NPC hostil, reserva, puerta cerrada, ausencia de barco, habilidad
insuficiente, personaje muerto, mapa ausente y coordenadas X/Y en 0 y 101. Los
casos adversos deben conservar el origen cuando corresponde y no pisar ocupantes.
El alcance completo esperado es 250.496 comandos WALK (239.420 + 852 × 13).

Las posiciones de aproximación y los estados iniciales se preparan como fixture;
no se presenta esa preparación como movimiento del jugador ni como prueba de
accesibilidad desde otro punto del mapa. El reloj inyectable de cadencia avanza
un segundo por caso independiente; esto evita esperar horas y no mide velocidad
real de juego. No ejecuta IA de NPCs ni renderizado. La aceptación gráfica y TLS
de dos clientes usa las pruebas nativas del cliente por separado.

`--limit N` produce una muestra marcada `partial: true`, que no acredita el
issue completo. `--shard I --shards N` reparte salidas y pares sin duplicarlos.
CI usa cuatro particiones y un job que verifica su unión:

```sh
uv run --locked python -m tools.analysis.audit_world_routes_network \
  --combine artifacts/routes/world-routes-tcp-*/result.json \
  --output artifacts/world-routes-complete
```

La unión exige las cuatro particiones aprobadas del mismo commit limpio, script,
hashes y dataset; rechaza faltantes, duplicados, muestras parciales y controles
incompletos. Cada resultado conserva conteos, procedencia y hash de resultados.
Los recibos de CI son la evidencia de ejecución; documentar el comando no implica
que una futura versión del dataset haya pasado sin volver a ejecutarlo.

## Correcciones y políticas vigentes

Los hallazgos de #348–#353 y #169 del cliente ya tienen implementación y regresiones:

- Las llegadas validan terreno, puertas, límites y ocupación antes del commit.
  La posición y navegación se confirman juntas y la reserva se libera al terminar.
- Los portales transmiten sus desbloqueos al entrar por login o por transición.
  Las llegadas sólidas se corrigieron en los datos, conservando rutas deliberadas.
- Los 420 cambios agua/tierra están clasificados en `data/world/water_routes.json`.
  Llegar al agua requiere estar vivo, barco real y habilidad suficiente; llegar a
  tierra actualiza navegación y apariencia del mismo estado confirmado.
- `data/world/map_roles.json` explicita el rol y acceso de los 290 mapas; los mapas
  reservados o de acceso especial no se presentan como regiones de acceso ordinario.
- Cliente y servidor sincronizan obstáculos estáticos y distinguen talleres y
  puertas dinámicas. La topología trata los bordes horizontales como fronteras.

Las salidas sobre otra salida, rutas sin regreso directo y aproximaciones
estáticas bloqueadas siguen siendo propiedades visibles del inventario; esas
cifras por sí solas no representan errores. Una ruta de un solo sentido no
crea automáticamente una ruta de vuelta.

## Contraste gráfico

El cliente conserva `tools/smoke-world-routes.py`: carga y renderiza los 290 mapas
y ambos extremos de cada par dirigido. Compara las máscaras completas de
2.900.000 casillas, comprueba caché acotada y cierre sin errores, también sobre
el ejecutable exportado. Su resultado `network_crossings: false` describe sólo
ese comprobador; la evidencia TCP anterior se registra aparte.
