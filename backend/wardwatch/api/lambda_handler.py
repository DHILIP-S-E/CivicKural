"""Lambda entrypoint — wraps the FastAPI app with Mangum for a Function URL."""
from __future__ import annotations

from mangum import Mangum

from .app import app

handler = Mangum(app)
