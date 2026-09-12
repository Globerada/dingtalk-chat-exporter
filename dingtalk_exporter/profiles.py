from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from typing import Any


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
    wanted = (
        "alias",
        "displayname",
        "display_name",
        "nick",
        "nickname",
        "realname",
        "real_name",
        "name",
        "username",
    )
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
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    column_names = [description[0] for description in cursor.description]
    for raw_row in cursor:
        mapping = dict(zip(column_names, raw_row))
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


def _safe_json(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _iter_forwarded_names(raw_attachments: str | None):
    parsed = _safe_json(raw_attachments)
    if not isinstance(parsed, list):
        return
    for item in parsed:
        if isinstance(item, str):
            item = _safe_json(item)
        if not isinstance(item, dict):
            continue
        extension = item.get("extension")
        if isinstance(extension, str):
            extension = _safe_json(extension)
        if not isinstance(extension, dict):
            continue
        raw_uid = extension.get("senderId") or extension.get("sender_id") or extension.get("uid")
        raw_name = extension.get("senderName") or extension.get("sender_name")
        try:
            uid = int(raw_uid)
        except (TypeError, ValueError):
            continue
        if isinstance(raw_name, str) and raw_name.strip():
            yield uid, raw_name.strip()


def resolve_profile_names(
    connection: sqlite3.Connection,
    current_uid: int,
    message_tables: list[str],
) -> dict[int, str]:
    # Apply lower-priority structured sources first so later sources can overwrite them.
    names: dict[int, str] = {current_uid: "Me"}
    for table in ("tbuser_group_nick", "tbuser_profile_v2", "tbuser_alias_name"):
        names.update(_collect_from_table(connection, table))

    mention_evidence: dict[int, list[str]] = defaultdict(list)
    forwarded_evidence: dict[int, list[str]] = defaultdict(list)

    for table in message_tables:
        columns = set(_columns(connection, table))
        selected = []
        if "atIds" in columns:
            selected.append("atIds")
        if "attachments" in columns:
            selected.append("attachments")
        if not selected:
            continue
        cursor = connection.execute(f'SELECT {", ".join(selected)} FROM "{table}"')
        for row in cursor:
            values = dict(zip(selected, row))
            raw_at_ids = values.get("atIds")
            data = _safe_json(raw_at_ids)
            if isinstance(data, dict):
                for raw_uid, raw_name in data.items():
                    try:
                        uid = int(raw_uid)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(raw_name, str) and raw_name.strip():
                        mention_evidence[uid].append(raw_name.strip())
            for uid, name in _iter_forwarded_names(values.get("attachments")) or ():
                forwarded_evidence[uid].append(name)

    # Forwarded metadata is lower confidence than mention evidence.
    for evidence in (forwarded_evidence, mention_evidence):
        for uid, candidates in evidence.items():
            if uid not in names and candidates:
                counts = Counter(candidates)
                names[uid] = sorted(counts, key=lambda value: (-counts[value], value.casefold()))[0]

    # Never overwrite the local user's friendly fallback with an empty value.
    names[current_uid] = names.get(current_uid) or "Me"
    return names
