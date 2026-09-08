from fastapi import Request
from app.dependencies.auth import get_current_user, CurrentUser

def setup_dependencies(app: FastAPI) -> None:
    pass

async def get_current_user(request: Request) -> CurrentUser:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    # Verify token via Better Auth or authlib
    # Returns CurrentUser with id, email, name, role
    return CurrentUser(id="user_123", email="test@example.com", name="Test", role="rep")

def get_pagination_params(skip: int = 0, limit: int = 25):
    return {"skip": skip, "limit": limit}

def build_list_response(rows, total, facet_counts=None):
    return {"rows": rows, "total": total, "facetCounts": facet_counts or {}}

def resolve_order_by(sort: str, allowed_fields: list[str]) -> list:
    if not sort:
        return []
    direction = "desc" if sort.startswith("-") else "asc"
    field = sort.lstrip("-")
    if field not in allowed_fields:
        return []
    return [(field, direction)]

def normalize_email(email: str) -> str:
    return email.strip().lower()

def blank_to_null(value: str):
    if value == "":
        return None
    return value

def page_range(total: int, page: int, page_size: int) -> dict:
    start = (page - 1) * page_size + 1
    end = min(page * page_size, total)
    return {"start": start, "end": end, "total": total}
