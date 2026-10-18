# Mutaciones de oro

Los créditos y débitos relativos del jugador usan WATCH/MULTI/EXEC sobre el hash de estadísticas y un recibo de operación. No se admite saldo negativo ni mayor que 999999999. Una cantidad inválida no inicia una transacción; un débito sin fondos o crédito que exceda el máximo deja el saldo intacto. Pickup usa un crédito limitado que devuelve la cantidad aceptada para conservar el remanente.

Una operación puede recibir `operation_id` generado con `src.utils.gold_atomic.operation_id()`. Conservarlo permite consultar el mismo resultado tras una respuesta incierta de EXEC, sin volver a aplicar la mutación. Reutilizarlo con otra petición se rechaza. Los recibos duran diez minutos y una operación sin recibo sólo puede iniciarse durante cinco minutos desde su creación; un reintento más antiguo se rechaza y exige consultar el saldo. El identificador utiliza reloj y nonce del servidor y no se deriva de credenciales. No permite reintentos ilimitados ni deduplicar dos acciones nuevas que el cliente envía por separado.

Subir de nivel conserva el saldo persistido; no vuelve a guardar la copia que leyó para calcular los atributos. Compras, drops y efectos consumen las primitivas relativas. Las transferencias que afectan otros recursos requieren sus propios commits conjuntos (#92, #93, #131, #132, #133, #134 y #153).

Validación: tests de concurrencia, límites, ACK perdido después de EXEC y rechazo de replay vencido; `uv run python -m src.operations.gold_atomic_smoke` reproduce créditos y débitos concurrentes contra un Redis nuevo autenticado, y limpia su contenedor y volumen.

## Banco

Depósitos y retiros usan el mismo EXEC para el saldo del jugador, el saldo del banco y el recibo. WATCH valida ambos valores actuales; fondos insuficientes y exceso del límite de destino conservan los dos saldos. El banco respeta int32 firmado (2147483647), y el jugador el límite de 999999999.

El identificador se crea al construir el comando y se conserva si se reejecuta ese mismo comando tras un resultado incierto. Dos acciones nuevas del protocolo legado son peticiones independientes. El cliente recibe los saldos sólo desde un resultado confirmado. La prueba nativa incluye depósitos simultáneos, retiro repetido y conservación del total. Las pruebas de fallas antes y después de EXEC verifican que no se utiliza compensación separada.

## Intercambio entre jugadores

La liquidación congela ambas ofertas y confirma los dos inventarios, dos saldos y un journal en el mismo EXEC. Comprueba identidad y cantidad de cada slot, capacidad total, límites de oro y equipo; exige desequipar los objetos ofrecidos. Primero retira ambos conjuntos en el plan local y luego distribuye ambos ingresos, por lo que admite intercambiar cuando la salida libera el espacio necesario. Un rechazo conserva los cuatro recursos.

El journal `trade:settlement:<operation_id>` conserva participantes, huella y resultado para consulta después de reiniciar, incluso si venció el recibo temporal. Es un registro inmutable de recuperación, sin contraseñas ni datos de conexión; esta versión no lo purga automáticamente. Reutilizar el ID para otra oferta se rechaza. Una confirmación cuyo resultado de persistencia sea incierto conserva el ID y bloquea ediciones/cancelación hasta resolverlo mediante un reintento; no se aplican compensaciones.

Antes de operar se comprueba AOF. Antes de anunciar el resultado se escribe una barrera y se exige fsync local con WAITAOF en una conexión exclusiva. La barrera posterior a EXEC también cubre ese commit previo en el orden de AOF; no se supone que el pool entregue la misma conexión que ejecutó la transacción. [Semántica oficial de WAITAOF](https://redis.io/docs/latest/commands/waitaof/).

`uv run python -m src.operations.trade_atomic_smoke` verifica confirmaciones concurrentes, mata sólo su propio Redis con SIGKILL, lo reinicia, consulta el journal y repite la operación sin duplicar recursos. Un segundo Redis sin AOF debe rechazar antes de tocar inventarios o saldos. No usa datos productivos. Las pruebas rápidas inyectan ACK perdido después de EXEC y una confirmación de fsync incierta.

## Objetos del banco

Depósito y retiro confirman ambos contenedores y el recibo en un solo EXEC. La distribución completa se calcula en memoria, incluyendo espacio en stacks existentes y nuevos. Inventario mantiene su tope configurado de stack y la bóveda limita cada stack a 32767, representable en el protocolo. Se rechazan cantidades persistidas fuera de rango sin corregir ni descartar objetos silenciosamente. Banco e inventario capturan sus capacidades efectivas al inicializarse.

El origen se comprueba por slot, identidad y cantidad; un cambio de identidad durante un reintento de WATCH se rechaza. Depositar equipo requiere desequiparlo primero. No se persiste una distribución parcial cuando el destino sólo admite parte de la cantidad. Ambos inventarios se sincronizan desde Redis después de confirmar AOF, incluidos los slots vacíos. El ID del comando y la política de recibos/replay acotados permiten resolver respuestas inciertas sin duplicar objetos; después del plazo se exige consultar los contenedores.

`uv run python -m src.operations.bank_items_smoke` prueba distribución en el banco y al retirar, usa el slot 30, mata su Redis propio con SIGKILL y repite ambas operaciones tras reiniciarlo. El total y los stacks deben coincidir exactamente con el primer commit.
