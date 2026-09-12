from pathlib import Path


def test_readme_documents_required_public_workflow_and_disclaimer():
    readme = Path("README.md").read_text(encoding="utf-8")
    required = [
        "Windows only",
        "python dingtalk_export.py",
        "pip install -r requirements.txt",
        "not affiliated with DingTalk or Alibaba",
        "close DingTalk",
        "JSON",
        "CSV",
        "TXT",
        "HTML",
    ]
    for phrase in required:
        assert phrase.casefold() in readme.casefold()


def test_required_docs_and_mit_license_exist():
    for path in [
        "docs/compatibility.md",
        "docs/privacy-and-safety.md",
        "docs/troubleshooting.md",
        "LICENSE",
    ]:
        assert Path(path).is_file()
    assert "MIT License" in Path("LICENSE").read_text(encoding="utf-8")
