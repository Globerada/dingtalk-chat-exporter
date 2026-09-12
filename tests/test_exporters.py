import json
from pathlib import Path

from dingtalk_exporter.exporters import export_conversation, sanitize_filename
from dingtalk_exporter.models import ConversationSummary, NormalizedMessage


def message(text: str) -> NormalizedMessage:
    return NormalizedMessage(
        conversation_id="cid/unsafe",
        message_id=1,
        local_id="a",
        sender_id=1,
        sender_name="Me & <Admin>",
        timestamp=1,
        datetime="1970-01-01 00:00:00",
        message_type=1,
        content_type=1,
        text=text,
        recalled=False,
        attachments=[],
        source_table="tbmsg_000",
        raw_content='{"text":"x"}',
        raw_extension="",
        raw_attachments="",
    )


def test_sanitize_filename_removes_windows_path_characters():
    assert sanitize_filename('AliExpress: UK/DE * Team?') == "AliExpress_ UK_DE _ Team_"


def test_exporters_preserve_unicode_and_escape_html(tmp_path: Path):
    conversation = ConversationSummary(cid="cid/unsafe", display_name="AliExpress: Team", message_count=1)
    paths = export_conversation(conversation, [message("你好 <script>alert(1)</script>")], tmp_path, current_uid=1)
    data = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert data[0]["text"].startswith("你好")
    assert paths.csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    html_text = paths.html_path.read_text(encoding="utf-8")
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text
