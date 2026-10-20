# Apariencia del equipamiento

[#361](https://github.com/cavazquez/pyao-server/issues/361) unifica la resolución
de apariencia para el equipo confirmado en Redis, los snapshots de login y mapa
y la publicación del ciclo vital. El handler de equipar publica el estado
completo al dueño y a los observadores después de guardar el cambio; reemplazar
y retirar una pieza también actualiza todas las capas.

El catálogo conserva `Anim`, `NumRopaje` y `RazaEnanaAnim` separados del icono
`GrhIndex`. La resolución usa la ropa equipada, las variantes de arma para razas
pequeñas y ceros explícitos para retirar armas, cascos y escudos. Muerte, barco y
mimetismo reemplazan la apariencia; al volver al estado normal se reconstruye el
equipo real, sin guardar otra copia de la apariencia en Redis.

Los snapshots transportan las capas completas, incluyendo transiciones y
teletransporte. Los paquetes que sólo cambian orientación llevan cuerpo/cabeza
cero; el cliente compañero conserva entonces la apariencia que ya tenía. El
movimiento evita releer inventario o cuenta para cada observador. Este contrato
requiere desplegar juntos el servidor y el cliente de la misma revisión funcional.

La regresión del cliente comprueba sprites reales en ambas ventanas, equipar,
reemplazar, retirar, cuatro orientaciones, reconexión y un cruce de portal. La
auditoría completa del catálogo y las referencias sin gráficos se conservan en
[el seguimiento del cliente](https://github.com/cavazquez/ArgentumOnlineGodot/issues/179).
Botas y anillos se siguen por separado en
[#181 del cliente](https://github.com/cavazquez/ArgentumOnlineGodot/issues/181)
y [#367 del servidor](https://github.com/cavazquez/pyao-server/issues/367).
