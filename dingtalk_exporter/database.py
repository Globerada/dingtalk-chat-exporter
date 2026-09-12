from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from .crypto import PAGE_SIZE, decrypt_page, derive_v2_key, validate_first_page
from .errors import CompatibilityError, DatabaseReconstructionError
from .models import AccountCandidate, ReconstructedDatabase

VALID_WAL_MAGIC = {0x377F0682, 0x377F0683}
WAL_HEADER_SIZE = 32
WAL_FRAME_HEADER_SIZE = 24


def apply_committed_wal(base: bytearray, wal: bytes, key: bytes, page_size: int = PAGE_SIZE) -> tuple[bytearray, int]:
    if len(wal) < WAL_HEADER_SIZE:
        raise DatabaseReconstructionError("SQLite WAL is shorter than its 32-byte header.")
    magic = struct.unpack(">I", wal[0:4])[0]
    if magic not in VALID_WAL_MAGIC:
        raise DatabaseReconstructionError("Unsupported SQLite WAL magic.")
    wal_page_size = struct.unpack(">I", wal[8:12])[0]
    if wal_page_size == 1:
        wal_page_size = 65536
    if wal_page_size != page_size:
        raise DatabaseReconstructionError(
            f"Unsupported SQLite WAL page size: expected {page_size}, found {wal_page_size}."
        )
    frame_size = WAL_FRAME_HEADER_SIZE + page_size
    frames: list[tuple[int, int, bytes]] = []
    offset = WAL_HEADER_SIZE
    while offset + frame_size <= len(wal):
        header = wal[offset:offset + WAL_FRAME_HEADER_SIZE]
        page_number, db_size = struct.unpack(">II", header[:8])
        payload = wal[offset + WAL_FRAME_HEADER_SIZE:offset + frame_size]
        frames.append((page_number, db_size, payload))
        offset += frame_size
    last_commit_index: int | None = None
    final_page_count: int | None = None
    for index, (_, db_size, _) in enumerate(frames):
        if db_size != 0:
            last_commit_index = index
            final_page_count = db_size
    if last_commit_index is None or final_page_count is None:
        return base, 0
    applied = 0
    for page_number, _, payload in frames[:last_commit_index + 1]:
        if page_number <= 0:
            raise DatabaseReconstructionError("SQLite WAL contains an invalid page number.")
        plain = decrypt_page(payload, key)
        start = (page_number - 1) * page_size
        end = start + page_size
        if len(base) < end:
            base.extend(b"\x00" * (end - len(base)))
        base[start:end] = plain
        applied += 1
    expected_size = final_page_count * page_size
    if len(base) > expected_size:
        del base[expected_size:]
    elif len(base) < expected_size:
        base.extend(b"\x00" * (expected_size - len(base)))
    return base, applied


def reconstruct_database(account: AccountCandidate, output_path: Path) -> ReconstructedDatabase:
    encrypted = account.database_path.read_bytes()
    if len(encrypted) < PAGE_SIZE or len(encrypted) % PAGE_SIZE != 0:
        raise CompatibilityError("Unsupported DingTalk database size: expected 4096-byte page alignment.")
    key = derive_v2_key(account.uid)
    validate_first_page(encrypted[:PAGE_SIZE], key)
    rebuilt = bytearray()
    for offset in range(0, len(encrypted), PAGE_SIZE):
        rebuilt.extend(decrypt_page(encrypted[offset:offset + PAGE_SIZE], key))
    wal_frames_applied = 0
    if account.wal_path and account.wal_path.exists() and account.wal_path.stat().st_size:
        rebuilt, wal_frames_applied = apply_committed_wal(rebuilt, account.wal_path.read_bytes(), key, PAGE_SIZE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rebuilt)
    try:
        con = sqlite3.connect(f"file:{output_path.as_posix()}?mode=ro", uri=True)
        result = con.execute("PRAGMA quick_check").fetchone()[0]
        con.close()
    except sqlite3.DatabaseError as exc:
        output_path.unlink(missing_ok=True)
        raise DatabaseReconstructionError(f"Reconstructed SQLite database could not be opened: {exc}") from exc
    if result != "ok":
        output_path.unlink(missing_ok=True)
        raise DatabaseReconstructionError(f"SQLite integrity check failed: {result}")
    return ReconstructedDatabase(output_path, account, wal_frames_applied)
