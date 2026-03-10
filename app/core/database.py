import os
import sqlite3
from app.config import DB_PATH, FAISS_DIR
from app.core.progress import set_progress, reset


def get_connection() -> sqlite3.Connection:
    os.makedirs(FAISS_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            path     TEXT    UNIQUE NOT NULL,
            hash     TEXT    NOT NULL,
            faiss_id INTEGER UNIQUE NOT NULL,
            mtime    REAL    NOT NULL DEFAULT 0
        )
    """)
    try:
        con.execute("ALTER TABLE files ADD COLUMN mtime REAL NOT NULL DEFAULT 0")
    except Exception:
        pass
    con.execute("CREATE INDEX IF NOT EXISTS idx_hash     ON files(hash)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_path     ON files(path)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_faiss_id ON files(faiss_id)")
    con.commit()
    return con


def cleanup_missing_in_folder(con: sqlite3.Connection, index, folder_path: str):
    folder_prefix = os.path.normpath(folder_path) + os.sep   # fix: os.sep prevents sibling folder match
    rows = con.execute(
        "SELECT path, faiss_id FROM files WHERE path LIKE ?",
        (folder_prefix + "%",)
    ).fetchall()

    missing_paths     = []
    missing_faiss_ids = []

    set_progress(done=0, total=len(rows), current="", phase="Database Cleanup", errors=0)

    for path, faiss_id in rows:
        if not os.path.exists(path):
            missing_paths.append((path,))
            missing_faiss_ids.append(faiss_id)

    if missing_paths:
        con.executemany("DELETE FROM files WHERE path=?", missing_paths)
        from app.core import indexer
        indexer.remove_embeddings(index, missing_faiss_ids)
        con.commit()
        set_progress(done=len(rows))
        reset()


def find_by_hash(con: sqlite3.Connection, hash_value: str):
    """Returns (path, faiss_id) or (None, None)"""
    row = con.execute(
        "SELECT path, faiss_id FROM files WHERE hash=?", (hash_value,)
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def find_by_path(con: sqlite3.Connection, path: str):
    """Returns (faiss_id, hash, mtime) or None"""
    row = con.execute(
        "SELECT faiss_id, hash, mtime FROM files WHERE path=?", (path,)
    ).fetchone()
    return row if row else None


def get_next_faiss_id(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT MAX(faiss_id) FROM files").fetchone()
    return (row[0] + 1) if row[0] is not None else 0


def insert_file(con: sqlite3.Connection, path: str, hash_value: str, faiss_id: int, mtime: float):
    con.execute(
        "INSERT OR REPLACE INTO files (path, hash, faiss_id, mtime) VALUES (?,?,?,?)",
        (path, hash_value, faiss_id, mtime)
    )


def move_file(con: sqlite3.Connection, old_path: str, new_path: str):
    con.execute("UPDATE files SET path=? WHERE path=?", (new_path, old_path))


def delete_file(con: sqlite3.Connection, path: str):
    con.execute("DELETE FROM files WHERE path=?", (path,))


def get_folder_id_map(con: sqlite3.Connection, folder_path: str) -> dict:
    """Returns {faiss_id: path} for all files under folder_path"""
    folder_prefix = os.path.normpath(folder_path) + os.sep   # fix: os.sep prevents sibling folder match
    rows = con.execute(
        "SELECT faiss_id, path FROM files WHERE path LIKE ?",
        (folder_prefix + "%",)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_folder_hashes(con: sqlite3.Connection, folder_path: str) -> set:
    folder_prefix = os.path.normpath(folder_path) + os.sep   # fix: os.sep prevents sibling folder match
    rows = con.execute(
        "SELECT hash FROM files WHERE path LIKE ?",
        (folder_prefix + "%",)
    ).fetchall()
    return {r[0] for r in rows}


def get_files_by_hashes(con: sqlite3.Connection, hashes: set) -> list:
    """Returns list of (path, faiss_id) for given hashes"""
    if not hashes:
        return []
    placeholders = ",".join("?" * len(hashes))
    return con.execute(
        f"SELECT path, faiss_id FROM files WHERE hash IN ({placeholders})",
        list(hashes)
    ).fetchall()


def get_folder_file_count(con: sqlite3.Connection, folder_path: str) -> int:
    """
    Returns count of files in DB under folder_path.
    Used by search_service for quick check before deciding to sync.
    """
    folder_prefix = os.path.normpath(folder_path) + os.sep
    cur = con.execute(
        "SELECT COUNT(*) FROM files WHERE path LIKE ?",
        (folder_prefix + "%",)
    )
    return cur.fetchone()[0]


def get_all_path(con: sqlite3.Connection) -> list:
    return con.execute("SELECT path FROM files").fetchall()