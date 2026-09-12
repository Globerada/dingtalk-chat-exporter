import json
import sqlite3

from dingtalk_exporter.messages import discover_message_tables, extract_readable_text, load_messages


def make_connection() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("""
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
    """)
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


def test_embedded_forwarded_attachment_summary_is_readable():
    content = json.dumps({
        "contentType": 1500,
        "attachments": [
            {
                "type": 101,
                "extension": json.dumps({
                    "summary": "Alice: First forwarded message\nMe: Reply",
                    "title": "Alice and Me chat history",
                }),
            }
        ],
    })
    text, attachments = extract_readable_text(content, "", 1500)
    assert text == "Alice: First forwarded message\nMe: Reply"
    assert attachments
