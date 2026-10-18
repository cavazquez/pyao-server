# Mutaciones de oro

Los créditos y débitos relativos del jugador usan WATCH/MULTI/EXEC sobre el hash de estadísticas y un recibo de operación. No se admite saldo negativo ni mayor que 999999999. Una cantidad inválida no inicia una transacción; un débito sin fondos o crédito que exceda el máximo deja el saldo intacto. Pickup usa un crédito limitado que devuelve la cantidad aceptada para conservar el remanente.

Una operación puede recibir `operation_id` generado con `src.utils.gold_atomic.operation_id()`. Conservarlo permite consultar el mismo resultado tras una respuesta incierta de EXEC, sin volver a aplicar la mutación. Reutilizarlo con otra petición se rechaza. Los recibos duran diez minutos y una operación sin recibo sólo puede iniciarse durante cinco minutos desde su creación; un reintento más antiguo se rechaza y exige consultar el saldo. El identificador utiliza reloj y nonce del servidor y no se deriva de credenciales. No permite reintentos ilimitados ni deduplicar dos acciones nuevas que el cliente envía por separado.

Subir de nivel conserva el saldo persistido; no vuelve a guardar la copia que leyó para calcular los atributos. Compras, drops y efectos consumen las primitivas relativas. Las transferencias que afectan otros recursos requieren sus propios commits conjuntos (#92, #93, #131, #132, #133, #134 y #153).

Validación: tests de concurrencia, límites, ACK perdido después de EXEC y rechazo de replay vencido; `uv run python -m src.operations.gold_atomic_smoke` reproduce créditos y débitos concurrentes contra un Redis nuevo autenticado, y limpia su contenedor y volumen.
