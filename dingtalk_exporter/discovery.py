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
        accounts.append(AccountCandidate(uid, account_dir, database_path, wal_candidate if wal_candidate.is_file() else None))
    return accounts


def is_dingtalk_running(process_listing: str | None = None) -> bool:
    if process_listing is None:
        try:
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise DiscoveryError(f"Could not query Windows process state: {exc}") from exc
        process_listing = completed.stdout
    for row in csv.reader(io.StringIO(process_listing)):
        if row and row[0].casefold() == "dingtalk.exe":
            return True
    return False
