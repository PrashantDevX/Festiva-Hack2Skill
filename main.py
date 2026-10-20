"""Vercel entrypoint for the FastAPI application.

Local development and tests continue to use ``backend/app/main.py`` (or the
``app.main`` module with ``--app-dir backend``). Vercel looks for ``app`` in
this supported entrypoint and runs it as a single Fluid-compute function.
"""

from backend.app.main import app

__all__ = ["app"]
