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
