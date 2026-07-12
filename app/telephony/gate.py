"""Registration gate.

Throwaway version: reads a single env flag so you can toggle the two call paths by hand.
In production this becomes a lookup keyed on the caller's number (the inbound 'from' field) --
exactly the role Bolna's caller-context played. Only the body of is_registered() changes.
"""

from app.core.config import settings


def is_registered(caller_number: str | None = None) -> bool:
    """Return whether the caller is registered.

    For now `caller_number` is ignored and the USER_REGISTERED env flag decides. Swap the body
    for a real DB/API lookup later without touching the callers of this function.
    """
    return settings.user_registered
