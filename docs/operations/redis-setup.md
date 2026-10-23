# Preparar Redis y Redis Insight

PyAO guarda la partida en una instancia Redis administrada por el operador. El
cliente Godot sólo se conecta al servidor de juego. Redis Insight es una GUI
opcional; el servidor funciona sin escritorio y sin esa aplicación instalada.

```sh
pyao.pyao-server --redis-guide
pyao.pyao-server --check-redis
```

Desde fuentes usar `uv run pyao-server` con las mismas opciones. La primera muestra
una guía aun con Redis ausente o TOML inválido. La segunda lee PING, INFO server y
CONFIG GET appendonly/appendfsync con límites de espera, cierra la conexión y
devuelve JSON/exit 0 sólo con política compatible. No escribe, instala, inicializa
datos, migra esquemas ni abre el listener. Un ACL que impide inspeccionar la
configuración requiere que el administrador verifique la política; no se cambian
permisos automáticamente. `--help` y `--version` tampoco necesitan Redis.

## Instancia local, remota o existente

Si ya existe una instancia apropiada, conservarla. Configurar `[redis]` host,
port, db y password_file en el TOML, o `PYAO_REDIS__HOST`, `PYAO_REDIS__PORT`,
`PYAO_REDIS__DB`, `PYAO_REDIS__PASSWORD_FILE`. En Snap el archivo secreto debe estar
dentro de `$SNAP_USER_COMMON`, con permisos 0600 y una sola línea. No incluirlo en
capturas, URLs ni argumentos. La guía imprime host/puerto/base, nunca su contenido.

Redis >=7.2 proporciona WAITAOF; la integración se prueba con Redis 8.10.2. La
instancia debe tener AOF activado, appendfsync `everysec` o `always`, volumen
persistente y autenticación. La guía usa `redis-cli --askpass`, que solicita el
secreto interactivamente. Un PONG no sustituye la comprobación de AOF ni un backup.
El juego exige fsync antes de confirmar cobros. El diagnóstico es de sólo lectura:
no envía una escritura de prueba ni afirma haber validado una recuperación real.

Para Linux, consultar la [instalación APT oficial](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/apt/):
origen packages.redis.io y paquete `redis`. También existe la
[vía Snap documentada por Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/snap/).
El [Snap oficial de Redis](https://snapcraft.io/redis), de Redis/redislabs, ofrecía
8.10.2 en `latest/stable` al verificarlo el 22 de octubre de 2026. Puede instalarse
opcionalmente con `sudo snap install redis --channel=latest/stable`.
Revisar `snap info redis` y la versión/canal antes de instalarlo: el paquete puede
iniciar un servicio y hay que preparar su autenticación, AOF y puerto antes de
usarlo. Estos comandos los ejecuta el operador; PyAO sólo los sugiere.

Una instancia remota no exige un paquete Redis local. Debe permitir las operaciones
y la persistencia requeridas por el juego. Usar red privada o túnel aprobado por
su administrador: esta configuración de conexión Redis no implementa TLS. El TLS
del socket de jugadores es independiente. No publicar el puerto Redis en Internet.

## GUI oficial opcional

La [documentación de Redis Insight](https://redis.io/docs/latest/operate/redisinsight/install/install-on-desktop/)
y su [Snap oficial publicado por Redis/redislabs](https://snapcraft.io/redisinsight)
se verificaron el 22 de octubre de 2026:

```sh
sudo snap install redisinsight --channel=latest/stable
sudo snap connect redisinsight:password-manager-service
```

La segunda conexión habilita el almacén de credenciales del escritorio. Abrir la
aplicación, agregar host, puerto y base de la configuración efectiva y escribir el
secreto en el campo privado. Para remoto usar el endpoint/túnel aprobado. Su ausencia
no impide iniciar PyAO; tampoco abre la GUI automáticamente.

## Validación

Las pruebas cubren endpoint local/remoto, Redis ausente, errores de autenticación,
versiones antiguas, AOF desactivado y falta de permisos. El proceso sólo puede usar
PING/INFO/CONFIG/cierre. Se ejecutaron guía, ayuda y versión con TOML roto y sin GUI,
y el diagnóstico contra Redis/AOF propio dentro del confinamiento del Snap instalado
revisión 30, usando una copia temporal de estas fuentes en su directorio común.
La base inspeccionada siguió vacía. Ese ensayo valida el runtime y confinamiento;
no representa la instalación de una nueva revisión publicada. La incorporación a
una distribución se realiza mediante los workflows habituales de publicación.
