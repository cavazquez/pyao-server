# Magia y ciclo vital de la 1.0

`SpellPlan` valida el libro, slot, habilidad, equipo, posición, rango Manhattan 10,
estado vital, objetivo y recursos sobre el snapshot observado por WATCH. El coste
usa `mana_cost` y `stamina_cost` del catálogo propio. Maná, stamina y efectos se
confirman junto al recibo; un rechazo no produce escrituras de dominio. Un ACK
incierto se resuelve con el mismo identificador y no se compensa restaurando saldos.
Los efectos se publican después de confirmar AOF. El antiguo paquete `spell_effects/` se retiró: no queda una vía alternativa con escrituras individuales. No se anuncia soporte de área,
proyectiles ni daño visual por este cambio.

`PvpPolicy` protege todas las fuentes de daño entre jugadores de la 1.0. Prohíbe
autoataque, mapas distintos, muertos y mapas seguros; ambas partes deben haber
persistido `safe_mode=0`. Las siete ciudades marcadas seguras por el dataset están
en `game.combat.safe_maps`. Curaciones, resurrección y buffs no requieren PvP.
Cualquier futura fuente de daño físico entre jugadores debe usar la misma política
sobre los recursos del commit, antes de cobrar o afectar al objetivo.

Los bastones se identifican por `ObjType=2` y `StaffPower` del catálogo. Se explicita
ese campo en el bastón newbie propio. Invocación usa `invoke_npc_id` e
`invoke_count`; coste, instancias, dueño, vencimiento e índices se confirman juntos.
El traslado de mascota también confirma posición e índices junto al coste.

El daño letal guarda `life_id`, `death_state=pending`, evento y coordenadas de muerte
con el HP. La liquidación confirma una vez por vida: 5% de EXP desde 100 puntos,
10% de oro, hasta tres stacks aleatorios y transformación en fantasma. Si no entra
un drop en el tile, permanece en el inventario o saldo. No se deduce y luego intenta
compensar. La marca `complete` persiste con los recursos, por lo que no depende del
TTL del recibo. Una nueva vida incrementa la generación; una tarea de la vida
anterior no puede liquidarla. `min_hp` es el campo canónico y `hp` es sólo fallback
para perfiles antiguos sin `min_hp`.

Los estados temporales se sincronizan por conexión bajo un lock. Parálisis emite
el toggle legacy sólo cuando cambia su estado; ceguera y aturdimiento emiten el
set/clear correcto. El tick reconcilia expiraciones y reconexiones sin invertir
estados por repetir una publicación.

El tick agenda tareas de muerte propias y recupera operaciones pendientes al
reconectar. No espera sus barreras AOF. El shutdown debe drenarlas antes de Redis
(#175). Un fantasma antiguo sin evento pendiente se adopta sin cobrar otra
penalización histórica. La apariencia de fantasma/mimetismo también se conserva
al reconectar.

Sacerdote y hechizo usan `revive_changes`: sólo una muerte liquidada puede
resucitar, en el lugar y con 50% de HP (mínimo uno). Se limpia morph y estados, se
incrementa la vida y se actualizan dueño y observadores. Un vivo o un segundo
caller no vuelven a cobrar ni a restaurar. El doble clic en los NPCs 81, 82 y 119
revalida identidad, HP, mapa y distancia Chebyshev máxima dos en el commit. La 1.0
no teletransporta al resucitar. Los IDs son configurables en
`game.spells.resurrection_npc_ids`.

Validación: matriz de rechazos sin gasto, carrera por recursos, efectos del catálogo,
mascotas, daño letal concurrente, vida posterior, resurrección concurrente,
recuperación del tick sin bloquear y ensayo Redis AOF descartable con dos SIGKILL:

```bash
uv run --locked --no-dev python -m src.operations.spell_lifecycle_smoke
```
