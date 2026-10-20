# Botín de todo el catálogo

La política versión 2 clasifica los 1.078 objetos del catálogo, incluidos los tres
equipos nuevos que completan la progresión superior: 1081 Escudo de Acero,
1082 Escudo Dracónico y 1083 Espada Rúnica. Reutilizan gráficos del catálogo propio.
Hay 494 objetos elegibles y 584 exclusiones con motivo. El oro real, ID 12, se emite
exclusivamente mediante la regla monetaria; no se suma el rango heredado del NPC.

La lista completa está en [el informe reproducible](../catalogs/npc-loot.json).
Incluye ID, nombre, categoría, stats/efectos, restricciones, cantidad, nivel mínimo
de NPC y motivo de exclusión. También enumera los 336 NPCs y las probabilidades
exactas por objeto, perfil y banda. Daga, espada, escudo y armadura son ejemplos:
los pools incluyen las 29 categorías de objetos transportables, con arcos,
bastones, cascos, accesorios, guantes, botas, pociones, comidas, bebidas, flechas,
pergaminos, herramientas, materiales, libros, embarcaciones, mochilas y otros.

## Calidad y probabilidades

Las bandas de nivel son 1–9, 10–24, 25–44, 45–69 y 70–255. La calidad se calcula
con los atributos reales de cada categoría: daño, defensa, poder de bastones,
defensa mágica o valor, según corresponda. El nivel mínimo explícito del objeto
también se respeta. Cada ID elegible tiene probabilidad positiva en al menos una
banda y una prueba ejecuta el sorteo para todos ellos con RNG controlado.

Por muerte hay hasta un montón de oro y un resultado de cada slot: equipo,
consumible y otros. Dentro de un slot se elige una categoría por peso; después,
la banda actual con probabilidad 70% o la anterior con 30%, y un ID uniforme de
esa calidad. Si una categoría carece de objetos en esa banda, se usa su mejor
banda anterior disponible; cuando acaba de desbloquearse, usa su primera banda.
Nunca se elige calidad superior a la permitida por el NPC.

Los humanoides tienen 85% de emitir oro y 12/16/20/24/28% de equipo según banda;
25% de consumibles y 8% de otros objetos. Los jefes tienen 95% de oro, un
multiplicador 1,7 para equipo, 50% de consumibles y 18% de otros. Los rangos de
oro por banda son 2–15, 20–80, 100–300, 350–800 y 1000–3000. Un resultado puede
no emitir objetos. La probabilidad de cada ID incluye las decisiones anteriores;
el informe la calcula exactamente, sin inferirla de una muestra aleatoria.

Las bestias no fabrican monedas ni equipo: sólo las especies con material
configurado pueden emitirlo, con probabilidad 65%. Los servicios amistosos tienen
perfil `none`. Las mascotas e invocaciones no emiten botín ni experiencia.

Los niveles de los 147 hostiles se hicieron explícitos a partir de sus HP máximos:
2/5/10/18/28/38/50/65/80/100 para HP hasta
30/100/200/500/1200/3000/8000/20000/50000 y superiores. Es una propuesta de balance
de PyAO, no un dato del Argentum original. Se conservan los campos de HP y daño
del catálogo. El nuevo nivel también interviene en las fórmulas de combate
existentes, incluido el ataque de NPC basado en nivel; por ello cambia la dificultad.
El recorrido de botín usa HP controlados y no certifica el balance completo de encuentros.

## Exclusiones

Puertas, árboles, yacimientos, carteles y otros elementos fijos no pertenecen a los
pools. `Agarrable=1` significa objeto fijo en este dataset. Las llaves con `Clave`
mantienen su entrega vinculada a casas, bóvedas y dungeons; los objetos de evento
y los marcados `NoSeCae` mantienen su mecánica de entrega. Las armas de 100/1000 de
daño y equipos administrativos quedan excluidos explícitamente. El campo
`Crucial` no se interpreta como exclusión: muchos objetos normales lo tienen.
Los objetos newbie y las variantes de raza, sexo, clase y facción se conservan;
ser elegible como botín no elimina sus restricciones de uso.

Los mensajes de inventario, banco y comercio conservan el `ObjType` real y los
límites distintos `MinDef`/`MaxDef`. Se corrigió el mapeo que enviaba escudos como
tipo 5/dinero y cascos como tipo 4/árbol, y la pérdida de defensa máxima al copiar
dos veces `MinDef`. El cliente usa los tipos canónicos 16/17 para mostrar su equipo.
La defensa media del escudo también aumenta la probabilidad de bloqueo (sumada a
la habilidad Defensa y limitada a 75%). La defensa del casco se suma a la de la
armadura para mitigar golpes, con el límite conjunto de 50% vigente. Hay pruebas
con el mismo golpe y tirada que contrastan equipo débil y fuerte del catálogo real.

Los alimentos y bebidas recogidos se consumen por tipo y por los valores del
catálogo, incluidos peces y los dos nombres históricos `MinHam`/`MinHAM`. Se
restauran hambre, sed y, cuando corresponda, HP y stamina. El objeto, el efecto
y el envase vacío del odre se confirman juntos. Una acción repetida no vuelve a
restaurar recursos, y un personaje muerto no puede resucitar comiendo.

## Confirmación y recuperación

El golpe letal marca HP y `death_state=pending` juntos en Redis. Ataques físicos,
hechizos y veneno pasan por la misma liquidación. La instancia tiene un sorteo
reproducible por UUID; si el suelo no admite todos los objetos, se persiste el
plan completo con los destinatarios de experiencia y no se paga parcialmente.
Una recompensa pendiente conserva el día de creación del oro, incluso al esperar
al día siguiente: no evita la devaluación diaria del 1%.

Un único EXEC confirma suelo, experiencia, subida de nivel, puntos, contabilidad
de party y marca de liquidación. Los avisos visuales se envían después de la
barrera AOF. Una instancia ya confirmada no vuelve a pagar, aunque el recibo
temporal haya caducado o los objetos ya se hayan recogido. Las instancias retiradas
no se pueden regenerar pasando una referencia vieja.

El arranque recupera las muertes pendientes antes de regenerar los NPCs. Un efecto
periódico revisa lotes de instancias cada cinco segundos para volver a intentar
casos retenidos por falta de espacio. El veneno valida la dosis y el intervalo
de dos segundos de forma atómica, y acredita la baja al envenenador una sola vez.
Las notificaciones de quests se envían después del commit de la recompensa;
este cambio no introduce una transacción conjunta con el progreso de quests.
Un cadáver retenido durante el arranque no emite después un retiro de personaje
con un CharIndex que el mundo regenerado pudo haber asignado a otro NPC.

## Validación

```sh
uv run python -m src.operations.npc_loot_audit --output docs/catalogs/npc-loot.json
uv run python -m src.operations.npc_loot_audit --output docs/catalogs/npc-loot.json --check
uv run pytest tests/services/npc tests/operations/test_npc_loot_audit.py
uv run python -m src.operations.npc_loot_smoke
```

El smoke crea su propio Redis autenticado y elimina únicamente ese contenedor y
volumen. Comprueba un plan retenido por capacidad, dos SIGKILL con recuperación
AOF, tres liquidaciones competidoras, dos recogidas por cada identidad de pila,
conservación de saldos/objetos y experiencia cobrada una sola vez. El recorrido
gráfico con dos Godot se ejecuta desde el cliente mediante `--scenario npc-loot`.
