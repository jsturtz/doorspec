"""Unit tests for cursor encoding. No database involved."""

import pytest

from app.pagination import InvalidCursorError, decode_cursor, encode_cursor


@pytest.mark.parametrize("last_id", [0, 1, 40, 2**31])
def test_cursor_round_trips(last_id):
    assert decode_cursor(encode_cursor(last_id)) == last_id


def test_cursor_is_url_safe_and_unpadded():
    cursor = encode_cursor(123456789)
    assert set(cursor) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


@pytest.mark.parametrize("cursor", ["", "!!!", "bm90IGpzb24", "W10", "eyJpZCI6IC0xfQ"])
def test_malformed_cursor_raises(cursor):
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)
