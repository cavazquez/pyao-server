# PyAO Server

<p align="center">
  <img src="data/desktop/icons/pyao-server-128.png" alt="Icono de PyAO Server" width="160" height="160">
</p>

<p align="center">
  <a href="https://github.com/cavazquez/pyao-server/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/cavazquez/pyao-server/ci.yml?branch=main&amp;label=CI&amp;logo=github" alt="CI del servidor"></a>
  <a href="https://github.com/cavazquez/pyao-server/actions/workflows/release.yml"><img src="https://img.shields.io/github/actions/workflow/status/cavazquez/pyao-server/release.yml?label=Release&amp;logo=github" alt="Workflow de Release"></a>
  <a href="https://github.com/cavazquez/pyao-server/releases"><img src="https://img.shields.io/github/v/release/cavazquez/pyao-server?include_prereleases&amp;sort=date&amp;label=release" alt="Última release, incluidas versiones de prueba"></a>
  <a href="https://github.com/cavazquez/pyao-server/releases"><img src="https://img.shields.io/github/downloads/cavazquez/pyao-server/total" alt="Descargas de GitHub Releases"></a>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/docs-referencia-007ec6?logo=readthedocs&amp;logoColor=white" alt="Documentación del servidor"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.14%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.14 o superior"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/cavazquez/pyao-server" alt="Licencia Apache 2.0"></a>
</p>

<p align="center">
  <a href="https://snapcraft.io/pyao"><img src="https://img.shields.io/snapcraft/v/pyao/latest/edge?arch=amd64&amp;label=snap%20edge&amp;logo=snapcraft" alt="Versión de pyao en Snap latest/edge para amd64"></a>
  <a href="https://github.com/cavazquez/homebrew-pyao#macos-homebrew"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcavazquez%2Fhomebrew-pyao%2Fmain%2Fchannel-manifest.json&amp;query=%24.version&amp;label=homebrew&amp;logo=homebrew&amp;color=FBB040" alt="Versión publicada mediante Homebrew para macOS Intel y Apple Silicon"></a>
  <a href="https://github.com/cavazquez/homebrew-pyao#debian-y-ubuntu-apt-firmado"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcavazquez%2Fhomebrew-pyao%2Fmain%2Fchannel-manifest.json&amp;query=%24.version&amp;label=apt&amp;logo=debian&amp;color=007ec6" alt="Versión publicada en APT firmado para amd64 y arm64"></a>
  <a href="https://github.com/cavazquez/pyao-server/issues/366"><img src="https://img.shields.io/badge/Microsoft%20Store-pendiente-lightgrey" alt="Microsoft Store pendiente de evaluación: issue 366"></a>
  <a href="https://github.com/microsoft/winget-pkgs/pull/458433"><img src="https://img.shields.io/badge/winget-en%20revisi%C3%B3n-lightgrey" alt="Propuesta WinGet en revisión: Cavazquez.PyAOServer"></a>
</p>

<p align="center">
  <a href="https://codecov.io/gh/cavazquez/pyao-server"><img src="https://codecov.io/gh/cavazquez/pyao-server/branch/main/graph/badge.svg" alt="Cobertura de tests"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://deepwiki.com/cavazquez/pyao-server"><img src="https://img.shields.io/badge/DeepWiki-consultar-blue" alt="Consultar DeepWiki"></a>
</p>

<p align="center">
  <a href="https://github.com/cavazquez/pyao-server">Proyecto</a> ·
  <a href="docs/README.md">Documentación</a> ·
  <a href="https://github.com/cavazquez/pyao-server/releases">Releases</a>
</p>

Homebrew y APT enlazan sus instrucciones de instalación verificadas. WinGet enlaza su propuesta en revisión; Microsoft Store sigue pendiente.

Instalación y actualización: [Homebrew, APT firmado y estado de WinGet](https://github.com/cavazquez/homebrew-pyao#readme).

Servidor de Argentum Online implementado en Python 3.14+ con asyncio.

Descargas de pruebas: **[releases del servidor](https://github.com/cavazquez/pyao-server/releases)** y **[releases del cliente](https://github.com/cavazquez/ArgentumOnlineGodot/releases)**. Instalar la misma versión en ambos. GitHub excluye las prereleases de `/releases/latest`; los indicadores superiores incluyen las RC publicadas.

Los PR ejecutan validaciones, pruebas y controles de dependencias sin construir
distribuciones. Compilar y publicar son operaciones manuales separadas; ver
[CI y releases](docs/development/CI_RELEASES.md).

> Implementación moderna y eficiente del servidor de Argentum Online.

Índice de toda la documentación interna: **[docs/README.md](docs/README.md)**.

**Próximo objetivo:** [alcance de la 1.0 de servidor y cliente](docs/development/ALCANCE_1_0.md), definido en el [issue #123](https://github.com/cavazquez/pyao-server/issues/123). Allí están los requisitos, el orden de los issues y las pruebas para aprobar una versión conjunta.

## Ejecutar desde fuentes

Se necesitan Python 3.14, uv y Redis configurado con autenticación y persistencia.
El cliente Godot se conecta al servidor; no necesita Redis local.

```sh
uv python install 3.14
uv sync --locked
uv run --locked pyao-server --version
uv run --locked pyao-server --help
```

`--version` y `--help` funcionan sin Redis y sin cargar la partida. Para preparar
una instancia nueva, seguir la [guía de Redis](docs/guides/REDIS.md); no reemplazar
la configuración de una instancia existente con una contraseña generada de nuevo.

Configurar el endpoint y un archivo privado con la contraseña:

```sh
export PYAO_REDIS__HOST=127.0.0.1
export PYAO_REDIS__PORT=6379
export PYAO_REDIS__PASSWORD_FILE=/ruta/privada/redis-password
uv run --locked pyao-server --ssl --host 127.0.0.1 --port 7666
```

Para otros equipos se debe configurar la dirección de escucha y la confianza del
certificado TLS en el cliente. Las opciones `--ssl-cert` y `--ssl-key` permiten
usar un certificado propio; ver [configuración](config/server.toml) y `--help`.

## Configuración vigente

La configuración vive en el paquete [`src/config/`](src/config/), con modelos
Pydantic/Pydantic Settings. Los valores y límites validados se definen en
[`GameConfig`](src/config/game_config.py); `config/server.toml` es la plantilla
incluida, no una copia de configuración guardada en Redis. Las variables de
entorno usan el prefijo `PYAO_` y `__` para campos anidados.

El CLI permite elegir `--config-file`, `--data-dir`, `--maps-dir` y `--state-dir`.
Sus equivalentes son `PYAO_CONFIG_FILE`, `PYAO_DATA_DIR`, `PYAO_MAPS_DIR` y
`PYAO_STATE_DIR`. Las rutas se resuelven antes de cargar los modelos y servicios.
El inventario propio tiene **30 slots**, definidos por
[`InventoryRepository`](src/repositories/inventory_repository.py).

No usar los antiguos ejemplos `GAME_MAX_INVENTORY_SLOTS`, `src/config.py` ni
configuración basada en dataclasses como instrucciones del runtime actual.

## Qué se guarda en Redis

Redis conserva el estado mutable de la partida: cuentas, personajes, posición,
progreso de habilidades, atributos, inventario y equipo, banco, oro, objetos del
suelo, stock comercial, organizaciones y estados persistentes de NPCs. Los
índices en RAM aceleran las consultas y los broadcasts; no sustituyen la
persistencia de las operaciones confirmadas. Los recibos y transacciones evitan
acreditar dos veces una misma recogida, muerte o intercambio.

Los mapas, sus colisiones y salidas y los catálogos estáticos se distribuyen como
archivos versionados. La geometría se carga en RAM en máscaras compactas y las
entidades activas tienen índices espaciales; caminar no consulta cada casilla
estática en Redis. La distribución incluye `archives/map_data.xz` y el caché
binario verificado: [formato de mapas](tools/compression/map_binary.py).

El esquema vigente de partida es **v6**. Una partida de un esquema anterior no
se migra ni se pisa automáticamente. Antes de actualizar: detener el servidor,
respaldar y verificar Redis y ejecutar el procedimiento explícito correspondiente.
Ver [esquema y migraciones](docs/guides/REDIS.md#esquema-y-migraciones) y
[migración del suelo v5 → v6](docs/operations/redis-ground-layout.md).

## Oro y devaluación

La regla vigente es **1% diario** sobre el saldo alcanzado por la devaluación,
con redondeo e idempotencia definidos en
[`taxes`](src/economy/taxes.py). Afecta al oro transportado,
al banco y al suelo, con el jugador conectado o desconectado. Tirar y recoger
oro no renueva su antigüedad ni evita un descuento pendiente.

No existe una regla de saldo cero a los 90 días. El intervalo corto de trabajo
del efecto sólo procesa vencimientos; no representa un descuento de 1% cada
60 segundos. La opción actual es `game.tax.daily_percentage`;
los ejemplos históricos de `game.gold_decay` no describen esta mecánica.

## Mapas, botín y equipamiento

La revisión versiona decisiones por coordenada, roles de los 290 mapas y los
cruces dirigidos. Las llegadas se validan y reservan antes de confirmar posición
y navegación; los portales sincronizan su colisión en cada entrada. No se
fabrican enlaces inversos ni se despejan paredes para resolver una llegada.

El botín clasifica todo el catálogo y conserva exclusiones explícitas. El nivel
del NPC determina la calidad y el oro; una muerte produce una sola liquidación.
Consultar el [catálogo de botín](docs/catalogs/npc-loot.json) y la
[revisión de rutas](docs/catalogs/world-routes.json).

El ObjType 18 ocupa una sola ranura de accesorio: incluye anillos, instrumentos
mágicos y guantes. Sus efectos se derivan del equipo actual; no se acumulan
modificadores por reconectar o reemplazar objetos. Las botas y su capa gráfica
siguen pendientes de la fase específica acordada con el usuario.

## Instalar y actualizar

El canal publicado de prueba es `latest/edge`:

```sh
sudo snap install pyao --edge
sudo snap install pyao-client --edge
pyao.pyao-server --version
```

Instalar la misma versión de producto en ambos proyectos. La configuración y los
archivos del servidor Snap se conservan en `SNAP_USER_COMMON`; la partida sigue
en Redis. Ver [instalación y actualización Snap](docs/guides/SNAP.md).

Las publicaciones reutilizan artefactos probados del mismo commit, comprueban
sus SHA256 y conservan recibos. El publicador espera automáticamente la
visibilidad de borradores nuevos: [publicación](docs/release-uploader.md).
Los canales Homebrew, APT, WinGet y Microsoft Store siguen su estado real en los
indicadores y issues de la cabecera.

## Desarrollo y pruebas

```sh
uv sync --locked --dev
uv run --locked ruff check src tests
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest tests
python3 -m unittest discover -s tools/tests
```

CI ejecuta calidad, pruebas, integración y recuperación con Redis descartable,
auditoría reproducible de mapas, enlaces y dependencias. La aceptación del par
incluye dos clientes reales, TLS y evidencia gráfica de las mecánicas. Los
recibos distinguen qué se comprobó sobre fuentes, exportados y paquetes
instalados: [CI y releases](docs/development/CI_RELEASES.md).

La deuda de tipos de las herramientas tiene un inventario y tareas separados;
no se ocultan errores del runtime para hacer pasar los controles.

## Documentación y licencia

- [Índice de documentación](docs/README.md).
- [Alcance de la versión 1.0](docs/development/ALCANCE_1_0.md).
- [Herramientas del proyecto](tools/README.md).
- [Licencia Apache 2.0](LICENSE). Los recursos adicionales conservan su licencia
  y procedencia junto a sus fuentes.
