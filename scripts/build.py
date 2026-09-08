#!/usr/bin/env python3
"""Build the FastAPI application."""

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=3001, reload=True)
