import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,              -- waiting | in_progress | finished
    word_set TEXT NOT NULL,            -- JSON list, the full set for this match
    words_remaining TEXT NOT NULL,     -- JSON list, words not yet claimed
    start_time REAL,
    duration INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_players (
    match_id INTEGER NOT NULL REFERENCES matches(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    score INTEGER NOT NULL DEFAULT 0,
    connected INTEGER NOT NULL DEFAULT 0,
    rematch_vote INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, user_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Thin, thread-safe SQLite wrapper. One connection, one lock.

    A single game server process handles a modest number of concurrent
    matches, so serializing DB access behind one lock is simple and safe
    rather than a bottleneck.
    """

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- users ------------------------------------------------------
    def create_user(self, username: str, password_hash: str):
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, _now()),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_user_by_username(self, username: str):
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    # ---- matches ------------------------------------------------------
    def create_match(self, word_set, duration: int, start_time: float):
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO matches (status, word_set, words_remaining, start_time, duration, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("in_progress", json.dumps(word_set), json.dumps(word_set), start_time, duration, _now()),
            )
            self.conn.commit()
            return cur.lastrowid

    def add_match_player(self, match_id: int, user_id: int):
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO match_players (match_id, user_id, score, connected, rematch_vote) "
                "VALUES (?, ?, COALESCE((SELECT score FROM match_players WHERE match_id=? AND user_id=?), 0), 1, 0)",
                (match_id, user_id, match_id, user_id),
            )
            self.conn.commit()

    def set_player_connected(self, match_id: int, user_id: int, connected: bool):
        with self.lock:
            self.conn.execute(
                "UPDATE match_players SET connected = ? WHERE match_id = ? AND user_id = ?",
                (1 if connected else 0, match_id, user_id),
            )
            self.conn.commit()

    def update_player_score(self, match_id: int, user_id: int, score: int):
        with self.lock:
            self.conn.execute(
                "UPDATE match_players SET score = ? WHERE match_id = ? AND user_id = ?",
                (score, match_id, user_id),
            )
            self.conn.commit()

    def set_player_rematch_vote(self, match_id: int, user_id: int, vote: bool):
        with self.lock:
            self.conn.execute(
                "UPDATE match_players SET rematch_vote = ? WHERE match_id = ? AND user_id = ?",
                (1 if vote else 0, match_id, user_id),
            )
            self.conn.commit()

    def update_words_remaining(self, match_id: int, words_remaining):
        with self.lock:
            self.conn.execute(
                "UPDATE matches SET words_remaining = ? WHERE id = ?",
                (json.dumps(words_remaining), match_id),
            )
            self.conn.commit()

    def restart_match(self, match_id: int, word_set, start_time: float):
        with self.lock:
            self.conn.execute(
                "UPDATE matches SET status='in_progress', word_set=?, words_remaining=?, start_time=? WHERE id=?",
                (json.dumps(word_set), json.dumps(word_set), start_time, match_id),
            )
            self.conn.execute(
                "UPDATE match_players SET score=0, rematch_vote=0 WHERE match_id=?",
                (match_id,),
            )
            self.conn.commit()

    def finish_match(self, match_id: int):
        with self.lock:
            self.conn.execute(
                "UPDATE matches SET status='finished' WHERE id = ?", (match_id,)
            )
            self.conn.commit()

    def get_match(self, match_id: int):
        with self.lock:
            row = self.conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            return dict(row) if row else None

    def get_in_progress_matches(self):
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM matches WHERE status = 'in_progress'"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_match_players(self, match_id: int):
        with self.lock:
            rows = self.conn.execute(
                "SELECT mp.*, u.username FROM match_players mp "
                "JOIN users u ON u.id = mp.user_id WHERE mp.match_id = ?",
                (match_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_active_match_for_user(self, user_id: int):
        """Return the in-progress match this user belongs to, if any."""
        with self.lock:
            row = self.conn.execute(
                "SELECT m.* FROM matches m "
                "JOIN match_players mp ON mp.match_id = m.id "
                "WHERE mp.user_id = ? AND m.status = 'in_progress' "
                "ORDER BY m.id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
