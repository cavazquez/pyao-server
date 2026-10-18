"""Plan de slots en memoria: nunca persiste una distribución parcial de stacks."""

from src.utils.inventory_slot import InventorySlot

MAX_SLOT_QUANTITY = 32767
MATERIAL_STACK_LIMIT = 10000
CRAFT_MATERIAL_IDS = frozenset({58, 136, 192, 193, 194, 386, 387, 388})


class SlotPlan:
    """Copia validada de slots para calcular un commit conjunto de inventarios."""

    def __init__(self, values: dict[str, str], capacity: int, max_stack: int) -> None:
        """Rechaza corrupción antes de considerar un slot como libre.

        Raises:
            ValueError: Si capacidad, tope o un slot existente son inválidos.
        """
        if capacity < 1 or max_stack < 1:
            msg = "Capacidad de slots inválida"
            raise ValueError(msg)
        self.capacity = capacity
        self.max_stack = max_stack
        self.slots: dict[int, InventorySlot] = {}
        for slot in range(1, capacity + 1):
            value = values.get(f"slot_{slot}", "")
            if not value:
                continue
            parsed = InventorySlot.parse(value)
            if (
                parsed is None
                or parsed.quantity > MAX_SLOT_QUANTITY
                or parsed.item_id > MAX_SLOT_QUANTITY
            ):
                msg = "Slot persistido inválido"
                raise ValueError(msg)
            self.slots[slot] = parsed

    def take(self, slot: int, item_id: int, quantity: int) -> None:
        """Retira de un slot exacto conservando identidad y cantidad.

        Raises:
            ValueError: Si el recurso cambió o la cantidad/slot no son válidos.
        """
        current = self.slots.get(slot)
        if not 1 <= slot <= self.capacity or quantity < 1 or current is None:
            msg = "El objeto ofrecido ya no está disponible"
            raise ValueError(msg)
        if current.item_id != item_id or current.quantity < quantity:
            msg = "El objeto o cantidad del slot cambió"
            raise ValueError(msg)
        if current.quantity == quantity:
            del self.slots[slot]
        else:
            self.slots[slot] = InventorySlot(item_id, current.quantity - quantity)

    def give(self, item_id: int, quantity: int) -> None:
        """Distribuye una cantidad completa entre stacks existentes y vacíos.

        Raises:
            ValueError: Si los datos no son válidos o no entra la cantidad completa.
        """
        if (
            type(item_id) is not int
            or type(quantity) is not int
            or not 1 <= item_id <= MAX_SLOT_QUANTITY
            or quantity < 1
        ):
            msg = "Objeto o cantidad inválidos"
            raise ValueError(msg)
        stack_limit = (
            max(self.max_stack, MATERIAL_STACK_LIMIT)
            if item_id in CRAFT_MATERIAL_IDS
            else self.max_stack
        )
        before = self.slots.copy()
        remaining = quantity
        matching = [slot for slot, item in self.slots.items() if item.item_id == item_id]
        empty = [slot for slot in range(1, self.capacity + 1) if slot not in self.slots]
        for slot in sorted(matching) + empty:
            current = self.slots.get(slot)
            existing = current.quantity if current else 0
            accepted = min(remaining, max(0, stack_limit - existing))
            if accepted:
                self.slots[slot] = InventorySlot(item_id, existing + accepted)
                remaining -= accepted
            if remaining == 0:
                return
        self.slots = before
        msg = "No hay espacio suficiente para todos los objetos"
        raise ValueError(msg)

    def fields(self) -> dict[str, str]:
        """Incluye slots vacíos para borrar los objetos retirados en el mismo HSET.

        Returns:
            Estado de todos los slots, sin afectar metadatos ni campos ajenos.
        """
        return {
            f"slot_{slot}": self.slots[slot].to_string() if slot in self.slots else ""
            for slot in range(1, self.capacity + 1)
        }
