import re
from typing import Optional

def normalize_domain(domain: str) -> Optional[str]:
    if not domain:
        return None
    domain = domain.strip().lower().rstrip(".")
    if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", domain):
        return None
    return domain

def domain_from_email(email: str) -> Optional[str]:
    if "@" not in email:
        return None
    return email.split("@")[1].lower()
