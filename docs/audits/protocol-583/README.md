# Auditoría cruzada de paquetes — #583

Esta auditoría identifica cobertura y ausencias. No implementa los opcodes históricos
por el hecho de que figuren en un enum ni sustituye la validación de entradas de #582.

El inventario generado comprende los 251 IDs de las dos direcciones del contrato,
los 146 subcomandos GM y 24 subtipos MultiMessage originales y las acciones JSON de
SKILL_ACTION/WORLD_ACTION, con sus campos y requisitos de capacidad. Para cada ID
registra serializador, recepción/dispatch, consumidor, llamadas, referencias a pruebas,
prioridad, impacto y reproducción conocida. Los campos vacíos de un ID no soportado
no se interpretan como un mensaje válido sin payload.

## Fuentes y reproducción

La línea base estática del servidor es `5a8614272e2032a3de4cacb32ba2be6cd373687d`
(índices #577/#578 y lotería #571–#576) y la del cliente
`bbea62b2851918cd57da8fc77996873a629cd830` (diálogo #217).
La muestra nativa conservada se ejecutó sobre el servidor
`9dd5467707118905e60720a897a4a4089fd3d2d4`: ahora es evidencia histórica y no
acredita automáticamente el runtime modificado. Las pruebas gráficas actuales de
índices se documentan en [su estudio](../../development/world-index-performance.md).
Los hashes de los archivos de runtime impiden reutilizar crédito dinámico obsoleto.

La referencia original es Comunidad-Winter/Argentum-Online, rama 0.13.3, commit
`928f826cd459f727e0c8ea134327bcf55711d573`. `original.json` registra rutas, objetos Git,
SHA256, nombres, IDs, operaciones de lectura/escritura y líneas. Se extrajeron hechos,
no se incorporó código VB6. El material local de `clientes/` tiene diferencias respecto
a esta revisión pública; no se le atribuye falsamente el commit del repositorio PyAO.

Con ambos checkouts, ejecutar desde el servidor:

```sh
uv run --no-project --python 3.14 python tools/analysis/protocol_inventory.py --client ../ArgentumOnlineGodot --check
uv run --no-project --python 3.14 python -m unittest discover -s tools/tests -p test_protocol_inventory.py -v
```

Para una actualización revisada, ejecutar el primer comando sin `--check`. Revisar
`decisions.json`, `inventory.json` e `inventory.md`; no aceptar un diff generado sin
examinar nuevos faltantes. CI ejecuta el mismo control en ambos repositorios, con la
contraparte fijada por commit. No instala el servidor, Redis o Godot para el chequeo.
El intérprete de la auditoría es Python 3.14 porque analiza su sintaxis; Python 3.12
no puede interpretar las excepciones múltiples sin paréntesis usadas por el servidor.

Para regenerar la referencia, obtener los cuatro archivos de `original.json` en su
commit exacto y ejecutar `extract_ao_protocol.py` con `--reference`, `--origin`,
`--catalog src/network/protocol/chat_commands.json` y `--output`. Los SHA256 deben
coincidir. La herramienta no acepta archivos locales parecidos como sustitutos.

## Cómo interpretar los estados

- `operational_end_to_end`: una muestra con dos clientes nativos confirmó el efecto
  señalado. No acredita todas las variantes, rechazos ni plataformas.
- `wired_not_exercised`: se encontraron extremos y rutas; todavía no se acredita
  una prueba dinámica completa de ese paquete.
- `negotiated_extension`: mensaje/acción propio, habilitado por capacidad. Su
  resultado dinámico se declara por separado.
- `partially_implemented`: existe una parte operativa y una divergencia concreta.
- `emitter_without_receiver` / `receiver_without_emitter`: falta uno de los extremos
  o su habilitación efectiva; no cuentan como funcionalidad implementada.
- `stub_or_noop`: hay una rama o clase que no produce un efecto.
- `declared_unused`: declaración histórica sin ruta habilitada acreditada.
- `replaced_by_other_transport`: función adaptada a TALK o a una extensión propia;
  no hace falta restaurar el opcode antiguo. Los cambios de semántica se explican.
- `retired_not_desired`: ID que no se ofrece en el diseño actual, con motivo explícito.

`binary_support`, `gameplay_support` y `ui_support` son dimensiones distintas.
Encontrar un lector, una llamada o el nombre de un test no prueba por sí solo que
el mensaje llegue al usuario. Las referencias a tests son un índice, no un resultado
de ejecución. Las operaciones primitivas y los campos históricos con control de flujo
no se presentan como esquemas completos; los formatos compuestos se señalan para prueba.

## Correcciones posteriores a la auditoría

La tanda coordinada de protocolo, combate, bóveda y clanes implementa los
seguimientos #582, #588–#593 y #596, con cliente #234/#235:

1. COMMERCE_INIT tiene un solo constructor de un byte; se retiró el extendido.
2. SHOW_PARTY_FORM no se emite y GRUPO conserva sus operaciones reales.
3. EXPANSION, plazos y baseline del contrato están actualizados; BANK_OK no se
   anuncia como soportado.
4. El intercambio usa una sola autoridad mediante TRADE_ACTION/TRADE_STATE. Se
   retiraron handlers, DTOs y emisiones antiguas.
5. Reordenar bóveda tiene una operación atómica con revisión, acceso físico y UI
   sin movimientos optimistas; no equivale a depositar y extraer.
6. Códice/descripción, noticias y sitio del clan tienen edición versionada para
   el líder vigente y conservación de borradores frente a conflictos.
7. Las fixtures cubren todos los mensajes y variantes soportados, escritores
   reales, receptores, fragmentación, límites y negociación. El combate conserva
   una barrera durable dentro de su commit antes de publicar efectos.

Los detalles, pruebas y límites de la fase están en
[protocol-bank-clans.md](../../development/protocol-bank-clans.md).
La muestra que sigue se conserva como evidencia histórica y no acredita por sí
sola las fuentes modificadas por esta tanda.

La tanda de objetos individuales incorpora la música de cliente #215 y agrega
botas al final de CharacterCreate/CharacterChange; requiere actualizar ambos
extremos juntos. Sus reglas y verificaciones están en
[durabilidad](../../items/durability.md). La muestra histórica de abajo sigue
sin acreditar automáticamente estos cambios.

El seguro específico de resurrección,
reputación VB6, macros automáticas, foros de mapa e ItemUpgrade conservan sus
respectivas decisiones de producto; no se habilitan al declarar sus opcodes.
El inventario actual tiene 30 slots.

## Muestra representativa

El 22 de octubre de 2026 se ejecutaron dos clientes nativos RC6 reales, con TLS,
PulseAudio y Redis 8.10.2 aislado contra el servidor fuente. Aprobaron los 22 recorridos
del smoke R10: alta/ciudades, inventario, banco, comercio, chat, party, combate,
hechizos, meditación, habilidades, mascotas, recolección y reconexión. La observación
posterior duró 10/11 segundos: **no es una nueva aceptación prolongada de 30 minutos**.
No se construyeron ni publicaron nuevos binarios ni Snaps para esta auditoría.

`representative-result.json`, `representative-scenarios.json` y `representative.json`
contienen resultados, casos, commits, hashes del binario y del runtime y el crédito
acotado por paquete. Al cambiar código probado, la muestra queda como histórica y
se retira su crédito del código actual. CI detecta el diff y exige revisarlo; para
acreditar de nuevo la ejecución hay que repetir la muestra. La muestra acredita
los escenarios observados, no cada campo ni cada mensaje individual de la sesión.

![Primer cliente de la muestra](representative-client-1.png)

![Segundo cliente de la muestra](representative-client-2.png)
