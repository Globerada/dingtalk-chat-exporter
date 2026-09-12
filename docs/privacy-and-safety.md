# Privacy and Safety

DingTalk Chat Exporter is an unofficial community project and has no affiliation with DingTalk or Alibaba.

## Authorized use only

Use the tool only for conversations that the local DingTalk user is already authorized to access. The project does not bypass DingTalk authentication and is not intended to access other users' accounts, recover deleted conversations, or retrieve server-side data that is unavailable locally.

## Local processing

The exporter reads the local DingTalk database, derives the validated local V2 key, reconstructs a temporary decrypted SQLite database, and writes export files on the same machine. The program does not upload chat data to a service operated by this project.

## Sensitive information

Exports may contain:

- names and contact information,
- personal data,
- business-confidential information,
- customer or partner discussions,
- contractual information,
- links and identifiers,
- attachments represented in message metadata,
- credentials or secrets that someone may have shared in chat.

Treat exports as sensitive files. Store, transmit, and delete them according to the rules that apply to the original conversation.

## Your responsibilities

You are responsible for complying with applicable law, data-protection requirements, workplace policy, employment obligations, contractual confidentiality terms, litigation holds, records-retention rules, and DingTalk terms that apply to you.

## Bug reports

Do not publish real exports or local DingTalk databases when reporting a bug. Remove or replace real UIDs, participant names, conversation IDs, message text, tokens, derived keys, organization IDs, and file paths that disclose personal information.

Prefer sanitized diagnostics such as version numbers, schema column names, table names, page sizes, WAL magic values, and exact error messages.
