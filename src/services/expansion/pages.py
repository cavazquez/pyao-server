"""Paginación por cantidad y bytes del contrato JSON, incluidos textos Unicode."""

import json
from typing import Any

QUEST_ROW_BUDGET = 2800


def bounded_pages(
    rows: list[dict[str, Any]], count: int, budget: int
) -> list[list[dict[str, Any]]]:
    """Mantiene filas completas sin producir páginas que excedan el transporte.

    Returns:
        Páginas estables con al menos una página vacía.

    Raises:
        ValueError: Si un único registro supera el presupuesto de su sección.
    """
    pages: list[list[dict[str, Any]]] = [[]]
    size = 2
    for row in rows:
        encoded = len(json.dumps(row, ensure_ascii=True, separators=(",", ":"))) + 1
        if encoded + 2 > budget:
            message = "Un registro excede el límite de la página del protocolo."
            raise ValueError(message)
        if pages[-1] and (len(pages[-1]) >= count or size + encoded > budget):
            pages.append([])
            size = 2
        pages[-1].append(row)
        size += encoded
    return pages
