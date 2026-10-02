"""Opaque cursors for keyset pagination.

A cursor is base64url-encoded JSON (e.g. {"id": 40}). Clients must treat it as an opaque token
and pass it back unchanged; its contents are an implementation detail we're free to change.
"""

import base64
import binascii
import json


class InvalidCursorError(ValueError):
    """The cursor wasn't issued by this API, or has been tampered with or truncated."""


def encode_cursor(last_id: int) -> str:
    """Build the cursor that resumes after the row with this id."""
    payload = json.dumps({"id": last_id}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    """Return the id to resume after. Raises InvalidCursorError for anything malformed."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise InvalidCursorError(cursor) from exc
    last_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(last_id, int) or isinstance(last_id, bool) or last_id < 0:
        raise InvalidCursorError(cursor)
    return last_id
