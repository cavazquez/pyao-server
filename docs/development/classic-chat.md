# Comandos clásicos y propios de PyAO

El catálogo `src/network/protocol/chat_commands.json` contiene 194 nombres:
177 del cliente AO 0.13.3 y 17 extensiones/alias propios. La misma versión del JSON
se distribuye con Godot. Incluye nombre exacto, sintaxis, descripción, rol y
transporte; la referencia histórica conserva la línea del parser original.

`/AYUDA [página]` y el autocompletado se generan desde ese catálogo. Una cuenta
normal no recibe comandos GM. El servidor revalida el rol al ejecutar y, en las
mutaciones administrativas, dentro de WATCH junto con los recursos. Ocultar una
opción en Godot no es una medida de autorización. `/AUTOUPDATE` sólo se anuncia
cuando el operador configuró un agente.

## Despacho y privacidad

El primer token se compara completo, sin interpretar prefijos. `/COMERCIARX`,
`/METRICS_EXTRA`, una barra sola y comandos desconocidos responden privadamente;
sus argumentos nunca pasan al chat del mapa. Espacios y tabulaciones separan el
token, sin convertir el contenido de argumentos en mayúsculas.

Los escritores nativos válidos se conservan para funciones existentes. El resto
usa TALK y los servicios del servidor; no se envían IDs del cliente VB6 que PyAO
no implementa. `/CONTRASEÑA`, `/FUNDARCLAN` y `/DETALLESCLAN` abren sus interfaces.
El formulario de fundación usa los requisitos actuales del servidor (nivel y
Liderazgo), sin inventar un cobro de oro del cliente. `/PING` usa el ping/pong real.

Los logs de TALK no contienen argumentos. El historial excluye comandos sensibles,
también cuando usan tabulación. Los informes GM no muestran hashes ni contraseñas.
`/APASS destino@origen` copia el hash autorizado del origen, revoca sesiones del
destino y audita identidades; nunca pide una contraseña en el chat.

## Interacciones de personajes

Los servicios NPC verifican instancia, plantilla, selección, mapa, vida y distancia
al confirmar los cambios. Plantillas propias y originales se reconocen por ID y
nombre; no suponer que todos los NPC con el mismo número en otro fork son iguales.
Banco y mercader conservan los datos de Redis. `/RESETINV` es una reposición
administrativa explícita desde su política persistida, no una recarga automática
que duplica stock al reiniciar.

`/ENTRENAR` presenta criaturas reales del entrenador; `/ENTRENAR número` crea una
por mapa, sin reaparición. `/DESCANSAR` requiere fogata viva cercana y termina al
moverse, morir o apagarse la fogata. La regeneración de energía usa su tasa de
descanso. `/CURAR` y `/RESUCITAR` reutilizan el ciclo de vida y sus publicaciones.

`/HOGAR` establece ciudadanía ante un gobernador estando vivo. Un fantasma puede
iniciar o cancelar el regreso de 60 segundos a su hogar; el plazo queda en Redis.
Resucitar cancela el regreso, y la transferencia vuelve a verificar su estado al
confirmar. La cárcel impide escapar; su vencimiento transcurre offline y el traslado
pendiente se completa al conectar, usando una llegada libre.

El casino clásico `/APOSTAR 1..5000` gana con probabilidad 47%; ganar devuelve dos
veces la apuesta, equivalente a una ganancia neta igual a lo apostado. Saldo y
contabilidad cambian juntos. La lotería investigada en #403 no está activada.

## Adaptaciones al sistema propio

Las facciones conservan las afiliaciones, prestigio y requisitos de PyAO. Los
nobles añaden las consultas y recompensas clásicas de armadura/experiencia, con
umbrales históricos, clase, tamaño, nivel y contador de recompensas. Se cuenta
desde la incorporación, sin borrar bajas históricas. No se introduce como requisito
oculto la reputación VB6 que el sistema propio no genera. `/AI` y `/AC` modifican
armaduras de recompensa, no crean un objeto en el inventario del GM. `/RAJAR`
restablece afiliación de facción y permisos, conservando contadores de toda la vida.

`/PARTY` sin nombre solicita ingreso al líder seleccionado; `/ACCEPTPARTY nombre`
aprueba una solicitud vigente o acepta una invitación. Se mantienen las invitaciones
modernas por nombre. `/CMSG`, `/PMSG` y `/BMSG` usan sus audiencias autorizadas.
Las elecciones de clan duran 24 horas: un voto inmutable por miembro, sólo candidatos
actuales y cambio de líder ante un único ganador. Empates o ausencia de votos
conservan al líder. Un worker las cierra aunque no haya jugadores conectados.

`/COMPARTIRNPC` concede permiso a otro jugador para las criaturas reclamadas durante
su combate; compartir no cambia al dueño original. La revocación modifica el índice
inverso persistido, utilizado por daño físico y hechizos hostiles. Las mascotas
mantienen su identidad y propietario con los alias clásicos de órdenes.

El panel GM y las antiguas ventanas Win32 se adaptan a consultas textuales paginadas.
`/SHOW SOS|DENUNCIAS|BUGS|ROL`, `/REM` y `/BORRAR SOS` son utilizables desde Godot.
`/SILENCIAR` afecta denuncias, como en el original; el silencio de canales de chat
se administra con `/MUTE` y `/UNMUTE`. El centinela conserva desafíos/resultados en
Redis y registra incumplimientos para revisión; no aplica bloqueos automáticos por
una única falta de respuesta.

## Edición del mundo

Los binarios base de mapas se conservan. Los cambios de GM son overlays en
`world:map:tiles:<mapa>` y `world:map:rules:<mapa>`, reconstruidos al arrancar.
`world:map:revision` protege los planes de acciones contra un cambio de reglas entre
la preparación y el commit. Una llegada conserva los controles de agua, embarcación,
ocupación y restricciones. La reserva espacial pertenece al servicio que confirma
la transferencia, y la creación de NPC convierte su reserva propia en ocupación.

`/CT mapa x y [radio]` crea un portal al norte del GM. `/DT` retira el seleccionado;
radio 0 conserva el destino exacto, de 1 a 6 elige una casilla libre del área.
`/BLOQ` actúa sobre casillas desocupadas. Los portales y colisiones se vuelven a
enviar al entrar o reconectar. `/CI`, `/DEST`, `/MASSDEST` y `/LIMPIAR` utilizan el
mismo suelo transaccional que los jugadores; LIMPIAR recorre los mapas conocidos.
Los portales se retiran explícitamente con DT, no como objetos recolectables.

Triggers: 0 normal, 1 techo (sin lluvia), 3 impide movimiento/creación NPC,
4 casilla segura sin combate ni robo, 6 duelo sin pérdida de objetos, oro o XP en
una muerte PvP directa. Los valores históricos 2 y 5 se conservan como metadatos;
no se inventa una nueva mecánica de antipiquetes. La seguridad de mapa continúa
requiriendo consentimiento de ambos jugadores para PvP.

MODMAPINFO valida tipos y opciones de PK/SEGURO, BACKUP, RESTRINGIR, MUSIC, NOMBRE,
MAGIASINEFECTO, INVISINEFECTO, RESUSINEFECTO, OCULTARSINEFECTO, INVOCARSINEFECTO,
ROBONPC, ROBO, TERRENO y ZONA. Terreno/zona clasifican exposición climática; no se
activa daño por frío ajeno al balance actual. Un GM no puede convertir texto libre
en rutas de archivos, claves Redis o código ejecutable.

`/GUARDAMAPA` conserva un checkpoint de configuración/NPC, excluyendo mascotas e
invocaciones temporales. BACKUP=1 actualiza ese checkpoint cada cinco minutos;
BACKUP=0 elimina el checkpoint automático. Las cuentas y la partida no dependen
de esa opción: siempre permanecen en Redis/AOF. Cambios de diálogo guardados con
el mapa se restauran sin reutilizar identidades de instancia anteriores.

## Operación y validación

`/GRABAR` confirma la barrera de persistencia AOF; no reescribe cuentas desde
snapshots viejos. `/DOBACKUP` espera el resultado de BGSAVE y comunica que el RDB
queda en el almacenamiento del Redis externo. Copiarlo y verificar restauración
es trabajo de la herramienta del operador, no una operación del cliente Godot.

SETINIVAR admite sólo cadencias y activación PvP con tipos/rangos validados. Recargas
de objetos, NPC y hechizos validan el nuevo catálogo antes de reemplazarlo y no
permiten retirar IDs existentes. No cambian retroactivamente una criatura en combate.
APAGAR y REINICIAR usan el ciclo real de cierre del servidor y drenan la respuesta.
AUTOUPDATE ejecuta únicamente una ruta absoluta, ejecutable y no modificable por
grupo/otros, configurada por el operador; sin shell ni argumentos recibidos por chat.
En Snap la actualización del paquete continúa a cargo de snapd.

La regresión está en `tests/services/classic_chat`, la matriz histórica independiente
en `tests/services/fixtures/classic_commands.json` y los controles atómicos de borrado
en `tests/utils/test_resource_replacement.py`. Godot prueba los 194 comandos con su
parser/escritores reales en `tests/chat_commands.tscn`, incorporado al smoke de CI.
Estas pruebas de parser no sustituyen la campaña gráfica de dos clientes, equipo,
hechizos, recolección, navegación, audio y reconexión requerida para publicar.
El escenario Godot `classic-chat` ejecuta reportes, edición, audiencias, colisiones,
etiquetas y reconexión, y rechaza todas las rutas GM desde un jugador común por TLS.
La consola conserva hasta 200 párrafos: una respuesta paginada no pierde su encabezado
al superar las diez líneas antiguas. La aceptación prolongada usa además el binario
y fuentes limpios de la versión que se va a distribuir.

Estudios separados: [durabilidad individual](../systems/item-durability-study.md),
[lotería física](../systems/lottery-study.md) y [rendimiento de CPython](python-performance-study.md).
