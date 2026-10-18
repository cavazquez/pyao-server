# Presupuesto de conversación (#140)

Cada jugador comparte un token bucket entre TALK, YELL, WHISPER y PARTY_MESSAGE.
El burst es de cinco mensajes, con reposición de uno por segundo mediante reloj
monotónico. Reconectar no entrega otra cuota: el contenedor comparte el presupuesto
entre factories/handlers. El límite de texto es 512 bytes Latin-1 por mensaje.
Clan y otros canales que pasan por TALK consumen la misma cuota.

El filtro se aplica después del framing/validación y antes de construir el handler:
un mensaje limitado no consulta posición, destinatario ni grupo y no se publica.
Como máximo se emite un aviso por jugador cada cinco segundos. No se guardan textos,
nombres ni contraseñas. Entradas inactivas vencen a los cinco minutos y la cantidad
de entradas tiene un límite de 10000.

PING, QUIT, cierre de comercio y comandos GM siguen sus rutas independientes.
En TALK se exceptúan exclusivamente METRICS, SALIRCLAN, RECHAZARCLAN y LIBERAR;
la autorización administrativa de METRICS y GM sigue siendo obligatoria. Un slash
arbitrario, prefijos parecidos o un espacio inicial no crean una excepción. El
límite de longitud también se aplica a los comandos exceptuados.

Los tests simulan reposición/fronteras, usuarios y canales independientes, reconexión,
longitud, avisos y dos factories compartiendo el mismo presupuesto, sin sleeps reales.
