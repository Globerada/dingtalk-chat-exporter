# DingTalk Chat Exporter

DingTalk Chat Exporter is an unofficial Windows-first Python CLI for exporting local DingTalk desktop conversations that you are already authorized to access.

> **Important:** v1 is **Windows only**. The project is not affiliated with DingTalk or Alibaba.

## Status and tested environment

Version 0.1.0 is designed around the DingTalk desktop `_v2` local storage format validated during development. The tested baseline used DingTalk desktop 7.6.48-style storage, 4096-byte encrypted SQLite pages, AES-128-ECB, and standard SQLite WAL files.

Compatibility is feature-detected. The tool will stop instead of guessing when the local database layout, encryption format, WAL page size, decrypted SQLite header, or schema does not match what v1 understands.

## Features

- Finds numeric `<uid>_v2` DingTalk account folders under `%APPDATA%\DingTalk`.
- Derives and validates the tested V2 local database key automatically.
- Decrypts the main local database without modifying the original files.
- Applies only committed SQLite WAL frames and ignores trailing uncommitted frames.
- Validates the reconstructed SQLite database with `PRAGMA quick_check`.
- Discovers `tbmsg_*` message shards dynamically rather than assuming a fixed shard count.
- Resolves participant names from aliases, user profiles, group nicknames, mentions, and available forwarded-message metadata.
- Attempts to resolve readable conversation names before falling back to the raw conversation ID.
- Exports every selected conversation to **JSON**, **CSV**, **TXT**, and self-contained **HTML**.
- Preserves Unicode content, including Chinese and multilingual chats.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- DingTalk desktop with local `_v2` chat data present under `%APPDATA%\DingTalk`.
- Permission to read your own local DingTalk data.
- You must **close DingTalk completely** before exporting, including the tray icon, so the database and WAL files are read in a stable state.

## Installation

Open PowerShell and run:

```powershell
git clone https://github.com/YOUR-USERNAME/dingtalk-chat-exporter.git
cd dingtalk-chat-exporter
python -m pip install -r requirements.txt
```

If `python` is not available, install Python 3.10+ from Python.org, reopen PowerShell, and repeat the command.

## Quick start

1. Close DingTalk completely. Use the DingTalk tray icon and choose Exit/Quit if necessary.
2. Open PowerShell in the repository folder.
3. Run:

```powershell
python dingtalk_export.py
```

4. If several compatible local accounts are found, select the account number.
5. Select the conversation you want to export.
6. The exporter writes a new folder under `exports/` containing all four output formats.

## Example session

```text
DingTalk Chat Exporter

[OK] Compatible DingTalk account database found
[OK] Database reconstructed (42 committed WAL frames applied)
Conversations found: 3
    1. Project Team — 1,247 messages
    2. Alice — 582 messages
    3. Bob — 391 messages
Select conversation: 1

Export complete:
exports\Project Team
```

The resulting folder contains:

```text
exports\Project Team\
├── chat.json
├── chat.csv
├── chat.txt
└── chat.html
```

## Output formats

### JSON

`chat.json` is the best archival and analysis format. It contains normalized fields such as timestamp, sender name, sender ID, message ID, message type, content type, readable text, recalled state, parsed attachments, source shard, and selected raw DingTalk fields.

### CSV

`chat.csv` contains the main normalized columns and is written as UTF-8 with BOM for good compatibility with Excel on Windows.

### TXT

`chat.txt` is a simple chronological transcript:

```text
[2026-09-12 10:15:22] Alice:
Hello there
```

### HTML

`chat.html` is a self-contained human-readable conversation view. Message text, sender names, timestamps, titles, and conversation identifiers are HTML-escaped before rendering.

## Conversation and participant naming

The exporter tries to produce human-readable names instead of raw IDs. In general it uses the best evidence available from:

1. explicit conversation title metadata,
2. direct-chat participant IDs encoded in the conversation ID,
3. participant/profile tables,
4. aliases and nicknames,
5. mention metadata such as `atIds`,
6. available forwarded-message sender metadata,
7. participant-name combinations for group chats,
8. the raw CID only when no reliable readable name can be resolved.

Name availability depends on what your local DingTalk database contains. A numeric ID may still appear when no trustworthy name is available.

## Compatibility

See [docs/compatibility.md](docs/compatibility.md).

Do not assume the tool supports every DingTalk release. The current version supports only the validated Windows `_v2` local database family and deliberately stops on unknown encryption/database formats.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md).

Common issues include:

- DingTalk is still running.
- No compatible `_v2` account directory is present.
- The decrypted first page does not contain a valid SQLite header.
- The WAL page size does not match the validated 4096-byte format.
- `PRAGMA quick_check` reports an integrity problem.

## Privacy and legal disclaimer

This is an unofficial community project and is **not affiliated with DingTalk or Alibaba**.

Use it only to export conversations that the local user is already authorized to access. Chat exports may contain personal data, confidential business information, trade secrets, credentials accidentally shared in messages, or other third-party information.

All database processing performed by this program is local. The tool does not upload chat history to a server. You are responsible for complying with applicable law, workplace policies, contractual confidentiality obligations, data-protection requirements, and DingTalk terms that apply to you.

Do not publish real chat exports, local databases, account identifiers, derived keys, or confidential message content when reporting bugs.

See [docs/privacy-and-safety.md](docs/privacy-and-safety.md) for more detail.

## Security notes

- Original DingTalk source files are treated as read-only inputs.
- The tool does not checkpoint, update, rename, or delete DingTalk databases.
- Derived decryption keys are not printed or written to the export.
- The reconstructed decrypted SQLite database is placed in a temporary directory and removed after normal CLI completion.
- HTML output escapes untrusted text before rendering.
- Exported JSON/CSV/TXT/HTML files contain readable conversation data; protect them like any other sensitive business or personal data.

## Development and testing

Install development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the test suite:

```powershell
python -m pytest -v
```

The repository tests use synthetic DingTalk-shaped SQLite fixtures only. Do not add real user databases or real exported chats to tests.

## Contributing

Issues and pull requests are welcome, especially for carefully documented compatibility findings from other DingTalk Windows versions.

Please do not commit or attach:

- real `dingtalk.db` files,
- WAL/SHM files from real accounts,
- exported chats,
- credentials or tokens,
- real UIDs,
- derived database keys,
- confidential message content.

When reporting a compatibility problem, provide only sanitized diagnostics such as DingTalk version, directory layout, page size, WAL magic, table names, and exact error messages where those details do not expose private data.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

The MIT License applies only to this project's source code. It does not grant rights to DingTalk software, Alibaba software, trademarks, protocols, or user data.
