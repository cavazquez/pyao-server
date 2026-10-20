# Magia ampliada

Cliente y servidor se distribuyen con la misma versión. No se exige compatibilidad
con clientes de versiones anteriores durante esta etapa previa a producción.

Los componentes son objetos reales del inventario, con cantidades enteras y sin
consumir equipo puesto. Se descuentan en el mismo EXEC que maná, energía y efecto.
Un rechazo no cobra materiales ni entrena magia.

El área se centra en el tile indicado: radio 1–4, cuadrado o rombo, hasta 16
objetivos únicos. El catálogo elige jugadores, NPCs o ambos. El servidor revalida
posición, vida, alcance y PvP de cada candidato. Un área sin blancos no cuesta.
La transacción incluye todos los resultados; sólo cobra y entrena una vez.

Los pulsos nuevos afectan jugadores. Hay un pulso de daño y otro de curación
como máximo; reaplicar el mismo modo reemplaza su magnitud y vencimiento.
Intervalo 1–60 s, duración hasta 600 s y magnitud hasta 5000. GameTick comparte
el trabajo con los efectos existentes; no se crean timers por hechizo. El veneno
mantiene su mecanismo propio y no se registra como un segundo pulso genérico.
Durante desconexión no hay pulsos ni cobro retroactivo. La duración es absoluta:
tras reiniciar se retoma un efecto aún vigente sin recuperar pulsos perdidos.
Entrar en una zona segura suprime el daño periódico. La autorización PvP se
comprueba al lanzar; el efecto confirmado dura hasta su vencimiento aunque el
lanzador se desconecte. Disipar y morir cancelan ambos modos.

Las barreras afectan jugadores: capacidad máxima 10000 y duración máxima 600 s.
Se especifican tipos `physical`, `magic`, `periodic` y `poison`. Reaplicar reemplaza
la protección. Daño de NPC, PvP, hechizos, veneno y pulsos consume la capacidad
atómicamente con el HP. Expiración, disipación y muerte la dejan en cero.

Entre clanes, una alianza o el mismo clan bloquean ataques hostiles. Una guerra
permite combatir fuera de zonas seguras aunque el seguro esté activado. Terminar
la guerra restablece el consentimiento bilateral normal. Ninguna declaración
habilita ataques en ciudades. Pertenencia y relación se observan en el commit.
