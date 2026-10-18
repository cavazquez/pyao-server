# Presupuesto y confirmación de habilidades (#150 / cliente #61)

El bit optativo 4 habilita MODIFY_SKILLS (38): versión u8=1, ID de operación
str16 y 22 pares `[id:u8, delta:i16]` en el orden del catálogo. Sólo se aceptan
deltas positivos de habilidades implementadas, hasta nivel 100, y el coste total
no puede superar los puntos de la cuenta autenticada. Campos históricos y XP
permanecen intactos. WATCH/MULTI confirma todos los niveles y el saldo junto con
un recibo; repetir el ID no vuelve a gastar y cambiar su contenido se rechaza.
Se exige AOF/fsync antes de confirmar éxito.

El servidor emite SKILL_ALLOCATION_STATE (254), con versión, ID correlacionado,
próximo ID, estado (0 consulta, 1 aplicado, 2 rechazo), mensaje y el catálogo con
presupuesto. Los IDs se emiten en el servidor: Godot no depende del reloj del PC
ni inventa un ID nuevo para repetir un gasto. El catálogo y el saldo salen de
una sola lectura del hash, con el mismo formato de 22 triples de #126.
REQUEST_SKILLS conserva 71 para clientes clásicos y 251 para quienes negocian
sólo el catálogo; la capacidad 4 recibe el estado 254.

La ventana mantiene un borrador. Guardar envía una sola vez y deshabilita edición
hasta el ack; no cambia Global.skillPoints ni afirma éxito anticipado. Rechazar
restaura el estado confirmado. Si vence la espera, se vuelve a consultar y se
mantiene la edición deshabilitada hasta recibir estado actual. Cerrar conserva
la operación pendiente y los resultados siguen actualizando el estado recibido.

Las cuentas nuevas reciben una única vez `game.character.initial_skill_points`
(10 en distribución), junto al seed inicial del perfil. No se conceden puntos a
cuentas antiguas al reconectar, ni se habilitan habilidades pendientes. El progreso
XP posterior suma los cruces de nivel sobre el nivel guardado, conservando lo
asignado con puntos.

La CI ejecuta un ensayo Redis AOF aislado: dos pedidos compiten por ocho puntos,
sólo uno gasta cinco y sus replays, incluso después de SIGKILL/reinicio, conservan
saldo y niveles. Los tests rápidos inyectan pérdida de ACK antes/después de EXEC.
