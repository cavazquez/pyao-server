# Formato de Archivos .map de Argentum Online VB6

## Descripción General

Los archivos `.map` de Argentum Online contienen información binaria sobre los mapas del juego. Cada mapa es de **100x100 tiles** y contiene múltiples capas gráficas, información de bloqueo, triggers, y otros datos.

## Ubicación

- **Servidor:** `server/Maps/MapaX.map`
- **Cliente:** `client/Maps/MapaX.map`
- **Formato:** Binario (Visual Basic 6)

## Estructura del Archivo

### 1. Header (Cabecera)

El header tiene un tamaño aproximado de **114-120 bytes**:

```
Offset  Tamaño  Tipo    Descripción
------  ------  ------  -----------
0       2       Int16   MapVersion (versión del formato del mapa)
2       100     String  MiCabecera (string de identificación, típicamente "Encodeado con el Indexador...")
102     2       Int16   Llueve (¿está lloviendo? 0/1)
104     2       Int16   Nieba (¿está nevando? 0/1)
106     2       Int16   TempInt (reservado)
108     2       Int16   TempInt (reservado)
110     2       Int16   TempInt (reservado)
112     2       Int16   TempInt (reservado)
114     ...     ...     Inicio de datos de tiles
```

**Nota:** Si el mapa no es formato AO original (`formatoAo = False`), hay 2 Int16 adicionales para:
- Cabecera de partículas
- Cabecera de luces

### 2. Tiles (100x100 = 10,000 tiles)

Cada tile se parsea en el orden: **Y=1 to 100, X=1 to 100**

#### Estructura de un Tile

Cada tile tiene un formato **variable** dependiendo de las flags:

```
Campo           Tamaño  Tipo    Condición
-----           ------  ------  ---------
ByFlags         1       Byte    SIEMPRE presente
Graphic(1)      2       Int16   SIEMPRE presente (capa base)
Graphic(2)      2       Int16   Solo si (ByFlags And 2)
Graphic(3)      2       Int16   Solo si (ByFlags And 4)
Graphic(4)      2       Int16   Solo si (ByFlags And 8)
Trigger         1       Byte    Solo si (ByFlags And 16)
Particle Group  ...     ...     Solo si (ByFlags And 32)
Luz             ...     ...     Solo si (ByFlags And 64)
```

#### ByFlags (Byte de Flags)

Es un byte que indica qué campos están presentes usando bits:

```
Bit  Valor  Significado
---  -----  -----------
0    1      Blocked (tile bloqueado, no se puede caminar)
1    2      Tiene Graphic(2) (capa 2)
2    4      Tiene Graphic(3) (capa 3)
3    8      Tiene Graphic(4) (capa 4)
4    16     Tiene Trigger (evento especial)
5    32     Tiene Particle Group (partículas)
6    64     Tiene Luz (iluminación)
```

**Ejemplo:**
- `ByFlags = 0` → Solo Graphic(1), no bloqueado
- `ByFlags = 1` → Solo Graphic(1), bloqueado
- `ByFlags = 7` → Graphic(1,2,3), bloqueado
- `ByFlags = 15` → Graphic(1,2,3,4), bloqueado

### 3. Graphic(N) - Índices Gráficos

Cada `Graphic(N)` es un **Int16 (2 bytes, Little Endian)** que representa:
- **GrhIndex:** Índice en el archivo de gráficos (`Graficos.ind`)
- **0:** Sin gráfico en esa capa

#### Rangos Importantes de GrhIndex

**Agua:**
- `1505-1520` → Agua tipo 1
- `5665-5680` → Agua tipo 2
- `13547-13562` → Agua tipo 3

**Árboles:**
- Varían según el tipo de árbol (consultar `Graficos.ind`)

**Yacimientos:**
- Varían según el tipo de mineral

### 4. Triggers

Son eventos especiales que se activan al pisar un tile:
- `1` → Zona segura
- `2` → Portal/Exit
- `3` → Zona de tiendas
- `4-6` → Otros eventos

## Código de Referencia VB6

### Guardar Mapa (Escritura)

```vb
' De: modMapIO.bas - MapaV2_Guardar()
For y = YMinMapSize To YMaxMapSize
    For X = XMinMapSize To XMaxMapSize
        
        ' Calcular ByFlags
        ByFlags = 0
        If MapData(X, y).Blocked = 1 Then ByFlags = ByFlags Or 1
        If MapData(X, y).Graphic(2).grhindex Then ByFlags = ByFlags Or 2
        If MapData(X, y).Graphic(3).grhindex Then ByFlags = ByFlags Or 4
        If MapData(X, y).Graphic(4).grhindex Then ByFlags = ByFlags Or 8
        If MapData(X, y).Trigger Then ByFlags = ByFlags Or 16
        If MapData(X, y).particle_group Then ByFlags = ByFlags Or 32
        If MapData(X, y).luz.Rango Then ByFlags = ByFlags Or 64
        
        ' Escribir ByFlags
        Put FreeFileMap, , ByFlags
        
        ' Escribir Graphic(1) - SIEMPRE
        Put FreeFileMap, , MapData(X, y).Graphic(1).grhindex
        
        ' Escribir capas opcionales
        For loopc = 2 To 4
            If MapData(X, y).Graphic(loopc).grhindex Then
                Put FreeFileMap, , MapData(X, y).Graphic(loopc).grhindex
            End If
        Next loopc
        
        ' Escribir Trigger si existe
        If MapData(X, y).Trigger Then
            Put FreeFileMap, , MapData(X, y).Trigger
        End If
        
    Next X
Next y
```

### Cargar Mapa (Lectura)

```vb
' De: modMapIO.bas - MapaV2_Cargar()
For y = YMinMapSize To YMaxMapSize
    For X = XMinMapSize To XMaxMapSize
        
        ' Leer ByFlags
        Get FreeFileMap, , ByFlags
        
        ' Blocked
        MapData(X, y).Blocked = (ByFlags And 1)
        
        ' Graphic(1) - SIEMPRE presente
        Get FreeFileMap, , MapData(X, y).Graphic(1).grhindex
        InitGrh MapData(X, y).Graphic(1), MapData(X, y).Graphic(1).grhindex
        
        ' Layer 2 (si ByFlags And 2)
        If ByFlags And 2 Then
            Get FreeFileMap, , MapData(X, y).Graphic(2).grhindex
            InitGrh MapData(X, y).Graphic(2), MapData(X, y).Graphic(2).grhindex
        Else
            MapData(X, y).Graphic(2).grhindex = 0
        End If
        
        ' Layer 3 (si ByFlags And 4)
        If ByFlags And 4 Then
            Get FreeFileMap, , MapData(X, y).Graphic(3).grhindex
            InitGrh MapData(X, y).Graphic(3), MapData(X, y).Graphic(3).grhindex
        Else
            MapData(X, y).Graphic(3).grhindex = 0
        End If
        
        ' Layer 4 (si ByFlags And 8)
        If ByFlags And 8 Then
            Get FreeFileMap, , MapData(X, y).Graphic(4).grhindex
            InitGrh MapData(X, y).Graphic(4), MapData(X, y).Graphic(4).grhindex
        Else
            MapData(X, y).Graphic(4).grhindex = 0
        End If
        
        ' Trigger (si ByFlags And 16)
        If ByFlags And 16 Then
            Get FreeFileMap, , MapData(X, y).Trigger
        Else
            MapData(X, y).Trigger = 0
        End If
        
    Next X
Next y
```

## Implementación en Python

```python
import struct
from pathlib import Path

def parse_ao_map(map_file: Path) -> dict:
    """Parsea un archivo .map de Argentum Online.
    
    Returns:
        Dict con estructura:
        {
            'version': int,
            'header': str,
            'llueve': int,
            'nieba': int,
            'tiles': list[list[dict]]  # 100x100
        }
    """
    with open(map_file, 'rb') as f:
        data = f.read()
    
    offset = 0
    
    # Header
    map_version = struct.unpack('<H', data[offset:offset+2])[0]
    offset += 2
    
    # Cabecera (100 bytes, string terminado en null)
    header = data[offset:offset+100].split(b'\x00')[0].decode('latin-1', errors='ignore')
    offset += 100
    
    llueve = struct.unpack('<H', data[offset:offset+2])[0]
    offset += 2
    
    nieba = struct.unpack('<H', data[offset:offset+2])[0]
    offset += 2
    
    # Skip TempInts (4 x 2 bytes = 8 bytes)
    offset += 8
    
    # Parsear tiles (100x100)
    tiles = []
    for y in range(1, 101):
        row = []
        for x in range(1, 101):
            # ByFlags
            by_flags = data[offset]
            offset += 1
            
            # Graphic(1) - SIEMPRE presente
            graphic1 = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            tile = {
                'x': x,
                'y': y,
                'blocked': bool(by_flags & 1),
                'graphic1': graphic1,
                'graphic2': 0,
                'graphic3': 0,
                'graphic4': 0,
                'trigger': 0,
            }
            
            # Graphic(2)
            if by_flags & 2:
                tile['graphic2'] = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
            
            # Graphic(3)
            if by_flags & 4:
                tile['graphic3'] = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
            
            # Graphic(4)
            if by_flags & 8:
                tile['graphic4'] = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
            
            # Trigger
            if by_flags & 16:
                tile['trigger'] = data[offset]
                offset += 1
            
            row.append(tile)
        tiles.append(row)
    
    return {
        'version': map_version,
        'header': header,
        'llueve': llueve,
        'nieba': nieba,
        'tiles': tiles
    }
```

## Detección de Recursos

### Agua

Verificar si `Graphic(1)` está en los rangos de agua:

```python
def is_water(graphic1: int) -> bool:
    water_ranges = [
        (1505, 1520),
        (5665, 5680),
        (13547, 13562),
    ]
    return any(min_val <= graphic1 <= max_val for min_val, max_val in water_ranges)
```

### Árboles y Yacimientos

Requiere consultar el catálogo de objetos o `Graficos.ind` para mapear GrhIndex → Tipo de recurso.

## Archivos Relacionados

### Archivos de Mapa

- **Mapa1.map** → Datos binarios del mapa
- **Mapa1.inf** → Información adicional (NPCs, objetos, etc.)
- **Mapa1.dat** → Metadata (nombre, música, etc.)

### Estructura de Archivos

```
server/
├── Maps/
│   ├── Mapa1.map  ← Tiles y gráficos (binario)
│   ├── Mapa1.inf  ← NPCs y objetos (texto)
│   └── Mapa1.dat  ← Metadata del mapa (texto)
└── Dat/
    ├── Graficos.ind  ← Índice de gráficos
    └── NPCs.dat      ← Definiciones de NPCs
```

## Referencias

- **Código fuente:** `/argentum-online-worldeditor/Codigo/modMapIO.bas`
- **Función de carga:** `MapaV2_Cargar()` y `MapaV3_Cargar()`
- **Función de guardado:** `MapaV2_Guardar()`
- **Parser implementado:** `/scripts/parse_map_resources.py`

## Notas Importantes

1. **Endianness:** Todos los Int16 son **Little Endian** (`<H` en struct)
2. **Orden de tiles:** Siempre Y primero, luego X (Y=1..100, X=1..100)
3. **Graphic(1):** SIEMPRE está presente, incluso si es 0
4. **Optimización:** El formato usa flags para ahorrar espacio (no escribe capas vacías)
5. **Versión:** MapVersion puede variar (típicamente 25 en AO 0.13.3)

## Tamaño del Archivo

**Cálculo aproximado:**
- Header: ~114 bytes
- Tiles mínimo: 10,000 tiles × 3 bytes/tile = 30,000 bytes
- Tiles con capas: Variable según ByFlags
- **Total típico:** 30,000 - 50,000 bytes (30-50 KB)

## Ejemplo Real

**Mapa1.map de AO 0.13.3:**
- Tamaño: 33,183 bytes
- MapVersion: 25
- Header: "Encodeado con el Indexador Imperium-AoYa"
- Tiles: 10,000 (100×100)
- Ciudad de Ullathorpe (sin agua, mayormente tierra)
