# Estado de PyAO Server y cliente Godot

Inspección del **18 de octubre de 2026**. Alcance y orden vigentes: [Versión 1.0 de ProyectoAO](ALCANCE_1_0.md), seguimiento en [servidor #123](https://github.com/cavazquez/pyao-server/issues/123).

## Versiones observadas

- Servidor: `pyproject.toml` declara **0.10.0-alpha**, Python `>=3.14` y dependencias gestionadas con **uv**.
- Revisión del servidor inspeccionada: `8204c732e517b598f14ce89a2983934c12fa2e39`.
- Revisión del cliente inspeccionada: `5e6181e88f42e8b13c2328d5a958cff017f58071`.
- Cliente: `project.godot` declara **4.5 / GL Compatibility**. La versión mantenida exacta del motor y sus templates se valida en [cliente #10](https://github.com/cavazquez/ArgentumOnlineGodot/issues/10).

La versión declarada del paquete o del proyecto Godot no acredita compatibilidad de extremo a extremo. La 1.0 se aprueba con las comprobaciones del documento de alcance.

## Sistemas presentes en el código

El servidor contiene alta y autenticación, mapas/NPCs, clases, inventario, banco, comercio, combate, magia, habilidades, mascotas, tala/minería/pesca, party y clanes. Party y clan tienen operaciones disponibles mediante comandos; sus paneles nuevos no son condición para conservar esas funciones.

El cliente contiene las pantallas y lectores/writers de base. La integración requiere las correcciones de protocolo, seguridad, inventario y UI seleccionadas en el alcance. Los ports de Hide Zone se adaptan al contrato y los datos propios de pyao.

## Bloqueos conocidos

- [Servidor #109](https://github.com/cavazquez/pyao-server/issues/109) y [#110](https://github.com/cavazquez/pyao-server/issues/110): recuperar tipos y aislar el bloqueo de inicialización en pruebas.
- [Servidor #86](https://github.com/cavazquez/pyao-server/issues/86): aislamiento de handlers y sesión por conexión.
- [Servidor #94](https://github.com/cavazquez/pyao-server/issues/94), [#95](https://github.com/cavazquez/pyao-server/issues/95), [#96](https://github.com/cavazquez/pyao-server/issues/96) y [cliente #4](https://github.com/cavazquez/ArgentumOnlineGodot/issues/4): contrato y reconstrucción de mensajes TCP.
- [Servidor #126](https://github.com/cavazquez/pyao-server/issues/126): el builder de habilidades y el reader del cliente consumen tamaños y semánticas diferentes.
- [Cliente #1](https://github.com/cavazquez/ArgentumOnlineGodot/issues/1), [#2](https://github.com/cavazquez/ArgentumOnlineGodot/issues/2) y [#3](https://github.com/cavazquez/ArgentumOnlineGodot/issues/3): secretos en logs/disco y verificación TLS.
- [Servidor #124](https://github.com/cavazquez/pyao-server/issues/124) y [cliente #54](https://github.com/cavazquez/ArgentumOnlineGodot/issues/54): el targeting requiere un formato inequívoco; no está resuelto sólo por tener coordenadas en el parser.

La lista completa de bloqueantes y su orden está en `ALCANCE_1_0.md`.

## Calidad y aprobación

No se declara aquí una suite completa aprobada ni una cobertura vigente. Para el candidato se guardan fecha, commits, versiones, comandos y resultados de lint, formato, tipos, pruebas e integración real. Los resultados históricos no sustituyen esa ejecución.

El cierre exige los requisitos R01 a R10 del alcance, incluidos dos clientes Godot reales, persistencia/restauración y ejecución desde los paquetes instalados. Los tests de protocolo con dos scripts cubren una capa distinta del recorrido del cliente.

## Historial

El [estado del 26/05/2026 conservado en 8204c732](https://github.com/cavazquez/pyao-server/blob/8204c732e517b598f14ce89a2983934c12fa2e39/docs/development/ESTADO_ACTUAL.md) documenta refactors y avances anteriores. Sus números de tests, cobertura y afirmaciones de completitud son históricos.
