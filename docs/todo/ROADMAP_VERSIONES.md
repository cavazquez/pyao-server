# Roadmap de PyAO Server y cliente Godot

Actualizado el **18 de octubre de 2026** mediante el [issue #123](https://github.com/cavazquez/pyao-server/issues/123).

El roadmap vigente es [Alcance de la versión 1.0 de ProyectoAO](../development/ALCANCE_1_0.md). Ese documento define los requisitos observables, los issues bloqueantes y su orden para el servidor y el cliente. Es la referencia para decidir cuándo está terminada la primera versión pública.

## Versión actual y objetivo

`pyproject.toml` declara **0.10.0-alpha**. La declaración identifica el paquete; no acredita que el cliente y servidor hayan pasado juntos las pruebas de la 1.0.

La 1.0 inicial incluye cliente nativo Linux amd64, servidor con uv y Redis persistente, cuentas, mapas y recursos propios, inventario de 30 slots, economía, combate PvE, magia, progresión y funciones sociales existentes. Se valida con dos clientes Godot reales y una instalación Snap `pyao-client` en `latest/edge`.

## Secuencia de trabajo

1. Recuperar comprobaciones y validar motor/datos.
2. Cerrar infraestructura, sesiones, autenticación y persistencia.
3. Alinear contrato binario, framing y primer recorrido conjunto.
4. Confirmar inventario, banco y comercio sin pérdidas ni duplicaciones.
5. Completar combate, magia y progresión.
6. Cerrar cuentas, comunidad y controles de interfaz.
7. Ejecutar integración completa y validar distribución instalada.

Los números de issue, las dependencias y las pruebas de salida de cada fase se mantienen únicamente en [ALCANCE_1_0.md](../development/ALCANCE_1_0.md).

## Después de la 1.0

Misiones, facciones, PvP físico nuevo, crafting, diplomacia/depósito de clan, Party Finder, nuevos paneles sociales, web/WSS, efectos visuales adicionales y otras plataformas quedan fuera del cierre inicial. Las funciones que ya existen se conservan aunque su interfaz nueva se posponga.

Los issues posteriores permanecen abiertos como opciones. No se convierten automáticamente en requisitos y no tienen una versión ni fecha de entrega comprometida.

## Historial

El [roadmap anterior, conservado en el commit 8204c732](https://github.com/cavazquez/pyao-server/blob/8204c732e517b598f14ce89a2983934c12fa2e39/docs/todo/ROADMAP_VERSIONES.md), contiene la planificación histórica 0.6–0.20. Sus versiones futuras, estimaciones y cifras de calidad no describen el estado actual ni son condiciones de la 1.0.
