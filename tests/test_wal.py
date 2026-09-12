import sqlite3
from pathlib import Path

import pytest

from dingtalk_exporter.crypto import derive_v2_key
from dingtalk_exporter.database import apply_committed_wal, reconstruct_database
from dingtalk_exporter.errors import DatabaseReconstructionError
from dingtalk_exporter.models import AccountCandidate
from conftest import PAGE_SIZE, encrypt_pages, make_sqlite_file, make_wal


def test_apply_committed_wal_ignores_trailing_uncommitted_frame(tmp_path: Path):
    key = derive_v2_key("1234567890")
    base = bytearray(b"A" * PAGE_SIZE * 2)
    committed_plain = b"B" * PAGE_SIZE
    uncommitted_plain = b"C" * PAGE_SIZE
    wal = make_wal([(2, 2, encrypt_pages(committed_plain, key)), (2, 0, encrypt_pages(uncommitted_plain, key))])
    rebuilt, applied = apply_committed_wal(base, wal, key)
    assert applied == 1
    assert rebuilt[PAGE_SIZE:PAGE_SIZE * 2] == committed_plain


def test_reconstruct_database_produces_valid_sqlite(tmp_path: Path):
    uid = "1234567890"
    key = derive_v2_key(uid)
    plain_path = tmp_path / "plain.db"
    plain = make_sqlite_file(plain_path, ["hello"])
    account_dir = tmp_path / f"{uid}_v2"
    db_dir = account_dir / "DBFiles"
    db_dir.mkdir(parents=True)
    encrypted_path = db_dir / "dingtalk.db"
    encrypted_path.write_bytes(encrypt_pages(plain, key))
    account = AccountCandidate(uid, account_dir, encrypted_path, None)
    output = tmp_path / "reconstructed.db"
    result = reconstruct_database(account, output)
    con = sqlite3.connect(result.path)
    assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert con.execute("SELECT value FROM messages").fetchone()[0] == "hello"
    con.close()


def test_invalid_wal_magic_is_rejected():
    key = derive_v2_key("1234567890")
    bad_wal = b"BAD!" + bytes(28)
    with pytest.raises(DatabaseReconstructionError, match="WAL magic"):
        apply_committed_wal(bytearray(PAGE_SIZE), bad_wal, key)
