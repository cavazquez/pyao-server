# Inicialización de Redis

El arranque valida `schema:state` antes de escribir. Una base vacía adopta la
versión actual; un esquema legado, futuro, inválido o una migración activa impiden
iniciar. Migrar exige la operación explícita documentada en la guía de Redis y
un respaldo verificado. El arranque normal nunca usa `force_clear`.

Las semillas se aplican individualmente, incluso después de una interrupción:

- `config:server:*` y `config:effects:*`: `SET NX` por clave.
- `config:skills:rules` y `config:crafting:recipes`: `SET NX` del documento completo.
  Una lista vacía de recetas es una configuración existente. Las nuevas reglas
  distribuidas en TOML se adoptan únicamente al crear la clave o mediante una
  actualización administrativa explícita.
- `world:home:1` a `world:home:6`: `HSETNX` por campo dentro de una transacción por
  ciudad. Una ciudad parcial recibe sólo los campos ausentes. Las posiciones de
  personajes existentes no dependen de volver a aplicar estas semillas.
- `merchant:<id>:inventory`, `catalog` e `items`: transacción con `WATCH`; conserva
  existencias agotadas, artículos revendidos y la política de reposición guardada.
  El índice derivado puede reconstruirse; la reposición ocurre por su política de
  tiempo, no por reiniciar. Los recibos técnicos de la transacción tienen TTL.
- `config:economy:daily_tax`: adopción transaccional al faltar la política; las diferencias
  de versión/tasa requieren migración explícita, nunca se sustituyen silenciosamente.
- Índice cuenta/ID: backfill reanudable, sin sustituir una identidad contradictoria.
- `server:dice:*` y `server:motd`: `SET NX`; incluso cero, cadena vacía o el texto
  del antiguo mensaje predeterminado se conservan.

Las escrituras condicionales no retiran ni renuevan TTL de valores existentes.
No se reinicializan cuentas, contadores de IDs, inventarios, equipamiento, banco,
oro, objetos del suelo ni progreso. La configuración inválida existente no se
"repara" sobrescribiéndola: debe diagnosticarse y corregirse explícitamente.

Hay dos cambios operativos intencionales en cada arranque de servidor:
`server:connections:count` vuelve a cero y `server:uptime:start` registra el inicio
del proceso. No representan datos de una partida. Varios cargadores concurrentes
son seguros; ejecutar dos servidores propietarios del mismo mundo sigue sin ser
una modalidad de despliegue admitida.

## Verificación reproducible

`uv run --locked pytest -q tests/core/test_redis_bootstrap.py` comprueba valores
personalizados, falsos, semillas parciales/concurrentes y rechazo de esquemas sin
escrituras. `uv run --locked --no-dev python -m src.operations.bootstrap_smoke`
crea un Redis autenticado propio, ejecuta el inicializador real, comprueba TTL y
stock agotado, mata Redis y verifica AOF tras reiniciar. También autentica dos
clientes TCP reales y ejecuta movimiento mediante los handlers de producción.
Nunca usar estas pruebas sobre un Redis del operador.
