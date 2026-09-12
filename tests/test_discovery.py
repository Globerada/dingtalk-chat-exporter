from pathlib import Path

from dingtalk_exporter.discovery import discover_accounts, is_dingtalk_running


def test_discover_accounts_returns_only_numeric_v2_databases(tmp_path: Path):
    root = tmp_path / "DingTalk"
    good = root / "1234567890_v2" / "DBFiles"
    good.mkdir(parents=True)
    (good / "dingtalk.db").write_bytes(b"encrypted")
    (good / "dingtalk.db-wal").write_bytes(b"wal")
    bad_missing_db = root / "123_v2" / "DBFiles"
    bad_missing_db.mkdir(parents=True)
    bad_non_numeric = root / "abc_v2" / "DBFiles"
    bad_non_numeric.mkdir(parents=True)
    (bad_non_numeric / "dingtalk.db").write_bytes(b"encrypted")
    accounts = discover_accounts(root)
    assert [a.uid for a in accounts] == ["1234567890"]
    assert accounts[0].wal_path == good / "dingtalk.db-wal"


def test_running_state_parses_tasklist_csv_text():
    running = '"DingTalk.exe","24824","Console","1","100,000 K"\n'
    stopped = '"python.exe","100","Console","1","20,000 K"\n'
    assert is_dingtalk_running(running) is True
    assert is_dingtalk_running(stopped) is False
