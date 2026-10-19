# Política de NPC del mundo

Las apariciones fijas conservan mapa, especie y cantidad. Se revisaron individualmente 12 tiles bloqueados y tres sin acceso cardinal; los desplazamientos de uno o dos tiles están registrados en `npc-spawn-corrections.json`. No se desactiva ninguna comprobación del auditor.

`heading` explícito prevalece sobre `direction`; sólo se aceptan 1..4 y el valor ausente es Sur (3).

Las plantillas con `behavior.respawn = 1` declaran un intervalo de 60–120 segundos; el booleano nunca representa segundos. Las zonas aleatorias tienen su propio cooldown de 60 segundos desde la muerte y son el único responsable de reponer sus NPC. Las mascotas domesticadas sobreviven al reinicio y no pasan por la reposición de criaturas salvajes. Las invocaciones mantienen su vencimiento propio.

Las voces se recuperan por coincidencia de ID **y nombre** con NPCs.dat de AO 0.13.3, manteniendo Snd1/2/3 y sus huecos. Cada apariencia documenta su procedencia o silencio intencional. El Guardia Real propio con ID 3 no hereda la voz del Cerdo original. La única sustitución de recurso es el daño del Kraken 610: 174 no existe en este cliente y se usa 175, la voz de la misma criatura ya distribuida. Su muerte también conserva 175. No se añade audio de procedencia desconocida.

Los guardias tienen rol explícito y facción real o caos. Defienden un radio Manhattan de ocho tiles desde su puesto, el mismo mapa y regresan al puesto al perder objetivo. Atacan criminales o afiliados a la facción opuesta y criaturas hostiles sin propietario; no atacan neutrales, guardias, mascotas ni invocaciones. Mantienen cadencia/daño del catálogo. No conceden XP a observadores por sus bajas. Esta política no habilita PvP entre jugadores dentro de una ciudad segura.
