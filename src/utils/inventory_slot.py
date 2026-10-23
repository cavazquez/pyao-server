"""Value Object para representar un slot de inventario."""

from dataclasses import dataclass

INDIVIDUAL_PARTS = 3
MAX_SLOT_QUANTITY = 32767
IDENTITY_LENGTH = 32


@dataclass(frozen=True)
class InventorySlot:
    """Representa un slot de inventario con item y cantidad.

    Es un Value Object inmutable que encapsula la lógica de parsing
    y formateo del formato "item_id:quantity" usado en Redis.
    """

    item_id: int
    quantity: int
    instance_ids: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str | bytes) -> InventorySlot | None:
        """Parsea un string en formato "item_id:quantity".

        Args:
            value: String o bytes en formato "item_id:quantity".

        Returns:
            InventorySlot o None si el formato es inválido o está vacío.
        """
        if not value:
            return None

        # Convertir bytes a string si es necesario
        if isinstance(value, bytes):
            value = value.decode("utf-8")

        value = value.strip()
        if not value:
            return None

        try:
            parts = value.split(":")
            if len(parts) == INDIVIDUAL_PARTS and parts[0] == "i1":
                identities = tuple(parts[2].split(","))
                if (
                    not parts[1].isdigit()
                    or int(parts[1]) < 1
                    or len(identities) > MAX_SLOT_QUANTITY
                    or len(set(identities)) != len(identities)
                    or any(
                        len(i) != IDENTITY_LENGTH or any(c not in "0123456789abcdef" for c in i)
                        for i in identities
                    )
                ):
                    return None
                return cls(int(parts[1]), len(identities), identities)
            if len(parts) != 2:  # ruff: ignore[magic-value-comparison]
                return None

            item_id = int(parts[0])
            quantity = int(parts[1])

            if item_id <= 0 or quantity <= 0:
                return None

            return cls(item_id=item_id, quantity=quantity)
        except ValueError, AttributeError:
            return None

    def to_string(self) -> str:
        """Convierte el slot a formato "item_id:quantity".

        Returns:
            String en formato "item_id:quantity" o referencias individuales.

        Raises:
            ValueError: Si las identidades no coinciden con la cantidad.
        """
        if self.instance_ids:
            if len(self.instance_ids) != self.quantity:
                msg = "Cantidad e identidades del slot no coinciden"
                raise ValueError(msg)
            return f"i1:{self.item_id}:" + ",".join(self.instance_ids)
        return f"{self.item_id}:{self.quantity}"

    def is_empty(self) -> bool:
        """Verifica si el slot está vacío.

        Returns:
            True si la cantidad es 0 o negativa.
        """
        return self.quantity <= 0

    def can_stack_with(self, other: InventorySlot) -> bool:
        """Verifica si este slot puede apilarse con otro.

        Args:
            other: Otro InventorySlot.

        Returns:
            True si tienen el mismo item_id.
        """
        return self.item_id == other.item_id and not self.instance_ids and not other.instance_ids

    def add_quantity(self, amount: int, max_stack: int = 20) -> tuple[InventorySlot, int]:
        """Intenta agregar cantidad al slot respetando el límite de stack.

        Args:
            amount: Cantidad a agregar.
            max_stack: Cantidad máxima por stack.

        Returns:
            Tupla (nuevo_slot, cantidad_sobrante).
            Si no se puede agregar nada, retorna (self, amount).
        """
        if amount <= 0:
            return self, 0
        if self.instance_ids:
            return self, amount

        space_available = max_stack - self.quantity
        if space_available <= 0:
            return self, amount

        to_add = min(amount, space_available)
        new_quantity = self.quantity + to_add
        remaining = amount - to_add

        new_slot = InventorySlot(item_id=self.item_id, quantity=new_quantity)
        return new_slot, remaining

    def remove_quantity(self, amount: int) -> InventorySlot | None:
        """Remueve cantidad del slot.

        Args:
            amount: Cantidad a remover.

        Returns:
            Nuevo InventorySlot con la cantidad reducida, o None si queda vacío.
            Si no hay suficiente cantidad, retorna None.
        """
        if amount <= 0:
            return self

        if self.quantity < amount:
            return None

        new_quantity = self.quantity - amount

        if new_quantity <= 0:
            return None

        return InventorySlot(self.item_id, new_quantity, self.instance_ids[amount:])
