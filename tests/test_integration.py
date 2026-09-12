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
