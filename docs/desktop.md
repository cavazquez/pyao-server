# Iconos y bandeja

Ambos iconos son vectores propios, con licencia MIT en la carpeta del recurso. `tools/build_icons.py` genera PNG de 16 a 1024 píxeles y contenedores ICO e ICNS con manifiesto SHA256. Sólo requiere ImageMagick para regenerar fuentes; el juego no lo requiere.

El cliente utiliza `StatusIndicator` de Godot en Windows y macOS. En Linux utiliza el pequeño puente GTK3/Ayatana `pyao-tray`, compilado con `python tools/build_tray.py`; requiere los paquetes de desarrollo `libgtk-3-dev` y `libayatana-appindicator3-dev` durante la construcción. Snap instala las bibliotecas de ejecución. Un escritorio sin host de indicadores conserva la ventana accesible. La opción de minimizar a bandeja está desactivada por defecto; el juego continúa conectado al minimizarse.

El servidor normal sigue siendo `pyao-server`: `--help`, `--version` y los procesos sin escritorio no importan bibliotecas gráficas. `pyao-server-indicator` es un supervisor opcional, con menú de registros, parada gradual y cierre del indicador. Sólo inicia y señaliza su propio proceso; no inicia ni detiene Redis. **Cerrar el indicador deja el servidor funcionando**; «Detener servidor» envía la señal gradual que usa el CLI. El título muestra el proceso real, no presupone que el puerto ya esté listo. Sus registros privados se guardan en `state_dir()/logs/indicator-PID.log`.

En Linux se compila `pyao-tray` y se coloca en PATH; el checkout también lo encuentra en `build/desktop`. Snap incluye el puente y un lanzador separado. Windows/macOS necesitan `uv pip install 'pyao-server[desktop]'`; la dependencia opcional pystray no afecta la instalación normal. El wheel incluye los iconos del servidor y el C fuente del puente.

Referencias de plataforma: [StatusIndicator de Godot](https://docs.godotengine.org/en/4.7/classes/class_statusindicator.html), [Ayatana](https://github.com/AyatanaIndicators/libayatana-appindicator), [pystray](https://pypi.org/project/pystray/).
