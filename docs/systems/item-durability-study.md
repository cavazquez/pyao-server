# Durabilidad individual de objetos — estudio #334

Decisión: es viable, pero requiere identidad por ejemplar antes de activar desgaste.
Esta publicación conserva las reglas actuales. No se rompen ni vencen objetos.

## Estado comprobado

`InventorySlot` y `SlotPlan` guardan `item_id:quantity` y apilan por tipo. El banco,
intercambio y equipo comparten ese formato. `GroundState` tiene `stack_id`, pero es
identidad del stack del suelo, no del ejemplar. `ITEMS_CATALOG` es compartido: cambiar
sus estadísticas degradaría todos los objetos de ese tipo. No sirve agregar un
contador al catálogo ni usar el slot como identidad.

## Regla propuesta

Todos los tipos del catálogo deben tener una política explícita: durable,
consumible o exento. Primera implementación: armas, escudos, armaduras, cascos,
herramientas, botas y accesorios que otorguen estadísticas. Embarcaciones tendrán
política propia antes de incluirlas: una rotura nunca deja a un personaje atrapado
en agua. Comida, pociones, munición y materiales conservan consumo y apilado; el oro
conserva su devaluación, sin recibir además durabilidad.

Un arma gasta un uso por ataque válido confirmado, incluso si falla; un escudo
por bloqueo efectivo, armadura/casco por impacto mitigado y herramienta por intento
válido de su oficio. Rechazos por alcance, cadencia, mapa, energía o permisos no
gastan. No cobrar simultáneamente un uso por ataque y otro por notificación visual.
El equipo pierde tiempo calendario desde su creación (UTC del servidor), incluido
el tiempo offline, en banco, suelo o comercio. Guardarlo no congela su edad.
No comenzar la edad en el primer uso: permite acumular equipo nuevo indefinidamente.

Parámetros por tipo: `max_uses`, `lifetime_seconds`, `minimum_factor_bps` y versión
de política. Cero significa límite deshabilitado, no vencimiento inmediato.
Estado: `instance_id`, `item_id`, `created_at`, `expires_at`, `uses_spent`, versión
y propietario/ubicación autoritativa. No confiar en timestamps enviados por Godot.
Las cifras iniciales de usos/días requieren decisión de balance; el estudio no las
inventa como reglas de producción.

Calcular con enteros:

```
use_bps  = max(0, (max_uses - uses_spent) * 10000 // max_uses)
time_bps = max(0, (expires_at - now) * 10000 // lifetime_seconds)
condition_bps = min(límites habilitados, por defecto 10000)
factor_bps = 5000 + condition_bps // 2  # propuesta: 100% a 50%
effective_stat = base_stat * factor_bps // 10000
```

El agotamiento de cualquier límite invalida el beneficio y uso del ejemplar,
conservándolo como roto para inspección o reciclaje. No desaparece silenciosamente
ni sigue otorgando stats porque quedó equipado. Los enteros se truncan hacia abajo;
una estadística base cero permanece cero. Daño mínimo no supera máximo. Duraciones,
identidad, resistencias booleanas y efectos especiales precisan políticas explícitas;
no multiplicar indiscriminadamente todos los campos del catálogo.

Se recomienda la curva lineal por ser explicable. Tramos facilitan balance pero
producen saltos; una curva exponencial complica comunicar el estado. La reparación
de usos puede estudiarse después; nunca reinicia creación/vencimiento ni convierte
equipo usado en nuevo. Desaparición directa ahorra limpieza pero destruye trazabilidad;
rotura permanente requiere reciclaje para evitar acumular basura.

## Redis y transferencias

Propuesta: slots versionados con referencia `i1:<uuid>` para durables de cantidad
uno y stacks versionados para consumibles. Hash `item:instance:<uuid>` con estado y
ubicación. La pertenencia al slot y el propietario deben coincidir bajo WATCH en
cada operación. No mantener un segundo contador de usos en Godot. No usar TTL para
borrar un objeto que todavía está referenciado por una bóveda.

`Resource`/`Decision` permite observar los hashes de instancia y ambos inventarios.
Actualizar usos, daño, HP, consumos y recibo en el mismo EXEC de combate/recolección.
Transferir identidad entre slots, banco, comercio, suelo y muerte: nunca crear un
UUID nuevo al recoger o comprar equipo usado. Un stack de varios durables se
descompone en ejemplares, con reserva previa de capacidad; si no entra, la migración
no borra ni sobrescribe el stack original. El botín y fabricación crean identidades
desde su operación de origen, con UUID derivado del recibo para reintentos.

Migración explícita y reanudable, antes de admitir jugadores: backup/restauración
verificados, versión de esquema, cursor y recibo por contenedor; edad de existentes
fijada al instante de migración, sin antigüedad ficticia. Nueva versión coordinada
de cliente/servidor; no se requiere mantener clientes viejos. Reloj monotónico para
cadencias, UTC persistido para vencimientos; no rejuvenecer ante retroceso del reloj.

## Coste y cliente

Con N ejemplares y B objetos implicados en una acción: espacio O(N), acceso hash
promedio O(1), actualización O(B). Calcular vencimiento al consultar/usar: O(1) por
ejemplar, sin barrer todos los inventarios cada segundo. Actualizar sólo el equipo
de conectados en el GameTick. Un índice ordenado de limpieza sería O(log N) por
alta/baja y sólo se justifica para rotos sin dueño. Leer metadatos en pipeline y
HMGET, nunca una ida y vuelta por objeto de una lista.

Medición de un prototipo aislado en Redis 8.10.2, Linux x86_64, sin datos de
partidas: con 100.000 objetos de cantidad uno, los slots actuales ocupan 1.522.251
bytes por `MEMORY USAGE`; las referencias `i1:<uuid>` y ocho campos de metadatos
por ejemplar ocupan 24.218.441 bytes, unos 242,18 bytes por objeto. Con 1.000
objetos: 15.181 frente a 241.181 bytes. Son unos 15,9 veces más memoria para este
modelo; no se puede presentar identidad individual como una optimización espacial.

Leer 30 slots cuesta una petición; resolver además 30 metadatos agrega un pipeline
con 30 HMGET. En 101 muestras calientes a 100.000 objetos, p50 pasó de 0,095 ms a
0,551 ms; p95 de 0,113 a 1,107 ms. La carga escribió unos 6,24 MB de AOF para el
formato actual y 37,37 MB para el prototipo, sin incluir futuros recibos de combate.
Estos tiempos pertenecen a un host de desarrollo con otras pruebas en ejecución;
no son una medida de capacidad de producción ni justifican un SLA. La memoria es
la suma real de las claves, no una extrapolación de payload ni RSS del proceso.

[Resultados crudos](../benchmarks/item-instance-layout-2026-10-22.json), reproducibles
con `python -m tools.analysis.item_instance_study --output /tmp/item-layout.json`.
El comando crea y elimina exclusivamente su propio Redis. La medición usa hashes
de metadatos, fecha sintética, pipelines de carga y 101 lecturas; no activa desgaste
ni mide todavía el coste completo de WATCH/EXEC/WAITAOF en combate. Antes de adoptar,
repetir con carga representativa, recibos, distintos tipos, AOF/backup y dos clientes.

Godot debe mostrar condición, usos y vencimiento, stats base y efectivos, estado
roto y avisos al 20%/5%. Las vistas de inventario, banco, equipo y comercio comparten
proyección. Un evento/revisión de equipo recalcula inmediatamente el personaje
equipado en ambos clientes; los iconos no prueban que el beneficio se actualizó.

## Trabajo derivado y validación

1. Política por todos los tipos y datos de balance; catálogo validado y exenciones.
2. Identidad individual, slots versionados y migración recuperable con conservación.
3. Transferencias de extremo a extremo, propiedad e idempotencia de recibos.
4. Descuento de usos en combate/oficios y estadísticas efectivas centralizadas.
5. Vencimiento UTC, equipo roto, alertas y reciclaje, con reloj controlado.
6. Protocolo y cinco vistas Godot; dos clientes, reemplazo, reconexión y comercio.
7. Carga, memoria/AOF y recuperación: EXEC incierto, dos atacantes, muerte y reinicio.

Secuencia 1→2→3→4/5→6→7. Esfuerzo estimado: 2–4 semanas de desarrollo más balance,
para servidor y cliente en conjunto. Pruebas con máximos 2 usos/60 segundos y reloj
inyectado: T−1/T/T+1, sin esperar días reales; duplicar la misma operación no gasta
dos veces, ni tirar/recoger, banco o muerte reparan el ejemplar. La economía debe
comparar entrada de equipo del #330 con salida por desgaste y comercio de usados;
la representación conserva las mejoras espaciales del #333.

## Issues derivados

Propuestas para una tanda posterior, según el orden y las dependencias anteriores:

- [cavazquez/pyao-server#565](https://github.com/cavazquez/pyao-server/issues/565): Durabilidad: definir y validar la política de todos los tipos de ítems.
- [cavazquez/pyao-server#566](https://github.com/cavazquez/pyao-server/issues/566): Durabilidad: agregar identidad por ejemplar y migración recuperable de slots.
- [cavazquez/pyao-server#567](https://github.com/cavazquez/pyao-server/issues/567): Durabilidad: conservar el ejemplar y su estado en todas las transferencias.
- [cavazquez/pyao-server#568](https://github.com/cavazquez/pyao-server/issues/568): Durabilidad: descontar usos y calcular estadísticas efectivas en acciones confirmadas.
- [cavazquez/pyao-server#569](https://github.com/cavazquez/pyao-server/issues/569): Durabilidad: aplicar vencimiento UTC y estado roto mientras el equipo está puesto.
- [cavazquez/ArgentumOnlineGodot#216](https://github.com/cavazquez/ArgentumOnlineGodot/issues/216): Durabilidad: mostrar condición, usos, vencimiento y estadísticas efectivas en Godot.
- [cavazquez/pyao-server#570](https://github.com/cavazquez/pyao-server/issues/570): Durabilidad: validar carga, conservación y recuperación de objetos individuales.
