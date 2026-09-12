import json
import sqlite3

from dingtalk_exporter.profiles import resolve_profile_names


def test_alias_beats_profile_and_mentions_fill_missing_names():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tbuser_profile_v2(uid INTEGER, nick TEXT)")
    con.execute("CREATE TABLE tbuser_alias_name(uid INTEGER, alias TEXT)")
    con.execute("CREATE TABLE tbmsg_000(cid TEXT, mid INTEGER, senderId INTEGER, createdAt INTEGER, content TEXT, atIds TEXT, attachments TEXT)")
    con.execute("INSERT INTO tbuser_profile_v2 VALUES (2, 'Profile Alice')")
    con.execute("INSERT INTO tbuser_alias_name VALUES (2, 'Alice')")
    con.execute("INSERT INTO tbmsg_000 VALUES ('c1', 1, 2, 1, '{}', '{\"3\":\"Bob\"}', '')")
    names = resolve_profile_names(con, current_uid=1, message_tables=["tbmsg_000"])
    assert names[1] == "Me"
    assert names[2] == "Alice"
    assert names[3] == "Bob"


def test_forwarded_sender_metadata_fills_missing_name():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tbmsg_000(cid TEXT, mid INTEGER, senderId INTEGER, createdAt INTEGER, content TEXT, atIds TEXT, attachments TEXT)")
    forwarded = [json.dumps({"type": 1, "extension": {"senderId": "4", "senderName": "Carol"}})]
    con.execute("INSERT INTO tbmsg_000 VALUES ('c1', 1, 2, 1, '{}', '', ?)", (json.dumps(forwarded),))
    names = resolve_profile_names(con, current_uid=1, message_tables=["tbmsg_000"])
    assert names[4] == "Carol"
