# db.py
import os
import sqlite3

DB_FILE = "events.db"


def init_db():
    need_init = not os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    if need_init:
        c.execute("""CREATE TABLE players (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP
                     )""")
        c.execute("""CREATE TABLE events (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      type TEXT,
                      rounds INTEGER,
                      round_time INTEGER,
                      status TEXT,
                      current_round INTEGER DEFAULT 0,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                      round_start_ts INTEGER
                     )""")
        c.execute("""CREATE TABLE event_players (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      event_id INTEGER,
                      player_id INTEGER,
                      guest_name TEXT,
                      seating_pos INTEGER,
                      UNIQUE(event_id, player_id, guest_name)
                     )""")
        c.execute("""CREATE TABLE matches (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      event_id INTEGER,
                      round INTEGER,
                      player1 INTEGER,
                      player2 INTEGER,
                      score_p1 INTEGER DEFAULT 0,
                      score_p2 INTEGER DEFAULT 0,
                      bye INTEGER DEFAULT 0
                     )""")
        conn.commit()
    else:
        # Migration: ensure round_start_ts exists on events table
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(events)").fetchall()]
            if 'round_start_ts' not in cols:
                c.execute("ALTER TABLE events ADD COLUMN round_start_ts INTEGER")
                conn.commit()
        except Exception:
            pass
    return conn


DB = init_db()
