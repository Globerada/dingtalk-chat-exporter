# Compatibility

## Supported baseline

DingTalk Chat Exporter v0.1.0 supports the Windows local storage format that has been validated with these characteristics:

- Windows DingTalk desktop.
- Account directory named `<numeric-uid>_v2` under `%APPDATA%\DingTalk`.
- Main chat database at `DBFiles\dingtalk.db`.
- Optional WAL at `DBFiles\dingtalk.db-wal`.
- Database page size: 4096 bytes.
- Page cipher: AES-128-ECB.
- Key derivation: lowercase `MD5(uid)`, take the first 16 hexadecimal characters, encode those characters as ASCII.
- Decrypted first page begins with `SQLite format 3\x00`.
- SQLite WAL magic accepted: `0x377f0682` or `0x377f0683`.
- Message tables are discovered by compatible `tbmsg_*` schemas rather than by a fixed count.

The validated development environment used a DingTalk desktop 7.6.48-style `_v2` account layout. That does **not** mean every 7.6.48 installation or later release is guaranteed to use the same format.

## Feature detection

The application does not treat the `_v2` suffix as proof of compatibility. It validates the format before export:

1. the account directory has a numeric UID candidate,
2. `DBFiles\dingtalk.db` exists,
3. the file is aligned to 4096-byte pages,
4. V2 key derivation decrypts the first page to a valid SQLite header,
5. any WAL has a supported SQLite WAL header/page size,
6. committed WAL frames can be reconstructed,
7. `PRAGMA quick_check` returns `ok`,
8. at least one compatible `tbmsg_*` message table exists.

If a validation step fails, the tool stops instead of trying alternate keys or modifying the source files.

## Not supported in v1

- macOS.
- Linux DingTalk clients.
- Android or iOS databases.
- DingTalk cloud/server API export.
- `_v3` or other unvalidated account formats.
- Unknown encryption schemes or page sizes.
- Deleted-message recovery.
- Downloading remote attachments that are not represented in the local database.

If you investigate a new format, use a copy of your own authorized local data and never submit the database or decrypted chat content to the repository.
