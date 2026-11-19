"""SQLite access: pooled connections, parameterised queries only.

Opening a connection costs more than most queries (connect, three PRAGMAs, close with a WAL clean-up: about 0.7 ms of a 1.5 to 2.2 ms
request, measured in logs/profile-before.txt), so finished requests hand their connection back to a small pool and the next
request reuses it. Set DB_POOL = False to get one connection per request again (useful when debugging).
"""
import queue
import sqlite3
import threading
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")
POOL_MAX_IDLE = 16

_pools: dict[str, queue.LifoQueue] = {}
_pools_lock = threading.Lock()


def connect(path: str) -> sqlite3.Connection:
    # check_same_thread is off because a pooled connection is used by one request at a time but by different threads over time
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # these two are per connection; journal_mode = WAL is stored in the file (see init_db)
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _pool(path: str) -> queue.LifoQueue:
    with _pools_lock:
        return _pools.setdefault(path, queue.LifoQueue())


def _checkout(path: str) -> sqlite3.Connection:
    try:
        return _pool(path).get_nowait()
    except queue.Empty:
        return connect(path)


def _release(path: str, conn: sqlite3.Connection):
    try:
        if conn.in_transaction:  # never let a half-finished transaction leak into the next request
            conn.rollback()
        pool = _pool(path)
        if pool.qsize() < POOL_MAX_IDLE:
            pool.put(conn)
            return
    except sqlite3.Error:
        pass
    conn.close()


def close_pool(path: str | None = None):
    """Close idle pooled connections (all databases, or one path). Used when a database file is about to be deleted."""
    with _pools_lock:
        targets = [path] if path else list(_pools)
        pools = [_pools.pop(p) for p in targets if p in _pools]
    for pool in pools:
        while True:
            try:
                pool.get_nowait().close()
            except queue.Empty:
                break


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = current_app.config["DATABASE"]
        g.db = _checkout(path) if current_app.config.get("DB_POOL", True) else connect(path)
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is None:
        return
    if current_app.config.get("DB_POOL", True):
        _release(current_app.config["DATABASE"], conn)
    else:
        conn.close()


def _migrate(conn: sqlite3.Connection):
    """Bring a database created by an older version up to date (Week 5: members are now counted by triggers)."""
    has_groups = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'study_groups'").fetchone()
    if not has_groups:
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(study_groups)")}
    if "member_count" not in columns:
        conn.execute("ALTER TABLE study_groups ADD COLUMN member_count INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE study_groups SET member_count = (SELECT COUNT(*) FROM memberships m WHERE m.group_id = study_groups.id)")
        conn.commit()


def init_db(path: str):
    conn = connect(path)
    _migrate(conn)
    conn.execute("PRAGMA journal_mode = WAL")  # persistent: set once here instead of on every request
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()


def one(sql: str, params=()):
    return get_db().execute(sql, params).fetchone()


def all_rows(sql: str, params=()):
    return get_db().execute(sql, params).fetchall()
