# Habilidades y hechizos de ProyectoAO

La referencia es el código de AO 0.13.3 (`Trabajo.bas`, `UsUaRiOs.bas`,
`SistemaCombate.bas`, `FileIO.bas`) del repositorio liberado. Se conservan el
dataset, las doce clases y las extensiones de ProyectoAO. Seguimiento:
[servidor #236](https://github.com/cavazquez/pyao-server/issues/236) a
[#263](https://github.com/cavazquez/pyao-server/issues/263), más recetas
[#137](https://github.com/cavazquez/pyao-server/issues/137), herrería
[#155](https://github.com/cavazquez/pyao-server/issues/155) y carpintería
[#167](https://github.com/cavazquez/pyao-server/issues/167).

## Progresión

El personaje recibe diez puntos al crearse, diez al alcanzar nivel dos y cinco
por cada nivel posterior. El nivel, crecimiento y puntos se confirman juntos;
`points_granted_through` evita concederlos otra vez al reconectar o reintentar.

Las dieciocho habilidades naturales suman 50 XP por éxito y 20 por fallo válido.
El umbral es `round(200 * 1.05 ** nivel_habilidad)` y cada mejora entrega 50 XP
generales. Deben haberse asignado los diez puntos iniciales y no haber hambre/sed.
El límite natural por nivel de personaje está en `data/skills.toml`: 3 al nivel
uno, 25 al diez, 50 al veinte y 100 desde el cuarenta.

Liderazgo, Navegación, Robustez y Agilidad se asignan manualmente. Los atributos
Fuerza, Agilidad, Inteligencia, Carisma y Constitución mantienen su creación y
modificadores temporales. Los puntos de nivel se asignan a habilidades.

El progreso v2 guarda nivel, XP parcial, XP histórica, puntos y puntos iniciales
asignados en `player:<id>:skills`. A diferencia del reinicio de contador del
original, asignar puntos manualmente conserva la XP parcial e histórica propia.
Los campos legacy se conservan para auditoría. La migración al esquema Redis 4
requiere servidor detenido y respaldo verificado: [REDIS.md](../guides/REDIS.md).

## Acciones y compatibilidad

Talar, Minería y Pesca validan herramienta equipada, terreno, distancia y espacio.
Se conservan las cantidades propias de 5 leñas, 3 minerales y 2 pescados.
Meditar ejecuta intentos cada tres segundos; el nivel cambia su probabilidad y
recupera 5% del maná máximo. Un tick sin maná que recuperar no entrena.

Armas, Wrestling y Proyectiles afectan impacto y entrenan en NPC/PvP. Los arcos
consumen munición y requieren línea de visión. Tácticas y Defensa actúan al
recibir ataques; Defensa requiere escudo equipado. Apuñalar usa arma apta,
clase/umbral y curvas del original. Se conservan los críticos propios y buffs.
Robustez reduce hasta 10% del daño físico restante; Agilidad (habilidad) añade
hasta diez puntos porcentuales a la evasión, independientemente del atributo.

Todas las clases propias pueden equipar objetos. Todas pueden intentar robar oro;
el Ladrón también puede robar objetos permitidos. Ocultarse tiene duración y
cancelación persistidas, independientes de Invisibilidad. Supervivencia permite
evaluar criaturas o encender una fogata con tres leñas. Domar usa Carisma × Domar,
el umbral `domable` del NPC y una probabilidad de 1/5; la propiedad permanente,
índices y seguimiento sobreviven al reinicio. El máximo propio es tres mascotas,
con hasta dos del mismo tipo. Las invocaciones temporales conservan su expiración.

Navegación valida el barco real, la costa y el requisito por clase; la apariencia
y el movimiento acuático se restauran al reconectar. Crear party exige Carisma ×
Liderazgo ≥ 100; fundar clan requiere Liderazgo 90 además del nivel previo 13.

Hay 87 recetas únicas de herrería, 34 de carpintería y tres de fundición. Los
materiales usan objetos reales y pueden apilarse hasta 10.000 para cubrir sus
costes. La fabricación valida habilidad, herramienta, taller, materiales y
capacidad; consumo, producto y entrenamiento se confirman en una operación.
Los 20 talleres originales provienen de los objetos `.inf`, ausentes del antiguo
extractor de capas `.map`. Su catálogo TOML repara también cachés existentes.

Las nuevas consultas/acciones usan cliente 251 y servidor 255, versión 1,
negociadas con capacidad 256. Los paquetes clásicos de trabajo, ataque y uso
comparten el mismo servicio y cadencia. No se aceptan XP, nivel ni resultados
declarados por el cliente. Los reintentos mantienen una identidad estable.

## Magia y validación

El catálogo conserva 45 hechizos: 35 utilizables y diez reservados con requisito
101. Los reservados siguen rechazados. Magia entrena después de un lanzamiento
confirmado; FX usan el CharIndex real y WAV las coordenadas del objetivo. Ambos
se publican a los observadores. `SET_INVISIBLE=true` oculta; resurrección y
mimetismo conservan la visibilidad correspondiente. Invocar Mascota reserva una
casilla libre junto al dueño antes del commit.

`./scripts/checks.sh --coverage` comprueba reglas, migración, economía, combate,
concurrencia, reintentos y protocolo. El cliente contiene escenarios reproducibles
`--scenario skills` (22 habilidades, reconexión y reinicio) y `--scenario spells`
(45 hechizos, cuadros y audio en dos Godot gráficos), documentados en su
`docs/MECANICAS_AO.md`. Son regresiones de desarrollo: una nueva aprobación R10
prolongada y la publicación del Snap requieren su procedimiento de distribución.
