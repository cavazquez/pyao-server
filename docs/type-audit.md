# Alcance del tipado (#370)

La ejecución `mypy src tests` controla el servidor. La ampliación histórica a `mypy .` encontró 145 errores en 13 utilidades sin cambios respecto de main. El inventario reproducible con línea, categoría y decisión por archivo está en [type-audit.json](type-audit.json).

Las utilidades de benchmarks, regeneración de catálogos, diagnóstico de skills, verificación de Snap y análisis de pruebas se conservan y se corrigen por archivo. Las dos pruebas manuales de la raíz tienen imports históricos: deben portarse o sustituirse por una regresión aislada equivalente antes de retirarlas. No se usa su estado para afirmar que todo el repositorio pasa mypy.

CI mantiene `mypy src tests` y agrega `mypy --config-file mypy-tools.ini` para las herramientas nuevas de esta fase. La lista de archivos es explícita y crecerá cuando se resuelva cada dependencia. No se añade una exclusión global de runtime ni `ignore_errors` a módulos nuevos. Los analizadores antiguos de `tools.*` conservan su exclusión previa en el chequeo general; el control independiente no hereda esa exclusión.

Cada tarea debe conservar la conducta de la herramienta, ejecutar una muestra con fuentes temporales o Redis descartable y pasar tipado estricto antes de sumarse a CI. Las dependencias y sus enlaces se agregan al inventario tras crearlas.
