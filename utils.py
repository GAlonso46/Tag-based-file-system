def normalize_tags(raw: str):
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    return [p.lstrip('@') for p in parts]
