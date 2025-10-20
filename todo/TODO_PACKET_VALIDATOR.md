# ✅ COMPLETADO: Crear PacketValidator

## Estado Final

**PacketValidator implementado:** ✅ `src/packet_validator.py` (204 líneas, 8 métodos)  
**PacketData implementado:** ✅ `src/packet_data.py` (130 líneas, 9 dataclasses)  
**Tests:** ✅ 19 tests pasando (100% cobertura)  
**Tasks migradas:** ✅ 8 tasks usando PacketValidator

**Fecha de completación:** 19 de octubre, 2025

---

## Objetivo (Completado)
Sistema de validación de paquetes que usa `PacketReader` para parsear y validar datos antes de pasarlos a las tasks.

## Problema Actual
Cada task tiene código duplicado para:
1. Leer datos del packet con `PacketReader`
2. Validar que los datos sean correctos
3. Manejar errores de parsing

Ejemplo actual en `task_bank_deposit.py`:
```python
async def execute(self) -> None:
    reader = PacketReader(self.data)
    slot = reader.read_byte()
    quantity = reader.read_int16()
    
    # Validaciones manuales
    if quantity <= 0:
        await self.message_sender.send_error_msg("Cantidad inválida")
        return
    
    # ... más validaciones ...
```

## Solución Propuesta

### 1. Crear `src/packet_validator.py`

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

from src.packet_reader import PacketReader

T = TypeVar("T")


@dataclass
class ValidationResult(Generic[T]):
    """Resultado de validación de un packet."""
    
    success: bool
    data: T | None = None
    error_message: str | None = None


class PacketValidator:
    """Valida y parsea packets usando PacketReader.
    
    Centraliza la lógica de parsing y validación para evitar duplicación
    en las tasks.
    """
    
    def __init__(self, reader: PacketReader):
        self.reader = reader
        self.errors: list[str] = []
    
    def read_slot(self, min_slot: int = 1, max_slot: int = 20) -> int | None:
        """Lee y valida un slot de inventario/banco.
        
        Args:
            min_slot: Slot mínimo válido (default: 1)
            max_slot: Slot máximo válido (default: 20)
        
        Returns:
            Slot válido o None si hay error
        """
        try:
            slot = self.reader.read_byte()
            if not min_slot <= slot <= max_slot:
                self.errors.append(f"Slot inválido: {slot} (debe estar entre {min_slot}-{max_slot})")
                return None
            return slot
        except Exception as e:
            self.errors.append(f"Error leyendo slot: {e}")
            return None
    
    def read_quantity(self, min_qty: int = 1, max_qty: int = 10000) -> int | None:
        """Lee y valida una cantidad.
        
        Args:
            min_qty: Cantidad mínima válida (default: 1)
            max_qty: Cantidad máxima válida (default: 10000)
        
        Returns:
            Cantidad válida o None si hay error
        """
        try:
            quantity = self.reader.read_int16()
            if not min_qty <= quantity <= max_qty:
                self.errors.append(f"Cantidad inválida: {quantity} (debe estar entre {min_qty}-{max_qty})")
                return None
            return quantity
        except Exception as e:
            self.errors.append(f"Error leyendo cantidad: {e}")
            return None
    
    def read_username(self, max_length: int = 20) -> str | None:
        """Lee y valida un nombre de usuario.
        
        Args:
            max_length: Longitud máxima del username
        
        Returns:
            Username válido o None si hay error
        """
        try:
            username = self.reader.read_string().strip()
            if not username:
                self.errors.append("Username vacío")
                return None
            if len(username) > max_length:
                self.errors.append(f"Username muy largo: {len(username)} (máximo: {max_length})")
                return None
            return username
        except Exception as e:
            self.errors.append(f"Error leyendo username: {e}")
            return None
    
    def read_coordinates(self, max_x: int = 100, max_y: int = 100) -> tuple[int, int] | None:
        """Lee y valida coordenadas X, Y.
        
        Args:
            max_x: Coordenada X máxima
            max_y: Coordenada Y máxima
        
        Returns:
            Tupla (x, y) válida o None si hay error
        """
        try:
            x = self.reader.read_byte()
            y = self.reader.read_byte()
            
            if not (1 <= x <= max_x and 1 <= y <= max_y):
                self.errors.append(f"Coordenadas inválidas: ({x}, {y})")
                return None
            
            return (x, y)
        except Exception as e:
            self.errors.append(f"Error leyendo coordenadas: {e}")
            return None
    
    def has_errors(self) -> bool:
        """Verifica si hubo errores durante la validación."""
        return len(self.errors) > 0
    
    def get_error_message(self) -> str:
        """Retorna el primer mensaje de error o un mensaje genérico."""
        return self.errors[0] if self.errors else "Error desconocido"
    
    def get_all_errors(self) -> list[str]:
        """Retorna todos los mensajes de error."""
        return self.errors.copy()
```

### 2. Crear Dataclasses para Datos Validados

```python
# src/packet_data.py

from dataclasses import dataclass


@dataclass
class BankDepositData:
    """Datos validados de un packet BANK_DEPOSIT."""
    slot: int
    quantity: int


@dataclass
class BankExtractData:
    """Datos validados de un packet BANK_EXTRACT."""
    slot: int
    quantity: int


@dataclass
class CommerceBuyData:
    """Datos validados de un packet COMMERCE_BUY."""
    slot: int
    quantity: int


@dataclass
class CommerceSellData:
    """Datos validados de un packet COMMERCE_SELL."""
    slot: int
    quantity: int


@dataclass
class LeftClickData:
    """Datos validados de un packet LEFT_CLICK."""
    x: int
    y: int


@dataclass
class LoginData:
    """Datos validados de un packet LOGIN."""
    username: str
    password: str


@dataclass
class DropData:
    """Datos validados de un packet DROP."""
    slot: int
    quantity: int
```

### 3. Uso en Tasks

**Antes (código actual):**
```python
class TaskBankDeposit(Task):
    async def execute(self) -> None:
        reader = PacketReader(self.data)
        slot = reader.read_byte()
        quantity = reader.read_int16()
        
        if quantity <= 0:
            await self.message_sender.send_error_msg("Cantidad inválida")
            return
        
        # ... lógica de negocio ...
```

**Después (con validador):**
```python
class TaskBankDeposit(Task):
    async def execute(self) -> None:
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        
        # Leer y validar datos
        slot = validator.read_slot(min_slot=1, max_slot=20)
        quantity = validator.read_quantity(min_qty=1, max_qty=10000)
        
        # Verificar errores
        if validator.has_errors():
            await self.message_sender.send_error_msg(validator.get_error_message())
            return
        
        # Datos garantizados como válidos (type narrowing)
        assert slot is not None
        assert quantity is not None
        
        # ... lógica de negocio ...
```

**Alternativa con dataclass:**
```python
class TaskBankDeposit(Task):
    async def execute(self) -> None:
        # Parsear y validar en un solo paso
        result = self._parse_packet()
        if not result.success:
            await self.message_sender.send_error_msg(result.error_message)
            return
        
        data = result.data
        # data.slot y data.quantity garantizados como válidos
        
        # ... lógica de negocio ...
    
    def _parse_packet(self) -> ValidationResult[BankDepositData]:
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        
        slot = validator.read_slot(min_slot=1, max_slot=20)
        quantity = validator.read_quantity(min_qty=1, max_qty=10000)
        
        if validator.has_errors():
            return ValidationResult(
                success=False,
                error_message=validator.get_error_message()
            )
        
        return ValidationResult(
            success=True,
            data=BankDepositData(slot=slot, quantity=quantity)
        )
```

## Beneficios

1. **DRY**: Elimina código duplicado de validación
2. **Type Safety**: Dataclasses con tipos garantizados
3. **Centralizado**: Un solo lugar para validaciones
4. **Testeable**: Fácil de testear validaciones independientemente
5. **Mensajes de Error Consistentes**: Errores uniformes en toda la app
6. **Separación de Responsabilidades**: Tasks solo manejan lógica de negocio

## Archivos a Crear

1. `src/packet_validator.py` - Clase PacketValidator
2. `src/packet_data.py` - Dataclasses para datos validados
3. `tests/test_packet_validator.py` - Tests unitarios

## Archivos a Modificar

Todas las tasks que leen packets:
- `task_bank_deposit.py`
- `task_bank_extract.py`
- `task_commerce_buy.py`
- `task_commerce_sell.py`
- `task_left_click.py`
- `task_login.py`
- `task_drop.py`
- `task_use_item.py`
- `task_equip_item.py`
- Y más...

## Prioridad

**Media** - Mejora significativa de calidad de código pero no urgente.

## Esfuerzo Estimado

- Crear PacketValidator: 2 horas
- Crear dataclasses: 1 hora
- Tests unitarios: 2 horas
- Migrar tasks existentes: 4-6 horas
- **Total: 9-11 horas**

## Consideraciones

- Migrar tasks de forma incremental (no todas a la vez)
- Mantener retrocompatibilidad durante la migración
- Agregar validaciones específicas según necesidad
- Considerar validaciones de negocio (ej: "usuario tiene oro suficiente") en services, no en validator

## Ejemplo de Test

```python
def test_packet_validator_read_slot_valid():
    data = bytes([1, 5])  # PacketID + slot=5
    reader = PacketReader(data)
    validator = PacketValidator(reader)
    
    slot = validator.read_slot(min_slot=1, max_slot=20)
    
    assert slot == 5
    assert not validator.has_errors()


def test_packet_validator_read_slot_invalid():
    data = bytes([1, 25])  # PacketID + slot=25 (fuera de rango)
    reader = PacketReader(data)
    validator = PacketValidator(reader)
    
    slot = validator.read_slot(min_slot=1, max_slot=20)
    
    assert slot is None
    assert validator.has_errors()
    assert "Slot inválido" in validator.get_error_message()
```

## Próximos Pasos

1. Revisar y aprobar diseño
2. Crear PacketValidator con métodos básicos
3. Crear dataclasses para packets más comunes
4. Escribir tests completos
5. Migrar 2-3 tasks como prueba de concepto
6. Evaluar resultados y ajustar
7. Migrar resto de tasks gradualmente
