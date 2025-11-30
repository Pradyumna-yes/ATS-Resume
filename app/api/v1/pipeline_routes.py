"""API router shim for pipeline endpoints.

This module exposes the router expected at `app.api.v1.pipeline_routes`.
It imports the implementation from `app.services.pipeline_routes` to avoid
duplicating logic while keeping API-level code under `app.api.v1`.

Keeping a small shim keeps imports stable for tests and for runtime.
"""
from app.services.pipeline_routes import router

__all__ = ["router"]
