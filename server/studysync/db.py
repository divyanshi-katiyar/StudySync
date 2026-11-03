"""SQLite access: one connection per request, parameterised queries only."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(path: str):
    conn = connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()


def one(sql: str, params=()):
    return get_db().execute(sql, params).fetchone()


def all_rows(sql: str, params=()):
    return get_db().execute(sql, params).fetchall()


def run(sql: str, params=()):
    return get_db().execute(sql, params)
