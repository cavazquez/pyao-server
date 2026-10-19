# Stock comercial persistente

Redis es la fuente de las existencias reales de cada mercader. El servidor y el
cliente no reconstruyen cantidades desde TOML durante una partida.

- `merchant:{npc_id}:inventory`: slots mutables con `item_id:quantity`.
- `merchant:{npc_id}:items`: índice auxiliar de artículos conocidos.
- `merchant:{npc_id}:catalog`: política versionada, independiente del stock.
  `items` contiene `[item_id, tope, incremento]`; `interval_seconds` define el
  intervalo y `last_restock` registra el último período aplicado en segundos UTC.

Las compras y ventas confirman stock, inventario del jugador, oro e índice en la
misma transacción Redis con WATCH/EXEC y recibos de operación. La existencia del
catálogo identifica a un mercader inicializado, incluso si su stock está agotado.
Una actualización de TOML o un reinicio normal no vuelven a sembrarlo. La adopción
de inventarios antiguos conserva cantidades y artículos revendidos.

## Valores iniciales de reposición

Al crear un mercader nuevo se copia la semilla de `data/npcs/merchants.toml`.
La política inicial repone cada hora hasta un 10% del stock inicial por artículo,
con mínimo una unidad por intervalo y sin superar ese stock. Los artículos con
una sola unidad inicial no se reponen automáticamente. Estos parámetros quedan
guardados en Redis; los siguientes arranques usan esa política persistida.

El mantenimiento recorre las políticas con SCAN cada minuto, aunque no haya
jugadores conectados. Recupera los intervalos vencidos en una sola operación por
mercader. Las reventas pueden superar el tope: el excedente se conserva y detiene
la reposición de ese artículo. Si los veinte slots están ocupados, no se borran
reventas para crear espacio. Dos workers simultáneos no reponen el mismo intervalo
dos veces; los cambios concurrentes de comercio fuerzan un nuevo cálculo.

## Cambios administrativos

Para adoptar una política nueva desde TOML, con la configuración Redis habitual:

```sh
uv run python -m src.operations.merchant_catalog
```

Este comando modifica la política, conserva `last_restock` y no altera las
cantidades. Conviene ejecutarlo durante mantenimiento y verificar antes el backup
habitual. El método `clear_merchant()` es un restablecimiento administrativo
explícito; no forma parte de una carga normal. Reiniciar o reinstalar el servidor
no requiere ese método.

## Verificación

Las regresiones cubren stock agotado, adopción de datos antiguos, carga repetida,
reventas, falta de espacio, topes, varios intervalos y dos inicializadores/workers.

```sh
uv run python -m pytest tests/economy/test_merchant_stock.py \
  tests/models/test_merchant_data_loader.py tests/services/test_commerce_service.py
uv run python -m src.operations.merchant_stock_smoke
```

El segundo comando crea su propio Redis con AOF, disputa la última unidad entre
dos compradores, conserva una reventa fuera del catálogo, mata ese Redis mediante
SIGKILL y verifica la recuperación exacta de existencias, índice y política. Elimina
únicamente su contenedor y volumen de prueba al terminar.
