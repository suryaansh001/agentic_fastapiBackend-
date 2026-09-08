from fastapi.openapi.utils import get_openapi
from app.main import app

def generate_openapi():
    return get_openapi(
        title="Agentic CRM API",
        version="0.1.0",
        routes=app.routes,
    )
