from __future__ import annotations

import sqlite3
from collections import defaultdict

from .messages import discover_message_tables
from .models import ConversationSummary


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _explicit_titles(connection: sqlite3.Connection) -> dict[str, str]:
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tbconversation'"
    ).fetchone() is None:
        return {}
    columns = _table_columns(connection, "tbconversation")
    cid_column = next((name for name in columns if name.casefold() == "cid"), None)
    title_column = next(
        (
            name
            for name in columns
            if name.casefold() in {"title", "name", "conversationname", "conversation_name", "nick"}
        ),
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
    if ":" in cid:
        encoded: list[int] = []
        for part in cid.split(":"):
            try:
                encoded.append(int(part))
            except ValueError:
                encoded = []
                break
        if encoded:
            participant_ids = sorted(set(participant_ids) | set(encoded))

    others = [uid for uid in participant_ids if uid != current_uid]

    if explicit_title and explicit_title.strip():
        title = explicit_title.strip()
        is_numeric_one_to_one_placeholder = len(others) == 1 and title == str(others[0])
        if not is_numeric_one_to_one_placeholder:
            return title

    resolved_others = [names[uid] for uid in others if uid in names and names[uid]]
    if len(others) == 1 and resolved_others:
        return resolved_others[0]

    participant_names = [names[uid] for uid in participant_ids if uid in names and names[uid]]
    participant_names = list(dict.fromkeys(participant_names))
    if participant_names:
        visible = participant_names[:4]
        suffix = " + others" if len(participant_names) > 4 else ""
        return ", ".join(visible) + suffix
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
        for cid, count, max_created in connection.execute(
            f'SELECT cid, COUNT(*) AS n, MAX(createdAt) AS latest FROM "{table}" GROUP BY cid'
        ):
            if cid is None:
                continue
            cid_text = str(cid)
            counts[cid_text] += int(count)
            if max_created is not None:
                latest[cid_text] = max(latest.get(cid_text, int(max_created)), int(max_created))
        columns = _table_columns(connection, table)
        if "senderId" in columns:
            for cid, sender_id in connection.execute(
                f'SELECT DISTINCT cid, senderId FROM "{table}" WHERE senderId IS NOT NULL'
            ):
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
