# Contrato binario de pyao 1.0

La fuente versionada es `src/network/protocol/contract.json`, copiada sin cambios
como `protocol/contract.json` en ArgentumOnlineGodot. `fixtures.json` contiene
bytes y valores exclusivamente sintéticos. No usar credenciales reales como fixtures.

El ID ocupa un byte, los números usan little-endian y las cadenas usan longitud
**u16 en bytes + ISO-8859-1 estricto**. No son UTF-16 ni Windows-1252. Un carácter
fuera de Latin-1 se rechaza sin reemplazo. Usuario: 3–20 bytes; contraseña: 6–32
bytes, sin strip, normalización ni cambio de mayúsculas. Inventario: slots 1–30;
el modelo Godot convierte a índices 0–29 una sola vez. Stats int16 con signo.

Cada dirección enumera todos los IDs de Godot y los del servidor. `supported`
indica un layout acordado; `unsupported` obliga a rechazarlo. La longitud se
calcula sumando los anchos de `fields`: u8=1, i16=2, i32/f32=4 y str16=2+longitud.
`variants` agrega campos según el primer campo (subcomando/subtipo); cualquier
variante no declarada es inválida. GM sólo declara WARP_CHAR=11. MULTI_MESSAGE
sólo declara los subtipos emitidos por pyao: 12, 13 y 17. Máximo por paquete: 4096.

Excepciones que se deben conservar: Logged **ID 0 + clase u8** (2 bytes), ChangeMap
**map i16 + versión i16** (5), MOVE_ITEM **origen u8 + destino u8** (3), CLAN_DETAILS
con miembros/enemigos/aliados **int32**, e inventario sin flags extra de AO Libre.
COMMERCE_INIT abre la ventana con el ID 7 solo; después llegan slots ID 59. El
builder extendido sin uso no define un segundo layout del mismo ID. SEND_SKILLS
71 registra el layout legacy de 9 int16; el catálogo/progreso se alinea en #126.

### Visibilidad de nombres de NPC

La revisión de nombres agrega `show_name u8` (0 u 1) después de `privileges` en
`CHARACTER_CREATE=29`. Se conserva el nombre completo para identificar al objetivo
en combate; la etiqueta sólo se permite para habitantes amistosos y guardias.
Criaturas, animales neutrales, mascotas e invocaciones tienen `show_name=0`.
Los jugadores conservan su nombre visible según preferencias e invisibilidad.
Las fixtures `character_bat`, `character_banker` y `character_player` fijan ambos
casos y sus fronteras. Esta revisión requiere actualizar cliente y servidor
juntos; no admite clientes con el layout anterior ni intenta inferirlo del stream.

## Coordinación de revisiones

La revisión de partida es servidor `37a8b22` y cliente `e911af34`. **No son todavía
una pareja compatible**: este commit fija la especificación, no declara terminadas
las correcciones de #95/#96/#103/#104/#105/#126 ni cliente #4/#5/#6/#12.
Las fixtures de login/alta, WALK, acentos, PARTY_JOIN, DOUBLE_CLICK, slots 25/26/30
y contadores de clan grandes son la puerta de compatibilidad de ambos repositorios.
La validación conjunta #111 registrará los dos commits exactos que las consumen.

PARTY_JOIN cambia coordinadamente a `93 + nickname str16`. Publicar cliente y
servidor compatibles juntos: la forma antigua de un byte no tiene información
para recuperar destinatario ni frontera. No inferirla mirando el siguiente paquete.

Las extensiones futuras usan negociación optativa **después** de Logged (#117).
Sin negociación no se emiten paquetes nuevos ni se cambia el stream legacy. No
importar AccountLogged/account_hash ni renumerar los IDs propios de pyao.

## Negociación optativa v1

El ID **250 en ambas direcciones** no colisiona con los enums AO existentes.
Solicitud y respuesta ocupan 6 bytes: `id u8, versión u8 (=1), máscara i32 LE`.
La máscara es no negativa. Las fixtures `capabilities_request_v1` y
`capabilities_response_none` fijan los bytes. Los bits se registran en el JSON:
catálogo de habilidades=1, cast dirigido=2, asignación=4, cambio de contraseña=8,
daño visual=16, proyectiles=32, clima=64 y estado de intercambio=128 y acciones de habilidades=256. Registrar un
bit no implementa una feature: el servidor sólo responde con bits implementados
solicitados por ese cliente. El registro inicial anuncia cero capacidades.

El cliente puede solicitar después de **Logged**, nunca antes del login directo.
El servidor acepta dentro de 30 segundos desde la autenticación completa para
tolerar la carga inicial del mapa en equipos lentos. Un
pedido previo, tardío, de versión distinta o máscara negativa se ignora; no altera
el login ni sus permisos. La primera negociación aceptada fija la intersección
por conexión. Repetir no amplía permisos. Sin solicitud no se emite nada y el
stream legacy permanece idéntico. Cerrar limpia todo el estado.

El cliente espera como máximo 30 segundos por la respuesta; ante ausencia, versión
inválida o bits no solicitados conserva las funciones base y cero extensiones.
Esta negociación no sustituye TLS ni importa el flujo cuenta/hash de AO Libre.
Una extensión nueva debe definir su propio layout, fixtures y bit antes de activarse.

## Catálogo y progreso de habilidades v1

`skills.json` asigna 22 IDs: conserva los 20 de AO y agrega **Robustez=21 y
Agilidad=22**, propias de pyao. Cada entrada declara almacenamiento, semántica
histórica e implementación. Los IDs sin progreso implementado se representan
explícitamente; un valor histórico de herrería/carpintería se conserva aunque su
progresión aún no esté habilitada.

SEND_SKILLS=71 conserva sus **9 int16** y su orden legacy. El reader reconstruye el
catálogo por IDs, sin tomar bytes de ChangeMap ni de otros mensajes para llenar
20 pares inexistentes. Las conexiones que negociaron el bit `skills_catalog=1`
reciben **ID 251**, versión u8, puntos libres i16 y 22 triples `(id u8, nivel u8,
porcentaje u8)`, en orden canónico: **70 bytes exactos**. El porcentaje es 0–99,
el nivel 0–100. XP acumulada no se empaqueta como nivel. El cliente rechaza esa
extensión si no la negoció. El servidor anuncia ahora el bit 1 al implementar
este catálogo; los demás bits siguen deshabilitados.

El esquema Redis v3 agrega `level:<clave>` y `xp:<clave>` sin borrar ni reescribir
los campos históricos. Tala, pesca y minería guardaban XP acumulada: se conserva
exactamente y se deriva nivel/porcentaje. Las demás claves guardaban niveles y
conservan su nivel inicial. `xp_per_level` guarda el umbral efectivo por personaje
para que una configuración posterior no reinterprete su progreso. Las subidas de
XP son transaccionales; cruzar un umbral incrementa el nivel, y asignar un nivel
explícito conserva la XP. El presupuesto `points` permanece autoritativo en Redis.

Migrar requiere el mismo procedimiento de backup verificado y servidor detenido
documentado en REDIS.md. Los pasos pendientes y sus journals se confirman juntos,
con idempotencia y auditoría. Las fixtures `skills_legacy` y `skills_catalog_v1`
se prueban seguidas por ChangeMap y partidas en cada frontera.
