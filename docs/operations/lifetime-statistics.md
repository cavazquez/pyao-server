# Muertes, bajas y condenas

`player:<id>:user_stats` conserva `deaths` (muertes propias), `player_kills`
(bajas de otros jugadores), `citizen_kills`, `criminal_kills` y `npc_kills`.
Los campos ausentes representan cero; el arranque no los reinicia. Cada contador
se satura en el máximo de un entero sin signo de 32 bits.

El golpe que cambia HP positivo a cero incrementa los contadores dentro del mismo
commit Redis que el daño. Repetir el paquete, liquidar dos veces las pérdidas o
reconectar no genera otra baja. Una nueva vida después de resucitar sí puede
generar una nueva muerte. El veneno y el daño periódico conservan al emisor para
atribuir una baja aunque se haya desconectado. Una muerte ambiental aumenta sólo
las muertes propias. La liquidación de fantasmas heredados no inventa muertes
históricas. No se reconstruye retroactivamente información que nunca se registró.

La clasificación usa el campo autoritativo `criminal=1` de la víctima en el momento
del golpe letal; por defecto se considera ciudadano. No se infiere criminalidad
del modo seguro, una clase como Ladrón ni de pertenecer a un clan. Esta clasificación
no introduce sanciones automáticas por PvP ni modifica el consentimiento bilateral.

El cliente solicita `REQUEST_MINI_STATS` (16) al abrir estadísticas y recibe
`MINI_STATS` (62): cinco contadores u32 en el orden ciudadanos, criminales,
jugadores, NPCs, muertes propias; clase u8; días restantes de condena u32, todo
little endian. El paquete mide 26 bytes. El contrato y su fixture binaria se
actualizan conjuntamente en servidor y cliente; no se requiere compatibilidad con
clientes previos a producción. La solicitud usa la identidad de su conexión y
no acepta consultar ni modificar un ID ajeno.

## Plazo administrativo de cárcel

La interfaz muestra **Cárcel: días restantes**, redondeando hacia arriba la parte
del día pendiente. Un día equivale a 86.400 segundos reales, también desconectado.
`jail_until` es el vencimiento absoluto UTC; `jail_total_days` y `jail_reason`
conservan el plazo original y su motivo. Vencido el plazo, la pantalla muestra cero.
El servidor no agrega condenas automáticas ni nuevos mapas/restricciones de
movimiento como parte de este contador.

El operador con acceso al secreto administrativo de Redis puede registrar o
liberar el plazo mediante el mismo endpoint/configuración del servidor:

```sh
uv run --locked python -m src.operations.player_jail Nombre --days 2 --reason 'Motivo administrativo'
uv run --locked python -m src.operations.player_jail Nombre --days 0 --reason 'Liberación'
```

Se admiten 0..365 días, sólo para una cuenta/personaje existente. La operación
confirma el plazo y su recibo juntos y exige persistencia AOF. No existe un paquete
que permita a un cliente normal editar condenas.

Las regresiones de `test_spell_lifecycle.py` comprueban duplicados, vidas, daño
diferido, contadores mayores a int16 y avance del reloj sin esperar días. La
campaña `lifetime-stats` del cliente compara Redis/protocolo/UI, registra una
condena por la CLI administrativa y verifica reconexión, reinicio y vencimiento;
su reloj se controla desplazando el vencimiento sólo en la base descartable.
