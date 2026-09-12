from dingtalk_exporter.cli import choose_index


def test_choose_index_reprompts_until_valid():
    answers = iter(["x", "0", "2"])
    output: list[str] = []
    selected = choose_index(
        label="Select conversation",
        count=3,
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )
    assert selected == 1
    assert len(output) == 2


def test_run_exports_selected_synthetic_conversation(tmp_path, monkeypatch):
    from dingtalk_exporter.cli import run
    from dingtalk_exporter.crypto import derive_v2_key
    from conftest import encrypt_pages, make_dingtalk_like_plain_db

    root = tmp_path / "DingTalk"
    db_dir = root / "1_v2" / "DBFiles"
    db_dir.mkdir(parents=True)
    plain = make_dingtalk_like_plain_db(tmp_path / "plain-cli.db")
    (db_dir / "dingtalk.db").write_bytes(encrypt_pages(plain, derive_v2_key("1")))

    monkeypatch.setattr("dingtalk_exporter.cli.is_dingtalk_running", lambda: False)
    output = []
    result = run(
        input_fn=lambda _: "1",
        output_fn=output.append,
        appdata_root=root,
        output_root=tmp_path / "exports",
    )

    assert result == 0
    assert any("Export complete" in line for line in output)
    assert list((tmp_path / "exports").glob("*/chat.json"))


def test_configure_console_encoding_requests_utf8_with_replacement():
    from dingtalk_exporter.cli import configure_console_encoding

    class FakeStream:
        def __init__(self):
            self.calls = []

        def reconfigure(self, **kwargs):
            self.calls.append(kwargs)

    stdout = FakeStream()
    stderr = FakeStream()

    configure_console_encoding((stdout, stderr))

    assert stdout.calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_conversation_listing_uses_ascii_separator(tmp_path, monkeypatch):
    from dingtalk_exporter.cli import run
    from dingtalk_exporter.crypto import derive_v2_key
    from conftest import encrypt_pages, make_dingtalk_like_plain_db

    root = tmp_path / "DingTalk"
    db_dir = root / "1_v2" / "DBFiles"
    db_dir.mkdir(parents=True)
    plain = make_dingtalk_like_plain_db(tmp_path / "plain-cli-ascii.db")
    (db_dir / "dingtalk.db").write_bytes(encrypt_pages(plain, derive_v2_key("1")))

    monkeypatch.setattr("dingtalk_exporter.cli.is_dingtalk_running", lambda: False)
    output = []
    result = run(
        input_fn=lambda _: "1",
        output_fn=output.append,
        appdata_root=root,
        output_root=tmp_path / "exports",
    )

    assert result == 0
    conversation_lines = [line for line in output if "messages" in line]
    assert conversation_lines
    assert all(" — " not in line for line in conversation_lines)
    assert all(" - " in line for line in conversation_lines)


def test_configure_console_encoding_ignores_unsupported_streams():
    from dingtalk_exporter.cli import configure_console_encoding

    class RaisingStream:
        def reconfigure(self, **kwargs):
            raise OSError("not supported")

    configure_console_encoding((object(), RaisingStream()))
