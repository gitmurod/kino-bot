import sqlite3
from typing import Optional, List, Dict


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._create_tables()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS movies (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    year        TEXT DEFAULT 'Noma''lum',
                    genre       TEXT DEFAULT 'Noma''lum',
                    rating      TEXT DEFAULT '—',
                    description TEXT DEFAULT '',
                    file_id     TEXT DEFAULT NULL,
                    views       INTEGER DEFAULT 0,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS users (
                    id         INTEGER PRIMARY KEY,
                    username   TEXT,
                    full_name  TEXT,
                    joined_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_blocked INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS admins (
                    user_id    INTEGER PRIMARY KEY,
                    added_by   INTEGER,
                    added_at   DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    title      TEXT,
                    link       TEXT,
                    active     INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            conn.commit()

    # ─── MOVIES ──────────────────────────────────────────────
    def add_movie(self, title, year, genre, rating, description="") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO movies (title, year, genre, rating, description) VALUES (?,?,?,?,?)",
                (title, year, genre, rating, description)
            )
            conn.commit()
            return cur.lastrowid

    def update_movie_file(self, movie_id, file_id):
        with self._connect() as conn:
            conn.execute("UPDATE movies SET file_id=? WHERE id=?", (file_id, movie_id))
            conn.commit()

    def delete_movie(self, movie_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM movies WHERE id=?", (movie_id,))
            conn.commit()

    def get_movie_by_id(self, movie_id) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
            if row:
                conn.execute("UPDATE movies SET views=views+1 WHERE id=?", (movie_id,))
                conn.commit()
            return dict(row) if row else None

    def search_movies(self, query) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM movies WHERE title LIKE ? ORDER BY title LIMIT 10",
                (f"%{query}%",)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_movies(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM movies ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def movies_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]

    # ─── USERS ───────────────────────────────────────────────
    def add_or_update_user(self, user_id, username, full_name):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(id,username,full_name) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                (user_id, username or "", full_name or "")
            )
            conn.commit()

    def get_all_users(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users WHERE is_blocked=0").fetchall()
            return [dict(r) for r in rows]

    def users_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked=0").fetchone()[0]

    def users_today(self) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE date(joined_at)=date('now') AND is_blocked=0"
            ).fetchone()[0]

    # ─── ADMINS ──────────────────────────────────────────────
    def get_admins(self) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM admins").fetchall()
            return [r[0] for r in rows]

    def add_admin(self, user_id, added_by):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO admins(user_id, added_by) VALUES(?,?)",
                (user_id, added_by)
            )
            conn.commit()

    def remove_admin(self, user_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
            conn.commit()

    def is_admin(self, user_id) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
            return row is not None

    # ─── CHANNELS ────────────────────────────────────────────
    def add_channel(self, channel_id, title, link) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO channels(channel_id,title,link) VALUES(?,?,?)",
                (channel_id, title, link)
            )
            conn.commit()
            return cur.lastrowid

    def get_active_channels(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM channels WHERE active=1").fetchall()
            return [dict(r) for r in rows]

    def get_all_channels(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM channels").fetchall()
            return [dict(r) for r in rows]

    def toggle_channel(self, ch_id, active: int):
        with self._connect() as conn:
            conn.execute("UPDATE channels SET active=? WHERE id=?", (active, ch_id))
            conn.commit()

    def delete_channel(self, ch_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM channels WHERE id=?", (ch_id,))
            conn.commit()

    # ─── SETTINGS ────────────────────────────────────────────
    def get_setting(self, key, default=None):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
            conn.commit()
