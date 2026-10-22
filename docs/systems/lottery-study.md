# Lotería física de oro — estudio #403

Recomendación: viable con un NPC amistoso de ciudad, apuestas enteras, pozo en
Redis y liquidación durable. No habilitarla en esta versión. `/APOSTAR` continúa
siendo el casino clásico, con reglas separadas; no comparte pozo ni probabilidades.

## Lugar y acceso

Propuesta de contenido: NPC nuevo «Lotero de Ullathorpe», plantilla 950 (libre en
el catálogo revisado), cuerpo 501/cabeza 1 ya utilizados por el comerciante, sin
hostilidad, ataque ni botín, nombre visible. Puesto en mapa 1, casilla (53,52),
orientación sur, junto al área comercial. Esa coordenada no figura en bloqueados,
objetos, salidas ni spawns del dataset revisado; tiene acceso desde (52,52) y
(54,52). Antes de activarla se revalidará contra overlays Redis y el cliente real,
porque un GM puede editar el mapa. No se agrega aún al catálogo de producción.
El alta será por identificador de spawn estable, `HSETNX`/transacción; inicializar
Redis o reiniciar no lo duplica. La tarea de contenido adjuntará capturas y verificará
puertas/talleres y ambos clientes, conservando banquero, herrero y salidas.

Cada apuesta exige selección de la instancia exacta, mismo mapa, distancia Chebyshev
≤3, jugador vivo y NPC activo, revalidados dentro del commit que descuenta oro.
Un botón global o un paquete con otro NPC no permite apostar. Alejarse o desconectar
después no retira una apuesta confirmada. Consultar el resultado público puede ser
remoto; participar requiere estar físicamente en el puesto.

## Comisión y probabilidades

Oro entero, apuesta mínima bruta 100. Elegir comisión acumulada por personaje y
ronda: `fee_total = ceil(gross_total / 100)`; cobrar en cada aporte la diferencia
contra la comisión ya cobrada. Así dividir apuestas no reduce la comisión. El 1%
se redondea hacia arriba a moneda entera, anunciado antes de confirmar; apuestas
múltiplos de 100 pagan exactamente 1%. No usar flotantes ni cobrar 1 a cada aporte
arbitrariamente: cambia probabilidades si un jugador divide su participación.

`net_total = gross_total - fee_total`. Si A aporta 100 y B 300: comisión 1+3,
pozo 99+297=396, probabilidades 25%/75%. A posee intervalo [0,99), B [99,396).
Sortear uniformemente `secrets.randbelow(pool)`; elegir el primer acumulado mayor
que el número. Número de boletos = monedas netas, no número de cuentas ni apuestas.
Nunca crear un objeto/entrada Redis por moneda.

Primera apuesta abre una ronda de 300 segundos configurables. Admisión con reloj
del servidor: `now < closes_at`. Una apuesta en el límite de cierre se rechaza sin
débito; reintento del mismo recibo devuelve el resultado original aunque ya cerró.
Sin apuestas: no sorteo y no se borra el ganador anterior. Un único participante
recibe el pozo neto al cerrar, habiendo pagado comisión; mostrar esta regla. Pueden
permitirse varias rondas sin operadores conectados. No extender el plazo al apostar.
Cancelar es una acción excepcional y auditada: reembolsar íntegramente bruto y
revertir comisión aún reservada, una vez por aporte; no anunciar un ganador.

## Contabilidad y recuperación

Claves propuestas: `lottery:current`, `lottery:round:<id>` (estado, plazo, pozo,
comisión, versión, compromiso RNG), hash por participantes con bruto/neto/acumulado,
recibos por apuesta y `lottery:last_winner`. Máximo inicial configurable 4096
participantes/ronda y límite por saldo/protocolo. Descontar bruto, aumentar aporte,
pozo y comisión y guardar recibo en un único EXEC bajo WATCH. Invariante por ronda:
`sum(bruto) = sum(comisión) + pozo` y saldo nunca negativo. Barrera WAITAOF antes de
confirmar al cliente, siguiendo el patrón existente de PyAO.

La comisión queda reservada hasta liquidar, no emitida a una cuenta particular.
Al cerrar, congelar lista ordenada por user_id y su hash, elegir y persistir una
única intención de pago. Crédito al ganador offline, estado `paid`, recibo y
`last_winner` se confirman juntos, con registro de distribución de comisión. Si
excede el máximo del bolsillo, acreditar al banco; si ambos topes impiden recibir,
mantener un saldo reclamable de premio con identidad de ronda. No truncar el premio
ni declarar `paid` antes de que todo el pozo tenga propietario. El reintento no
vuelve a sortear ni paga dos veces. Si se pierde respuesta de EXEC, leer el recibo;
reiniciar reanuda `open/closing/pending_payment`, sin crear otra ronda solapada.

La devaluación del 1% diario sigue afectando cualquier oro. Recomendación: si una
ronda cruza el cambio UTC, liquidar el mismo cargo sobre su pozo reservado antes
del pago y registrar el oro desaparecido. Reducir aportes netos mediante reparto
entero proporcional con restos mayores y desempate por user_id; conservar la suma
exacta. La interfaz anticipa el importe efectivo, que puede disminuir al cambio
de día. Devaluación, premio y comprobantes comparten la misma fecha/recibo: no
permitir evadirla dejando una ronda pendiente ni cobrar dos veces al ganador.

Las [transacciones Redis](https://redis.io/docs/latest/develop/using-commands/transactions/)
permiten confirmar el conjunto bajo WATCH; la recuperación debe basarse en recibos
durables, no en suponer que una conexión cortada significa que EXEC no ocurrió.

## Aleatoriedad auditable

`secrets.randbelow` evita sesgo del módulo respecto del pozo. Para auditoría posterior,
antes de admitir apuestas publicar SHA-256 de una semilla aleatoria de 256 bits.
Al cerrar fijar orden y hash de aportes, revelar semilla y derivar bloques HMAC con
contador; usar rejection sampling, no `% pool` directo. La especificación debe
incluir encoding y vectores, de forma que cualquiera reproduzca el intervalo ganador.
El compromiso evita cambiar la semilla publicada a posteriori, pero no prueba que un
operador que controla el servidor no eligió varias semillas previamente o canceló
selectivamente. Aleatoriedad externa verificable sería un estudio separado; no
prometer imparcialidad criptográfica absoluta ni exponer la semilla antes del cierre.

## Cliente, ganador y complejidad

Diálogo junto al NPC: bruto, comisión incremental, neto, pozo, participación neta y
porcentaje, plazo UTC y cuenta regresiva orientativa; botón de confirmación inequívoca
y respuesta con recibo. Saldo, tiempo válido y ganador los decide el servidor.

Guardar ID estable, nombre público al pagar, premio completo, ronda y fecha del
ganador. Mostrar «Todavía no hubo ganador» inicialmente. Conservar el nombre hasta
el pago durable del próximo ganador; una ronda vacía/cancelada/abierta o un fallo
no lo borra. Renombrar una cuenta no cambia a quién se pagó: mostrar nombre histórico
y, opcionalmente, el actual resuelto por ID. Cuenta eliminada sigue como histórico,
sin reutilizar ID ni pagar a otra cuenta. Publicar el resultado en el chat y puesto.

Para P participantes/A aportes: O(P+A) almacenamiento con recibos, O(1) hash promedio
por apuesta más conflictos WATCH, O(P log P) ordenación única al cerrar, O(log P)
búsqueda binaria del número sobre prefijos. Una sola selección O(P) también es válida
con el tope inicial. No añadir árbol Fenwick antes de medir necesidad. Estimación de
payload 100–250 bytes/participante más recibos, no memoria Redis medida. Guardar
auditoría de pagos 90 días inicialmente, resúmenes compactos permanentes y recibos
por el plazo de reintento; documentar volumen/AOF y backup antes del lanzamiento.

## Prototipo medido

En Redis 8.10.2 sobre Linux x86_64, el hash sintético de participantes ocupa 88 bytes
para un jugador, 4.722 para 128 y 271.582 para 4.096. No incluye recibos, ronda,
AOF ni auditoría: son costes adicionales, no memoria cero. Para 4.096 participantes,
ordenar y construir prefijos tuvo p50 0,894 ms y p95 1,000 ms en 101 muestras; buscar
un intervalo promedió 167 ns en 10.000 búsquedas calientes. Un host compartido de
desarrollo no acredita capacidad del servidor ni latencias con WATCH/EXEC y fsync.

El prototipo verifica los números 0/98/99/395, conservación 400=4+396 y comisión
acumulada independiente del fraccionamiento. La simulación reproducible usa semilla
403 y 200.000 sorteos; publica frecuencia e incertidumbre para el participante con
probabilidad 25%. Su PRNG sirve sólo para comparar el modelo: no sustituye `secrets`
en producción ni prueba imparcialidad criptográfica o pagos durables.

[Resultados crudos](../benchmarks/lottery-prototype-2026-10-22.json). Reproducir con
`python -m tools.analysis.lottery_study --output /tmp/lottery-study.json`; crea su
propio Redis y lo retira al terminar. No incorpora el NPC ni habilita apuestas.

## Tareas derivadas y pruebas

1. Validar NPC, ID y casilla física; spawn idempotente y política de nombre.
2. Esquema de rondas, límites, comisión acumulada y política de devaluación.
3. Apuesta atómica con control físico y recibos; concurrencia con banco/comercio.
4. Worker de cierre, RNG reproducible y vectores públicos de intervalos/compromiso.
5. Pago offline, límites, saldo reclamable, cancelación y recuperación tras fallos.
6. Diálogo Godot y último ganador persistente, anunciado tras pago durable.
7. Simulaciones y campaña de dos clientes con reloj/RNG controlados.

Orden 1/2→3→4→5→6→7. Estimación 1–2 semanas más revisión económica. Casos: números
0,98,99,395; apuestas 100+300; fraccionamiento; T−1/T/T+1; cero/uno/múltiples jugadores;
NPC falso/remoto; límite entero; dos cierres simultáneos; muerte, desconexión y
renombre; reinicio antes/después de cada EXEC/WAITAOF; día UTC; pago incierto y ronda
vacía conservando ganador. En simulaciones reportar desviación e intervalo estadístico
con semilla y tamaño identificados; no exigir frecuencias exactas ni usar simulación
como prueba única del RNG. Ninguna tarea activa esta mecánica sin una tanda posterior.

## Issues derivados

Propuestas para una tanda posterior, según el orden y las dependencias anteriores:

- [cavazquez/pyao-server#571](https://github.com/cavazquez/pyao-server/issues/571): Lotería: agregar un NPC amistoso con acceso físico validado.
- [cavazquez/pyao-server#572](https://github.com/cavazquez/pyao-server/issues/572): Lotería: definir rondas Redis, límites y comisión acumulada del 1%.
- [cavazquez/pyao-server#573](https://github.com/cavazquez/pyao-server/issues/573): Lotería: confirmar apuestas atómicas ante el NPC con recibos idempotentes.
- [cavazquez/pyao-server#574](https://github.com/cavazquez/pyao-server/issues/574): Lotería: cerrar rondas una vez y sortear por intervalos de aportes netos.
- [cavazquez/pyao-server#575](https://github.com/cavazquez/pyao-server/issues/575): Lotería: pagar el pozo completo al ganador offline y recuperar pagos inciertos.
- [cavazquez/ArgentumOnlineGodot#217](https://github.com/cavazquez/ArgentumOnlineGodot/issues/217): Lotería: diálogo físico con confirmación y último ganador persistente.
- [cavazquez/pyao-server#576](https://github.com/cavazquez/pyao-server/issues/576): Lotería: validar economía, probabilidades y recuperación con dos clientes.
