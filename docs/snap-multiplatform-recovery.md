# Recuperación del ajuste Snap local (#119)

Se inspeccionó el contenido de `snap/snapcraft.yaml` del stash
`64410a9d5aad98070c5afccb06eab9f81908b192` sin aplicarlo ni eliminarlo.
Su intención era declarar amd64, arm64, armhf y riscv64. También contenía
configuración antigua que fue reemplazada por trabajos ya fusionados: plugin
Python sin lock, variables de entorno anteriores y copia duplicada de recursos.

La receta vigente conserva el empaquetado con `uv.lock`, Python 3.14 de core26,
las variables `PYAO_`, configuración en SNAP_USER_COMMON y datos persistidos en
Redis. No se recupera la configuración obsoleta del stash.

Arquitecturas declaradas: amd64 y arm64. Cada una se construye e instala en su
runner nativo mediante Server Snap. El script rechaza una arquitectura distinta
del host. La prueba instalada recorre recursos, TLS, Redis y reinicio, y conserva
la procedencia junto con SHA256 del paquete exacto. Construir no autoriza publicar.

armhf y riscv64 se excluyen explícitamente de esta versión: no hay un runtime uv
fijado con SHA256 ni runner nativo de aceptación en este proyecto para ellas.
Para incorporarlas se requiere primero agregar ambas piezas y demostrar la
instalación con Redis; no basta declarar la arquitectura en YAML.

Los resultados de construcción e instalación se incorporan al expediente de la
entrega. Este documento registra la decisión de recuperación; no afirma que un
artefacto aún no construido esté verificado.
