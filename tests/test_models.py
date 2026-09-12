from pathlib import Path

from dingtalk_exporter.errors import CompatibilityError, DingTalkExporterError
from dingtalk_exporter.models import AccountCandidate, NormalizedMessage


def test_shared_contracts_are_constructible():
    account = AccountCandidate(
        uid="1234567890",
        account_dir=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2"),
        database_path=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2/DBFiles/dingtalk.db"),
        wal_path=Path("C:/Users/Test/AppData/Roaming/DingTalk/1234567890_v2/DBFiles/dingtalk.db-wal"),
    )
    message = NormalizedMessage(
        conversation_id="cid-1",
        message_id=123,
        local_id="local-1",
        sender_id=456,
        sender_name="Alice",
        timestamp=1755176432118,
        datetime="2025-08-14 15:00:32",
        message_type=1,
        content_type=1,
        text="Hello",
        recalled=False,
        attachments=[],
        source_table="tbmsg_004",
        raw_content='{"text":"Hello"}',
        raw_extension="",
        raw_attachments="",
    )

    assert account.uid == "1234567890"
    assert message.sender_name == "Alice"
    assert issubclass(CompatibilityError, DingTalkExporterError)
