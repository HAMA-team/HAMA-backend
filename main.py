"""
Legacy entry point for backwards compatibility.

The actual FastAPI application lives in ``src.main``. Import the shared
application instance so tooling that still references ``main:app`` continues
to work without duplicating route registrations.
"""
from src.main import app  # noqa: F401
