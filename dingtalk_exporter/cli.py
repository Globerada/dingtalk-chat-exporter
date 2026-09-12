from __future__ import annotations

import os
import sqlite3
import sys
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


def configure_console_encoding(streams=None) -> None:
    targets = (sys.stdout, sys.stderr) if streams is None else streams
    for stream in targets:
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


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
    if output_fn is print:
        configure_console_encoding()

    output_fn("DingTalk Chat Exporter")
    output_fn("")
    try:
        if os.name != "nt" and appdata_root is None:
            raise DingTalkExporterError("This version of DingTalk Chat Exporter supports Windows only.")
        if is_dingtalk_running():
            raise DingTalkExporterError(
                "DingTalk appears to be running. Close it completely before exporting so the latest WAL state can be read consistently."
            )

        accounts = discover_accounts(appdata_root)
        if not accounts:
            raise DingTalkExporterError(
                "No compatible `_v2` DingTalk account databases were found under %APPDATA%\\DingTalk."
            )
        output_fn(f"[OK] Compatible DingTalk account database{'s' if len(accounts) != 1 else ''} found")

        account = accounts[0]
        if len(accounts) > 1:
            output_fn("Accounts found:")
            for index, item in enumerate(accounts, 1):
                output_fn(f"  {index}. {item.uid}")
            account = accounts[choose_index("Select account", len(accounts), input_fn, output_fn)]

        with tempfile.TemporaryDirectory(prefix="dingtalk-export-") as temp_dir:
            reconstructed = reconstruct_database(account, Path(temp_dir) / "dingtalk.reconstructed.db")
            output_fn(f"[OK] Database reconstructed ({reconstructed.wal_frames_applied} committed WAL frames applied)")
            con = sqlite3.connect(f"file:{reconstructed.path.as_posix()}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            try:
                tables = discover_message_tables(con)
                names = resolve_profile_names(con, int(account.uid), tables)
                conversations = discover_conversations(con, int(account.uid), names)
                if not conversations:
                    raise DingTalkExporterError("No conversations were found in the reconstructed database.")

                output_fn(f"Conversations found: {len(conversations)}")
                for index, conversation in enumerate(conversations, 1):
                    output_fn(f"  {index:>3}. {conversation.display_name} - {conversation.message_count:,} messages")
                selected = conversations[choose_index("Select conversation", len(conversations), input_fn, output_fn)]
                messages = load_messages(con, selected.cid, names)
            finally:
                con.close()

            paths = export_conversation(selected, messages, output_root, int(account.uid))

        output_fn("")
        output_fn("Export complete:")
        output_fn(str(paths.directory))
        return 0
    except DingTalkExporterError as exc:
        output_fn(f"Error: {exc}")
        return 1
