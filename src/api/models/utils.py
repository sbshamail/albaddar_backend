# Convert empty → None
# Convert empty string → None
import json


def clean(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


# Convert "true"/"false"/"1"/"0" → boolean
def to_bool(v):
    v = clean(v)
    if v is None:
        return None
    val = str(v).lower()
    if val in ["true", "1", "yes"]:
        return True
    if val in ["false", "0", "no"]:
        return False
    return None  # fallback


# Convert JSON string → dict
def clean_json(v):

    v = clean(v)
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        raise ValueError(f"Invalid JSON: {v}")


# Convert to int
def to_int(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return int(v)
    except:
        return None


# Convert to float
def to_float(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return float(v)
    except:
        return None
