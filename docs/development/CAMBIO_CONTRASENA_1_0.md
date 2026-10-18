# Cambio autenticado y confirmación (#127 / cliente #55)

La capacidad optativa 8 habilita CHANGE_PASSWORD (107), con versión u8=1 y
cadenas str16 Latin-1: ID de operación, clave actual y nueva. Las claves siguen
la misma política literal de 6–32 bytes que login/alta. Una petición vacía obtiene
un ID emitido por el servidor; con ID y claves vacías consulta su resultado.

Antes de Argon2 se exige cuenta autenticada y presupuesto compartido de
conexión/IP/cuenta. Hashing y verificación usan el executor acotado existente.
El commit comprueba propietario y hash autenticado mediante WATCH/MULTI y cambia
sólo password_hash junto con un recibo temporal. No se restaura un hash viejo ante
un resultado incierto. Repetir el ID con las mismas claves devuelve el resultado;
un contenido distinto se rechaza. Login vuelve a comprobar el hash después de
verificar para no aceptar una credencial sustituida durante Argon2.

El recibo conserva hashes Argon2 anterior/nuevo durante 600 segundos para validar
un retry incluso si el hash ya cambió. Nunca conserva claves en claro en el recibo ni las
incluye en su metadata, logs o respuestas. La consulta autenticada devuelve sólo resultado
y mensaje. Un recibo ausente se informa como indeterminado, sin afirmar fracaso.
La persistencia exige AOF/fsync antes de confirmar.

PASSWORD_CHANGE_RESULT (253) contiene versión, ID original, próximo ID, estado
(0 preparado, 1 confirmado, 2 rechazado, 3 indeterminado) y mensaje. Se envía sólo
con la capacidad negociada. Las consultas tienen cadencia máxima de una por segundo.

Godot valida política y confirmación; guardar envía una vez, borra inmediatamente
los tres campos y espera el ack. Un timeout consulta el ID original sin volver a
enviar claves. Sólo estado 1 anuncia éxito; rechazo, desconexión y resultado incierto
tienen mensajes distintos. Cerrar/reabrir limpia campos y restablece el modo oculto.
No se escriben claves en preferencias, historial ni logs. Usar TLS en distribución;
el ensayo TCP de CI usa exclusivamente loopback y credenciales sintéticas.

La CI verifica TCP real, consulta tras ack ignorado, validez de la nueva clave e
invalidez de la anterior, y recuperación de hash/recibo tras SIGKILL de un Redis
AOF descartable. Las pruebas rápidas cubren pérdida de ACK antes/después de EXEC,
concurrencia, propiedad de cuenta, presupuesto, políticas y ausencia de secretos.
