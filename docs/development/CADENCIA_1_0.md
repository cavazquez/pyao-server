# Cadencia autoritativa (#101, #102, #149)

`game.cadence` configura segundos mínimos: `walk_seconds=0.2`,
`attack_seconds=0.5`, `cast_seconds=1.0`. Pydantic exige 0.01–10 segundos.
El cliente no comunica ni puede reducir estos límites.

El contenedor comparte una instancia `ActionCadence` entre todos los handlers.
La reserva se decide sin await, antes de validar/leer estado, consumir stamina,
mover, dañar, cobrar maná o conceder recompensas. Rechazar por frecuencia no
invoca ninguna de esas operaciones. Cada jugador y cada acción tiene presupuesto
independiente, y una operación en curso conserva su exclusión aunque tarde más
que el intervalo. `finally` libera la exclusión pero conserva el próximo plazo.
Los intentos inválidos también ocupan su intervalo para limitar spam de validación.

El reloj es monotónico y se inyecta en las pruebas. Muerte, desconexión y
reconexión conservan el plazo ya reservado; reconectar no permite acelerar
ataques. Al vencer, las entradas inactivas se podan periódicamente. El cierre
no puede dejar una reserva en curso porque cada handler libera en `finally`.
Los tests ejercitan ráfagas de WALK comprobando posición y cobro de stamina,
fronteras, trabajos en curso e independencia de jugadores/acciones sin sleeps.
