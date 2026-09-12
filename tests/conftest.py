import sqlite3
import struct
from pathlib import Path

from dingtalk_exporter.crypto import _encrypt_page_for_testing

PAGE_SIZE = 4096


def encrypt_pages(data: bytes, key: bytes) -> bytes:
    assert len(data) % PAGE_SIZE == 0
    return b"".join(_encrypt_page_for_testing(data[i:i + PAGE_SIZE], key) for i in range(0, len(data), PAGE_SIZE))


def make_sqlite_file(path: Path, rows: list[str]) -> bytes:
    con = sqlite3.connect(path)
    con.execute("PRAGMA page_size=4096")
    con.execute("CREATE TABLE messages(value TEXT)")
    con.executemany("INSERT INTO messages(value) VALUES (?)", [(row,) for row in rows])
    con.commit()
    con.close()
    data = path.read_bytes()
    assert len(data) % PAGE_SIZE == 0
    return data


def make_wal(frames: list[tuple[int, int, bytes]], page_size: int = PAGE_SIZE) -> bytes:
    header = struct.pack(">8I", 0x377F0682, 3007000, page_size, 0, 1, 2, 0, 0)
    output = bytearray(header)
    for page_number, db_size, payload in frames:
        assert len(payload) == page_size
        frame_header = struct.pack(">6I", page_number, db_size, 1, 2, 0, 0)
        output.extend(frame_header)
        output.extend(payload)
    return bytes(output)


def make_dingtalk_like_plain_db(path: Path) -> bytes:
    import json

    con = sqlite3.connect(path)
    con.execute("PRAGMA page_size=4096")
    con.execute("CREATE TABLE tbuser_profile_v2(uid INTEGER, nick TEXT)")
    con.execute("CREATE TABLE tbuser_alias_name(uid INTEGER, alias TEXT)")
    con.execute("CREATE TABLE tbmsg_000(primaryKey INTEGER PRIMARY KEY, cid TEXT, localId TEXT, mid INTEGER, senderId INTEGER, type INTEGER, createdAt INTEGER, contentType INTEGER, content TEXT, extension TEXT, recallStatus INTEGER, attachments TEXT, atIds TEXT)")
    con.execute("INSERT INTO tbuser_profile_v2 VALUES (2, 'Alice Profile')")
    con.execute("INSERT INTO tbuser_alias_name VALUES (2, 'Alice')")
    con.execute(
        "INSERT INTO tbmsg_000(cid,localId,mid,senderId,type,createdAt,contentType,content,extension,recallStatus,attachments,atIds) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("1:2", "local-1", 10, 2, 1, 1755176432118, 1, json.dumps({"contentType": 1, "text": "Hello there"}), "", 0, "", ""),
    )
    con.commit()
    con.close()
    data = path.read_bytes()
    assert len(data) % PAGE_SIZE == 0
    return data
