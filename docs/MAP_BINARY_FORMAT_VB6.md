# Formato de Archivo Binario de Mapas VB6

## Tabla de Contenidos
1. [Estructura General](#estructura-general)
2. [Cabecera del Mapa](#cabecera-del-mapa)
3. [Datos de Tiles](#datos-de-tiles)
4. [Estructura de Bloques](#estructura-de-bloques)
5. [Sistema de Capas](#sistema-de-capas)
6. [Triggers y Eventos](#triggers-y-eventos)
7. [Sistema de Partículas y Luces](#sistema-de-partículas-y-luces)
8. [Ejemplo de Código](#ejemplo-de-código)

## Estructura General

Los archivos de mapa del cliente VB6 de Argentum Online siguen una estructura binaria que consta de:

1. **Cabecera** (118-124 bytes)
2. **Datos de Tiles** (variable)
3. **Datos Adicionales** (opcionales)

## Cabecera del Mapa

| Offset | Tamaño | Tipo    | Descripción |
|--------|--------|---------|-------------|
| 0      | 2      | Int16   | Versión del formato (generalmente 5) |
| 2      | 100    | Char[]  | Texto descriptivo (ISO-8859-1) |
| 102    | 2      | Int16   | Lluvia (0 = No, 1 = Sí) |
| 104    | 2      | Int16   | Niebla (0 = No, 1 = Sí) |
| 106    | 2      | Int16   | Reservado |
| 108    | 2      | Int16   | Reservado |
| 110    | 2      | Int16   | Reservado |
| 112    | 2      | Int16   | Reservado |
| 114    | 2      | Int16   | Sistema de Partículas (opcional) |
| 116    | 2      | Int16   | Sistema de Luces (opcional) |

**Nota:** Los últimos 4 bytes (114-118) pueden no estar presentes en mapas antiguos.

## Datos de Tiles

Cada tile puede contener hasta 4 capas gráficas y datos adicionales. La estructura se define mediante flags:

### Byte de Flags (ByFlags)

| Bit | Significado |
|-----|-------------|
| 0   | Usa Capa 2  |
| 1   | Usa Capa 3  |
| 2   | Usa Capa 4  |
| 3   | Tiene Trigger |
| 4   | Tiene Partículas |
| 5   | Tiene Luz    |
| 6-7 | Reservado   |

## Estructura de Bloques

1. **Capa Base** (siempre presente)
   - 2 bytes: Gráfico (Int16)

2. **Capas Adicionales** (opcionales)
   - 2 bytes por capa habilitada

3. **Datos Adicionales** (según flags)
   - 1 byte: Trigger (si flag 0x08)
   - 2 bytes: Grupo de Partículas (si flag 0x10)
   - 2 bytes: Intensidad de Luz (si flag 0x20)

## Sistema de Capas

1. **Capa 1 (Base)**: Siempre presente, terreno base
2. **Capa 2**: Objetos y decoración
3. **Capa 3**: Objetos superiores
4. **Capa 4**: Efectos especiales

## Triggers y Eventos

Los triggers se almacenan como un byte que puede representar:

- Puertas
- Teletransportes
- Zonas de daño
- Puntos de spawn
- Áreas de trigger para eventos

## Sistema de Partículas y Luces

- **Partículas**: Referencia a un grupo de partículas
- **Luces**: Intensidad y posiblemente color (dependiendo de la versión)

## Ejemplo de Código

```vb
' Estructura simplificada en VB6
Type MapTile
    ByFlags As Byte
    Graphic(1 To 4) As Integer
    Trigger As Byte
    ParticleGroup As Integer
    Light As Integer
End Type

' Lectura del archivo
Sub LoadMap(FileName As String)
    Dim FileNum As Integer
    Dim Version As Integer
    Dim Header As String * 100
    Dim Rain As Integer
    Dim Fog As Integer
    
    FileNum = FreeFile
    Open FileName For Binary As #FileNum
    
    ' Leer cabecera
    Get #FileNum, , Version
    Get #FileNum, , Header
    Get #FileNum, , Rain
    Get #FileNum, , Fog
    
    ' Leer tiles
    ' ...
    
    Close #FileNum
End Sub
```

## Notas Adicionales

1. El orden de los bytes es little-endian
2. Los strings están en codificación ISO-8859-1
3. Los valores de gráficos se refieren a índices en los archivos .bmp/.png
4. Algunos mapas personalizados pueden tener extensiones no estándar

## Referencias

- [Documentación del Motor Gráfico](ENGINE.md)
- [Sistema de Mapas](MAP_SYSTEM.md)
- [Guía de Triggers](TRIGGERS.md)
