# Validar datos antes de iniciar el mundo

Desde la raíz del servidor, instalar el entorno fijado y validar sin iniciar Redis ni el servidor:

```bash
uv sync --locked --dev
uv run --locked python -m tools.compression.decompress_map_data --target map_data
uv run --locked python -m src.validation.dataset
uv run --locked python -m src.validation.dataset --json
```

Para otro dataset, seleccionar ambos directorios explícitamente:

```bash
uv run --locked python -m src.validation.dataset --data-dir /ruta/data --maps-dir /ruta/map_data
```

El comando sólo lee archivos y escribe su informe a stdout. No importa inicializadores, no crea directorios ni modifica Redis. Devuelve `0` sin errores bloqueantes y `1` si encuentra alguno. Las advertencias se conservan en ambos formatos. Cada diagnóstico contiene archivo, ruta de campo, ID y motivo; los índices de listas empiezan en cero y las líneas NDJSON en uno.

La descompresión es un paso de preparación separado, necesario en un clon nuevo: `archives/map_data.xz` está versionado y `map_data/` es su copia de trabajo ignorada por Git. Si esa copia ya existe, validar directamente o descomprimir el archivo a otro directorio y seleccionarlo con `--maps-dir`; no es necesario sobrescribir datos locales.

## Comprobaciones

- IDs únicos del catálogo activo de ítems, NPCs hostiles y amigables, hechizos y mapas; identidades de mercaderes, loot, materiales y recetas.
- Referencias de puertas, minerales/lingotes y pergaminos; NPCs invocados, inventarios de mercaderes y tablas de loot.
- Productos y materiales de armas, armaduras y carpintería; cantidades positivas, probabilidades finitas entre cero y uno, extremos mínimos/máximos ordenados y skills válidos.
- Índice de mapas igual a los metadatos NDJSON; archivos de colisiones, objetos y transiciones requeridos; coordenadas dentro del tamaño del mapa y destinos de salida existentes.
- Ciudades, ciudad predeterminada, spawns fijos/aleatorios y puertas manuales.

`materials.toml:index` pertenece al catálogo de materiales de crafting; las recetas de herrería los referencian por su ID textual. No se interpreta como ID de ítem. Los NPCs de servicio pueden tener HP cero; un boss puede superar 65535 HP. `min_skill=101` conserva el centinela VB6 que impide usar ciertos hechizos mediante skills normales (máximo 100).

Se validan los catálogos efectivos que carga el servidor: `items/**/*.toml`, `npcs/hostiles.toml` y `npcs/friendly.toml`. `npcs/complete.toml` y `npcs/traders.toml` son extracciones de referencia, no catálogos adicionales cargados por `NPCCatalog`. Validar recetas no implementa ni activa el servicio de crafting, que tiene su propio issue.

## Recursos del cliente y fallbacks

El servidor no necesita gráficos ni sonidos para esta validación. Sin cliente seleccionado se informa una advertencia de cobertura audiovisual omitida. Para comprobar también el índice gráfico y los mapas propios:

```bash
uv run --locked python -m src.validation.dataset --client-dir ../ArgentumOnlineGodot
```

Con esa opción, un índice gráfico malformado, un `GrhIndex` inexistente o un mapa binario/escena faltante bloquean. Un sonido de hechizo ausente advierte: `AudioManager.PlayAudio` informa su ausencia y retorna sin reproducirlo. `GrhIndex=0` advierte y conserva el comportamiento de objetos invisibles: `MapContainer.AddObject` sólo dibuja cuando el índice es positivo. Ningún fallback permite omitir referencias de gameplay rotas. La importación/exportación real del cliente sigue siendo una comprobación adicional; esta herramienta no genera adyacencias ni reemplaza el issue #24 del cliente.

## Saneamiento inicial de #143

Había 1096 filas de ítems pero sólo 1070 IDs efectivos. Veintiséis definiciones quedaban ocultas por el orden de carga de `ItemCatalog`: IDs 832–846 y 1000–1010. Se movieron íntegramente a `data/archive/shadowed_items.toml`, fuera de `data/items/`, conservando su archivo de origen. Se comprobó que el diccionario efectivo completo de los 1070 ítems permanece idéntico, sin renumerar IDs. El archivo de archivo no forma parte del dataset activo; no debe moverse de nuevo al catálogo sin resolver las colisiones.

El mapa 36 tenía 14 spawns pero carecía de geometría y metadatos en el servidor. Se recuperaron sólo sus registros desde los originales VB6 locales, usando `extract_map_objects_vb6` y `read_inf_file`: 2729 colisiones, 999 objetos y 336 salidas. El `.map` original coincide byte por byte con `Assets/Maps/mapa36.map` del cliente propio. Se preservaron todos los registros existentes y el mundo pasa a tener 290 mapas.

Procedencia para reproducir la extracción:

- `.map` SHA256: `1f138d57b678307f734e0d05a523465f2341e7d8f5d8f0fd4fe0c035cec485c8`.
- `.inf` SHA256: `564f15d558139ffaca2b3abff64a5a81a7de1de537d2d2fe32cc8041270261c4`.
- Los originales provienen de `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Maps/mapa36.*`; la CI sólo necesita los datos recuperados versionados.

La CI ejecuta la herramienta con uv fijado y el lock versionado antes de lint/tests. Los tests incluyen corrupción de TOML/NDJSON, referencias rotas, duplicados, rangos, archivos ausentes y validación del dataset completo.
