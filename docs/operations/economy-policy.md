# Política económica 1

La devaluación hace desaparecer el 1% del oro por cada corte a las 00:00 UTC,
conectado o desconectado. Afecta al oro en bolsillo, banco y montones del suelo.
Los días durante un apagado se aplican antes de la siguiente operación de dinero.
Se acumulan fracciones enteras de 1/10000 de moneda: no existe mínimo diario de
una moneda. La migración al esquema Redis 5 inicia el reloj sin reducir saldos
por períodos anteriores y desactiva el descuento antiguo por minuto.

WATCH/EXEC confirma la devaluación con la operación comercial, bancaria, de loot,
transferencia o gasto. Depositar o retirar no reinicia períodos. El crédito de oro
nuevo ocurre después de liquidar los días previos, por lo que no se devalúa
por días anteriores a su obtención. Redis conserva el último corte, el resto
fraccionario, el total pagado y los recibos de cada período materializado. El
mantenimiento recorre perfiles sin exigir conexiones activas. Una cuenta dañada
no bloquea a los demás personajes ni a los mercaderes.

Cada montón de oro guarda `devaluation_day` y `devaluation_remainder` en su lista
JSON por casilla del hash de suelo en Redis. El [esquema 6](redis-ground-layout.md)
conserva esas fechas y fracciones al migrar. Tirar, recoger y morir transfieren las fracciones pendientes;
recoger un montón parcial deja el resto en el suelo. El oro generado como loot
empieza en el corte siguiente a su creación. Un montón que llega a cero se retira
de Redis y de los clientes que lo ven. El mantenimiento usa SCAN incluso sin
jugadores y conserva el vencimiento original de los objetos del suelo.

La adopción usa `ground_activation_day`; reiniciar no lo mueve ni inventa deuda
anterior. Las claves internas `config:economy:daily_tax`, `tax:*` y el tópico
`tax` se conservan para compatibilidad. La presentación se llama devaluación y
reduce monedas, en lugar de modificar los precios del catálogo.

## Comercio y fabricación

Los IDs, habilidades necesarias, artículos y precios base siguen siendo los del
catálogo propio. La compra aplica Comerciar mediante techo de
`valor * 100 / (100 + habilidad)` y el NPC paga `valor // 2` por unidad vendida.
Las especialidades usan el ObjType explícito del catálogo; un rechazo no consume
objetos ni paga oro. Los compradores generales admiten las categorías existentes,
y los compradores de madera también admiten embarcaciones.

El presupuesto de entrenamiento comercial es una oportunidad de entrenamiento
por cada 100 monedas de volumen confirmado, hasta cuatro por minuto. Dividir una
compra en paquetes no genera más progreso. Cambiar entre compra y venta del mismo
artículo dentro de esa ventana deja de sumar volumen para ese artículo. Se
conservan los topes naturales, requisitos de asignación, hambre/sed y las reglas
de progreso existentes.

La carpintería limita la relación entre ingreso NPC y oportunidad de vender sus
materiales a 1,2 para requisitos hasta 30; 1,3 hasta 60; 1,4 hasta 90; y 1,5 hasta
100. Se aumentó la madera de las recetas que excedían esos presupuestos,
incluyendo instrumentos que pagaban más de cien veces sus materiales. Las tres
embarcaciones consumen 5000, 10000 y 15000 leñas respectivamente. A su habilidad
mínima, con éxito del 80% y pérdida de media receta al fallar, los márgenes
esperados son aproximadamente 6,7%, 17,8% y 28,9% sobre materiales.

La herrería mantiene ingreso bruto como máximo igual al valor NPC de los insumos:
su propósito principal es el progreso, el uso propio y el mercado entre jugadores,
donde el precio puede ser diferente. No toda receta garantiza beneficio al NPC.
La fundición conserva la recompensa original de refinamiento (hasta 18 veces el
valor del mineral, con requisito de Minería y fragua); esos minerales no son
creados por la reposición comercial. Ninguna receta tiene todos sus materiales
en la semilla artificial de los NPC: las reventas de materias primas son recursos
finitos obtenidos de otros jugadores.

## Auditoría reproducible

```sh
uv run python -m src.economy.crafting_budget
uv run python -m pytest tests/economy
```

El informe cubre las 124 recetas. Incluye valor de oportunidad, uso previsto,
requisito, probabilidades a 0/50/100 y habilidad mínima, lotes de 1/100, redondeo
hacia arriba de las pérdidas parciales y compra de insumos a Comerciar 0/50/100.
El tiempo informado es únicamente el mínimo de fabricación con la cadencia de
referencia de 0,5 segundos; no incluye recolectar, viajar, vender ni reintentos de
red. La regresión del catálogo completo impide reintroducir los márgenes excesivos
o un ciclo abastecido íntegramente por la semilla de los NPC.
