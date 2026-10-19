# Auditoría de NPC

`src.operations.npc_audit` compara los NPC configurados con los que cargan el
servicio real, Redis y MapManager. No modifica el catálogo para aprobar la
validación. Crea un Redis autenticado descartable, reinicia su contenedor con el
mismo AOF y retira exclusivamente sus recursos al terminar. No acepta una URL
Redis del operador.

Desde un checkout preparado con `uv sync --locked` y los mapas extraídos:

```bash
uv run --locked python -m src.operations.npc_audit \
  --output /tmp/npc-audit.json \
  --client ../ArgentumOnlineGodot
```

Requiere Docker y la imagen fijada por `redis/Dockerfile`. La opción
`--original-npcs /ruta/NPCs.dat` compara también las voces contra una copia del
DAT histórico; esa referencia es opcional y no sustituye las decisiones propias
del catálogo. La semilla por defecto es 307; `--seed` permite repetir otra.

El comando escribe el informe completo y devuelve **1 si encuentra
discrepancias**. `audit_executed: true` acredita la ejecución y
`world_checks_passed: false` indica que el mundo requiere correcciones. No usar
`|| true` ni rebajar una comprobación para presentar un mundo válido.

## Qué se comprueba

- Universo de mapas del índice, incluyendo mapas sin NPC configurados.
- Multiconjunto de spawns fijos: faltantes, sobrantes, IDs, posiciones,
  orientaciones, cuerpos/cabezas, hostilidad, posibilidad de recibir ataques y
  flags explícitos de comercio/banco.
- Tiles bloqueados, límites, ausencia de vecino caminable, duplicados y
  discrepancias entre Redis y el índice en memoria.
- Dos entradas concurrentes por zona aleatoria, cupos, posiciones, hostilidad,
  muerte y cooldown con reloj controlado. Las zonas superpuestas se atribuyen
  por el origen que conserva el generador, no sólo por rectángulo geométrico.
- Reinicio AOF, reconstrucción de habitantes fijos y preservación de una mascota
  de control, separada de los habitantes normales.
- Serializadores reales hacia dos receptores, muerte/retiro y un timer de
  reaparición de control. El timer de un segundo pertenece sólo a una instancia
  sintética: **no acredita la reaparición de las plantillas sin timer**.
- Configuración ausente de sonidos, silencio explícito, rango del byte y WAV
  disponibles. El lector histórico conserva huecos: `SND2=103` es el segundo
  evento, aunque Snd1 no aparezca.

Una ubicación sin vecino cardinal caminable necesita revisar las reglas de
interacción y los mostradores/decoración. No equivale por sí sola a que el NPC
sea inaccesible. Las excepciones deben justificarse individualmente.

Los roles `guard_hint` y `priest_hint` son indicios extraídos de los datos, no
pruebas de comportamiento. Los sacerdotes tienen un camino específico de
resurrección en `LeftClickHandler`; los guardias amistosos no entran en la IA
hostil y no tienen una conducta de defensa conectada. Ver issue #317.

## Muestra gráfica breve

El cliente incorpora un escenario separado que conserva el archivo de spawns
del servidor y verifica su SHA256. Usa cuentas efímeras, posiciones preparadas
al desconectar y salud de control; las entradas, reconexiones, clicks y cambio
de mapa pasan por Godot, TLS y el servidor reales.

```bash
cd ../ArgentumOnlineGodot
xvfb-run -a ../pyao-server/.venv/bin/python tools/integration-world.py \
  --server-project ../pyao-server --source \
  --godot /ruta/al/Godot_fijado_por_el_cliente \
  --output /tmp/npc-clients --seconds 10 --scenario npcs
```

Comprueba identidad/posición/apariencia en dos clientes, una criatura hostil
visible, apertura del comercio, reconexión y retiro de los NPC del mapa anterior.
La posición se contrasta dentro del rango al que el servidor transmite
movimientos; fuera de ese rango se conserva la última posición recibida. La
identidad y apariencia se comprueban para todos los NPC del mapa. Los archivos
`npc-difference-1.json` y `npc-difference-2.json` localizan diferencias sin
confundir ese contrato de visibilidad con una desincronización cercana.
Entrega capturas y recibos independientes. Este escenario no acredita la
campaña R10 prolongada ni los sonidos ausentes del catálogo.

Los controles positivos de ataque/daño/muerte comprueban los WAV específicos
47/103/62 en los serializadores del servidor y en Godot. La reproducción de un
WAV de control no demuestra que una serpiente normal esté enviando su voz.

Durante la muestra se detectó y corrigió en el cliente el issue #137: un
CHARACTER_MOVE con la misma posición hacía caminar al NPC al sur, y un salto
autoritativo de varios tiles se convertía en un único paso. La regresión Godot
falla con el handler anterior y pasa con la corrección, incluyendo un duplicado
durante la interpolación y una corrección que cancela el destino visual anterior.

## Resultado del 19 de octubre de 2026

Ver [evidencia y tareas de corrección](../audits/npc-307/README.md) y el
[informe por mapa](../audits/npc-307/maps.json). La auditoría reproduce fallos;
las correcciones de datos, cupos, roles y voces están separadas en issues
atómicos. No se generaron ni publicaron paquetes.
