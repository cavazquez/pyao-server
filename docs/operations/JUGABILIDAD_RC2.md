# Operación y validación de la RC2

Servidor y cliente se entregan con la misma versión 1.0.0rc2. Las partidas,
inventarios y progresión continúan en Redis. Ningún evento visual modifica los
resultados del combate ni sustituye sus mensajes legacy.

## Pesca

`data/fishing.toml` define bandas por distancia de Manhattan sobre agua real. La
primera casilla junto a tierra tiene distancia cero. El valor esperado del
catálogo por pez es 8 en costa, 10,75 en la banda desde 4 casillas y 13,70 desde
12 casillas. La cantidad por captura y la curva de éxito de Pesca se conservan.
El pez dorado sólo aparece mar adentro. Los precios efectivos de cada comerciante
siguen sus reglas propias.

La clasificación reconoce islas y salidas acuáticas entre bordes opuestos de los
mapas. Los bordes exteriores desconocidos no se inventan como costa. Los
componentes que no conectan con mapas declarados marinos conservan pescado simple;
un teleport interior no convierte un lago en alta mar. `marine_maps` permite
seleccionar explícitamente mapas marinos; vacío usa `world/map_metadata.toml`.
La clasificación se cachea por masa de agua y se renueva al reiniciar con otro
dataset. Captura y progreso se confirman juntos, conservando validaciones de
posición, caña, capacidad y reintentos. El cliente no envía una especie ni banda.

## Diagnóstico y registros

```sh
uv run pyao-server --diagnose --config-file config/server.toml
uv run pyao-server --diagnose --ssl --ssl-cert certs/server.crt --ssl-key certs/server.key
uv run pyao-server --log-format json
```

`--diagnose` devuelve JSON y código 0/1. Lee configuración, valida recursos,
comprueba Redis con PING y verifica certificados existentes. No inicia el mundo,
no escribe seeds, no migra datos y no genera certificados. `--help` y `--version`
siguen disponibles sin configuración válida ni Redis.

El formato JSON conserva timestamp, nivel, componente e identidades de conexión y
operación, con contexto aislado por task. Contraseñas, tokens y argumentos de
excepciones no se serializan. `PYAO_LOG_FORMAT=json` equivale al argumento CLI.
La consola legible sigue disponible.

## Rendimiento reproducible

Usar exclusivamente una instancia descartable y cuentas de prueba únicas. Crear
un archivo JSON privado de perfiles `username`/`password`, sin incorporarlo al
repositorio o a los artefactos públicos. El benchmark sólo apunta a loopback por
defecto; un laboratorio remoto exige `--allow-remote`.

```sh
PYAO_METRICS_FILE=/ruta/del/ensayo/ticks.json uv run pyao-server --port 17666
uv run python tools/benchmark.py --accounts /ruta/privada/perfiles.json \
  --port 17666 --connections 2 --slow-readers 1 --seconds 60 \
  --pid PID_SERVIDOR --metrics /ruta/del/ensayo/ticks.json \
  --output /ruta/del/ensayo/benchmark.json
```

El informe registra entorno, carga, CPU/RSS, login, RTT p50/p95/p99, paquetes,
fallos y métricas del tick real. No presupone una capacidad universal. Los
presupuestos `--max-p95-ms` y `--max-login-ms` son explícitos y se contrastan con
las mediciones del hardware ensayado. Las muestras y buffers están acotados por
conexiones, cadencia y duración. Los lectores lentos reciben una ráfaga acotada y
los lectores normales deben seguir respondiendo. La campaña gráfica completa
incluye la recuperación de ambos clientes tras ese ensayo.

## Entrega

Construir el wheel y los Snaps desde commits limpios, validar el par final y
fusionar ambos repositorios antes de promover a latest/edge. El publicador
`ArgentumOnlineGodot/tools/release-pair.py` verifica versión común, procedencia,
CI y evidencia, carga todos los paquetes sin canal y después coordina su promoción
con recuperación del par anterior. La Store no tiene una transacción entre nombres.
