from __future__ import annotations

import hashlib

from .errors import CompatibilityError

SQLITE_HEADER = b"SQLite format 3\x00"
PAGE_SIZE = 4096

try:
    from Crypto.Cipher import AES as _AES
except ImportError:  # pragma: no cover - exercised only in offline dev environments
    _AES = None
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:  # pragma: no cover
        Cipher = algorithms = modes = None


def derive_v2_key(uid: str) -> bytes:
    if not uid.isdigit():
        raise CompatibilityError("Unsupported account UID: expected a numeric `_v2` directory prefix.")
    digest = hashlib.md5(uid.encode("utf-8")).hexdigest()
    return digest[:16].encode("ascii")


def _cryptography_cipher(key: bytes):
    if Cipher is None:
        raise CompatibilityError(
            "AES support is unavailable. Install dependencies with `pip install -r requirements.txt`."
        )
    return Cipher(algorithms.AES(key), modes.ECB())


def decrypt_page(page: bytes, key: bytes) -> bytes:
    if len(key) != 16:
        raise CompatibilityError("Invalid DingTalk V2 AES key length; expected 16 bytes.")
    if len(page) % 16 != 0:
        raise CompatibilityError("Encrypted page length is not aligned to the AES block size.")
    if _AES is not None:
        return _AES.new(key, _AES.MODE_ECB).decrypt(page)
    decryptor = _cryptography_cipher(key).decryptor()
    return decryptor.update(page) + decryptor.finalize()


def _encrypt_page_for_testing(page: bytes, key: bytes) -> bytes:
    if len(page) % 16 != 0:
        raise ValueError("Test plaintext must be AES block aligned.")
    if _AES is not None:
        return _AES.new(key, _AES.MODE_ECB).encrypt(page)
    encryptor = _cryptography_cipher(key).encryptor()
    return encryptor.update(page) + encryptor.finalize()


def validate_first_page(encrypted_page: bytes, key: bytes) -> bytes:
    if len(encrypted_page) != PAGE_SIZE:
        raise CompatibilityError("Unsupported DingTalk database page size; expected 4096 bytes.")
    decrypted = decrypt_page(encrypted_page, key)
    if not decrypted.startswith(SQLITE_HEADER):
        raise CompatibilityError(
            "Unsupported DingTalk database format: the decrypted first page did not contain a valid SQLite header."
        )
    return decrypted
