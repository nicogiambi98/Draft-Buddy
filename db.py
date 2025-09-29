# db.py
import os
import sqlite3
import shutil

try:
    from kivy.app import App
    from kivy.utils import platform
except Exception:  # Allow importing outside Kivy (e.g., for tooling)
    App = None
    platform = None


def _get_persistent_db_path(filename: str = "events.db") -> str:
    """Return a path under a persistent app data directory.
    - On Android/iOS: use Kivy's App.user_data_dir which survives app updates.
    - Elsewhere: use a folder in the user's home directory.
    Also performs a one-time seed: if no DB exists at the persistent
    location but a bundled copy exists alongside this file, copy it.
    """
    # Determine base persistent dir
    base_dir = None
    # Prefer Kivy App.user_data_dir when available (after App has started)
    if App is not None:
        try:
            app = App.get_running_app()
        except Exception:
            app = None
        if app is not None:
            try:
                base_dir = app.user_data_dir
            except Exception:
                base_dir = None
    # If still not decided and running on Android, use p4a-provided env vars
    if not base_dir:
        try:
            plat = platform if platform is not None else None
        except Exception:
            plat = None
        if plat == 'android':
            # ANDROID_PRIVATE points to the app-internal files dir (persistent, no permissions needed)
            base_dir = os.environ.get('ANDROID_PRIVATE')
            if not base_dir:
                # Fallback: ANDROID_ARGUMENT is the app dir; use its parent (files dir)
                arg = os.environ.get('ANDROID_ARGUMENT')
                if arg:
                    base_dir = os.path.dirname(arg)
        elif plat == 'ios':
            # On iOS, expanduser("~") is safe and points to app sandbox
            base_dir = os.path.expanduser('~')
    # Final fallback for desktop/tools or unknown platforms
    if not base_dir:
        base_dir = os.path.join(os.path.expanduser("~"), ".draft_buddy")
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass

    target_path = os.path.join(base_dir, filename)

    # One-time seed from bundled file if target doesn't exist
    if not os.path.exists(target_path):
        bundled_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        try:
            if os.path.exists(bundled_path):
                shutil.copy2(bundled_path, target_path)
        except Exception:
            # Ignore seeding failures; we'll create an empty schema below
            pass
    return target_path


def init_db():
    db_path = _get_persistent_db_path()
    need_init = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    if need_init:
        c.execute("""CREATE TABLE players (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      nickname TEXT,
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
        # Migration: add players.nickname column if missing
        try:
            pcols = [r[1] for r in c.execute("PRAGMA table_info(players)").fetchall()]
            if 'nickname' not in pcols:
                c.execute("ALTER TABLE players ADD COLUMN nickname TEXT")
                # Initialize nickname with a simple default: first name + first surname initial
                # Note: Uniqueness will be handled on insert/update logic in main.py
                try:
                    rows = c.execute("SELECT id, name FROM players").fetchall()
                    for pid, fullname in rows:
                        if not fullname:
                            continue
                        parts = str(fullname).strip().split()
                        if len(parts) == 1:
                            nick = parts[0]
                        else:
                            nick = f"{parts[0]} {parts[1][0]}."
                        c.execute("UPDATE players SET nickname=? WHERE id=?", (nick, pid))
                except Exception:
                    pass
                conn.commit()
        except Exception:
            pass
    return conn


DB = init_db()
