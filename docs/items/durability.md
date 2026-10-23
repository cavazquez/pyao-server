# Objetos individuales y desgaste

Implementa #565–#570. El protocolo nuevo se usa junto con el cliente de esta
misma tanda: no se mantiene compatibilidad con los clientes anteriores.

## Balance inicial configurable

`data/item_durability.toml` clasifica explícitamente los 37 tipos del catálogo.
Los límites se congelan al crear cada ejemplar: cambiar el balance no repara
los objetos existentes.

- Armas: 10.000 usos y 30 días desde su creación UTC.
- Armaduras, escudos y cascos: 20.000 usos y 30 días.
- Herramientas 127, 138, 187, 198, 389 y 561–565: 5.000 usos y 30 días.
- Accesorios, joyas, instrumentos y botas: 30 días; sin contador de usos.
- Comida, pociones, materiales, pergaminos y municiones se consumen por unidades.
- Oro, embarcaciones y elementos fijos quedan exentos de este desgaste. El oro
  mantiene su devaluación propia del 1 % diario. Una embarcación no vence en el mar.
- Cero deshabilita cada límite. Con ambos límites activos, manda el menor
  porcentaje restante. La condición se expresa en 10.000 puntos base.
- Las estadísticas efectivas bajan linealmente del 100 % al mínimo configurado
  del 50 %. Se redondea hacia arriba y se conservan las estadísticas base.
  Al agotar el límite real, el factor es cero. El objeto permanece identificable
  en inventario/equipo/banco/suelo; no se destruye ni desaparece su capa gráfica.

Un golpe válido, incluso fallido, gasta un uso del arma. El escudo gasta al
bloquear y la protección al recibir el impacto físico. Una acción válida de
talar/minar/pescar gasta herramienta, incluso si falla la tirada. Fabricar un lote gasta un uso de herramienta por intento de unidad, incluso
si falla; un lote sin suficientes usos se rechaza entero. Fundir no exige una
herramienta portátil. Rechazos por
alcance, capacidad, estado, cadencia o recursos no cobran usos. Repetir la misma
operación recupera el recibo, sin repetir daño, entrenamiento o desgaste.

## Redis y conservación

El formato `i1:tipo:identidad[,identidad...]` referencia hashes
`item:instance:<identidad>` con creación/vencimiento UTC, límites originales,
usos, versión de política, versión de estado y ubicación. Inventarios personales
y bóvedas usan un slot por ejemplar. El stock comercial y los stacks del suelo
conservan vectores de identidades; los consumibles siguen apilándose.

Inventario, equipo, banco, intercambio, comercio NPC, robo, depósito del clan,
suelo y caída por muerte conservan la identidad. Una reventa conserva los usos
y fechas; sólo la reposición comercial crea ejemplares nuevos. Los retiros
intencionales (consumo/venta sin capacidad del mercader) dejan una marca
`retired` por siete días. Nunca se reutiliza una identidad retirada.

Las ubicaciones y el desgaste se confirman en el mismo EXEC que los recursos de
negocio y el recibo. WATCH cubre los contenedores y los metadatos necesarios.
Un lector Lua obtiene los metadatos y un reloj UTC creciente en una llamada.
En stock comercial sólo se leen los metadatos de unidades efectivamente movidas;
no se carga todo el mercado para cada compra. Un conflicto de lectura se
revalida con WATCH antes de denunciar corrupción.

No se recorre el catálogo de objetos cada segundo. Se calcula la condición al
usar/inspeccionar el ejemplar; la publicación periódica alcanza sólo los slots
de jugadores conectados, bóvedas abiertas y ofertas de intercambios activos.
Los avisos del equipo al 20 %, 5 % y rotura se emiten una vez por conexión.
Un reloj atrasado no rejuvenece objetos ya observados.

## Migración y recuperación

Iniciar una sola instancia del servidor, sin jugadores conectados, y conservar
un backup AOF antes de actualizar. La inicialización migra antes de aceptar
conexiones y activa `items:format_version=1` sólo al completar todos los
contenedores. Redis vacío recibe los mismos datos iniciales y el formato nuevo.

La antigüedad anterior era desconocida. Se adopta una única época UTC persistida
`items:migration:epoch`, con IDs deterministas y copia original por contenedor en
`items:migration:backup:<clave>`. Un reinicio reanuda sin duplicar ni rejuvenecer.
Los contenedores terminados incluyen su copia y sus cambios en el mismo EXEC.

Si una bolsa/bóveda con equipo apilado no tiene slots para separarlo, se detiene
el arranque con un error de capacidad, sin borrar las unidades ni activar el
formato. Liberar espacio con el servidor anterior sobre una restauración del
backup y repetir la actualización, o restaurar el backup completo para volver
al formato previo. No usar una versión anterior sobre una migración parcial.
Las copias de migración sirven para inspeccionar/reanudar; no son un rollback
seguro después de haber admitido transacciones nuevas.

## Verificación reproducible

- `uv run pytest tests/items`: límites, reloj, estadísticas base, capacidad,
  identidad, banco/suelo, intercambio de ejemplares del mismo tipo y recompra.
- `uv run python tools/item_instances_smoke.py --output artifacts/items`:
  Redis Docker descartable con AOF, concurrencia, ACK perdido, reinicio,
  1.000 y 100.000 objetos. Nunca usa el Redis del operador.
- Cliente: `tools/integration-world.py --scenario durable-items` ejercita
  equipo en dos observadores, banco/suelo, vencimiento equipado, combate y
  recolección. El modo `--client-audio PulseAudio` usa salida real.

El comercio NPC muestra la identidad y condición del próximo ejemplar del
stock (FIFO), indicando expresamente cuando hay más unidades con estado
individual. En el intercambio entre jugadores se muestran los ejemplares
ofrecidos y no se habilita la confirmación hasta recibir sus condiciones.
