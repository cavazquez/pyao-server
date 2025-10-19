# TODO: Refactorings y Mejoras

**Estado:** 📝 Lista de mejoras pendientes  
**Prioridad:** Media-Baja  
**Versión objetivo:** 0.5.0+

---

## 🎯 Mejoras de Arquitectura

### 1. Crear PacketReader para Centralizar Lectura de Parámetros

**Problema:**
Actualmente cada Task lee los parámetros del packet usando `struct.unpack` directamente sobre `self.data`, lo que resulta en código repetitivo y propenso a errores.

**Ejemplo actual:**
```python
# En cada task:
slot = struct.unpack("B", self.data[1:2])[0]
quantity = struct.unpack("<H", self.data[2:4])[0]
```

**Solución propuesta:**
Crear una clase `PacketReader` que encapsule la lectura de diferentes tipos de datos:

```python
# src/packet_reader.py
class PacketReader:
    """Helper para leer parámetros de packets del cliente."""
    
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 1  # Saltar PacketID
    
    def read_byte(self) -> int:
        """Lee un byte (uint8)."""
        value = struct.unpack("B", self.data[self.offset:self.offset + 1])[0]
        self.offset += 1
        return value
    
    def read_int16(self) -> int:
        """Lee un int16 little-endian."""
        value = struct.unpack("<H", self.data[self.offset:self.offset + 2])[0]
        self.offset += 2
        return value
    
    def read_int32(self) -> int:
        """Lee un int32 little-endian."""
        value = struct.unpack("<I", self.data[self.offset:self.offset + 4])[0]
        self.offset += 4
        return value
    
    def read_string(self) -> str:
        """Lee un string con formato: length (uint16 LE) + UTF-16LE bytes."""
        length = self.read_int16()
        value = self.data[self.offset:self.offset + length].decode("utf-16-le")
        self.offset += length
        return value
```

**Uso en tasks:**
```python
# En TaskCommerceBuy:
reader = PacketReader(self.data)
slot = reader.read_byte()
quantity = reader.read_int16()
```

**Beneficios:**
- ✅ Código más limpio y legible
- ✅ Menos propenso a errores de offset
- ✅ Centraliza la lógica de parsing
- ✅ Facilita agregar validaciones
- ✅ Type hints completos

**Archivos a modificar:**
- Crear `src/packet_reader.py`
- Actualizar todas las tasks que leen packets
- Agregar tests unitarios

**Prioridad:** Media  
**Esfuerzo:** 2-3 horas

---

## 🔄 Otras Mejoras Pendientes

### 2. Service Container / Dependency Injection

Ver `docs/TODO_ARQUITECTURA.md` sección 2 para propuestas de mejora en la creación de tasks con dependencias.

### 3. Validación de Packets

Agregar validación de longitud de packets antes de parsear para evitar errores de índice fuera de rango.

### 4. Logging Estructurado

Considerar usar logging estructurado (JSON) para facilitar análisis de logs en producción.

---

**Última actualización:** 2025-10-18  
**Autor:** Sugerido durante implementación del sistema de comercio  
**Estado:** 📝 Pendiente
