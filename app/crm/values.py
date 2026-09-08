def normalize_email(email: str) -> str:
    return email.strip().lower()

def blank_to_null(value: str):
    if value == "":
        return None
    return value

def canonical_value(value: str) -> str:
    import re
    value = value.lower().strip()
    value = re.sub(r"^www\.", "", value)
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"/$", "", value)
    return value
