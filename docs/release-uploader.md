# Publicación: visibilidad del borrador

`tools/github_release_upload.py stage` crea como máximo un borrador por ejecución.
Después de crearlo, consulta su visibilidad durante **60 segundos como máximo**,
contando el tiempo de las peticiones HTTP y de las pausas. Las pausas son de
1, 2, 4 y luego 5 segundos, recortadas al tiempo restante. El endpoint de tag y
la lista autenticada paginada comparten el presupuesto de cada consulta.

Sólo una consulta exitosa sin la release esperada permite seguir esperando.
Un error de permisos, transporte, formato o duplicación detiene la operación.
Cuando aparece el borrador se verifican inmediatamente el tag, las propiedades,
los nombres, los tamaños y los SHA256 de los assets existentes. No se espera a
que un contenido incompatible cambie por sí solo. Tampoco se repite la creación
cuando su respuesta se pierde: se comprueba el resultado dentro del mismo plazo.
Si falla la creación y no aparece el borrador, se conservan ambos diagnósticos.

Los borradores parciales se completan sólo con los assets faltantes. No se usa
`--clobber`, no se borran borradores ni assets para recuperarse de un fallo y las
releases públicas continúan siendo de sólo verificación. `--dry-run` no crea
recursos ni entra en la espera de un borrador nuevo.

Con `--receipt`, el JSON conserva `draft_visibility`, con número de intento,
tiempo transcurrido y estado (`missing`, `visible` o `failed`). Si hay un error
de consulta, se registra su mensaje. Cada intento también se imprime en stderr
para conservarlo en Actions aunque la ejecución se interrumpa. El workflow de
release sigue guardando esos recibos con `if: always()`.

## Prueba real del publicador

El workflow manual **Release uploader smoke**, ejecutado desde `main`, usa el
`GITHUB_TOKEN` de Actions con `contents: write`. Crea un tag temporal único de
versión `0.0.0rc…` para esa ejecución y un único borrador. Sube únicamente una
fixture de texto con su manifiesto y sus hashes, descarga los tres archivos,
verifica sus SHA256 y deja un recibo del resultado y de cada consulta.

El borrador nunca se publica. Al terminar se eliminan exclusivamente el borrador
y el tag de esa fixture, después de comprobar su identidad, commit, notas,
assets y condición de borrador. Si el tag se movió o el recurso es público o
ajeno, se conserva y la prueba falla. También se verifica la ausencia final de
ambos recursos. El artefacto `release-uploader-smoke-<run_id>-<attempt>` conserva
los recibos y los bytes pequeños de prueba durante 14 días, incluso si falla.

Esta comprobación no construye ni publica paquetes del juego, no cambia los
canales de Snap ni modifica tags o releases de producto. Las pruebas unitarias
complementan el workflow con demoras deterministas, ausencia persistente,
errores de consulta y protección de recursos ajenos durante la limpieza.
