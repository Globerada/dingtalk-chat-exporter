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
    base_name = sanitize_filename(conversation.display_name)
    base = output_root / base_name
    if not base.exists():
        return base
    suffix = sanitize_filename(conversation.cid)[-12:]
    candidate = output_root / f"{base_name}_{suffix}"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = output_root / f"{base_name}_{suffix}_{index}"
        if not numbered.exists():
            return numbered
        index += 1


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

        csv_fields = [
            "datetime",
            "sender_name",
            "sender_id",
            "message_id",
            "message_type",
            "content_type",
            "text",
            "recalled",
        ]
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
