# Troubleshooting

## `DingTalk appears to be running`

Exit DingTalk completely from the desktop and the Windows tray, then run the exporter again. The tool intentionally does not terminate DingTalk for you because the source database and WAL should be read only after the application has finished writing them.

## `No compatible _v2 DingTalk account databases were found`

Check `%APPDATA%\DingTalk` in File Explorer. A supported account should look similar to:

```text
%APPDATA%\DingTalk\<numeric-uid>_v2\DBFiles\dingtalk.db
```

If your installation uses another layout, v1 may not support it. Do not rename folders to make them look compatible.

## `Unsupported DingTalk database format` / invalid SQLite header after decryption

The tested V2 key derivation or AES format did not produce a valid SQLite header. This usually means the local DingTalk build uses a different database generation or encryption scheme.

Do not guess keys and do not modify the database. Report sanitized compatibility diagnostics instead.

## `Unsupported SQLite WAL magic`

The WAL does not match the supported SQLite WAL format. Make sure DingTalk is fully closed and that the WAL belongs to the same `dingtalk.db`. If the error persists, the local format may be unsupported.

## `Unsupported SQLite WAL page size`

The validated format uses 4096-byte pages. A mismatch indicates an unsupported local format. Report only sanitized diagnostics.

## `SQLite integrity check failed`

The reconstructed database failed `PRAGMA quick_check`. The exporter stops rather than generating potentially incomplete or corrupted chat output.

Close DingTalk cleanly and retry. If the problem remains, keep the original files untouched and report sanitized diagnostics.

## Conversation names are numeric IDs

Name resolution is best-effort. The local database may not contain an alias/profile/nickname for every participant. The exporter uses raw IDs only when a reliable readable name is unavailable.

## Some complex messages look like Markdown or metadata

DingTalk uses multiple content types. v1 normalizes ordinary text and common Markdown/attachment representations while preserving unknown raw content instead of silently discarding it. JSON is the best format for investigating an unusual message type.

## PowerShell cannot find `python`

Install Python 3.10+ and select the installer option that adds Python to PATH, then reopen PowerShell. You can also try the Windows Python launcher:

```powershell
py dingtalk_export.py
```
