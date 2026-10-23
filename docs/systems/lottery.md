# Lotería de Ullathorpe

La lotería de oro virtual se ofrece mediante el Lotero de Ullathorpe, plantilla
950, mapa 1 (53,52), cuerpo 501/cabeza 1. Su nombre es visible, no ataca, no puede
ser atacado y no tiene botín. Se inicializa con la identidad estable
`lottery-ullathorpe`: un reinicio no crea otro puesto. Si un overlay bloquea su
casilla, no se fuerza la ocupación. El administrador debe liberar el acceso.

Seleccionarlo abre el diálogo del cliente. Apostar requiere estar vivo, en el mismo
mapa y a distancia Chebyshev <=3. Selección exacta, índice, instancia, posición,
vida, ronda y plazo se revalidan bajo WATCH dentro del cobro. Una selección vieja,
un NPC falsificado o consultar la ventana desde lejos no habilita una apuesta.
Una apuesta confirmada sigue vigente al alejarse, morir o desconectarse.
`/APOSTAR` sigue siendo el casino clásico y no usa este pozo.

## Aportes y sorteo

Mínimo bruto 100. Por personaje y ronda la comisión total es `ceil(bruto/100)`;
cada aporte cobra sólo la diferencia contra la comisión anterior. Así fraccionar
no evade el 1%. Para importes no múltiplos de 100 se anuncia el redondeo hacia
arriba antes de confirmar. El neto acumulado determina la participación.

A aporta 100 y B aporta 300: 1+3 de comisión, 99+297 netos, pozo 396. A tiene el
intervalo [0,99) y probabilidad 25%; B [99,396), 75%. El ganador recibe todo el pozo
neto vigente. Con un solo participante recibe su neto al cerrar. Límite bruto de
ronda 2.147.483.647 y 4.096 participantes. No hay una entrada por moneda.

La primera apuesta fija el cierre en `now+300` segundos. Se configura con
`[game.lottery] round_seconds`, entre 10 y 86400. Apostar no extiende el plazo.
Se admite sólo `now < closes_at`; T y T+1 rechazan sin cobrar la apuesta. Una ronda
sin aportes no inicia el reloj, no sortea ni reemplaza al último ganador.

## Persistencia y economía

`lottery:current` referencia la ronda; `lottery:round:<id>` conserva estado,
compromiso, reserva, plazo e intención de pago. `:snapshot` guarda la auditoría
congelada aparte, para mantener las lecturas de la vista y del pago en O(1).
`:participants` es un hash con una
entrada JSON por ID estable. Cobro bruto, comisión, neto y comprobante
`operation:resources:<id>` se confirman en un EXEC y se exige WAITAOF antes del ACK.
El reintento con el mismo ID devuelve el resultado original incluso después del
cierre, sin depender de la posición nueva. La ventana de reintento es 300s y la
retención de recibos 600s; pasada esa ventana consultar estado, nunca emitir otra
apuesta para resolver un resultado incierto. Cambiar el contenido del mismo ID se
rechaza. Banco/comercio y apuestas comparten las claves monetarias observadas.

Al cruzar cada corte UTC se devalúa el pozo reservado según la política diaria
del juego (1% por defecto). Se acumulan fracciones enteras en
`lottery:tax_remainder`, incluso entre rondas; no se impone una moneda mínima.
Se redistribuyen los netos vigentes mediante restos mayores y desempate por ID;
su suma sigue siendo el pozo exacto. Puede cambiar una probabilidad por redondeo de
una moneda. La comisión reservada pertenece al juego, no participa del sorteo.
Un premio pendiente también se devalúa, sin volver a elegir al ganador. Se guardan
el pozo al sortear, el premio al pagar y el oro desaparecido. Si el pozo desaparece
íntegramente, termina sin anunciar un premio cero ni borrar al ganador anterior.

Cerrar congela una lista ordenada y un hash, boleto y ganador únicos. Dos workers
usan WATCH/EXEC y no resortean. El pago offline acredita primero lo que cabe en el
bolsillo y después el banco. Si el conjunto no admite TODO el premio, queda
`pending`, no se paga parcialmente ni se pierde la diferencia. El worker reintenta
al liberar capacidad. Verifica la identidad por el índice de cuentas y sus datos,
sin pagar a un nombre reutilizado. La ronda siguiente espera a resolver el premio.

Pago, estado `paid`, resumen permanente y `lottery:last_winner` comparten EXEC y
fsync. La vista pública exige durabilidad antes de publicar un ganador nuevo.
El nombre histórico al pagar, identidad, importe, ronda y fecha permanecen tras
renombrar o eliminar una cuenta; una ronda vacía, cancelada o pendiente no los borra.
Ambos clientes muestran ese ganador y lo anuncian en chat. Una respuesta perdida
de EXEC/WAITAOF se recupera leyendo estado/recibo, sin repetir el débito ni pago.

La auditoría detallada de una ronda liquidada expira a los 90 días; los resúmenes
compactos y el último ganador son permanentes. Las reservas pendientes no caducan.
La copia de seguridad debe incluir todas estas claves y AOF.

## Cancelación excepcional

Sólo el operador, mediante sus credenciales Redis, puede solicitarla antes del
sorteo. No existe un paquete de jugador para cancelar:

```sh
pyao.pyao-server --cancel-lottery ID_DE_RONDA --lottery-reason "Motivo operativo"
```

Se registra intención y motivo. El worker devuelve una reserva por turno, también
offline, y reanuda tras reiniciar. Devuelve todo el bruto (incluida comisión) menos
la devaluación que ya desapareció del neto; no crea oro para reponer devaluación.
Cada devolución se marca en el mismo commit del crédito. Si no cabe o la identidad
requiere revisión permanece reservada. Una cancelación no anuncia otro ganador.

## Auditoría del azar y sus límites

Antes de admitir apuestas se persiste/publica SHA-256 de una semilla de 32 bytes
generada por `secrets`. No se revela durante la ronda. Al cerrar se serializan
`[[user_id,{fee,gross,net}],...]` por ID numérico, JSON ASCII compacto con claves
ordenadas. `snapshot_hash=SHA256(snapshot_ascii)`.

Cada bloque es HMAC-SHA256 con clave `bytes.fromhex(seed)` y mensaje:
`b'pyao-lottery-v1\0' + round_id_ascii + b'\0' + snapshot_hash_ascii + b'\0' + counter_uint64_big_endian`.
Se interpreta como entero big endian y se rechaza si es mayor o igual a
`2**256 - (2**256 % pool)`; sólo un bloque aceptado se reduce módulo pool. El
contador comienza en cero. Se elige el primer acumulado mayor que el boleto.
El resumen publica semilla, compromiso, hash, boleto y pozo original; el snapshot
detallado se conserva en Redis para auditoría por el operador durante su retención.

Esto permite reproducir el resultado y detectar un cambio posterior de semilla
respecto del compromiso observado. Un operador privilegiado controla Redis y puede
cancelar/selectivamente ocultar rondas o estudiar semillas antes de publicarlas.
El protocolo no prueba imparcialidad absoluta ni publica datos de participantes a
otros jugadores. Una fuente externa verificable necesitaría otro diseño.

## Coste y validación

Apuesta: O(1) de datos leídos/escritos respecto de participantes, más reintentos
WATCH acotados. El recurso parcial del hash usa HMGET/HSET del personaje, no
HGETALL. Cierre/devaluación: O(P log P), memoria O(P), P<=4096. Búsqueda del boleto
por prefijos O(log P). Recibos O(A) acotados por TTL; no objetos por moneda.

Las pruebas cubren 0/98/99/395, comisión acumulada, T-1/T/T+1, dos workers, débito
contra banco, pérdida de respuesta EXEC, fallo de fsync, SIGKILL de Redis/AOF,
renombre, desconexión, topes, devoluciones y corte UTC. La campaña de dos Godot
usa los controles reales, Redis aislado y cierre productivo de 300s con ambos
desconectados; los asserts consultan Redis independientemente de la UI.

```sh
PYAO_RUN_LOTTERY_REDIS=1 uv run pytest tests/services/test_lottery.py
```

La simulación estadística usa semillas reproducibles sólo como fixture. No
sustituye las pruebas del rechazo del RNG ni las transacciones Redis reales.
Con 200.000 sorteos y semilla de fixture 576, el primer participante obtuvo
24,871%; intervalo normal del 95% [24,682%, 25,060%], compatible con el 25% esperado.
[Resultados y vector reproducible](../benchmarks/lottery-implemented-2026-10-22.json).
