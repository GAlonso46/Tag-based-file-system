def normalize_tags(raw: str):
    """Normaliza una cadena de tags separadas por comas, eliminando espacios y '@'."""
    # Si la cadena está vacía, retorna lista vacía
    if not raw:
        return []
    # Separa por comas y elimina espacios
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    # Elimina el prefijo '@' si existe
    return [p.lstrip('@') for p in parts]
