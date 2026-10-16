"""Expresión compartida por la búsqueda y su índice de PostgreSQL."""
ACCENTS = "áàâäãåéèêëíìîïóòôöõúùûüñç"
PLAIN = "aaaaaaeeeeiiiiooooouuuunc"
SEARCH_EXPRESSION = f"translate(lower(coalesce(cdgo_producto_externo, '') || ' ' || name_product), '{ACCENTS}', '{PLAIN}')"


def search_pattern(query: str) -> str:
    value = query.strip().lower().translate(str.maketrans(ACCENTS, PLAIN))
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
