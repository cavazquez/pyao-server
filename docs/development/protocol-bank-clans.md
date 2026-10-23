# Protocolo, combate, bóveda y ficha del clan

Alcance coordinado de servidor #596, #582, #588–#593 y cliente #234/#235.
Servidor y cliente conservan la versión de producto 1.0.0rc6. No se exige
compatibilidad con los transportes de clientes anteriores.

## Red

- COMMERCE_INIT tiene una sola API y produce exactamente `07`. Los objetos del
  mercader llegan por CHANGE_NPC_INVENTORY_SLOT. Un PONG concatenado conserva su
  frontera.
- SHOW_PARTY_FORM (99) ya no se emite durante login. GRUPO continúa funcionando
  mediante WORLD_ACTION/WORLD_STATE.
- BANK_OK (85) no se anuncia como soportado. Los saldos y slots confirmados son la
  respuesta bancaria efectiva.
- El intercambio usa exclusivamente TRADE_ACTION/TRADE_STATE con sesión, revisión,
  invitación, oferta y confirmación. Se retiraron handlers, DTOs y emisiones de las
  rutas binarias cliente 18/19/22/23/48 y servidor 9/10/84.
- Ambas copias del contrato incluyen EXPANSION=1024 y los plazos de negociación de
  30 segundos. El objetivo de login listo sigue siendo menor a cinco segundos;
  la ventana posterior de negociación no es una espera añadida al login.
- Python valida los frames enviados antes de encolarlos en las conexiones
  productivas. Ambos framers validan campos y rechazan números fuera de rango,
  floats no finitos, longitudes falsas y variantes desconocidas.
- Godot valida los argumentos antes de escribir, evitando truncar un 257 a un
  byte válido. Flush valida también el lote completo. Los errores no incluyen
  contraseñas, tokens ni el payload completo.
- La recepción acumula fragmentos válidos; drena tramos antes de aceptar más
  bytes. Un mensaje desconocido o irrecuperable cierra la conexión sin buscar
  otra frontera arbitraria. EOF incompleto no despacha un fragmento.
- El servidor rechaza acciones previas al login, login repetido y extensiones
  sin negociación. TCP/TLS y WSS usan esa misma ruta y autoridad de sesión.

Las fixtures compartidas contienen ejemplos de todos los IDs y subtipos
soportados, y metadatos para ejecutar los escritores reales. La suite verifica
los 61 escritores de Godot, todos los emisores Python de los 61 IDs del servidor,
los receptores del cliente, cada frontera de fragmentación y límites numéricos.
DICE_ROLL se recibe en la pantalla de creación, no en el dispatcher del juego.
Las operaciones económicas tienen además pruebas de negocio y recuperación.

## Combate y durabilidad

El golpe físico comprueba AOF antes de mutar mediante INFO, confirma recursos y
recibo juntos con WATCH/EXEC, y conserva una barrera WAITAOF después del commit.
Se eliminaron las dos barreras exteriores de SkillActionService para ese camino:
el propio commit ahora es dueño de la garantía y no publica daño antes de fsync.
Armas, entrenamiento, daño, recompensas y cadencia mantienen sus reglas.

El perfil Redis distribuido usa `appendfsync always`. Con `everysec`, dos
barreras podían acumular cerca de dos segundos de espera; una sola todavía
puede esperar un segundo. `always` elimina esa espera periódica y mantiene
fsync. Las instalaciones existentes no se reconfiguran automáticamente: deben
revisar su archivo de Redis y reiniciar el servicio administrado por su operador.
El servidor sigue admitiendo `everysec`, con su costo de latencia.

Referencias: [persistencia Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
y [semántica de WAITAOF](https://redis.io/docs/latest/commands/waitaof/).

La barrera escribe una marca posterior a EXEC y espera su fsync en la misma
conexión dedicada. No presupone que el pool devuelva la conexión del EXEC.
Un ACK perdido se resuelve con el mismo recibo, sin repetir daño, coste o XP.
Las pruebas comprueban que no salen efectos ni sonidos mientras falta la
confirmación, y que SIGKILL/reinicio de Redis conserva el golpe confirmado.

Las mediciones se reproducen con `tools.analysis.nuitka_network_study` usando
`--cpython-only --combat --combat-receipts`, 2/8 clientes, `--cadence 1.5` (ataque
del cliente) o `0.1` (carga agresiva), y `--slow-readers 0/1`. Se informan por
separado RTT de PING, ACK de ataques aplicados, visibilidad del daño en el
destinatario, rechazos por cadencia, CPU, RSS y p50/p95/p99. No son una medida de
capacidad máxima ni de latencia sobre Internet. El perfil instrumentado se
ejecuta separado y no se mezcla con los tiempos ordinarios.

### Resultados locales del 22 de octubre

La [evidencia JSON](../benchmarks/combat-durability-596.json) conserva hardware,
intérprete, hashes, muestras y límites de la comparación. El presupuesto local
para ACK aplicado y daño visible es p95 menor a 100 ms. Las 16 mediciones ordinarias
lo cumplieron: ACK p95 de 13,78 a 68,79 ms y daño visible p95 máximo de 65,86 ms.
El consumo medio del proceso durante cada muestra fue de 3,10–18,24 % de un núcleo.

Con el mismo control anterior de ocho jugadores, PING p95 pasó de 1.959/1.999 ms
con las barreras anteriores y `everysec`, a 921/921 ms tras quitar la barrera
redundante, y 1,77/1,80 ms con `always`. Esos RTT de PING no se presentan como
confirmación de golpe: el ACK y el daño se midieron después de forma correlacionada.

En el perfil separado, admisión por cadencia tuvo p95 de 0,010 ms; el preflight
AOF, 1,81 ms; las barreras posteriores, 3,42 ms; y WATCH/EXEC, 3,01 ms por pipeline.
El commit físico completo tuvo p95 de 47,67 ms y el camino con publicación,
54,12 ms. Son medidas inclusivas y no se suman. Las etapas generales incluyen
también sus ejecuciones de arranque/warmup; las físicas se identifican por separado.
`--stage-profile` permite repetir este diagnóstico sin el coste del perfilador CPU:
la ejecución con cProfile excedió el límite de inicialización en este intérprete.

Las primeras muestras de dos clientes preceden al arreglo del banquero invulnerable
con HP cero. Se verificaron iguales todos los hashes del combate, transporte,
configuración y datos; las muestras de ocho clientes ya usan el runtime final.
Son pruebas de loopback con carga de desarrollo concurrente; no certifican Internet
ni capacidad máxima. Las instalaciones Redis existentes conservan su política
hasta que el operador cambie su configuración.

## Bóveda

`bank.read` devuelve capacidad, banquero, acceso y stacks compactos de la propia
bóveda. `bank.move` sólo acepta `source`, `destination` y el banquero previamente
observado; la identidad del jugador viene de la sesión.

Se observan en WATCH la bóveda completa, posición, vida y NPC. Al decidir el
commit se vuelve a verificar apertura, sesión actual, banquero disponible, mismo mapa,
distancia máxima de tres casillas y revisión de la bóveda. Dos slots se cambian
en el mismo EXEC que el recibo. No se acepta del cliente el objeto ni la cantidad.
Una revisión vieja, origen vacío o acceso revocado no mueve objetos. Los
banqueros permanentes del catálogo con HP máximo cero e invulnerabilidad siguen
disponibles; un NPC atacable muerto o eliminado no concede acceso.

Godot reutiliza la grilla de inventario para arrastrar dentro de la bóveda.
No mueve el modelo de forma optimista: espera los slots confirmados. Mientras
espera, bloquea movimientos y transferencias; permite reintentar la misma
operación incierta. Cerrar el banco revoca la apertura de esa conexión.
El estado se conserva al cerrar, reconectar y reiniciar.

## Ficha pública del clan

La descripción/códice, noticias y sitio se consultan en `WORLD_STATE clan` y se
editan mediante `clan.profile`. La petición incluye el clan observado y la
versión de la ficha, sin conceder por ello permisos.

- Sólo el líder vigente puede guardar: se verifican membresía, rango 4 y
  `leader_id` bajo WATCH, además de la versión.
- Cada campo admite 200 caracteres Latin-1. El conjunto serializado tiene un
  límite de 1.200 bytes escapados. El sitio admite http/https sin credenciales ni
  espacios. La UI muestra texto, sin interpretar HTML.
- `clan:<id>:profile` guarda textos y revisión. El repositorio aplica ese estado
  sobre los metadatos anteriores al leer. Guardar un roster antiguo no pisa la
  ficha; no se requiere migrar ni borrar clanes existentes.
- La edición y su recibo son atómicos y se confirman por AOF antes del ACK.
  Cambiar líder o membresía durante la operación invalida el commit.
- Miembros normales consultan la ficha. El formulario se habilita según permisos
  del servidor. Un rechazo, desconexión o conflicto conserva el borrador.
  Una versión concurrente se muestra arriba y requiere revisión explícita antes
  de guardar el borrador sobre ella; no se sobrescribe silenciosamente.

## Validación reproducible

Las suites rápidas, Ruff y mypy se ejecutan en CI. Godot ejecuta
`wire_validation.tscn` y `storage_ui.tscn` desde `tools/smoke-godot.sh`. La etapa
Redis de CI ejecuta `PYAO_RUN_STORAGE_REDIS=1 pytest
tests/services/test_storage_actions.py` en un contenedor y volumen nuevos,
incluyendo caída abrupta y reintentos.

`tests/network/test_wire_transports.py` prueba el handler productivo por sockets
TCP, TLS y WSS, con certificados verificados, PING agrupados, fragmentación,
longitudes falsas, valores inválidos, acción anterior al login y EOF incompleto.
Los mensajes rechazados no llegan al ejecutor de acciones.

El escenario gráfico `storage-protocol` de `tools/integration-world.py` ejecuta
la regresión completa R10 y después arrastra slots vacíos/ocupados, edita la ficha
con líder y miembro, prueba conflicto de borrador y cambio de líder, rechaza al
exlíder y reinicia el servidor. Usa dos Godot, TLS, audio real y Redis propio.
Su ejecución corta es una regresión funcional, no una nueva aceptación prolongada
de 30 minutos ni una publicación de distribuciones.
