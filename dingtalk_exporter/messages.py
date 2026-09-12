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


def _extract_from_attachment_objects(items: list[Any]) -> str | None:
    for item in items:
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
                return value
    return None


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

    attachment_text = _extract_from_attachment_objects(attachment_objects)
    if attachment_text:
        return attachment_text, attachment_objects

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
    previous_factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    messages: list[NormalizedMessage] = []
    try:
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
                text, parsed_attachments = extract_readable_text(
                    row["content"], row["attachments"], row["contentType"]
                )
                sender_id = row["senderId"]
                messages.append(
                    NormalizedMessage(
                        conversation_id=cid,
                        message_id=row["mid"],
                        local_id=row["localId"],
                        sender_id=sender_id,
                        sender_name=sender_names.get(
                            sender_id,
                            str(sender_id) if sender_id is not None else "Unknown",
                        ),
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
    finally:
        connection.row_factory = previous_factory
    messages.sort(key=lambda item: (item.timestamp or 0, item.message_id or 0))
    return messages
