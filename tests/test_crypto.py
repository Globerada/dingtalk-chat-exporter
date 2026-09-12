import pytest

from dingtalk_exporter.crypto import _encrypt_page_for_testing, derive_v2_key, validate_first_page
from dingtalk_exporter.errors import CompatibilityError


def test_known_uid_derives_validated_v2_key():
    assert derive_v2_key("1234567890") == b"e807f1fcf82d132f"


def test_validate_first_page_recovers_sqlite_header():
    key = derive_v2_key("1234567890")
    plain = b"SQLite format 3\x00" + bytes(4096 - 16)
    encrypted = _encrypt_page_for_testing(plain, key)
    assert validate_first_page(encrypted, key).startswith(b"SQLite format 3\x00")


def test_invalid_key_is_rejected():
    good_key = derive_v2_key("1234567890")
    plain = b"SQLite format 3\x00" + bytes(4096 - 16)
    encrypted = _encrypt_page_for_testing(plain, good_key)
    with pytest.raises(CompatibilityError, match="SQLite header"):
        validate_first_page(encrypted, b"0000000000000000")
