# Estado de interfaz negociado

El cliente solicita `WORLD_STATE = 512` con la negociación existente. El paquete
248 usa versión 1, longitud uint16 y JSON. Las solicitudes conservan Latin-1 y
admiten hasta 1020 bytes de JSON; las respuestas usan escapes ASCII para Unicode
y admiten hasta 3800 bytes. Ningún mensaje legacy cambia de longitud. El bit 64
reservado de clima sigue sin anunciarse: el clima usa el canal de estado 512.

Cada conexión tiene un `epoch` nuevo y una `sequence` creciente. Los tópicos son
impuestos, grupo, clan, mascotas, clima, comandos y metadatos del intercambio.
El servidor publica únicamente cambios en tópicos suscritos; impuestos y clima
se mantienen activos. Los demás se suscriben al abrir su ventana y se liberan al
cerrarla. La cadencia de publicación es un segundo y cada conexión dispone de
una ráfaga de ocho solicitudes, recargada a cuatro por segundo.

La consulta toma al actor de su sesión autenticada. Los parámetros nunca eligen
otra cuenta, grupo o clan. El roster del clan se pagina de ocho en ocho; el
catálogo de objetos del intercambio, de tres en tres y ligado a la sesión y
revisión de la oferta. Los nombres y propiedades provienen del catálogo del
servidor. Un artículo sin datos mantiene disponible cancelar y bloquea confirmar.

Las mutaciones sociales envían la revisión mostrada, el epoch y un identificador
con fecha y nonce. El servidor conserva una intención durable antes de ejecutar
y un resultado durable después. Un reintento devuelve ese resultado; un fallo
intermedio conserva la operación como incierta y exige consultar el estado.
La interfaz no agrega miembros, cambia rangos ni resta recursos antes del ACK.
Las rutas nativas y nuevas de grupo/clan comparten la misma exclusión de proceso.
Cambiar de líder invalida invitaciones anteriores; los miembros conservan el
nombre canónico de su conexión, además de su ID persistido.

La revisión de permisos cambia ante cambios de rol, miembros y conexión. La vida
de los miembros se actualiza sin invalidar continuamente los menús de gestión.
Los saldos usan además `money_revision`, incrementada en la misma transacción
Redis que el movimiento: un resumen fiscal viejo no puede reemplazar oro nuevo.
Los clientes legacy reciben los paquetes nativos de bolsillo y banco y un aviso
por recibo fiscal en la conexión.

## Clima, mascotas y moderación

La clasificación de exteriores procede de `data/world/map_metadata.toml`.
Ciudades, wilderness y agua admiten lluvia explícita. Interiores, dungeons y mapas
desconocidos permanecen sin lluvia. La política actual no genera clima aleatorio;
un GM puede establecer un estado explícito, persistido en Redis y repetible sin
invertir un toggle. Un cambio de mapa consulta el estado vigente.

Las órdenes de mascotas identifican la instancia UUID. Seguir, esperar y liberar
comprueban propietario, vida y vigencia bajo WATCH. Liberar marca primero la
instancia como inactiva, luego retira su representación e índices; repetir una
operación no afecta otro NPC que reutilice el índice visual.

`/BAN nombre días motivo` admite cero días para permanente; `/UNBAN nombre motivo`
revoca el bloqueo. Ambas operaciones requieren un GM indexado vigente. El estado,
el espejo del perfil, la revocación de la reserva y la auditoría se confirman
juntos. La instancia cierra las conexiones de la cuenta; las reservas también
verifican el bloqueo al adquirir y renovar. El login informa el bloqueo después
de comprobar la contraseña. La auditoría guarda actor, motivo y vencimiento y no
incluye credenciales. Los vencimientos usan el reloj del servidor y no necesitan
un proceso que borre el historial.

## Verificación sin distribuir paquetes

`tests/services/test_world_state.py` cubre autorización, revisiones, privacidad,
órdenes de mascotas, clima, límites binarios y catálogo de intercambio.
`src.operations.economy_smoke` verifica impuestos y bloqueos tras SIGKILL con AOF;
`src.operations.merchant_stock_smoke` verifica stock y reposición en Redis propio.
El cliente dispone de smokes de interfaz y `tools/integration-world.py --source`
para dos Godot reales sin construir wheel, ejecutables ni Snap.
