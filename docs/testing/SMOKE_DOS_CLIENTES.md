# Smoke de dos clientes y Redis descartable

Ejecutar desde el checkout: `uv run --locked python -m src.operations.two_client_smoke`.
Requiere Docker local y la imagen Redis fijada en `redis/Dockerfile`; crea nombres,
volumen, secreto ACL privado y puerto loopback aleatorios. No usa la configuración
Redis del operador, no conecta al puerto 6379 existente y no ejecuta FLUSHALL ni
limpieza global de Docker. Al terminar elimina sólo los recursos que creó.

La fixture levanta un mapa vacío con repositorios, autenticación Argon2, leases,
spawn, broadcast y movimiento reales. No usa mocks para esos caminos. No inicia
NPCs ni tick periódico: es una prueba mínima de red/sesión, no la aceptación del
juego ni la prueba Godot de 30 minutos de la versión 1.0.

Verifica dos cuentas con clase y oro diferentes, índices y estadísticas propias,
slot 30, WALK byte a byte y WALK+PING concatenados una sola vez. A queda legacy y
B negocia el catálogo extendido. Desconectar A libera su reserva y conserva la de
B, que puede seguir moviéndose y recibir su segundo PONG.

El resultado es JSON sin credenciales ni payloads. Cada espera tiene un plazo de
8 segundos y el escenario completo 45. Ante un fallo se conservan sus mensajes de
diagnóstico por stderr; CI guarda JSON/logs como artefactos aun cuando falle. El
receptor observa EOF y errores para no quedar esperando silenciosamente.

La lógica y el contrato comprobados corresponden a servidor `5b3c35e` y cliente
`bdc4d58d`: ambas revisiones consumen las mismas fixtures, incluyendo acentos,
30 slots, habilidades legacy de 19 bytes y catálogo negociado de 70 bytes.
Godot verifica esos readers y los cambios de pantalla en su propia CI. Este smoke
TCP complementa esa evidencia y no reemplaza una sesión conjunta de juego Godot.
