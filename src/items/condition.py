"""Condición y estadísticas enteras, compartidas por negocio y presentación."""

from src.items.policy import BASIS_POINTS, STAT_FIELDS


def condition(state: dict[str, str], now: int) -> tuple[int, int, bool]:
    """Combina tiempo y usos sin rejuvenecer ante un retroceso UTC.

    Returns:
        Condición en puntos base, factor efectivo y estado roto.
    """
    now = max(now, int(state.get("last_seen", state["created_at"])))
    limits = [BASIS_POINTS]
    maximum, spent = int(state["max_uses"]), int(state["uses_spent"])
    lifetime = int(state["lifetime_seconds"])
    if maximum:
        remaining = maximum - spent
        limits.append(max(1, remaining * BASIS_POINTS // maximum) if remaining > 0 else 0)
    if lifetime:
        remaining = int(state["expires_at"]) - now
        limits.append(max(1, remaining * BASIS_POINTS // lifetime) if remaining > 0 else 0)
    quality = min(BASIS_POINTS, *limits)
    minimum = int(state["minimum_factor_bps"])
    factor = minimum + quality * (BASIS_POINTS - minimum) // BASIS_POINTS if quality else 0
    return quality, factor, quality == 0


def effective(base: dict[str, object], state: dict[str, str], now: int) -> dict[str, object]:
    """Proyecta una copia; no degrada el catálogo compartido.

    Returns:
        Campos numéricos degradados, conservando gráficos y propiedades del tipo.
    """
    _, factor, broken = condition(state, now)
    result = base.copy()
    for field in STAT_FIELDS & base.keys():
        result[field] = (max(0, int(str(base[field]))) * factor + BASIS_POINTS - 1) // BASIS_POINTS
    result["_broken"] = broken
    result["_instance_id"] = state["id"]
    if broken:
        for field in ("NoSeCaen", "InmunidadVeneno", "ResistenciaMagica"):
            if field in result:
                result[field] = 0
    return result
