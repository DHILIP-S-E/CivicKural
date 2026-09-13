"""Lambda entrypoint — wraps the FastAPI app with Mangum for a Function URL."""
from __future__ import annotations

from mangum import Mangum

from .app import app

_adapter = Mangum(app)


def handler(event, context):
    """Normalize sparse HTTP API v2 contexts before passing them to Mangum.

    Some API Gateway configurations omit ``sourceIp`` even though Mangum
    expects the key to exist.  The application does not use the value, so a
    neutral fallback keeps normal and privacy-proxied requests compatible.
    """
    request_context = event.get("requestContext", {})
    http_context = request_context.get("http")
    if event.get("version") == "2.0" and isinstance(http_context, dict):
        http_context.setdefault("sourceIp", "0.0.0.0")
    return _adapter(event, context)
