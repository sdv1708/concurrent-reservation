from fastapi import Request
from fastapi.responses import JSONResponse
from app.exceptions.custom import ResourceNotFoundError, UnauthorizedError, AccessDeniedError


# ── Error response shape — consistent across ALL errors in the API ────────────
# { "error": { "code": 404, "message": "Hotel not found with id: 5" } }

async def not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(status_code=404, content={"error": {"code": 404, "message": exc.message}})


async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(status_code=401, content={"error": {"code": 401, "message": exc.message}})


async def access_denied_handler(request: Request, exc: AccessDeniedError):
    return JSONResponse(status_code=403, content={"error": {"code": 403, "message": exc.message}})


async def generic_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exception — returns 500 with the error message."""
    return JSONResponse(status_code=500, content={"error": {"code": 500, "message": str(exc)}})
