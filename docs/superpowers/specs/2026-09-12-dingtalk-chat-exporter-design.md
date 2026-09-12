# DingTalk Chat Exporter — Design Specification

Date: 2026-09-12
Status: Approved architecture, pending implementation plan
Language: English for all public-facing materials

## 1. Purpose

DingTalk Chat Exporter is a Windows-first, open-source Python CLI tool that exports DingTalk desktop chat history that the current user can already access locally.

The tool is intended to turn the manual reverse-engineering workflow validated during development into a reproducible, user-friendly process that can be run from a fresh Windows environment with one main command.

Primary user goal:

```powershell
python dingtalk_export.py
```

The application should automatically discover compatible DingTalk data, derive the local database key, reconstruct a current SQLite database including committed WAL frames, resolve conversations and participant names, let the user choose a conversation, and export it to human- and machine-readable formats.

## 2. Scope

### In scope for v1

- Windows only.
- DingTalk desktop installations using the tested `_v2` local account layout.
- Automatic discovery of local DingTalk account directories.
- Automatic derivation of the tested V2 database key scheme.
- Read-only handling of DingTalk source files.
- Decryption of the main local chat database.
- Application of committed SQLite WAL frames.
- Dynamic discovery of message shard tables (`tbmsg_*`).
- Automatic conversation discovery and naming.
- Automatic participant name resolution where possible.
- Interactive CLI conversation selection.
- Export to JSON, CSV, TXT, and HTML.
- UTF-8 output with support for multilingual chat content.
- Useful compatibility diagnostics when a local installation differs from the tested format.
- Automated tests for cryptography, WAL reconstruction, message parsing, naming, and exporters.

### Explicitly out of scope for v1

- macOS, Linux, Android, or iOS support.
- Cloud/API-based export from DingTalk servers.
- Bypassing DingTalk authentication.
- Exporting conversations the current local user cannot access.
- Writing to or modifying DingTalk databases.
- Restoring deleted messages.
- Downloading remote attachments that are not already represented in local data.
- Standalone `.exe` distribution.
- PyPI publication.
- Support claims for every DingTalk version or every database format.

## 3. Compatibility baseline

The implementation is based on a validated Windows DingTalk installation with these observed characteristics:

- DingTalk desktop 7.6.48 branch.
- Account storage directory matching `<uid>_v2` under `%APPDATA%\\DingTalk`.
- Main database under `DBFiles\\dingtalk.db`.
- Associated SQLite WAL and SHM files.
- Database page size: 4096 bytes.
- SQLite WAL magic observed as `0x377f0682`.
- Main database encrypted page-by-page with AES-128-ECB in the validated build.
- Key derivation in the validated build:
  1. Extract numeric UID from the account directory name.
  2. Compute lowercase MD5 hex digest of the UID string.
  3. Use the first 16 ASCII characters of that digest as the AES key.
- A successful decryption is feature-detected by checking for the SQLite header `SQLite format 3\x00` and validating the reconstructed database with SQLite.

The implementation must not silently assume compatibility merely because a directory ends with `_v2`. It must validate the observed format before proceeding.

## 4. Design principles

### 4.1 One-command user experience

The public interface is a single entry point:

```powershell
python dingtalk_export.py
```

Internal functionality is modular but users should not need to run internal scripts individually.

### 4.2 Never modify source data

The application must treat DingTalk files as read-only input.

It must never:

- write to the original database,
- rename DingTalk files,
- delete source files,
- modify the WAL or SHM,
- issue SQL writes to the original files.

Reconstructed or decrypted databases must be written to a temporary or application-owned working directory.

### 4.3 Detect rather than assume

Compatibility checks should include:

- expected account directory pattern,
- database existence,
- WAL header validation when present,
- successful key derivation test,
- decrypted SQLite header validation,
- SQLite `PRAGMA quick_check`,
- required table/column capability detection.

The tool should fail with an actionable explanation when these checks do not pass.

### 4.4 Preserve raw data while producing clean exports

Machine-readable JSON should preserve selected original fields alongside normalized fields.

Normalized fields should include at minimum:

- datetime,
- timestamp,
- sender ID,
- sender name,
- message ID,
- message type,
- content type,
- clean message text,
- recalled state.

Raw fields should include, where present:

- raw content,
- raw extension,
- raw attachments,
- source shard table.

## 5. Repository structure

```text
dingtalk-chat-exporter/
│
├── dingtalk_export.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── dingtalk_exporter/
│   ├── __init__.py
│   ├── discovery.py
│   ├── crypto.py
│   ├── database.py
│   ├── conversations.py
│   ├── messages.py
│   ├── profiles.py
│   ├── exporters.py
│   ├── models.py
│   └── errors.py
│
├── tests/
│   ├── fixtures/
│   ├── test_discovery.py
│   ├── test_crypto.py
│   ├── test_wal.py
│   ├── test_conversations.py
│   ├── test_messages.py
│   └── test_exporters.py
│
└── docs/
    ├── compatibility.md
    ├── privacy-and-safety.md
    └── troubleshooting.md
```

## 6. CLI flow

The expected interactive flow is:

```text
DingTalk Chat Exporter

[OK] DingTalk data directory found
[OK] Compatible account found: 1234567890
[OK] Database format recognized
[OK] Encryption key validated
[OK] Main database decrypted
[OK] Committed WAL frames applied
[OK] SQLite integrity check passed

Conversations found: 27

  1. Project Team          1,247 messages
  2. Alice                       582 messages
  3. Bob                     391 messages
  ...

Select conversation: 1

Export formats:
  [x] JSON
  [x] CSV
  [x] TXT
  [x] HTML

Export complete:
exports/AliExpress_CSS_Team/
```

### Multiple accounts

If more than one compatible account is detected, the CLI should present an account selection step before database processing.

### Non-interactive mode

Not required for the initial UI, but internal APIs should not prevent adding future flags such as:

```text
--account
--cid
--format
--output
--yes
```

No need to implement these in v1 unless doing so is low-cost after the interactive flow is complete.

## 7. Account discovery

`discovery.py` is responsible for locating candidate account directories.

Primary search root:

```text
%APPDATA%\\DingTalk
```

Candidate pattern:

```text
*_v2
```

A candidate account must contain the expected database path:

```text
DBFiles\\dingtalk.db
```

The numeric portion before `_v2` is treated as the UID candidate only after validation succeeds.

The discovery layer should return structured account objects rather than raw paths.

## 8. Cryptography

`crypto.py` owns key derivation and page decryption.

### Key derivation for the validated V2 format

```text
uid = numeric account directory prefix
md5_hex = md5(uid.encode("utf-8")).hexdigest()
key = md5_hex[:16].encode("ascii")
```

### Page cipher

Validated configuration:

```text
AES-128-ECB
page size = 4096 bytes
```

### Validation

The first decrypted page must begin with:

```text
SQLite format 3\x00
```

If it does not, the account is reported as unsupported rather than continuing with corrupted output.

Cryptographic code must be isolated behind a clear interface so future DingTalk formats can introduce a different decryptor without changing the rest of the application.

## 9. Database and WAL reconstruction

`database.py` is responsible for producing a temporary current SQLite database.

### Main database

- Read encrypted source bytes.
- Validate page alignment.
- Decrypt each 4096-byte page independently.
- Keep decrypted bytes in application-owned output only.

### WAL

If `dingtalk.db-wal` exists:

1. Validate the 32-byte SQLite WAL header.
2. Read the page size from the header.
3. Parse 24-byte frame headers.
4. Identify committed frames using non-zero database-size fields.
5. Apply frames only through the last committed transaction.
6. Decrypt each WAL page payload with the same validated page decryptor.
7. Extend or truncate the reconstructed database to the page count declared by the final commit.

Do not apply uncommitted trailing frames.

### Integrity validation

After reconstruction:

```sql
PRAGMA quick_check;
```

must return `ok` before conversation discovery begins.

The temporary decrypted database should be removed automatically on normal exit unless the user explicitly chooses a debug/keep-temp option in a future version.

## 10. Schema capability discovery

The tool must not assume exactly 128 message tables.

Discover message tables dynamically:

```sql
SELECT name
FROM sqlite_master
WHERE type='table'
  AND name LIKE 'tbmsg_%';
```

Before reading them, verify expected columns such as:

- `cid`
- `mid`
- `senderId`
- `createdAt`
- `content`

Optional fields must be capability-detected.

This allows the exporter to remain tolerant of minor schema variations.

## 11. Conversation discovery

`conversations.py` is responsible for building the selectable conversation list.

Sources should include, in priority order where useful:

1. `tbconversation`
2. conversation extension tables
3. distinct `cid` values from message shards
4. message-derived metadata

For each conversation, compute or estimate:

- CID
- display name
- participant IDs
- resolved participant names
- message count
- last message timestamp

Conversation discovery must not require loading every raw message body into memory when SQL aggregation can provide counts or timestamps more efficiently.

## 12. Conversation naming strategy

The application should attempt to resolve a useful human-readable name for every conversation.

Priority order:

1. Explicit conversation/group title from conversation tables.
2. Explicit group/member metadata.
3. Resolved participant names.
4. Names found in structured message metadata such as mentions or forwarded-message sender fields.
5. One-to-one CID parsing when the CID itself encodes participant UIDs.
6. A generated participant list such as `Alice, Bob, Me`.
7. CID as final fallback.

For one-to-one conversations, prefer the other participant's name instead of displaying both users.

For group conversations without an explicit title, use a compact participant summary rather than only the CID.

Name resolution must be deterministic and testable.

## 13. Profile resolution

`profiles.py` maps user IDs to display names.

Primary sources include:

- `tbuser_profile_v2`
- user alias tables
- user group nickname tables
- structured `atIds` JSON in messages
- structured sender metadata from forwarded-message attachments
- other compatible profile fields discovered from schema

Resolution precedence should favor explicit aliases/display names over raw identifiers.

Known current-user UID should be mapped to the local account display name when discoverable, with a neutral fallback such as `Me` rather than hardcoding `Me`.

## 14. Message extraction

`messages.py` reads all message shard tables containing the chosen CID.

Messages are sorted by:

1. `createdAt`
2. `mid`

This produces deterministic ordering for messages sharing the same timestamp.

Normalized message model:

```text
conversation_id
message_id
local_id
sender_id
sender_name
timestamp
datetime
message_type
content_type
text
recalled
attachments
source_table
raw_content
raw_extension
raw_attachments
```

## 15. Content parsing

The parser should support the formats observed in the validated database without claiming exhaustive DingTalk protocol support.

### Plain text

For content resembling:

```json
{"contentType":1,"text":"Hello"}
```

use `text` directly.

### Rich/markdown messages

For attachment structures containing an `extension.markdown` or title, extract a readable representation.

### Forwarded chat-history bundles

Observed `contentType=1500` messages can contain:

- a human-readable summary,
- title,
- embedded child message metadata,
- sender names.

For v1:

- preserve all raw attachment data in JSON,
- render the summary/title cleanly in TXT/HTML,
- optionally expose child sender names when parsing is straightforward,
- do not attempt full protocol decoding of binary/base64 message payloads unless required for accurate readable output.

### Unknown content types

Unknown types must not be discarded.

Fallback behavior:

- retain raw JSON/string data,
- include type/contentType,
- show a readable placeholder or raw text in human-oriented exports.

## 16. Export formats

### JSON

Primary archival/debug export.

Requirements:

- UTF-8
- pretty-printed
- normalized fields
- selected raw fields
- no lossy removal of unsupported message types

### CSV

Analysis-friendly export.

Columns:

```text
datetime
sender
sender_id
mid
type
content_type
text
recalled
```

Use UTF-8 with BOM for good Windows/Excel compatibility.

### TXT

Simple chronological transcript:

```text
[2026-09-11 09:42:10] Alice:
Message text
```

### HTML

Human-readable offline transcript.

Requirements:

- single self-contained HTML file where practical,
- escaped message content,
- clear differentiation between local-user and other messages,
- sender name,
- timestamp,
- responsive layout,
- multilingual Unicode support,
- no external CDN dependencies required for rendering.

## 17. Output paths and filenames

Default repository runtime output:

```text
exports/<sanitized-conversation-name>/
```

Files:

```text
chat.json
chat.csv
chat.txt
chat.html
```

If the sanitized conversation name collides with an existing directory, append a stable suffix such as the CID fragment.

Never use untrusted chat names directly as filesystem paths without sanitization.

## 18. Error handling

Errors should be concise, actionable, and in English.

Examples:

```text
Unsupported DingTalk database format: the decrypted first page did not contain a valid SQLite header.
```

```text
DingTalk appears to be running. Close it completely before exporting so the latest WAL state can be read consistently.
```

```text
No compatible `_v2` DingTalk account databases were found under %APPDATA%\\DingTalk.
```

Use custom exception types in `errors.py` so the CLI can distinguish compatibility errors from filesystem failures and unexpected bugs.

## 19. DingTalk running-state behavior

The safest default is to require DingTalk to be closed before producing a final export.

Reason:

- the WAL may be changing while it is read,
- file contents may not represent one consistent point in time,
- recent messages can live in committed WAL frames rather than the base DB.

The CLI should detect running `DingTalk.exe` processes and ask the user to exit DingTalk before continuing.

The application should not terminate DingTalk automatically.

## 20. Privacy, safety, and disclaimer

The README and `docs/privacy-and-safety.md` must state clearly:

- This is an unofficial community tool and is not affiliated with DingTalk or Alibaba.
- It is intended to export local conversations the current user is already authorized to access.
- Chat exports may contain personal, confidential, or third-party information.
- Users are responsible for complying with applicable law, workplace policies, contractual obligations, and DingTalk terms.
- The tool does not upload chat contents anywhere.
- All processing is local unless the user separately chooses to move or share the generated files.
- Users should protect exported files appropriately.

The documentation should avoid presenting the tool as a means to bypass security or gain access to other users' data.

## 21. README structure

The README should be written entirely in English and include:

1. Project title and one-sentence description.
2. Status / tested environment.
3. Screenshot or terminal example later if useful.
4. Features.
5. Requirements.
6. Installation.
7. Quick start.
8. Example interactive session.
9. Output formats.
10. How conversation naming works.
11. Compatibility notes.
12. Troubleshooting.
13. Privacy and legal disclaimer.
14. Security notes.
15. Development/testing instructions.
16. Contributing.
17. License.

A prominent compatibility statement should say that v1 is Windows-only and initially validated against the tested DingTalk V2 local database format.

## 22. Dependencies

Keep dependencies minimal.

Expected runtime dependencies:

- `pycryptodome` for AES.
- Python standard library for SQLite, JSON, CSV, hashing, filesystem, HTML generation, and CLI interaction.

Avoid large UI frameworks or database abstractions unless later requirements justify them.

Test dependency:

- `pytest`.

## 23. Testing strategy

Tests must not require a real user's DingTalk database.

### Crypto tests

- known UID -> expected MD5-derived key,
- AES decryption of a synthetic SQLite-header page,
- invalid key fails format validation.

### WAL tests

Build synthetic WAL fixtures covering:

- valid WAL magic,
- page application,
- multiple commits,
- uncommitted trailing frames,
- database growth,
- final truncation,
- invalid WAL page size.

### Message tests

- plain text JSON,
- markdown/rich attachment extraction,
- unknown content type fallback,
- multilingual strings,
- recalled messages,
- stable chronological ordering.

### Name-resolution tests

- explicit group title,
- one-to-one profile lookup,
- alias preferred over raw profile name,
- names learned from `atIds`,
- participant-list fallback,
- CID fallback.

### Export tests

- valid JSON,
- CSV quoting/newlines,
- UTF-8 BOM for CSV,
- safe HTML escaping,
- sanitized output paths,
- Unicode round-trip.

### Integration fixture

Create a small synthetic encrypted SQLite database plus WAL using the validated V2 cipher so an end-to-end test can exercise:

```text
discover fixture -> derive key -> decrypt -> apply WAL -> discover chat -> export
```

No real chat content should be committed to the repository.

## 24. Security engineering notes

- Never log derived keys by default.
- Never print full raw message bodies during normal discovery.
- Avoid leaving decrypted temporary databases behind after successful execution.
- Use temporary directories with predictable cleanup behavior.
- Escape all HTML output.
- Sanitize filesystem names.
- Do not execute content found inside chat messages.
- Treat JSON and attachment strings as untrusted input.

A `--debug` mode may be added later to retain working files and increase logging, but it should be opt-in.

## 25. Licensing

Use a permissive open-source license unless the repository owner chooses otherwise.

Recommended default: MIT License.

The README must make clear that the license applies to this project's source code, not to DingTalk software, protocols, trademarks, or user data.

## 26. Future extensions

Potential later work, not part of v1 acceptance:

- standalone Windows `.exe`,
- PyPI package,
- non-interactive CLI flags,
- attachment extraction/copying,
- search before export,
- export multiple/all conversations,
- richer forwarded-message decoding,
- additional DingTalk DB generations,
- macOS support if storage format is understood,
- optional GUI.

## 27. v1 acceptance criteria

The v1 repository is complete when a new Windows user with a compatible DingTalk V2 installation can:

1. Clone the repository.
2. Install documented Python dependencies.
3. Run `python dingtalk_export.py`.
4. Have the tool detect at least one compatible account automatically.
5. Have the tool validate and derive the local database key automatically.
6. Have the tool reconstruct the current database including committed WAL frames.
7. See a list of conversations with best-effort human-readable names.
8. Select a conversation interactively.
9. Export it to JSON, CSV, TXT, and HTML.
10. See resolved sender names where local data makes them available.
11. Complete the process without modifying DingTalk's source files.
12. Follow the process using English-only public documentation.

