import shlex

def normalize_tags(raw):
    """
    Normaliza una cadena de tags: separa por comas, elimina espacios,
    convierte a minúsculas y devuelve lista ordenada y sin duplicados.
    Acepta también listas (en cuyo caso las normaliza).
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        tags = [str(t).strip().lower() for t in raw if str(t).strip()]
    else:
        tags = [t.strip().lower() for t in str(raw).split(",") if t.strip()]
    # eliminar duplicados manteniendo orden: usar dict.fromkeys
    return list(dict.fromkeys(tags))

def unquote(token: str):
    """Quita comillas envolventes simples o dobles si existen."""
    if not token:
        return token
    token = str(token)
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token

def split_input_preserve_quotes(line: str):
    """
    Divide una línea como lo hace shlex.split pero dejando
    posix=False para Windows-style backslashes si se necesita.
    """
    return shlex.split(line, posix=False)
