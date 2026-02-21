class ResourceNotFoundError(Exception):
    """Raise when a DB record is not found. Mapped to HTTP 404 by the exception handler."""
    def __init__(self, message: str):
        self.message = message


class UnauthorizedError(Exception):
    """Raise for authentication failures (bad token, wrong password). Mapped to HTTP 401."""
    def __init__(self, message: str):
        self.message = message


class AccessDeniedError(Exception):
    """Raise when user lacks permission for a resource. Mapped to HTTP 403."""
    def __init__(self, message: str):
        self.message = message
