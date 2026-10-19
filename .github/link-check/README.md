# Herramientas de enlaces de CI

`npm ci --ignore-scripts` instala exclusivamente el lockfile. `npm audit` rechaza
vulnerabilidades altas y críticas; Dependabot revisa este manifiesto el 1 de diciembre de cada año.

Se fuerza basic-ftp 6.2.3 mediante una dependencia directa y un override que la
referencia. get-uri todavía solicita la serie 5, vulnerable a
[GHSA-c475-qrg2-pj4r](https://github.com/advisories/GHSA-c475-qrg2-pj4r); la corrección
empieza en 6.2.1. La verificación del README y los índices usa HTTP(S) y archivos
locales. Retirar el override cuando la cadena de dependencias adopte la versión
corregida por sí misma.
