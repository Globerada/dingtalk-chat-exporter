import sqlite3

from dingtalk_exporter.conversations import discover_conversations, resolve_conversation_name


def test_one_to_one_name_prefers_other_participant():
    assert resolve_conversation_name(
        cid="2222222222:1234567890",
        explicit_title=None,
        participant_ids=[2222222222, 1234567890],
        current_uid=1234567890,
        names={2222222222: "Alice", 1234567890: "Me"},
    ) == "Alice"


def test_explicit_group_title_wins():
    assert resolve_conversation_name(
        cid="69169246850",
        explicit_title="Project Team",
        participant_ids=[1, 2, 3],
        current_uid=1,
        names={1: "Me", 2: "Alice", 3: "Bob"},
    ) == "Project Team"


def test_discovery_counts_messages_and_last_timestamp():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE tbmsg_000(cid TEXT, mid INTEGER, senderId INTEGER, createdAt INTEGER, content TEXT)")
    con.executemany(
        "INSERT INTO tbmsg_000 VALUES (?,?,?,?,?)",
        [("c1", 1, 1, 100, '{}'), ("c1", 2, 2, 200, '{}')],
    )
    conversations = discover_conversations(con, current_uid=1, names={1: "Me", 2: "Alice"})
    assert conversations[0].message_count == 2
    assert conversations[0].last_message_timestamp == 200
    assert conversations[0].display_name == "Alice"
