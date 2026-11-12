class AuthError(Exception):
    """Bad credentials / bad token -> HTTP 401."""

class Forbidden(Exception):
    """Authenticated but not allowed -> HTTP 403."""

class NotFound(Exception):
    """Missing OR invisible to the caller -> HTTP 404 (never reveal which)."""

class Invalid(Exception):
    """Bad input -> HTTP 422."""
