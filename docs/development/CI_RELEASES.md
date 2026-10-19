# CI y publicación en GitHub

Los PR y pushes a main/develop ejecutan Ruff, formato, mypy, 2.687 pruebas con
cobertura mínima del 79%, integración con Redis descartable, recuperación,
metadatos de distribución y enlaces Markdown. El check `test` exige éxito de
todos esos grupos. No produce wheels, sdists ni Snaps en esos eventos.

`Seguridad y workflows` añade actionlint/ShellCheck y tests de las puertas de
release; revisa nuevas dependencias vulnerables en los PR y audita todas las
versiones de uv.lock, incluidas herramientas de desarrollo, con pip-audit.
Las revisiones programadas corren el 1 de diciembre de cada año a las 10:00 de Argentina (13:00 UTC). CodeQL y secret scanning siguen activos.
Dependabot revisa uv, Actions y el validador de enlaces npm sólo ese día. Los enlaces usan Node 24 y npm ci con lockfile; npm audit rechaza vulnerabilidades altas y críticas.

## Crear una nueva entrega, cuando esté autorizada

1. Fusionar los commits de ambos proyectos, comprobar CI y usar la misma versión
   en pyproject.toml y project.godot. Crear el mismo tag `v<VERSION>` en los dos
   repositorios. Crear un tag no compila ni publica archivos automáticamente.
2. Ejecutar `CI` manualmente **sobre ese tag** con `build_packages=true`: además
   de los chequeos normales genera wheel y sdist y valida su instalación aislada.
3. Ejecutar `Server Snap` manualmente **sobre el mismo tag** para amd64 y arm64.
   Los paquetes deben pasar instalación, TLS y reinicio con Redis descartable.
4. Ejecutar `Release GitHub` sobre main con tag, ID de CI e ID de Server Snap.
   No compila. Exige ejecuciones manuales completas del mismo commit fusionado,
   wheel instalado y validado, ambas arquitecturas, procedencia limpia, hashes
   y versión igual al tag del cliente. Conserva nombres instalables del backend.
5. Por defecto prepara un borrador con wheel, sdist, dos Snaps, manifiesto y
   SHA256SUMS. Descarga y verifica todos los assets. `publish=true` permite hacer
   pública la release nueva después de esa verificación. Completar los dos
   borradores antes de publicar la pareja; para borradores ya preparados usar
   GitHub/CLI tras revisarlos. No hay transacción atómica entre repositorios.

Los artefactos de compilación duran siete días. Un artefacto vencido requiere una
nueva compilación autorizada. Se rechazan commits, versiones, hashes o jobs que
no coincidan, y releases existentes; no se sobreescriben assets públicos. Un fallo
de subida deja un borrador para inspección y recuperación manual.

Las RC siguen siendo prereleases. GitHub no las devuelve en `/releases/latest`;
para una RC usar el enlace explícito del README o el listado de releases. Las
entregas estables sí actualizan latest al publicarse.

La Store se publica por el proceso coordinado de aceptación de ambos repositorios;
ninguno de estos workflows promueve automáticamente canales Snap.
