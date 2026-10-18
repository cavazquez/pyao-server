# Backlog de PyAO Server y cliente Godot

Actualizado el **18 de octubre de 2026**. La selección para la primera versión pública está en [Alcance de la versión 1.0 de ProyectoAO](../development/ALCANCE_1_0.md), definido en el [issue #123](https://github.com/cavazquez/pyao-server/issues/123).

## Trabajo requerido para la 1.0

Usar las fases, enlaces y pruebas observables del documento de alcance. Incluye los P1 abiertos de ambos repositorios y sus dependencias; no hace falta implementar todo el backlog para aprobar esa versión.

- [Issues del servidor](https://github.com/cavazquez/pyao-server/issues): estado y criterios de cada cambio de backend, protocolo, datos y operación.
- [Issues del cliente](https://github.com/cavazquez/ArgentumOnlineGodot/issues): estado y criterios de UI, transporte, Godot y distribución.
- [Estado observado](../development/ESTADO_ACTUAL.md): versiones declaradas y bloqueos conocidos.

La etiqueta de prioridad de un issue indica urgencia. Su presencia en las fases de `ALCANCE_1_0.md` determina si bloquea esta versión.

## Funciones existentes que se conservan

El servidor ya contiene sistemas de clases, party, clanes mediante comandos, banco, comercio, combate, magia, mascotas y trabajos. Tener modelos, servicios o tests unitarios no acredita su recorrido completo desde Godot. Las pruebas conjuntas del alcance cubren esos flujos y las correcciones necesarias para conservarlos.

El targeting con coordenadas requiere alinear formato/framer y cliente en [servidor #124](https://github.com/cavazquez/pyao-server/issues/124) y [cliente #54](https://github.com/cavazquez/ArgentumOnlineGodot/issues/54). La lógica parcial actual no permite tratarlo como una tarea exclusiva de UI.

## Opciones posteriores

Las listas de issues pospuestos se mantienen en el documento de alcance. Los siguientes documentos conservan detalles e ideas de dominio y no agregan requisitos de cierre:

- [Características de VB6](TODO_CARACTERISTICAS_VB6.md).
- [Party Finder](TODO_PARTY_FINDER.md).
- [Arquitectura](TODO_ARQUITECTURA.md).
- [Cliente](TODO_CLIENTE.md).
- [Items](ITEMS_SYSTEM_TODO.md).

## Cómo actualizar el backlog

Al resolver un issue, adjuntar la evidencia de sus criterios y ejecutar la regresión que afecte. Para agregar una funcionalidad a la 1.0, actualizar explícitamente el documento de alcance y comprobar que sus dependencias siguen dentro del plan y sin ciclos.

Las cantidades de tests, cobertura y resultados de lint/tipos se registran con fecha y revisión probada. No se trasladan desde documentos históricos como si describieran el candidato actual.

## Historial

El [TODO consolidado anterior en 8204c732](https://github.com/cavazquez/pyao-server/blob/8204c732e517b598f14ce89a2983934c12fa2e39/docs/todo/TODO_CONSOLIDADO.md) conserva el detalle previo. Los [completados históricos](TODOS_COMPLETADOS.md) no sustituyen las pruebas de integración de la versión actual.
