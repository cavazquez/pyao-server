# Canales del par PyAO

Estado: preparación de Homebrew, APT y WinGet para RC5. Microsoft Store queda
aplazada por decisión del mantenedor. Las recetas todavía no acreditan un canal
publicado: los indicadores se cambian sólo después de verificar la publicación.

## Candidatos y procedencia

`tools/package_channels.py server` copia el Python administrado por uv a un
directorio privado e instala los paquetes exportados del lock, con sus hashes,
y el wheel del servidor. Windows incorpora un pequeño lanzador C; Unix usa un
lanzador que conserva argumentos, aísla las importaciones y no escribe bytecode
en la instalación. Se incluyen licencia, recursos, dependencias de escritorio
y puente de bandeja Linux. No se requiere Python del operador y no se instala
ni inicia Redis.

`validate-server` copia el árbol a un directorio con espacios fuera del checkout
y prueba versión, ayuda, recursos e importación desde el Python privado.
`integration-world.py --wheel WHEEL --server-bundle CANDIDATO` verifica todos sus
archivos y enlaces antes de ejecutar el servidor y los dos clientes por TLS.
El recibo registra el hash del candidato, wheel y ambos commits. El trabajador
usa `-B` para evitar modificar la instalación mientras la prueba.

`seal-server` requiere las dos evidencias anteriores del mismo candidato limpio.
Preserva enlaces y permisos en el ZIP. La promoción reutiliza estos archivos;
no recompila ni vuelve a instalar dependencias durante la publicación.

## Instaladores

- Homebrew: fórmula del servidor y cask del cliente para macOS ARM64 y x86_64.
  El tap previsto es `cavazquez/homebrew-pyao`. La fórmula usa el runtime privado.
  El cliente conserva la firma ad hoc de su export; esta entrega no acredita
  notarización ni aceptación automática de la cuarentena de Internet.
- Debian: `pyao-server` y `pyao-client` para AMD64 y ARM64, comprobados en Ubuntu
  24.04 y Debian Trixie. La versión de producto `1.0.0rc5` se representa como
  `1.0.0~rc5`, para que dpkg ordene la candidata antes de `1.0.0` final. Los
  programas se instalan bajo `/opt`, los lanzadores e iconos bajo `/usr`, y la
  configuración y preferencias permanecen en sus directorios de usuario.
  El servidor incluye una unidad systemd **de usuario**, sin habilitarla ni
  iniciarla. La biblioteca del indicador se recomienda; no es requisito del CLI.
- WinGet: ZIPs portables con identificadores `Cavazquez.PyAOServer` y
  `Cavazquez.PyAOClient`, versión común y SHA256 de las releases inmutables.
  Los manifiestos usan el esquema 1.10.0 y se validan con WinGet en el runner.

Las pruebas de instaladores usan una revisión anterior **del empaquetado de los
mismos bytes aprobados**. No se presentan como compatibilidad con una versión
anterior del juego. Instalan, actualizan, abren y desinstalan; comprueban la
conservación de configuración y un marcador en el `options.cfg` real del cliente.
Las pruebas completas del par comprueban preferencias, gráficos, audio, entrada
y login de esos mismos ejecutables. Homebrew/WinGet sustituyen solamente la URL
de descarga por una fixture local con el mismo SHA256 antes de que exista una
release pública. Esos manifiestos de prueba nunca se publican.

## Repositorio y promoción

`tools/channel_repository.py prepare --plan PLAN.json --output DESTINO` requiere
los cinco portables nativos de cada proyecto, los cuatro paquetes Debian y cinco
pruebas de instalación: dos APT, dos Homebrew y una WinGet. Todas deben compartir
versión y commits, referenciar los mismos archivos y aprobar instalación,
actualización, desinstalación y conservación de configuración/preferencias.

El plan enumera `version`, `sources` (`server` y `client` con SHA completos),
`server` y `client` (listas de manifiestos sellados), `debs` (cuatro manifiestos
con instalación verificada) y `checks` (las cinco evidencias de instaladores).
Las rutas se interpretan desde el directorio del plan. `prepare` genera las
recetas Homebrew/WinGet, los assets de producto y un índice APT plano; no publica.

APT usa assets de GitHub Releases para evitar el límite de tamaño de archivos
Git. Los paquetes aprobados se conservan en la release inmutable de producto;
el índice del canal se promueve en la release `apt-edge` del tap. `sign-apt`
requiere una huella completa y un almacén GPG explícito; genera clave pública,
`Release.gpg` e `InRelease`. La clave privada no entra al repositorio ni a los
artefactos. La comprobación de firma y una instalación desde el repositorio
publicado preceden al cambio del indicador APT.

Después de probar el par y publicar las releases coordinadas se publican el tap,
el repositorio APT firmado y las propuestas WinGet. Los enlaces y estados reales
quedan en sus issues. Microsoft Store y las botas permanecen pendientes.

## Servicio Debian opcional

El usuario puede preparar `~/.config/pyao-server/service.env` con
`PYAO_SERVER_ARGS`, certificados TLS y referencias a su configuración Redis.
La unidad escucha en loopback por defecto. Después de configurar esos valores:

```sh
systemctl --user daemon-reload
systemctl --user enable --now pyao-server
```

La instalación del paquete por sí sola no ejecuta esos comandos. El indicador de
escritorio y la unidad opcional son mecanismos independientes de inicio; ambos
utilizan el CLI y las rutas persistentes del usuario.

Referencias de formato y publicación:
[Homebrew](https://docs.brew.sh/Formula-Cookbook),
[casks](https://docs.brew.sh/Cask-Cookbook),
[WinGet](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest),
[Debian Python Policy](https://www.debian.org/doc/packaging-manuals/python-policy/).
