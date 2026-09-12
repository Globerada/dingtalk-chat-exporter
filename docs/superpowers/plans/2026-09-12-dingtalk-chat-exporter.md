# DingTalk Chat Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-first Python CLI that discovers compatible DingTalk V2 local databases, derives and validates the decryption key, reconstructs SQLite state including committed WAL frames, resolves conversations and participant names, and exports one selected conversation to JSON, CSV, TXT, and HTML.

**Architecture:** The public entry point is `dingtalk_export.py`; all behavior lives in focused modules under `dingtalk_exporter/`. Source DingTalk files are opened read-only, decrypted/reconstructed bytes are written only to an application-owned temporary directory, and schema/name/content handling is capability-driven rather than hardcoded to one exact table count. The implementation uses strict validation boundaries so unsupported DingTalk formats fail safely and actionably.

**Tech Stack:** Python 3.10+, standard library (`sqlite3`, `hashlib`, `json`, `csv`, `tempfile`, `pathlib`, `html`, `subprocess`), `pycryptodome` for AES-128-ECB, `pytest` for tests.

**Spec:** `docs/superpowers/specs/2026-09-12-dingtalk-chat-exporter-design.md`

## Global Constraints

- Public-facing documentation, CLI prompts, code comments, examples, and error messages are English-only.
- v1 supports Windows only and only the validated DingTalk `_v2` local account layout.
- Primary discovery root is `%APPDATA%\\DingTalk`; compatible candidates contain `DBFiles\\dingtalk.db`.
- Validated database page size is exactly 4096 bytes.
- Validated cipher is AES-128-ECB.
- Validated key derivation is lowercase `MD5(uid)` with the first 16 hexadecimal characters encoded as ASCII.
- Source DingTalk files must never be modified, renamed, deleted, checkpointed, or opened for SQL writes.
- Final export requires DingTalk to be closed; the tool must not terminate DingTalk automatically.
- WAL handling must apply only frames through the final committed transaction and must ignore uncommitted trailing frames.
- Reconstructed SQLite must pass `PRAGMA quick_check` with result `ok` before chat discovery.
- Message shard tables are discovered dynamically with `name LIKE 'tbmsg_%'`; do not assume exactly 128 shards.
- Unknown message/content types must be preserved rather than discarded.
- JSON preserves normalized fields plus selected raw fields; CSV is UTF-8 with BOM; HTML is self-contained and escapes all untrusted content.
- Tests must use synthetic fixtures only; no real DingTalk user database or chat content may be committed.
- Runtime dependencies remain limited to `pycryptodome`; test dependency is `pytest`.
- MIT is the default project license.

---

## File Structure

Create and maintain these files:

```text
dingtalk-chat-exporter/
├── dingtalk_export.py                  # Thin CLI entry point.
├── requirements.txt                    # Runtime dependency pin floor.
├── requirements-dev.txt                # Test dependency.
├── README.md                           # Full English user/developer documentation.
├── LICENSE                             # MIT license text.
├── .gitignore                          # Python caches, exports, temp/decrypted DBs.
├── dingtalk_exporter/
│   ├── __init__.py                     # Package metadata/version.
│   ├── models.py                       # Shared dataclasses and typed records.
│   ├── errors.py                       # Custom exception hierarchy.
│   ├── discovery.py                    # Windows account discovery and running-state detection.
│   ├── crypto.py                       # Key derivation and page decryption.
│   ├── database.py                     # DB + WAL reconstruction and SQLite validation.
│   ├── messages.py                     # Shard discovery, schema validation, content parsing, chat loading.
│   ├── profiles.py                     # User-name evidence collection and deterministic resolution.
│   ├── conversations.py                # Conversation inventory, participant inference, display naming.
│   ├── exporters.py                    # Path sanitization and JSON/CSV/TXT/HTML writers.
│   └── cli.py                          # Interactive orchestration and cleanup.
├── tests/
│   ├── conftest.py                     # Shared synthetic DB/WAL fixture helpers.
│   ├── test_discovery.py
│   ├── test_crypto.py
│   ├── test_wal.py
│   ├── test_messages.py
│   ├── test_profiles.py
│   ├── test_conversations.py
│   ├── test_exporters.py
│   ├── test_cli.py
│   └── test_integration.py
└── docs/
    ├── compatibility.md
    ├── privacy-and-safety.md
    └── troubleshooting.md
```

---

### Task 1: Establish package contracts, models, errors, and test runner

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `dingtalk_exporter/__init__.py`
- Create: `dingtalk_exporter/models.py`
- Create: `dingtalk_exporter/errors.py`
- Create: `tests/test_models.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `AccountCandidate`, `ReconstructedDatabase`, `NormalizedMessage`, `ConversationSummary`, `ExportPaths` dataclasses.
- Produces: `DingTalkExporterError`, `DiscoveryError`, `CompatibilityError`, `DatabaseReconstructionError`, `SchemaError`, `ExportError` exceptions.
- Later tasks import these contracts directly; field names must remain stable.

- [ ] **Step 1: Write the failing model/error test**

```python
# tests/test_models.py
from pathlib import Path

from dingtalk_exporter.errors import CompatibilityError, DingTalkExporterError
from dingtalk_exporter.models import AccountCandidate, NormalizedMessage


def test_shared_contracts_are_constructible():
    account = AccountCandidate(
        uid="1234567890",
        account_dir=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2"),
        database_path=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2/DBFiles/dingtalk.db"),
        wal_path=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2/DBFiles/dingtalk.db-wal"),
    )
    message = NormalizedMessage(
        conversation_id="cid-1",
        message_id=123,
        local_id="local-1",
        sender_id=456,
        sender_name="Alice",
        timestamp=1755176432118,
        datetime="2025-08-14 15:00:32",
        message_type=1,
        content_type=1,
        text="Hello",
        recalled=False,
        attachments=[],
        source_table="tbmsg_004",
        raw_content='{"text":"Hello"}',
        raw_extension="",
        raw_attachments="",
    )

    assert account.uid == "1234567890"
    assert message.sender_name == "Alice"
    assert issubclass(CompatibilityError, DingTalkExporterError)
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
python -m pytest tests/test_models.py -v
```

Expected: FAIL because `dingtalk_exporter.models` and `dingtalk_exporter.errors` do not exist.

- [ ] **Step 3: Implement the contracts**

```python
# dingtalk_exporter/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AccountCandidate:
    uid: str
    account_dir: Path
    database_path: Path
    wal_path: Path | None


@dataclass(frozen=True)
class ReconstructedDatabase:
    path: Path
    source_account: AccountCandidate
    wal_frames_applied: int


@dataclass
class NormalizedMessage:
    conversation_id: str
    message_id: int | None
    local_id: str | None
    sender_id: int | None
    sender_name: str
    timestamp: int | None
    datetime: str
    message_type: int | None
    content_type: int | None
    text: str
    recalled: bool
    attachments: list[Any]
    source_table: str
    raw_content: str | None
    raw_extension: str | None
    raw_attachments: str | None


@dataclass
class ConversationSummary:
    cid: str
    display_name: str
    participant_ids: list[int] = field(default_factory=list)
    participant_names: list[str] = field(default_factory=list)
    message_count: int = 0
    last_message_timestamp: int | None = None


@dataclass(frozen=True)
class ExportPaths:
    directory: Path
    json_path: Path
    csv_path: Path
    txt_path: Path
    html_path: Path
```

```python
# dingtalk_exporter/errors.py
class DingTalkExporterError(Exception):
    """Base exception for expected exporter failures."""


class DiscoveryError(DingTalkExporterError):
    pass


class CompatibilityError(DingTalkExporterError):
    pass


class DatabaseReconstructionError(DingTalkExporterError):
    pass


class SchemaError(DingTalkExporterError):
    pass


class ExportError(DingTalkExporterError):
    pass
```

```python
# dingtalk_exporter/__init__.py
__version__ = "0.1.0"
```

```text
# requirements.txt
pycryptodome>=3.23,<4
```

```text
# requirements-dev.txt
-r requirements.txt
pytest>=8,<9
```

```gitignore
__pycache__/
.pytest_cache/
*.pyc
*.pyo
*.pyd
.venv/
venv/
exports/
*.decrypted.db
*.reconstructed.db
*.sqlite.tmp
```

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```bash
python -m pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt requirements-dev.txt .gitignore dingtalk_exporter tests/test_models.py
git commit -m "chore: establish exporter package contracts"
```

---

### Task 2: Discover compatible Windows account directories and detect running DingTalk

**Files:**
- Create: `dingtalk_exporter/discovery.py`
- Create: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `AccountCandidate`, `DiscoveryError`.
- Produces: `discover_accounts(appdata_root: Path | None = None) -> list[AccountCandidate]`.
- Produces: `is_dingtalk_running(process_listing: str | None = None) -> bool`.
- `discover_accounts` returns numeric `_v2` candidates only when `DBFiles/dingtalk.db` exists.

- [ ] **Step 1: Write failing discovery tests**

```python
# tests/test_discovery.py
from pathlib import Path

from dingtalk_exporter.discovery import discover_accounts, is_dingtalk_running


def test_discover_accounts_returns_only_numeric_v2_databases(tmp_path: Path):
    root = tmp_path / "DingTalk"
    good = root / "1234567890_v2" / "DBFiles"
    good.mkdir(parents=True)
    (good / "dingtalk.db").write_bytes(b"encrypted")
    (good / "dingtalk.db-wal").write_bytes(b"wal")

    bad_missing_db = root / "123_v2" / "DBFiles"
    bad_missing_db.mkdir(parents=True)
    bad_non_numeric = root / "abc_v2" / "DBFiles"
    bad_non_numeric.mkdir(parents=True)
    (bad_non_numeric / "dingtalk.db").write_bytes(b"encrypted")

    accounts = discover_accounts(root)

    assert [a.uid for a in accounts] == ["1234567890"]
    assert accounts[0].wal_path == good / "dingtalk.db-wal"


def test_running_state_parses_tasklist_csv_text():
    running = '"DingTalk.exe","24824","Console","1","100,000 K"\n'
    stopped = '"python.exe","100","Console","1","20,000 K"\n'

    assert is_dingtalk_running(running) is True
    assert is_dingtalk_running(stopped) is False
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_discovery.py -v
```

Expected: FAIL because `dingtalk_exporter.discovery` does not exist.

- [ ] **Step 3: Implement account and process discovery**

```python
# dingtalk_exporter/discovery.py
from __future__ import annotations

import csv
import io
import os
import subprocess
from pathlib import Path

from .errors import DiscoveryError
from .models import AccountCandidate


def _default_root() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise DiscoveryError("APPDATA is not set; DingTalk account discovery is unavailable.")
    return Path(appdata) / "DingTalk"


def discover_accounts(appdata_root: Path | None = None) -> list[AccountCandidate]:
    root = appdata_root or _default_root()
    if not root.exists():
        return []

    accounts: list[AccountCandidate] = []
    for account_dir in sorted(root.glob("*_v2")):
        if not account_dir.is_dir():
            continue
        uid = account_dir.name[:-3]
        if not uid.isdigit():
            continue
        database_path = account_dir / "DBFiles" / "dingtalk.db"
        if not database_path.is_file():
            continue
        wal_candidate = Path(str(database_path) + "-wal")
        accounts.append(
            AccountCandidate(
                uid=uid,
                account_dir=account_dir,
                database_path=database_path,
                wal_path=wal_candidate if wal_candidate.is_file() else None,
            )
        )
    return accounts


def is_dingtalk_running(process_listing: str | None = None) -> bool:
    if process_listing is None:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        process_listing = completed.stdout

    for row in csv.reader(io.StringIO(process_listing)):
        if row and row[0].casefold() == "dingtalk.exe":
            return True
    return False
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_discovery.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/discovery.py tests/test_discovery.py
git commit -m "feat: discover DingTalk V2 accounts"
```

---

### Task 3: Implement and validate V2 key derivation and AES page decryption

**Files:**
- Create: `dingtalk_exporter/crypto.py`
- Create: `tests/test_crypto.py`

**Interfaces:**
- Consumes: `CompatibilityError`.
- Produces: `derive_v2_key(uid: str) -> bytes`.
- Produces: `decrypt_page(page: bytes, key: bytes) -> bytes`.
- Produces: `validate_first_page(encrypted_page: bytes, key: bytes) -> bytes` that returns the decrypted page or raises `CompatibilityError`.

- [ ] **Step 1: Write failing crypto tests**

```python
# tests/test_crypto.py
from Crypto.Cipher import AES
import pytest

from dingtalk_exporter.crypto import decrypt_page, derive_v2_key, validate_first_page
from dingtalk_exporter.errors import CompatibilityError


def test_known_uid_derives_validated_v2_key():
    assert derive_v2_key("1234567890") == b"e807f1fcf82d132f"


def test_validate_first_page_recovers_sqlite_header():
    key = derive_v2_key("1234567890")
    plain = b"SQLite format 3\x00" + bytes(4096 - 16)
    encrypted = AES.new(key, AES.MODE_ECB).encrypt(plain)

    assert validate_first_page(encrypted, key).startswith(b"SQLite format 3\x00")


def test_invalid_key_is_rejected():
    good_key = derive_v2_key("1234567890")
    plain = b"SQLite format 3\x00" + bytes(4096 - 16)
    encrypted = AES.new(good_key, AES.MODE_ECB).encrypt(plain)

    with pytest.raises(CompatibilityError, match="SQLite header"):
        validate_first_page(encrypted, b"0000000000000000")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_crypto.py -v
```

Expected: FAIL because `crypto.py` does not exist.

- [ ] **Step 3: Implement key derivation and page decryption**

```python
# dingtalk_exporter/crypto.py
from __future__ import annotations

import hashlib
from Crypto.Cipher import AES

from .errors import CompatibilityError

SQLITE_HEADER = b"SQLite format 3\x00"
PAGE_SIZE = 4096


def derive_v2_key(uid: str) -> bytes:
    if not uid.isdigit():
        raise CompatibilityError("Unsupported account UID: expected a numeric `_v2` directory prefix.")
    digest = hashlib.md5(uid.encode("utf-8")).hexdigest()
    return digest[:16].encode("ascii")


def decrypt_page(page: bytes, key: bytes) -> bytes:
    if len(key) != 16:
        raise CompatibilityError("Invalid DingTalk V2 AES key length; expected 16 bytes.")
    if len(page) % AES.block_size != 0:
        raise CompatibilityError("Encrypted page length is not aligned to the AES block size.")
    return AES.new(key, AES.MODE_ECB).decrypt(page)


def validate_first_page(encrypted_page: bytes, key: bytes) -> bytes:
    if len(encrypted_page) != PAGE_SIZE:
        raise CompatibilityError("Unsupported DingTalk database page size; expected 4096 bytes.")
    decrypted = decrypt_page(encrypted_page, key)
    if not decrypted.startswith(SQLITE_HEADER):
        raise CompatibilityError(
            "Unsupported DingTalk database format: the decrypted first page did not contain a valid SQLite header."
        )
    return decrypted
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_crypto.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/crypto.py tests/test_crypto.py
git commit -m "feat: decrypt DingTalk V2 database pages"
```

---

### Task 4: Reconstruct the current SQLite database from encrypted DB + committed WAL

**Files:**
- Create: `dingtalk_exporter/database.py`
- Create: `tests/conftest.py`
- Create: `tests/test_wal.py`

**Interfaces:**
- Consumes: `AccountCandidate`, `ReconstructedDatabase`, `derive_v2_key`, `decrypt_page`, `validate_first_page`.
- Produces: `reconstruct_database(account: AccountCandidate, output_path: Path) -> ReconstructedDatabase`.
- Produces internal pure helper `apply_committed_wal(base: bytearray, wal: bytes, key: bytes, page_size: int = 4096) -> tuple[bytearray, int]` for deterministic unit testing.

- [ ] **Step 1: Add synthetic encrypted DB/WAL fixture helpers**

```python
# tests/conftest.py
import sqlite3
import struct
from pathlib import Path

from Crypto.Cipher import AES

PAGE_SIZE = 4096


def encrypt_pages(data: bytes, key: bytes) -> bytes:
    assert len(data) % PAGE_SIZE == 0
    cipher = AES.new(key, AES.MODE_ECB)
    return b"".join(cipher.encrypt(data[i:i + PAGE_SIZE]) for i in range(0, len(data), PAGE_SIZE))


def make_sqlite_file(path: Path, rows: list[str]) -> bytes:
    con = sqlite3.connect(path)
    con.execute("PRAGMA page_size=4096")
    con.execute("CREATE TABLE messages(value TEXT)")
    con.executemany("INSERT INTO messages(value) VALUES (?)", [(row,) for row in rows])
    con.commit()
    con.close()
    data = path.read_bytes()
    assert len(data) % PAGE_SIZE == 0
    return data


def make_wal(frames: list[tuple[int, int, bytes]], page_size: int = PAGE_SIZE) -> bytes:
    header = struct.pack(
        ">8I",
        0x377F0682,
        3007000,
        page_size,
        0,
        1,
        2,
        0,
        0,
    )
    output = bytearray(header)
    for page_number, db_size, payload in frames:
        assert len(payload) == page_size
        frame_header = struct.pack(">6I", page_number, db_size, 1, 2, 0, 0)
        output.extend(frame_header)
        output.extend(payload)
    return bytes(output)
```

- [ ] **Step 2: Write failing WAL tests**

```python
# tests/test_wal.py
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
    wal = make_wal([
        (2, 2, encrypt_pages(committed_plain, key)),
        (2, 0, encrypt_pages(uncommitted_plain, key)),
    ])

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
```

- [ ] **Step 3: Verify RED**

Run:

```bash
python -m pytest tests/test_wal.py -v
```

Expected: FAIL because `database.py` does not exist.

- [ ] **Step 4: Implement DB + WAL reconstruction**

```python
# dingtalk_exporter/database.py
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


def apply_committed_wal(
    base: bytearray,
    wal: bytes,
    key: bytes,
    page_size: int = PAGE_SIZE,
) -> tuple[bytearray, int]:
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
        rebuilt, wal_frames_applied = apply_committed_wal(
            rebuilt,
            account.wal_path.read_bytes(),
            key,
            PAGE_SIZE,
        )

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
```

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python -m pytest tests/test_wal.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add dingtalk_exporter/database.py tests/conftest.py tests/test_wal.py
git commit -m "feat: reconstruct SQLite database with committed WAL"
```

---

### Task 5: Discover message shards, validate schema, and normalize message content

**Files:**
- Create: `dingtalk_exporter/messages.py`
- Create: `tests/test_messages.py`

**Interfaces:**
- Consumes: `NormalizedMessage`, `SchemaError`.
- Produces: `discover_message_tables(connection: sqlite3.Connection) -> list[str]`.
- Produces: `extract_readable_text(content: str | None, attachments: str | None, content_type: int | None) -> tuple[str, list[object]]`.
- Produces: `load_messages(connection, cid: str, sender_names: dict[int, str]) -> list[NormalizedMessage]`.

- [ ] **Step 1: Write failing message tests**

```python
# tests/test_messages.py
import json
import sqlite3

from dingtalk_exporter.messages import discover_message_tables, extract_readable_text, load_messages


def make_connection() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    schema = """
        CREATE TABLE tbmsg_004(
            primaryKey INTEGER PRIMARY KEY,
            cid TEXT NOT NULL,
            localId TEXT,
            mid INTEGER NOT NULL,
            senderId INTEGER,
            type INTEGER,
            createdAt INTEGER,
            contentType INTEGER,
            content TEXT,
            extension TEXT,
            recallStatus INTEGER DEFAULT 0,
            attachments TEXT
        )
    """
    con.execute(schema)
    return con


def test_plain_text_and_markdown_are_normalized():
    assert extract_readable_text('{"contentType":1,"text":"Hello"}', "", 1)[0] == "Hello"

    attachments = json.dumps([
        json.dumps({"type": 1200, "extension": {"markdown": "**Readable** text", "title": "Fallback"}})
    ])
    assert extract_readable_text("{}", attachments, 1200)[0] == "**Readable** text"


def test_unknown_content_is_preserved_as_readable_fallback():
    raw = '{"contentType":9999,"custom":"value"}'
    assert extract_readable_text(raw, "", 9999)[0] == raw


def test_load_messages_sorts_by_created_at_then_mid():
    con = make_connection()
    con.executemany(
        "INSERT INTO tbmsg_004(cid, localId, mid, senderId, type, createdAt, contentType, content, extension, recallStatus, attachments) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("c1", "b", 20, 2, 1, 1000, 1, '{"text":"second"}', "", 0, ""),
            ("c1", "a", 10, 1, 1, 1000, 1, '{"text":"first"}', "", 0, ""),
        ],
    )

    messages = load_messages(con, "c1", {1: "Me", 2: "Alice"})

    assert [m.text for m in messages] == ["first", "second"]
    assert [m.sender_name for m in messages] == ["Me", "Alice"]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_messages.py -v
```

Expected: FAIL because `messages.py` does not exist.

- [ ] **Step 3: Implement schema discovery and message normalization**

```python
# dingtalk_exporter/messages.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .errors import SchemaError
from .models import NormalizedMessage

REQUIRED_MESSAGE_COLUMNS = {"cid", "mid", "senderId", "createdAt", "content"}


def discover_message_tables(connection: sqlite3.Connection) -> list[str]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tbmsg_%' ORDER BY name"
        )
    ]
    valid: list[str] = []
    for name in names:
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')}
        if REQUIRED_MESSAGE_COLUMNS.issubset(columns):
            valid.append(name)
    if not valid:
        raise SchemaError("No compatible DingTalk message shard tables were found.")
    return valid


def _parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _attachment_objects(value: str | None) -> list[Any]:
    parsed = _parse_json(value)
    if not isinstance(parsed, list):
        return []
    result: list[Any] = []
    for item in parsed:
        if isinstance(item, str):
            decoded = _parse_json(item)
            result.append(decoded if decoded is not None else item)
        else:
            result.append(item)
    return result


def extract_readable_text(
    content: str | None,
    attachments: str | None,
    content_type: int | None,
) -> tuple[str, list[Any]]:
    content_obj = _parse_json(content)
    attachment_objects = _attachment_objects(attachments)

    if isinstance(content_obj, dict):
        text = content_obj.get("text")
        if isinstance(text, str) and text:
            return text, attachment_objects
        summary_parts: list[str] = []
        for key in ("title", "summary"):
            value = content_obj.get(key)
            if isinstance(value, str) and value:
                summary_parts.append(value)
        embedded = content_obj.get("attachments")
        if isinstance(embedded, list):
            attachment_objects.extend(embedded)
        if summary_parts:
            return "\n".join(dict.fromkeys(summary_parts)), attachment_objects

    for item in attachment_objects:
        if not isinstance(item, dict):
            continue
        extension = item.get("extension")
        if isinstance(extension, str):
            extension = _parse_json(extension)
        if not isinstance(extension, dict):
            continue
        for key in ("markdown", "summary", "title"):
            value = extension.get(key)
            if isinstance(value, str) and value:
                return value, attachment_objects

    return content or "", attachment_objects


def _format_timestamp(timestamp: int | None) -> str:
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")


def load_messages(
    connection: sqlite3.Connection,
    cid: str,
    sender_names: dict[int, str],
) -> list[NormalizedMessage]:
    messages: list[NormalizedMessage] = []
    for table in discover_message_tables(connection):
        columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
        optional = {
            "localId": "NULL AS localId",
            "type": "NULL AS type",
            "contentType": "NULL AS contentType",
            "extension": "NULL AS extension",
            "recallStatus": "0 AS recallStatus",
            "attachments": "NULL AS attachments",
        }
        selected = ["cid", "mid", "senderId", "createdAt", "content"]
        for name, fallback in optional.items():
            selected.append(name if name in columns else fallback)
        sql = f'SELECT {", ".join(selected)} FROM "{table}" WHERE cid = ?'
        for row in connection.execute(sql, (cid,)):
            text, parsed_attachments = extract_readable_text(row["content"], row["attachments"], row["contentType"])
            sender_id = row["senderId"]
            messages.append(
                NormalizedMessage(
                    conversation_id=cid,
                    message_id=row["mid"],
                    local_id=row["localId"],
                    sender_id=sender_id,
                    sender_name=sender_names.get(sender_id, str(sender_id) if sender_id is not None else "Unknown"),
                    timestamp=row["createdAt"],
                    datetime=_format_timestamp(row["createdAt"]),
                    message_type=row["type"],
                    content_type=row["contentType"],
                    text=text,
                    recalled=bool(row["recallStatus"]),
                    attachments=parsed_attachments,
                    source_table=table,
                    raw_content=row["content"],
                    raw_extension=row["extension"],
                    raw_attachments=row["attachments"],
                )
            )
    messages.sort(key=lambda item: (item.timestamp or 0, item.message_id or 0))
    return messages
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_messages.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/messages.py tests/test_messages.py
git commit -m "feat: normalize DingTalk message shards"
```

---

### Task 6: Resolve user profile names from aliases, profiles, mentions, and forwarded metadata

**Files:**
- Create: `dingtalk_exporter/profiles.py`
- Create: `tests/test_profiles.py`

**Interfaces:**
- Produces: `resolve_profile_names(connection: sqlite3.Connection, current_uid: int, message_tables: list[str]) -> dict[int, str]`.
- Deterministic precedence: alias/display name > profile name > group nickname > `atIds` evidence > forwarded sender metadata > current user fallback `Me` > raw UID handled by callers.

- [ ] **Step 1: Write failing profile precedence test**

```python
# tests/test_profiles.py
import sqlite3

from dingtalk_exporter.profiles import resolve_profile_names


def test_alias_beats_profile_and_mentions_fill_missing_names():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tbuser_profile_v2(uid INTEGER, nick TEXT)")
    con.execute("CREATE TABLE tbuser_alias_name(uid INTEGER, alias TEXT)")
    con.execute("CREATE TABLE tbmsg_000(cid TEXT, mid INTEGER, senderId INTEGER, createdAt INTEGER, content TEXT, atIds TEXT)")
    con.execute("INSERT INTO tbuser_profile_v2 VALUES (2, 'Profile Alice')")
    con.execute("INSERT INTO tbuser_alias_name VALUES (2, 'Alice')")
    con.execute("INSERT INTO tbmsg_000 VALUES ('c1', 1, 2, 1, '{}', '{\"3\":\"Bob\"}')")

    names = resolve_profile_names(con, current_uid=1, message_tables=["tbmsg_000"])

    assert names[1] == "Me"
    assert names[2] == "Alice"
    assert names[3] == "Bob"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_profiles.py -v
```

Expected: FAIL because `profiles.py` does not exist.

- [ ] **Step 3: Implement schema-tolerant profile evidence collection**

```python
# dingtalk_exporter/profiles.py
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _best_id_column(columns: list[str]) -> str | None:
    priorities = ["uid", "userId", "userid", "user_id", "openId", "openid", "id"]
    lower = {name.casefold(): name for name in columns}
    for candidate in priorities:
        if candidate.casefold() in lower:
            return lower[candidate.casefold()]
    return next((name for name in columns if name.casefold().endswith("uid")), None)


def _best_name_columns(columns: list[str]) -> list[str]:
    wanted = ("alias", "displayname", "display_name", "nick", "nickname", "realname", "real_name", "name", "username")
    ordered: list[str] = []
    for wanted_name in wanted:
        for column in columns:
            if column.casefold() == wanted_name.casefold() and column not in ordered:
                ordered.append(column)
    return ordered


def _collect_from_table(connection: sqlite3.Connection, table: str) -> dict[int, str]:
    if not _table_exists(connection, table):
        return {}
    columns = _columns(connection, table)
    id_column = _best_id_column(columns)
    name_columns = _best_name_columns(columns)
    if not id_column or not name_columns:
        return {}
    result: dict[int, str] = {}
    for row in connection.execute(f'SELECT * FROM "{table}"'):
        mapping = dict(row)
        try:
            uid = int(mapping[id_column])
        except (TypeError, ValueError):
            continue
        for name_column in name_columns:
            value = mapping.get(name_column)
            if isinstance(value, str) and value.strip():
                result[uid] = value.strip()
                break
    return result


def resolve_profile_names(
    connection: sqlite3.Connection,
    current_uid: int,
    message_tables: list[str],
) -> dict[int, str]:
    connection.row_factory = sqlite3.Row
    names: dict[int, str] = {current_uid: "Me"}

    # Lower-priority sources are applied first; higher-priority sources overwrite later.
    for table in ("tbuser_group_nick", "tbuser_profile_v2", "tbuser_alias_name"):
        names.update(_collect_from_table(connection, table))

    mention_evidence: dict[int, list[str]] = defaultdict(list)
    for table in message_tables:
        columns = set(_columns(connection, table))
        if "atIds" not in columns:
            continue
        for (raw_at_ids,) in connection.execute(f'SELECT atIds FROM "{table}" WHERE atIds IS NOT NULL AND atIds != ""'):
            try:
                data = json.loads(raw_at_ids)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            for raw_uid, raw_name in data.items():
                try:
                    uid = int(raw_uid)
                except (TypeError, ValueError):
                    continue
                if isinstance(raw_name, str) and raw_name.strip():
                    mention_evidence[uid].append(raw_name.strip())

    for uid, candidates in mention_evidence.items():
        if uid not in names and candidates:
            names[uid] = sorted(candidates, key=lambda value: (-candidates.count(value), value.casefold()))[0]

    names[current_uid] = names.get(current_uid) or "Me"
    return names
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_profiles.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/profiles.py tests/test_profiles.py
git commit -m "feat: resolve DingTalk participant names"
```

---

### Task 7: Build conversation inventory and deterministic display names

**Files:**
- Create: `dingtalk_exporter/conversations.py`
- Create: `tests/test_conversations.py`

**Interfaces:**
- Consumes: `ConversationSummary`, `discover_message_tables`.
- Produces: `discover_conversations(connection, current_uid: int, names: dict[int, str]) -> list[ConversationSummary]`.
- Produces: `resolve_conversation_name(cid, explicit_title, participant_ids, current_uid, names) -> str`.

- [ ] **Step 1: Write failing naming/inventory tests**

```python
# tests/test_conversations.py
import sqlite3

from dingtalk_exporter.conversations import discover_conversations, resolve_conversation_name


def test_one_to_one_name_prefers_other_participant():
    assert resolve_conversation_name(
        cid="2222222222:1234567890",
        explicit_title=None,
        participant_ids=[2222222222, 1234567890],
        current_uid=1234567890,
        names={2222222222: "Alice", 1234567890: "Me"},
    ) == "Alice"


def test_explicit_group_title_wins():
    assert resolve_conversation_name(
        cid="69169246850",
        explicit_title="Project Team",
        participant_ids=[1, 2, 3],
        current_uid=1,
        names={1: "Me", 2: "Alice", 3: "Bob"},
    ) == "Project Team"


def test_discovery_counts_messages_and_last_timestamp():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tbmsg_000(cid TEXT, mid INTEGER, senderId INTEGER, createdAt INTEGER, content TEXT)")
    con.executemany(
        "INSERT INTO tbmsg_000 VALUES (?,?,?,?,?)",
        [("c1", 1, 1, 100, '{}'), ("c1", 2, 2, 200, '{}')],
    )

    conversations = discover_conversations(con, current_uid=1, names={1: "Me", 2: "Alice"})

    assert conversations[0].message_count == 2
    assert conversations[0].last_message_timestamp == 200
    assert conversations[0].display_name == "Alice"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_conversations.py -v
```

Expected: FAIL because `conversations.py` does not exist.

- [ ] **Step 3: Implement efficient SQL aggregation and naming fallbacks**

```python
# dingtalk_exporter/conversations.py
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from .messages import discover_message_tables
from .models import ConversationSummary


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _explicit_titles(connection: sqlite3.Connection) -> dict[str, str]:
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tbconversation'").fetchone() is None:
        return {}
    columns = _table_columns(connection, "tbconversation")
    cid_column = next((name for name in columns if name.casefold() == "cid"), None)
    title_column = next(
        (name for name in columns if name.casefold() in {"title", "name", "conversationname", "conversation_name", "nick"}),
        None,
    )
    if not cid_column or not title_column:
        return {}
    titles: dict[str, str] = {}
    for cid, title in connection.execute(f'SELECT "{cid_column}", "{title_column}" FROM tbconversation'):
        if cid is not None and isinstance(title, str) and title.strip():
            titles[str(cid)] = title.strip()
    return titles


def resolve_conversation_name(
    cid: str,
    explicit_title: str | None,
    participant_ids: list[int],
    current_uid: int,
    names: dict[int, str],
) -> str:
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()

    if ":" in cid:
        encoded = []
        for part in cid.split(":"):
            try:
                encoded.append(int(part))
            except ValueError:
                encoded = []
                break
        if encoded:
            participant_ids = sorted(set(participant_ids) | set(encoded))

    others = [uid for uid in participant_ids if uid != current_uid]
    resolved_others = [names[uid] for uid in others if uid in names and names[uid]]
    if len(others) == 1 and resolved_others:
        return resolved_others[0]

    participant_names = [names[uid] for uid in participant_ids if uid in names and names[uid]]
    participant_names = list(dict.fromkeys(participant_names))
    if participant_names:
        return ", ".join(participant_names[:4]) + (" + others" if len(participant_names) > 4 else "")
    return cid


def discover_conversations(
    connection: sqlite3.Connection,
    current_uid: int,
    names: dict[int, str],
) -> list[ConversationSummary]:
    tables = discover_message_tables(connection)
    titles = _explicit_titles(connection)
    counts: dict[str, int] = defaultdict(int)
    latest: dict[str, int] = {}
    participants: dict[str, set[int]] = defaultdict(set)

    for table in tables:
        sql = f'''SELECT cid, COUNT(*) AS n, MAX(createdAt) AS latest FROM "{table}" GROUP BY cid'''
        for cid, count, max_created in connection.execute(sql):
            if cid is None:
                continue
            cid = str(cid)
            counts[cid] += int(count)
            if max_created is not None:
                latest[cid] = max(latest.get(cid, int(max_created)), int(max_created))
        for cid, sender_id in connection.execute(f'SELECT DISTINCT cid, senderId FROM "{table}" WHERE senderId IS NOT NULL'):
            if cid is not None:
                participants[str(cid)].add(int(sender_id))

    results: list[ConversationSummary] = []
    for cid in counts:
        ids = sorted(participants[cid] | {current_uid})
        display_name = resolve_conversation_name(cid, titles.get(cid), ids, current_uid, names)
        results.append(
            ConversationSummary(
                cid=cid,
                display_name=display_name,
                participant_ids=ids,
                participant_names=[names[uid] for uid in ids if uid in names],
                message_count=counts[cid],
                last_message_timestamp=latest.get(cid),
            )
        )
    results.sort(key=lambda item: (item.last_message_timestamp or 0, item.message_count), reverse=True)
    return results
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_conversations.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/conversations.py tests/test_conversations.py
git commit -m "feat: discover and name DingTalk conversations"
```

---

### Task 8: Export JSON, CSV, TXT, and self-contained HTML safely

**Files:**
- Create: `dingtalk_exporter/exporters.py`
- Create: `tests/test_exporters.py`

**Interfaces:**
- Consumes: `NormalizedMessage`, `ConversationSummary`, `ExportPaths`, `ExportError`.
- Produces: `sanitize_filename(name: str) -> str`.
- Produces: `export_conversation(conversation, messages, output_root: Path, current_uid: int) -> ExportPaths`.

- [ ] **Step 1: Write failing exporter tests**

```python
# tests/test_exporters.py
import csv
import json
from pathlib import Path

from dingtalk_exporter.exporters import export_conversation, sanitize_filename
from dingtalk_exporter.models import ConversationSummary, NormalizedMessage


def message(text: str) -> NormalizedMessage:
    return NormalizedMessage(
        conversation_id="cid/unsafe",
        message_id=1,
        local_id="a",
        sender_id=1,
        sender_name="Me & <Admin>",
        timestamp=1,
        datetime="1970-01-01 00:00:00",
        message_type=1,
        content_type=1,
        text=text,
        recalled=False,
        attachments=[],
        source_table="tbmsg_000",
        raw_content='{"text":"x"}',
        raw_extension="",
        raw_attachments="",
    )


def test_sanitize_filename_removes_windows_path_characters():
    assert sanitize_filename('AliExpress: UK/DE * Team?') == "AliExpress_ UK_DE _ Team_"


def test_exporters_preserve_unicode_and_escape_html(tmp_path: Path):
    conversation = ConversationSummary(cid="cid/unsafe", display_name="AliExpress: Team", message_count=1)
    paths = export_conversation(conversation, [message("你好 <script>alert(1)</script>")], tmp_path, current_uid=1)

    data = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert data[0]["text"].startswith("你好")
    assert paths.csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "<script>" not in paths.html_path.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in paths.html_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_exporters.py -v
```

Expected: FAIL because `exporters.py` does not exist.

- [ ] **Step 3: Implement the four exporters and path collision handling**

```python
# dingtalk_exporter/exporters.py
from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict
from pathlib import Path

from .errors import ExportError
from .models import ConversationSummary, ExportPaths, NormalizedMessage

INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    cleaned = INVALID_WINDOWS_CHARS.sub("_", name).strip().rstrip(".")
    return cleaned[:120] or "conversation"


def _choose_directory(output_root: Path, conversation: ConversationSummary) -> Path:
    base = output_root / sanitize_filename(conversation.display_name)
    if not base.exists():
        return base
    suffix = sanitize_filename(conversation.cid)[-12:]
    return output_root / f"{sanitize_filename(conversation.display_name)}_{suffix}"


def export_conversation(
    conversation: ConversationSummary,
    messages: list[NormalizedMessage],
    output_root: Path,
    current_uid: int,
) -> ExportPaths:
    try:
        directory = _choose_directory(output_root, conversation)
        directory.mkdir(parents=True, exist_ok=False)
        json_path = directory / "chat.json"
        csv_path = directory / "chat.csv"
        txt_path = directory / "chat.txt"
        html_path = directory / "chat.html"

        payload = [asdict(message) for message in messages]
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        csv_fields = ["datetime", "sender_name", "sender_id", "message_id", "message_type", "content_type", "text", "recalled"]
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=csv_fields)
            writer.writeheader()
            for item in payload:
                writer.writerow({field: item[field] for field in csv_fields})

        with txt_path.open("w", encoding="utf-8") as handle:
            for message in messages:
                handle.write(f"[{message.datetime}] {message.sender_name}:\n{message.text}\n\n")

        blocks: list[str] = []
        for message in messages:
            own = " own" if message.sender_id == current_uid else ""
            sender = html.escape(message.sender_name)
            text = html.escape(message.text).replace("\n", "<br>")
            timestamp = html.escape(message.datetime)
            blocks.append(
                f'<article class="message{own}"><div class="sender">{sender}</div>'
                f'<div class="text">{text}</div><div class="time">{timestamp}</div></article>'
            )
        title = html.escape(conversation.display_name)
        cid = html.escape(conversation.cid)
        document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — DingTalk export</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f5;margin:0;padding:24px}}
main{{max-width:900px;margin:auto}}header,.message{{background:#fff;border-radius:12px;padding:14px 16px;margin:10px 0}}
.message{{max-width:72%}}.message.own{{margin-left:auto;background:#dcf8c6}}.sender{{font-weight:600}}.time{{font-size:11px;color:#666;margin-top:7px}}
.text{{word-wrap:break-word}}</style></head><body><main><header><h1>{title}</h1><p>CID: {cid}<br>Messages: {len(messages)}</p></header>{''.join(blocks)}</main></body></html>'''
        html_path.write_text(document, encoding="utf-8")
        return ExportPaths(directory, json_path, csv_path, txt_path, html_path)
    except OSError as exc:
        raise ExportError(f"Could not write export files: {exc}") from exc
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_exporters.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dingtalk_exporter/exporters.py tests/test_exporters.py
git commit -m "feat: export DingTalk chats in four formats"
```

---

### Task 9: Implement interactive CLI orchestration with safe temporary cleanup

**Files:**
- Create: `dingtalk_exporter/cli.py`
- Create: `dingtalk_export.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes all previous modules.
- Produces: `run(input_fn=input, output_fn=print, appdata_root: Path | None = None, output_root: Path = Path("exports")) -> int`.
- `dingtalk_export.py` only imports `run` and exits with its return code.

- [ ] **Step 1: Write failing CLI selection tests**

```python
# tests/test_cli.py
from pathlib import Path

from dingtalk_exporter.cli import choose_index


def test_choose_index_reprompts_until_valid():
    answers = iter(["x", "0", "2"])
    output: list[str] = []

    selected = choose_index(
        label="Select conversation",
        count=3,
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )

    assert selected == 1
    assert len(output) == 2
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: FAIL because `cli.py` does not exist.

- [ ] **Step 3: Implement selection and orchestration**

```python
# dingtalk_exporter/cli.py
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Callable

from .conversations import discover_conversations
from .database import reconstruct_database
from .discovery import discover_accounts, is_dingtalk_running
from .errors import DingTalkExporterError
from .exporters import export_conversation
from .messages import discover_message_tables, load_messages
from .profiles import resolve_profile_names

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def choose_index(label: str, count: int, input_fn: InputFn = input, output_fn: OutputFn = print) -> int:
    while True:
        raw = input_fn(f"{label}: ").strip()
        try:
            value = int(raw)
        except ValueError:
            output_fn(f"Enter a number from 1 to {count}.")
            continue
        if 1 <= value <= count:
            return value - 1
        output_fn(f"Enter a number from 1 to {count}.")


def run(
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    appdata_root: Path | None = None,
    output_root: Path = Path("exports"),
) -> int:
    output_fn("DingTalk Chat Exporter")
    output_fn("")
    try:
        if is_dingtalk_running():
            raise DingTalkExporterError(
                "DingTalk appears to be running. Close it completely before exporting so the latest WAL state can be read consistently."
            )

        accounts = discover_accounts(appdata_root)
        if not accounts:
            raise DingTalkExporterError(
                "No compatible `_v2` DingTalk account databases were found under %APPDATA%\\DingTalk."
            )
        account = accounts[0]
        if len(accounts) > 1:
            output_fn("Accounts found:")
            for index, item in enumerate(accounts, 1):
                output_fn(f"  {index}. {item.uid}")
            account = accounts[choose_index("Select account", len(accounts), input_fn, output_fn)]

        with tempfile.TemporaryDirectory(prefix="dingtalk-export-") as temp_dir:
            reconstructed = reconstruct_database(account, Path(temp_dir) / "dingtalk.reconstructed.db")
            con = sqlite3.connect(f"file:{reconstructed.path.as_posix()}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            tables = discover_message_tables(con)
            names = resolve_profile_names(con, int(account.uid), tables)
            conversations = discover_conversations(con, int(account.uid), names)
            if not conversations:
                con.close()
                raise DingTalkExporterError("No conversations were found in the reconstructed database.")

            output_fn(f"Conversations found: {len(conversations)}")
            for index, conversation in enumerate(conversations, 1):
                output_fn(f"  {index:>3}. {conversation.display_name} — {conversation.message_count:,} messages")
            selected = conversations[choose_index("Select conversation", len(conversations), input_fn, output_fn)]
            messages = load_messages(con, selected.cid, names)
            con.close()
            paths = export_conversation(selected, messages, output_root, int(account.uid))

        output_fn("")
        output_fn("Export complete:")
        output_fn(str(paths.directory))
        return 0
    except DingTalkExporterError as exc:
        output_fn(f"Error: {exc}")
        return 1
```

```python
# dingtalk_export.py
from dingtalk_exporter.cli import run


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Smoke-check the public entry point without DingTalk data**

Run in a shell where `APPDATA` points to an empty temporary directory:

```bash
python dingtalk_export.py
```

Expected: an English actionable error stating that no compatible `_v2` database was found; no traceback.

- [ ] **Step 6: Commit**

```bash
git add dingtalk_exporter/cli.py dingtalk_export.py tests/test_cli.py
git commit -m "feat: add interactive one-command exporter"
```

---

### Task 10: Add a synthetic end-to-end encrypted fixture test

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_integration.py`

**Interfaces:**
- Tests the complete boundary: discovery fixture -> key derivation -> DB decryption -> WAL application -> name resolution -> conversation selection data -> message load -> exporters.
- No production interface changes are introduced unless the test exposes a design defect.

- [ ] **Step 1: Extend fixture helpers to create a minimal DingTalk-shaped schema**

```python
# append to tests/conftest.py
import json


def make_dingtalk_like_plain_db(path: Path) -> bytes:
    con = sqlite3.connect(path)
    con.execute("PRAGMA page_size=4096")
    con.execute("CREATE TABLE tbuser_profile_v2(uid INTEGER, nick TEXT)")
    con.execute("CREATE TABLE tbuser_alias_name(uid INTEGER, alias TEXT)")
    con.execute("CREATE TABLE tbmsg_000(primaryKey INTEGER PRIMARY KEY, cid TEXT, localId TEXT, mid INTEGER, senderId INTEGER, type INTEGER, createdAt INTEGER, contentType INTEGER, content TEXT, extension TEXT, recallStatus INTEGER, attachments TEXT, atIds TEXT)")
    con.execute("INSERT INTO tbuser_profile_v2 VALUES (2, 'Alice Profile')")
    con.execute("INSERT INTO tbuser_alias_name VALUES (2, 'Alice')")
    con.execute(
        "INSERT INTO tbmsg_000(cid,localId,mid,senderId,type,createdAt,contentType,content,extension,recallStatus,attachments,atIds) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("1:2", "local-1", 10, 2, 1, 1755176432118, 1, json.dumps({"contentType": 1, "text": "Hello there"}), "", 0, "", ""),
    )
    con.commit()
    con.close()
    data = path.read_bytes()
    assert len(data) % PAGE_SIZE == 0
    return data
```

- [ ] **Step 2: Write the end-to-end failing test**

```python
# tests/test_integration.py
import sqlite3
from pathlib import Path

from dingtalk_exporter.conversations import discover_conversations
from dingtalk_exporter.crypto import derive_v2_key
from dingtalk_exporter.database import reconstruct_database
from dingtalk_exporter.discovery import discover_accounts
from dingtalk_exporter.exporters import export_conversation
from dingtalk_exporter.messages import discover_message_tables, load_messages
from dingtalk_exporter.profiles import resolve_profile_names
from conftest import encrypt_pages, make_dingtalk_like_plain_db


def test_synthetic_encrypted_database_exports_end_to_end(tmp_path: Path):
    uid = "1"
    root = tmp_path / "DingTalk"
    db_dir = root / f"{uid}_v2" / "DBFiles"
    db_dir.mkdir(parents=True)
    plain = make_dingtalk_like_plain_db(tmp_path / "plain.db")
    (db_dir / "dingtalk.db").write_bytes(encrypt_pages(plain, derive_v2_key(uid)))

    account = discover_accounts(root)[0]
    rebuilt = reconstruct_database(account, tmp_path / "rebuilt.db")
    con = sqlite3.connect(rebuilt.path)
    con.row_factory = sqlite3.Row
    tables = discover_message_tables(con)
    names = resolve_profile_names(con, current_uid=1, message_tables=tables)
    conversations = discover_conversations(con, current_uid=1, names=names)
    messages = load_messages(con, conversations[0].cid, names)
    con.close()
    paths = export_conversation(conversations[0], messages, tmp_path / "exports", current_uid=1)

    assert conversations[0].display_name == "Alice"
    assert messages[0].text == "Hello there"
    assert paths.html_path.exists()
    assert paths.json_path.exists()
```

- [ ] **Step 3: Run the integration test and fix only defects it exposes**

Run:

```bash
python -m pytest tests/test_integration.py -v
```

Expected first run: FAIL only if an interface mismatch or schema capability assumption remains. Apply the smallest production-code correction needed, then rerun until PASS.

- [ ] **Step 4: Run the entire test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_integration.py dingtalk_exporter
git commit -m "test: cover encrypted export workflow end to end"
```

---

### Task 11: Write complete English README, compatibility, privacy, troubleshooting, license, and install metadata

**Files:**
- Create: `README.md`
- Create: `docs/compatibility.md`
- Create: `docs/privacy-and-safety.md`
- Create: `docs/troubleshooting.md`
- Create: `LICENSE`
- Create: `tests/test_documentation.py`

**Interfaces:**
- Public documentation contract: a new Windows user can clone, install, close DingTalk, run `python dingtalk_export.py`, select a chat, and understand where files are written.
- Documentation must not claim support outside the validated V2 Windows format.

- [ ] **Step 1: Write a failing documentation-presence test**

```python
# tests/test_documentation.py
from pathlib import Path


def test_readme_documents_required_public_workflow_and_disclaimer():
    readme = Path("README.md").read_text(encoding="utf-8")
    required = [
        "Windows only",
        "python dingtalk_export.py",
        "pip install -r requirements.txt",
        "not affiliated with DingTalk or Alibaba",
        "close DingTalk",
        "JSON",
        "CSV",
        "TXT",
        "HTML",
    ]
    for phrase in required:
        assert phrase.casefold() in readme.casefold()


def test_required_docs_and_mit_license_exist():
    for path in [
        "docs/compatibility.md",
        "docs/privacy-and-safety.md",
        "docs/troubleshooting.md",
        "LICENSE",
    ]:
        assert Path(path).is_file()
    assert "MIT License" in Path("LICENSE").read_text(encoding="utf-8")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_documentation.py -v
```

Expected: FAIL because public docs do not yet exist.

- [ ] **Step 3: Write `README.md` with this exact section structure**

```markdown
# DingTalk Chat Exporter

DingTalk Chat Exporter is an unofficial Windows-first Python CLI that exports local DingTalk desktop conversations you are already authorized to access.

## Status and tested environment
State that v1 is Windows only and initially validated against DingTalk desktop 7.6.48-style `_v2` storage with 4096-byte AES-128-ECB encrypted SQLite pages.

## Features
List automatic account discovery, V2 key derivation, WAL reconstruction, conversation naming, sender-name resolution, and JSON/CSV/TXT/HTML export.

## Requirements
Document Windows 10/11, Python 3.10+, DingTalk desktop local data, and that DingTalk must be closed before final export.

## Installation
Show `git clone`, `cd`, and `pip install -r requirements.txt`.

## Quick start
Show `python dingtalk_export.py` and explain account/conversation selection.

## Example session
Include an English terminal transcript with `[OK]`-style status lines and a successful `exports/<conversation>/` result.

## Output formats
Explain JSON archival/raw fields, CSV BOM/Excel compatibility, TXT transcript, and self-contained HTML.

## Conversation and participant naming
Document the fallback order and state that CID is used only when no human-readable evidence is available.

## Compatibility
Link to `docs/compatibility.md` and explicitly avoid claiming universal DingTalk version support.

## Troubleshooting
Link to `docs/troubleshooting.md` and include the most common issues: DingTalk still running, no `_v2` account found, unsupported SQLite header, failed quick_check.

## Privacy and legal disclaimer
State that the project is not affiliated with DingTalk or Alibaba, that exports can contain third-party/confidential data, processing stays local, and users are responsible for applicable law, workplace policy, contracts, and DingTalk terms.

## Security notes
State that source files are read-only, derived keys are not logged, decrypted temporary databases are removed after normal completion, HTML is escaped, and exported files should be protected appropriately.

## Development and testing
Show `pip install -r requirements-dev.txt` and `python -m pytest -v`.

## Contributing
Ask contributors not to commit real user databases, exported chats, credentials, or derived keys.

## License
State MIT applies to this project's source code only, not DingTalk software, trademarks, protocols, or user data.
```

- [ ] **Step 4: Write the supporting docs with concrete compatibility and safety content**

`docs/compatibility.md` must include:

```text
Supported baseline: Windows DingTalk local account directories named <numeric-uid>_v2 under %APPDATA%\DingTalk, DBFiles\dingtalk.db, 4096-byte pages, AES-128-ECB, key = first 16 ASCII chars of lowercase MD5(uid), SQLite WAL magic 0x377f0682/0x377f0683. Compatibility is feature-detected; unsupported formats stop safely.
```

`docs/privacy-and-safety.md` must include:

```text
Unofficial community project; no DingTalk/Alibaba affiliation. Only export conversations the local user is already authorized to access. All processing is local. Exported files may contain personal/confidential third-party information. Users must comply with law, workplace policy, contracts, and DingTalk terms. Do not publish real exports when reporting bugs.
```

`docs/troubleshooting.md` must map each message to an action:

```text
DingTalk appears to be running -> exit DingTalk from the desktop/tray and rerun.
No compatible `_v2` account -> verify desktop DingTalk has local history and inspect %APPDATA%\DingTalk.
Invalid SQLite header after decryption -> unsupported database generation/build; do not guess keys.
WAL page size mismatch -> unsupported local format; report sanitized diagnostics only.
PRAGMA quick_check failure -> stop; do not export potentially corrupted reconstructed data.
```

Create the standard MIT License with year `2026` and copyright holder `Meel Regidor` unless the repository owner changes it before publication.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python -m pytest tests/test_documentation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/compatibility.md docs/privacy-and-safety.md docs/troubleshooting.md LICENSE tests/test_documentation.py
git commit -m "docs: document installation compatibility and privacy"
```

---

### Task 12: Final verification against v1 acceptance criteria

**Files:**
- Modify only files required by failing verification; do not add new features.

**Interfaces:**
- Confirms the repository satisfies the approved spec as a whole.

- [ ] **Step 1: Run all automated tests**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS with no unexpected warnings or errors.

- [ ] **Step 2: Verify importability and public command syntax**

Run:

```bash
python -c "import dingtalk_exporter; from dingtalk_exporter.cli import run; print(dingtalk_exporter.__version__)"
python -m py_compile dingtalk_export.py dingtalk_exporter/*.py
```

Expected: prints `0.1.0`; compilation exits 0.

- [ ] **Step 3: Verify no sensitive fixture data or derived-key logging is present**

Run:

```bash
git grep -n -E "1234567890|e807f1fcf82d132f|the tech team|Alice发起了群聊" -- . ':!docs/superpowers/specs/*' ':!docs/superpowers/plans/*' ':!tests/test_crypto.py'
```

Expected: no output. Replace any accidental real-data occurrences before continuing.

- [ ] **Step 4: Verify repository cleanliness rules**

Run:

```bash
git status --short
find . -maxdepth 3 -type f \( -name '*.db' -o -name '*.sqlite' -o -name 'chat.json' -o -name 'chat.html' \) -print
```

Expected: only intended source/doc changes before final commit; no real/decrypted databases or exports are present.

- [ ] **Step 5: Review README steps from a clean-user perspective**

Meally confirm the README contains, in order:

```text
clone -> install Python dependencies -> close DingTalk -> run python dingtalk_export.py -> select account if needed -> select conversation -> locate exports
```

Expected: no undocumented prerequisite is required.

- [ ] **Step 6: Commit final verification-only corrections, if any**

If verification required changes:

```bash
git add -A
git commit -m "chore: finalize v1 exporter verification"
```

If no changes were required, do not create an empty commit.

---

## Self-Review Results

- **Spec coverage:** Every v1 acceptance criterion maps to Tasks 2–12: discovery (2), key validation (3), DB/WAL reconstruction (4), dynamic shards/content (5), sender names (6), conversation inventory/naming (7), four formats (8), one-command interactive flow and cleanup (9), synthetic end-to-end workflow (10), English documentation/privacy/compatibility/license (11), final repository verification (12).
- **Explicit exclusions preserved:** no macOS/Linux/mobile, server/API scraping, authentication bypass, deleted-message recovery, remote attachment download, standalone EXE, PyPI, GUI, or universal-version support.
- **Placeholder scan:** no `TBD`, `TODO`, “implement later”, or undefined hand-waving steps remain.
- **Type/interface consistency:** `AccountCandidate`, `ReconstructedDatabase`, `NormalizedMessage`, `ConversationSummary`, and `ExportPaths` field names are used consistently across tasks; public module function names match their consuming tasks.
- **Security/privacy consistency:** original DingTalk data remains read-only; decrypted DB uses a temporary directory in the CLI; derived key is never printed; HTML output is escaped; real user data is excluded from tests and repository content.
