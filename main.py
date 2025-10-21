"""Draft Buddy application entry point.

This module wires together all Kivy Screens, kv layout, and business logic for:
- Player management
- Event creation and Swiss-like rounds with standings
- Seating and round timer integration
- League tracker and MTG bingo helper
- Settings (import/export DB, login, guest sync) and a simple server client

Notes:
- This documentation pass adds docstrings and comments without changing logic
  or visuals.
- The embedded KV string defines most of the UI; the code-behind updates it.
"""

import sqlite3
import random
import os
import time
from datetime import datetime
import json
import requests

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition, SlideTransition
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, NumericProperty, DictProperty, ObjectProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from pairing import get_name_for_event_player, compute_standings, generate_round_one, compute_next_round_pairings
from timer import DraftTimer, IconButton
from kivy.core.window import Window
from kivy.utils import platform
from kivy.metrics import dp
from kivy.animation import Animation
from db import get_db_path

# Ensure desktop window starts in a smartphone-like portrait proportion (20:9)
# Only apply on desktop platforms to avoid interfering with mobile builds
if platform in ("win", "linux", "macosx"):
    try:
        base_height = 1000  # arbitrary portrait height
        base_width = int(base_height * 9 / 20)
        Window.size = (base_width, base_height)
        # Optionally position the window nicely
        try:
            Window.top = 50
            Window.left = 50
        except Exception:
            pass
    except Exception:
        # Silently ignore if Window is not available or setting size fails
        pass

DB_FILE = "events.db"

KV = r'''
#:import dp kivy.metrics.dp

<PlayersScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                markup: True
                text: "[b]Players[/b]"
            Button:
                text: "New Player"
                size_hint_x: None
                width: dp(140)
                on_release: root.manager.current = "newplayer"

        BoxLayout:
            size_hint_y: None
            height: dp(36)
            TextInput:
                id: filter_input
                hint_text: "Filter..."
                on_text: root.filter_players(self.text)

        ScrollView:
            GridLayout:
                id: players_list
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                row_default_height: dp(36)

        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                text: "Events"
                on_release: root.manager.current = "eventslist"
            Button:
                text: "League Tracker"
                on_release: root.manager.current = "league"
            Button:
                text: "Bingo"
                on_release: root.manager.current = "bingo"
            Button:
                text: "Draft Timer"
                on_release: root.manager.current = "drafttimer"

<NewPlayerScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            markup: True
            text: "[b]Add New Player[/b]"
        TextInput:
            id: name_input
            hint_text: "Player name"
            multiline: False
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: "Save"
                on_release:
                    root.save_player(name_input.text)
            Button:
                text: "Back"
                on_release: root.manager.current = "players"

<CreateEventScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            markup: True
            text: "[b]Create Event[/b]"
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            TextInput:
                id: event_name
                hint_text: "Event name"
                multiline: False
            Spinner:
                id: event_type
                text: "draft"
                values: ["draft", "sealed", "cube"]
                size_hint_x: None
                width: dp(120)
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            TextInput:
                id: rounds_input
                hint_text: "Rounds (e.g. 3)"
                multiline: False
                input_filter: "int"
            TextInput:
                id: round_time
                hint_text: "Round time (sec)"
                multiline: False
                input_filter: "int"
            Button:
                text: "Randomize seating"
                size_hint_x: None
                width: dp(140)
                on_release: root.randomize_seating()
        Label:
            text: "Select players (or add guests)"
            size_hint_y: None
            height: dp(24)
        ScrollView:
            GridLayout:
                id: players_select
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                row_default_height: dp(36)
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            TextInput:
                id: guest_name
                hint_text: "Guest name (optional)"
                multiline: False
            Button:
                text: "Add guest to list"
                on_release:
                    root.add_guest(guest_name.text)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: "Start Event"
                on_release:
                    root.start_event(event_name.text, event_type.text, rounds_input.text, round_time.text)
            Button:
                text: "Cancel"
                on_release: root.manager.current = "players"

<EventsListScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            markup: True
            text: "[b]Events[/b]"
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Button:
                text: "Create Event"
                size_hint_x: None
                width: dp(140)
                on_release: root.manager.current = "createevent"
            Widget:
        ScrollView:
            GridLayout:
                id: events_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                row_default_height: dp(48)
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                text: "Events"
                on_release: root.manager.current = "eventslist"
            Button:
                text: "League Tracker"
                on_release: root.manager.current = "league"
            Button:
                text: "Bingo"
                on_release: root.manager.current = "bingo"
            Button:
                text: "Draft Timer"
                on_release: root.manager.current = "drafttimer"

<EventScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                id: event_title
                text: root.event_title
                color: 0,0,0,1
            Label:
                id: round_label
                text: "Round: " + str(root.current_round)
                color: 0,0,0,1
            Button:
                text: "Close Event"
                size_hint_x: None
                width: dp(120)
                on_release: root.close_event()
        ScrollView:
            GridLayout:
                id: matches_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                row_default_height: dp(48)
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                id: next_btn
                text: "Next Round"
                on_release: root.next_round()
            Button:
                text: "Back to Events"
                on_release: root.manager.current = "eventslist"
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                text: "Events"
                on_release: root.manager.current = "eventslist"
            Button:
                text: "League Tracker"
                on_release: root.manager.current = "league"
            Button:
                text: "Bingo"
                on_release: root.manager.current = "bingo"
            Button:
                text: "Draft Timer"
                on_release: root.manager.current = "drafttimer"

<MatchRow>:
    size_hint_y: None
    height: dp(48)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: (0.95,0.95,0.95,1) if self.bye else (1,1,1,1)
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: root.p1_name
        color: 0,0,0,1
    Button:
        id: p1btn
        text: str(root.score1)
        size_hint_x: None
        width: dp(60)
        on_release: root.cycle_score(1)
        color: 0,0,0,1
    Label:
        text: "-"
        size_hint_x: None
        width: dp(20)
        color: 0,0,0,1
    Button:
        id: p2btn
        text: str(root.score2)
        size_hint_x: None
        width: dp(60)
        on_release: root.cycle_score(2)
        color: 0,0,0,1
    Label:
        text: root.p2_name
        color: 0,0,0,1

<SeatingScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        TitleLabel:
            text: "Table Seating"
            size_hint_y: None
            height: dp(32)
        ScrollView:
            id: seat_sv
            do_scroll_x: False
            canvas.after:
                Color:
                    rgba: 1, 1, 1, 1
                Line:
                    rectangle: (self.x, self.y, self.width, self.height)
                    width: 1.2
            GridLayout:
                id: seating_list
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                row_default_height: dp(32)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: "Randomize again"
                on_release: root.randomize()
            Button:
                text: "Begin Round 1"
                on_release: root.confirm_and_begin()
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                text: "Events"
                on_release: root.manager.current = "eventslist"
            Button:
                text: "League Tracker"
                on_release: root.manager.current = "league"
            Button:
                text: "Bingo"
                on_release: root.manager.current = "bingo"
            Button:
                text: "Draft Timer"
                on_release: root.manager.current = "drafttimer"

<StandingsScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        TitleLabel:
            id: standings_title
            text: "Standings"
            size_hint_y: None
            height: dp(32)
        ScrollView:
            id: std_sv
            do_scroll_x: False
            canvas.after:
                Color:
                    rgba: 1, 1, 1, 1
                Line:
                    rectangle: (self.x, self.y, self.width, self.height)
                    width: 1.2
            GridLayout:
                id: standings_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(4)
                row_default_height: dp(28)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: "Back to Events"
                on_release: root.manager.current = "eventslist"
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            Button:
                text: "Events"
                on_release: root.manager.current = "eventslist"
            Button:
                text: "League Tracker"
                on_release: root.manager.current = "league"
            Button:
                text: "Bingo"
                on_release: root.manager.current = "bingo"
            Button:
                text: "Draft Timer"
                on_release: root.manager.current = "drafttimer"

<LeagueScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            text: "League Tracker (coming soon)"

<BingoScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            text: "Bingo (coming soon)"

<DraftTimerScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(10)
        spacing: dp(8)
        Label:
            text: "Draft Timer (coming soon)"
'''

# ----------------------
# DB helpers
# ----------------------
from db import DB

# ----------------------
# Nickname helpers
# ----------------------

def _compute_unique_nickname(fullname: str) -> str:
    """Compute a short nickname unique among existing players.

    Strategy:
    - Use "First S." if a surname is present; otherwise just "First".
    - If collisions occur within existing nicknames, gradually extend the
      surname prefix ("First Su.", "First Sur.", ...) until unique.
    - As a last resort, append a numeric suffix ("First S. 2").
    This function only reads existing DB nicknames and returns a suggestion;
    it does not write to the DB.
    """
    name = (fullname or "").strip()
    if not name:
        return ""
    parts = name.split()
    first = parts[0]
    surname = parts[1] if len(parts) > 1 else ""
    # fetch existing nicknames
    try:
        rows = DB.execute("SELECT nickname FROM players WHERE nickname IS NOT NULL").fetchall()
        existing = set(r[0] for r in rows if r and r[0])
    except Exception:
        existing = set()
    # base nick
    if not surname:
        base = first
    else:
        base = f"{first} {surname[0]}."
    if base not in existing:
        return base
    # extend surname letters
    i = 1
    while i < len(surname):
        i += 1
        cand = f"{first} {surname[:i]}."
        if cand not in existing:
            return cand
    # fallback: append numeric suffix
    n = 2
    while True:
        cand = f"{base[:-1]} {n}." if surname else f"{first} {n}"
        if cand not in existing:
            return cand
        n += 1


def _rebuild_all_nicknames():
    """Recompute all player nicknames for minimal unique prefixes.

    Within each group sharing the same first name (case-insensitive), compute the
    minimal unique surname prefix length so that "First S." style nicknames do not
    collide. Players without a surname get just "First"; duplicates receive a small
    numeric suffix. Writes changes to the DB.
    """
    try:
        rows = DB.execute("SELECT id, name FROM players ORDER BY id").fetchall()
    except Exception:
        return
    # Parse players into components while preserving original case
    players = []  # list of dicts: {id, first, surname, first_norm, surname_norm}
    for pid, fullname in rows:
        if not fullname:
            continue
        parts = str(fullname).strip().split()
        first = parts[0]
        surname = parts[1] if len(parts) > 1 else ""
        players.append({
            'id': pid,
            'first': first,
            'surname': surname,
            'first_norm': first.lower(),
            'surname_norm': surname.lower(),
        })

    # Group by first name (case-insensitive)
    from collections import defaultdict
    groups = defaultdict(list)
    for p in players:
        groups[p['first_norm']].append(p)

    updates = []

    def lcp_len(a: str, b: str) -> int:
        n = min(len(a), len(b))
        i = 0
        while i < n and a[i] == b[i]:
            i += 1
        return i

    # Build nicknames per group
    all_nicks = set()
    for first_key, plist in groups.items():
        # Split into with-surname and no-surname
        with_surname = [p for p in plist if p['surname']]
        no_surname = [p for p in plist if not p['surname']]

        # Compute minimal unique prefix lengths for surnames in this first-name group
        prefix_map = {}
        for p in with_surname:
            s = p['surname_norm']
            # minimal k = 1 + max LCP with any other surname in the same group
            max_lcp = 0
            for q in with_surname:
                if q is p:
                    continue
                max_lcp = max(max_lcp, lcp_len(s, q['surname_norm']))
            k = max_lcp + 1
            # Clamp to full length at most
            k = min(k, len(p['surname']))
            # Build nickname using original case for the prefix
            nick = f"{p['first']} {p['surname'][:k]}."
            prefix_map[p['id']] = nick

        # Assign base nicknames for no-surname entries (first name only)
        first_counts = {}
        for p in no_surname:
            base = p['first']
            # ensure uniqueness within the no-surname subset first
            first_counts[base] = first_counts.get(base, 0) + 1
            count = first_counts[base]
            nick = base if count == 1 else f"{base} {count}"
            prefix_map[p['id']] = nick

        # Now ensure global uniqueness across whole DB by appending minimal numeric suffixes if needed
        for p in plist:
            nick = prefix_map[p['id']]
            if nick not in all_nicks:
                all_nicks.add(nick)
                updates.append((nick, p['id']))
            else:
                # Append incremental numeric suffix before the final dot if present
                if nick.endswith('.'):
                    base = nick[:-1]
                    n = 2
                    while f"{base} {n}." in all_nicks:
                        n += 1
                    nick2 = f"{base} {n}."
                else:
                    base = nick
                    n = 2
                    while f"{base} {n}" in all_nicks:
                        n += 1
                    nick2 = f"{base} {n}"
                all_nicks.add(nick2)
                updates.append((nick2, p['id']))

    # apply updates
    try:
        for nick, pid in updates:
            DB.execute("UPDATE players SET nickname=? WHERE id=?", (nick, pid))
        DB.commit()
    except Exception:
        pass


# ----------------------
# UI Widgets
# ----------------------
class MatchRow(BoxLayout):
    p1_name = StringProperty("")
    p2_name = StringProperty("")
    score1 = NumericProperty(0)
    score2 = NumericProperty(0)
    match_id = NumericProperty(0)
    bye = NumericProperty(0)
    row_index = NumericProperty(0)
    on_score_change = ObjectProperty(None, allownone=True)

    def get_bg(self):
        try:
            app = App.get_running_app()
        except Exception:
            app = None
        try:
            if app and hasattr(app, 'theme'):
                s = app.theme.get('surface', (1, 1, 1))
                # ensure we have 3 components
                r, g, b = float(s[0]), float(s[1]), float(s[2])
                if self.bye:
                    # Make BYE rows clearly distinct with a soft, lighter tint
                    return [min(r + 0.10, 1), min(g + 0.10, 1), min(b + 0.06, 1), 1]
                if (int(self.row_index) % 2) == 0:
                    return [r, g, b, 1]
                else:
                    return [max(r - 0.03, 0), max(g - 0.03, 0), max(b - 0.03, 0), 1]
            else:
                # Fallback light/alt rows; BYE gets a warm highlight
                if self.bye:
                    return [1.0, 0.97, 0.88, 1]
                return [0.96, 0.96, 0.96, 1] if (int(self.row_index) % 2) == 0 else [0.92, 0.92, 0.92, 1]
        except Exception:
            return [1, 1, 1, 1]

    def get_score_bg_rgba(self, disabled, state):
        # Theme-aware blueish pill background for score buttons
        try:
            app = App.get_running_app()
        except Exception:
            app = None
        try:
            if disabled:
                return [0.75, 0.75, 0.78, 0.35]
            # Enabled state
            alpha = 0.22 if state == 'normal' else 0.32
            if app and hasattr(app, 'theme'):
                p = app.theme.get('primary', (0.16, 0.47, 0.96))
                r, g, b = float(p[0]), float(p[1]), float(p[2])
                return [r, g, b, alpha]
            # Fallback primary-ish blue
            return [0.16, 0.47, 0.96, alpha]
        except Exception:
            return [0.16, 0.47, 0.96, 0.22]

    def get_score_border_rgba(self, disabled):
        # Subtle border matching the primary hue
        try:
            app = App.get_running_app()
        except Exception:
            app = None
        try:
            if disabled:
                return [0.6, 0.6, 0.65, 0.45]
            if app and hasattr(app, 'theme'):
                p = app.theme.get('primary', (0.16, 0.47, 0.96))
                r, g, b = float(p[0]), float(p[1]), float(p[2])
                return [r, g, b, 0.45]
            return [0.16, 0.47, 0.96, 0.45]
        except Exception:
            return [0.16, 0.47, 0.96, 0.45]

    def cycle_score(self, side):
        """Cycle a player's game score 0→1→2→0 and persist it.

        Guards:
        - BYE rows are non-interactive.
        - Guests cannot change scores.
        Behavior:
        - Updates the corresponding score column in DB and commits.
        - If both players reach 2-2 (invalid), reset to 0-0 to encourage resolution.
        - Notifies parent via on_score_change callback if set.
        """
        # cycles 0 -> 1 -> 2 -> 0 and writes to DB
        if self.bye:
            return
        # Guests cannot submit match results
        try:
            if not _is_manager():
                app = App.get_running_app()
                if app:
                    app.show_toast('Guests cannot submit results')
                return
        except Exception:
            if not _is_manager():
                return
        if side == 1:
            self.score1 = (self.score1 + 1) % 3
            DB.execute("UPDATE matches SET score_p1 = ? WHERE id = ?", (self.score1, self.match_id))
        else:
            self.score2 = (self.score2 + 1) % 3
            DB.execute("UPDATE matches SET score_p2 = ? WHERE id = ?", (self.score2, self.match_id))
        DB.commit()
        # If both scores reach 2-2, reset to 0-0 (visual and DB)
        try:
            if int(self.score1) == 2 and int(self.score2) == 2:
                self.score1, self.score2 = 0, 0
                DB.execute("UPDATE matches SET score_p1 = 0, score_p2 = 0 WHERE id = ?", (self.match_id,))
                DB.commit()
        except Exception:
            pass
        # Manager: upload DB after score change
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("match_score_change")
        except Exception:
            pass
        # Notify parent/screen that a score changed
        try:
            if self.on_score_change:
                self.on_score_change(self)
        except Exception:
            pass
        # visually update (buttons bound to values)


# ----------------------
# Screens
# ----------------------
class PlayersScreen(Screen):
    def on_enter(self):
        self.refresh()

    def open_add_player(self):
        # Guests cannot add players
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot add players')
            except Exception:
                pass
            return
        # Create a lightweight popup to add a new player without leaving the list
        try:
            from kivy.uix.textinput import TextInput
            content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
            ti = TextInput(hint_text='Player name', multiline=False)
            try:
                ti.size_hint_y = None
                ti.height = dp(48)
                ti.font_size = '18sp'
            except Exception:
                pass
            # Trim leading spaces as user types
            def _lstrip(_inst, _val):
                try:
                    _inst.text = _inst.text.lstrip()
                except Exception:
                    pass
            ti.bind(text=_lstrip)
            # Buttons row
            btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            btn_save = Button(text='Save')
            btn_cancel = Button(text='Cancel')
            btns.add_widget(btn_save)
            btns.add_widget(btn_cancel)
            content.add_widget(ti)
            content.add_widget(btns)
            pop = Popup(title='Add New Player', content=content, size_hint=(0.9, None), height=dp(180), pos_hint={'top': 0.95})
            
            def _submit(*_):
                self._save_new_player_from_popup(ti.text, pop)
            
            btn_save.bind(on_release=_submit)
            btn_cancel.bind(on_release=lambda *_: pop.dismiss())
            ti.bind(on_text_validate=_submit)
            pop.open()
            # Focus after open
            Clock.schedule_once(lambda *_: setattr(ti, 'focus', True), 0.05)
        except Exception:
            # Fallback: navigate to old screen if popup fails
            try:
                self.manager.current = 'newplayer'
            except Exception:
                pass

    def _save_new_player_from_popup(self, name, popup):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot add players')
            except Exception:
                pass
            try:
                popup.dismiss()
            except Exception:
                pass
            return
        name = (name or '').strip()
        if not name:
            try:
                popup.dismiss()
            except Exception:
                pass
            return
        # Avoid duplicate exact names (case-insensitive)
        try:
            row = DB.execute("SELECT id FROM players WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
            if row:
                try:
                    Popup(title="Duplicate name",
                          content=Label(text="A player with this exact name already exists.", color=(0,0,0,1)),
                          size_hint=(0.85, 0.35)).open()
                except Exception:
                    pass
                return
        except Exception:
            pass
        # Compute initial nickname and insert
        nick = _compute_unique_nickname(name)
        DB.execute("INSERT INTO players (name, nickname) VALUES (?, ?)", (name, nick))
        DB.commit()
        # Recompute all nicknames to avoid new collisions
        _rebuild_all_nicknames()
        # Manager: upload DB after write
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("new_player_popup")
        except Exception:
            pass
        try:
            popup.dismiss()
        except Exception:
            pass
        # Clear the Players filter so the new player is visible in full list
        try:
            self.ids.filter_input.text = ""
        except Exception:
            pass
        self.refresh()

    def _add_player_row(self, pid, name):
        row = BoxLayout(size_hint_y=None, height=dp(56))
        # Show full name only on Players main list
        lbl = Label(text=f"{name}", color=(1,1,1,1))
        btn_del = Button(text="Delete", size_hint_x=None, width=dp(200))
        try:
            btn_del.text_size = (None, None)
            btn_del.shorten = True
            btn_del.font_size = '18sp'
        except Exception:
            pass
        # Disable delete for guests
        try:
            btn_del.disabled = not _is_manager()
            btn_del.opacity = 1 if _is_manager() else 0.5
        except Exception:
            pass
        btn_del.bind(on_release=lambda inst, _pid=pid, _name=name: self.delete_player(_pid, _name))
        row.add_widget(lbl)
        row.add_widget(btn_del)
        self.ids.players_list.add_widget(row)

    def refresh(self):
        grid = self.ids.players_list
        grid.clear_widgets()
        cur = DB.execute("SELECT id, name FROM players ORDER BY name")
        for pid, name in cur.fetchall():
            self._add_player_row(pid, name)

    def filter_players(self, text):
        grid = self.ids.players_list
        grid.clear_widgets()
        q = "%" + (text or "") + "%"
        cur = DB.execute("SELECT id, name FROM players WHERE name LIKE ? ORDER BY name", (q,))
        for pid, name in cur.fetchall():
            self._add_player_row(pid, name)

    def delete_player(self, pid, name):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot delete players')
            except Exception:
                pass
            return
        # deny delete if player is in any active event
        row = DB.execute("SELECT COUNT(*) FROM events e JOIN event_players ep ON e.id=ep.event_id WHERE e.status='active' AND ep.player_id=?", (pid,)).fetchone()
        if row and row[0] > 0:
            try:
                Popup(title="Cannot delete",
                      content=Label(text="Player is part of an active event.\nClose the event first.", color=(0,0,0,1)),
                      size_hint=(0.8, 0.4)).open()
            except Exception:
                pass
            return
        # preserve historical names in past events
        try:
            DB.execute("UPDATE event_players SET guest_name = COALESCE(guest_name, ?) WHERE player_id=?", (name, pid))
        except Exception:
            pass
        DB.execute("DELETE FROM players WHERE id=?", (pid,))
        DB.commit()
        # Manager: upload DB after delete
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("delete_player")
        except Exception:
            pass
        self.refresh()


class NewPlayerScreen(Screen):
    def save_player(self, name):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot add players')
            except Exception:
                pass
            return
        if not name or not name.strip():
            return
        fullname = name.strip()
        # Avoid duplicate exact names (case-insensitive)
        try:
            row = DB.execute("SELECT id FROM players WHERE LOWER(name) = LOWER(?)", (fullname,)).fetchone()
            if row:
                try:
                    Popup(title="Duplicate name",
                          content=Label(text="A player with this exact name already exists.", color=(0,0,0,1)),
                          size_hint=(0.85, 0.35)).open()
                except Exception:
                    pass
                return
        except Exception:
            pass
        nick = _compute_unique_nickname(fullname)
        DB.execute("INSERT INTO players (name, nickname) VALUES (?, ?)", (fullname, nick))
        DB.commit()
        _rebuild_all_nicknames()
        # Manager: upload DB after write
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("new_player_screen")
        except Exception:
            pass
        # Navigate back to Players and clear the filter so the new player is visible
        try:
            players = self.manager.get_screen("players")
            players.ids.filter_input.text = ""
            players.refresh()
        except Exception:
            pass
        self.manager.current = "players"
        try:
            App.get_running_app().show_toast("Player saved", timeout=1.8)
        except Exception:
            pass


class CreateEventDetailsScreen(Screen):
    def next_to_players(self, name, etype, rounds, round_time):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot create events')
            except Exception:
                pass
            return
        # sanitize and store on CreateEventScreen
        name = (name or '').strip() or f"Event {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        etype = (etype or 'draft').strip() or 'draft'
        r = int(rounds) if rounds and str(rounds).isdigit() else 3
        rt_mins = int(round_time) if round_time and str(round_time).isdigit() else 30
        rt = rt_mins * 60
        try:
            create = self.manager.get_screen("createevent")
            create._event_name = name
            create._event_type = etype
            create._rounds = r
            create._round_time = rt
        except Exception:
            pass
        # Go to players selection page
        try:
            self.manager.current = "createevent"
        except Exception:
            pass


class CreateEventScreen(Screen):
    seating = ListProperty([])  # deprecated for seating preview
    guest_list = ListProperty([])  # list of (None, guest_name)
    def on_enter(self):
        # reset lists and refresh UI
        self.guest_list = []
        self.selected_ids = set()
        # clear filter if present
        try:
            self.ids.filter_input.text = ""
        except Exception:
            pass
        self.refresh_players()
        self.update_selected_view()

    def refresh_players(self):
        # Rebuild the selectable players list, applying filter and excluding already selected players
        sel = self.ids.players_select
        sel.clear_widgets()
        try:
            filt = (self.ids.filter_input.text or "").strip().lower()
        except Exception:
            filt = ""
        if not hasattr(self, 'selected_ids'):
            self.selected_ids = set()
        cur = DB.execute("SELECT id, COALESCE(nickname, name) as dname, name FROM players ORDER BY name")
        rows = cur.fetchall()
        for pid, disp_name, full_name in rows:
            # Skip players already added to the event (they will appear in the Selected list)
            if pid in self.selected_ids:
                continue
            hay = f"{disp_name} {full_name}".lower()
            if filt and filt not in hay:
                continue
            row = BoxLayout(size_hint_y=None, height=dp(56))
            lbl = Label(text=disp_name)
            # Make label flexible and centered; button has fixed width (prevents clipping)
            try:
                lbl.size_hint_x = 1
                lbl.halign = 'center'
                lbl.valign = 'middle'
                lbl.shorten = True
                # Centering requires text_size to match width
                lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
            except Exception:
                pass
            def add_player(instance, _pid=pid):
                self.selected_ids.add(_pid)
                # Rebuild lists so the player disappears here and appears in Selected
                self.refresh_players()
                self.update_selected_view()
            btn = Button(text="Add")
            try:
                btn.size_hint_x = None
                btn.width = dp(80)
                btn.text_size = (None, None)
                btn.shorten = True
                btn.font_size = '18sp'
            except Exception:
                pass
            btn.bind(on_release=add_player)
            row.add_widget(lbl)
            row.add_widget(btn)
            sel.add_widget(row)
        # Update the selected list preview
        self.update_selected_view()

    def filter_players(self, text):
        # Rebuild list based on filter text
        self.refresh_players()

    def update_selected_view(self):
        # Populate the selected players/guests list
        cont = self.ids.get('selected_list')
        if not cont:
            return
        cont.clear_widgets()
        # Players (selected_ids)
        if hasattr(self, 'selected_ids') and self.selected_ids:
            for pid in sorted(self.selected_ids, key=lambda x: x):
                try:
                    name = DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (pid,)).fetchone()
                    name = name[0] if name else f"Player {pid}"
                except Exception:
                    name = f"Player {pid}"
                row = BoxLayout(size_hint_y=None, height=dp(56))
                row.add_widget(Label(text=f"• {name}"))
                btn = Button(text="X", size_hint_x=None, width=dp(56), font_size='22sp')
                def remove_player(instance, pid_to_remove=pid):
                    if hasattr(self, 'selected_ids') and pid_to_remove in self.selected_ids:
                        self.selected_ids.remove(pid_to_remove)
                    # rebuild lists to reflect change
                    self.refresh_players()
                    self.update_selected_view()
                btn.bind(on_release=remove_player)
                row.add_widget(btn)
                cont.add_widget(row)
        # Guests (keep index for precise removal)
        for idx, (pid, gname) in enumerate(list(self.guest_list)):
            if pid is None:
                row = BoxLayout(size_hint_y=None, height=dp(56))
                row.add_widget(Label(text=f"• {gname} (guest)"))
                gbtn = Button(text="X", size_hint_x=None, width=dp(56), font_size='22sp')
                def remove_guest(instance, guest_index=idx):
                    try:
                        if 0 <= guest_index < len(self.guest_list):
                            self.guest_list.pop(guest_index)
                    except Exception:
                        pass
                    self.refresh_players()
                    self.update_selected_view()
                gbtn.bind(on_release=remove_guest)
                row.add_widget(gbtn)
                cont.add_widget(row)

    def add_guest(self, guest_name):
        if not guest_name:
            return
        # append to guest_list as guest record with player_id None
        name = guest_name.strip()
        if not name:
            return
        self.guest_list.append((None, name))
        self.ids.guest_name.text = ""
        # update selected preview
        self.update_selected_view()

    def randomize_seating(self):
        # collect selected players and guests only (use selected_ids, not UI state)
        chosen = []
        if not hasattr(self, 'selected_ids'):
            self.selected_ids = set()
        for pid in self.selected_ids:
            try:
                row = DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (pid,)).fetchone()
                if row:
                    chosen.append((pid, row[0]))
            except Exception:
                pass
        # plus any guests explicitly added
        chosen.extend(self.guest_list)
        if len(chosen) < 2:
            return
        random.shuffle(chosen)
        self.seating = chosen
        # write seating preview into the selected_list area for quick check
        cont = self.ids.get('seating_list') or self.ids.get('players_select')
        if cont is None:
            return
        try:
            cont.clear_widgets()
        except Exception:
            pass
        for idx, (pid, name) in enumerate(self.seating, start=1):
            display = f"{idx}. {name} (guest)" if pid is None else f"{idx}. {name}"
            try:
                cont.add_widget(Label(text=display, size_hint_y=None, height=28))
            except Exception:
                pass

    def start_event(self):
        # collect selected players and guests, then navigate to SeatingScreen
        chosen = []
        # Build from selected_ids to avoid dependence on filter/UI list
        if not hasattr(self, 'selected_ids'):
            self.selected_ids = set()
        for pid in self.selected_ids:
            row = DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (pid,)).fetchone()
            if row:
                chosen.append((pid, row[0]))
        # plus any guests explicitly added
        chosen.extend(self.guest_list)
        if len(chosen) < 2:
            return
        # Retrieve stored event details (set by CreateEventDetailsScreen)
        name = getattr(self, '_event_name', f"Event {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        etype = getattr(self, '_event_type', 'draft')
        r = int(getattr(self, '_rounds', 3) or 3)
        rt = int(getattr(self, '_round_time', 30*60) or 30*60)
        # Let seating screen handle event creation and round 1
        seat_screen = self.manager.get_screen("seating")
        seat_screen.set_data(chosen, name, etype, r, rt)
        self.manager.current = "seating"


class EventsListScreen(Screen):
    def on_enter(self):
        self.refresh()

    def refresh(self):
        grid = self.ids.events_grid
        grid.clear_widgets()
        cur = DB.execute("SELECT id, name, type, status FROM events ORDER BY (status='active') DESC, created_at DESC")
        for eid, name, etype, status in cur.fetchall():
            btn = Button(text=f"{name} [{etype}] ({status})", size_hint_y=None, height=dp(68))
            def open_event(inst, _eid=eid, _status=status):
                if _status == 'closed':
                    self.manager.get_screen('standings').show_for_event(_eid)
                    self.manager.current = 'standings'
                else:
                    try:
                        cur_round = DB.execute("SELECT current_round FROM events WHERE id=?", (_eid,)).fetchone()
                        cur_round = int(cur_round[0]) if cur_round and cur_round[0] is not None else 0
                    except Exception:
                        cur_round = 0
                    if cur_round == 0:
                        seat = self.manager.get_screen('seating')
                        seat.load_existing_event(_eid)
                        self.manager.current = 'seating'
                    else:
                        self.manager.get_screen('event').load_event(_eid)
                        self.manager.current = 'event'
            btn.bind(on_release=open_event)
            grid.add_widget(btn)


class EventScreen(Screen):
    event_id = NumericProperty(0)
    event_title = StringProperty("Event")
    current_round = NumericProperty(0)
    timer_text = StringProperty("00:00")
    round_duration = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.timer_event = None
        self.time_left = 0
        self._timer_round = 0
        self._end_sound_played = False
        self.view_round = None  # if set, we are viewing a past (or specific) round without changing state
        # load sounds: only tick for countdown and rooster at end (no random pool)
        try:
            self.tick_sound = SoundLoader.load("assets/tick.wav")
        except Exception:
            self.tick_sound = None
        try:
            self.end_sound = SoundLoader.load("assets/rooster.mp3")
        except Exception:
            self.end_sound = None

    def load_event(self, event_id):
        self.event_id = event_id
        # Reset viewing override on explicit load
        self.view_round = None
        row = DB.execute("SELECT name, rounds, current_round, status FROM events WHERE id=?", (event_id,)).fetchone()
        if not row:
            return
        name, rounds, current_round, status = row
        self.event_title = name
        self.current_round = current_round
        # fetch round duration
        try:
            rt = DB.execute("SELECT round_time FROM events WHERE id= ?", (event_id,)).fetchone()
            self.round_duration = int(rt[0]) if rt and rt[0] is not None else 0
        except Exception:
            self.round_duration = 0
        self.ids.matches_grid.clear_widgets()
        self.refresh_matches()

    def refresh_matches(self):
        self.ids.matches_grid.clear_widgets()
        # Determine which round to display: a specific view_round or the current round (defaulting to 1)
        round_to_show = None
        try:
            round_to_show = int(self.view_round) if getattr(self, 'view_round', None) else None
        except Exception:
            round_to_show = None
        if not round_to_show:
            round_to_show = self.current_round if self.current_round > 0 else 1
        cur = DB.execute("SELECT id, round, player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=? AND round=?",
                        (self.event_id, round_to_show))
        rows = cur.fetchall()
        if not rows and self.current_round == 0 and round_to_show == 1:
            # initialize first round view if needed
            self.current_round = 1
            DB.execute("UPDATE events SET current_round=? WHERE id=?", (1, self.event_id))
            DB.commit()
            rows = DB.execute("SELECT id, round, player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=? AND round=?", (self.event_id,1)).fetchall()
        for idx, (mid, rnd, p1, p2, s1, s2, bye) in enumerate(rows):
            p1name = get_name_for_event_player(self.event_id, p1)
            p2name = get_name_for_event_player(self.event_id, p2) if p2 else "BYE"
            row_widget = MatchRow()
            row_widget.p1_name = p1name
            row_widget.p2_name = p2name
            row_widget.score1 = s1
            row_widget.score2 = s2
            row_widget.match_id = mid
            row_widget.bye = bye
            row_widget.row_index = idx
            row_widget.on_score_change = lambda w, _self=self: _self._on_match_score_changed(w)
            self.ids.matches_grid.add_widget(row_widget)
        # update round label (mark if viewing a past round)
        label = f"Round: {round_to_show}"
        try:
            if int(round_to_show) != int(self.current_round):
                label += " (viewing)"
        except Exception:
            pass
        self.ids.round_label.text = label
        # update next button label depending on last round (based on actual current round)
        e = DB.execute("SELECT rounds FROM events WHERE id=?", (self.event_id,)).fetchone()
        if e:
            total_rounds = e[0]
            if self.current_round >= total_rounds:
                self.ids.next_btn.text = "Finish Event"
            else:
                self.ids.next_btn.text = "Next Round"
        # start or reset the round timer only if we are showing the actual current round
        if getattr(self, 'view_round', None) is None or int(round_to_show) == int(self.current_round):
            self.maybe_start_timer()
        else:
            # Stop timer display when viewing past round
            self.stop_timer()
            self.timer_text = "--:--"

    def _format_time(self, secs):
        try:
            s = int(secs)
        except Exception:
            s = 0
        sign = "-" if s < 0 else ""
        s = abs(s)
        m = s // 60
        ss = s % 60
        return f"{sign}{m:02d}:{ss:02d}"

    def stop_timer(self):
        if self.timer_event:
            try:
                self.timer_event.cancel()
            except Exception:
                pass
            self.timer_event = None

    def maybe_start_timer(self):
        # Ensure we have the round duration
        if not self.round_duration:
            try:
                rt = DB.execute("SELECT round_time FROM events WHERE id=?", (self.event_id,)).fetchone()
                self.round_duration = int(rt[0]) if rt and rt[0] is not None else 0
            except Exception:
                self.round_duration = 0
        if self.current_round <= 0:
            return
        # read or initialize round_start_ts
        try:
            row = DB.execute("SELECT round_start_ts FROM events WHERE id=?", (self.event_id,)).fetchone()
            ts = int(row[0]) if row and row[0] is not None else 0
        except Exception:
            ts = 0
        now_ts = int(time.time())
        if ts <= 0:
            # initialize start timestamp for this round
            try:
                DB.execute("UPDATE events SET round_start_ts=? WHERE id=?", (now_ts, self.event_id))
                DB.commit()
            except Exception:
                pass
            ts = now_ts
        # compute remaining
        remaining = int(self.round_duration or 0) - (now_ts - ts)
        if remaining <= -10:
            # already expired; clamp and do not start scheduling
            self.stop_timer()
            self.time_left = -10
            self.timer_text = self._format_time(self.time_left)
            self._timer_round = int(self.current_round)
            self._end_sound_played = True
            return
        # schedule/update only if new round or timer not running
        if self._timer_round != self.current_round or self.timer_event is None:
            self.stop_timer()
            self.time_left = remaining
            self.timer_text = self._format_time(self.time_left)
            self._timer_round = int(self.current_round)
            # end sound not yet played if we are above 0
            self._end_sound_played = self.time_left <= 0
            self.timer_event = Clock.schedule_interval(self._tick, 1)

    def _tick(self, dt):
        # Tick sound for last five seconds (5..1)
        if 1 <= self.time_left <= 5 and getattr(self, 'tick_sound', None):
            try:
                self.tick_sound.play()
            except Exception:
                pass
        # Decrement
        self.time_left -= 1
        # Play end sound at 0 exactly
        if self.time_left == 0 and not self._end_sound_played:
            try:
                snd = getattr(self, 'end_sound', None)
                if snd:
                    snd.play()
            except Exception:
                pass
            self._end_sound_played = True
        # Stop at -10
        if self.time_left <= -10:
            self.timer_text = self._format_time(-10)
            self.stop_timer()
            return
        # Update label
        self.timer_text = self._format_time(self.time_left)

    def _display_round(self):
        try:
            return int(self.view_round) if getattr(self, 'view_round', None) else int(self.current_round or 1)
        except Exception:
            return int(self.current_round or 1)

    def show_round(self, round_number: int):
        # Show a specific round without changing event state
        try:
            rn = int(round_number)
        except Exception:
            rn = self.current_round or 1
        if rn < 1:
            rn = 1
        self.view_round = rn
        self.refresh_matches()

    def prev_round_view(self):
        # Guests cannot navigate rounds
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot change round view')
            except Exception:
                pass
            return
        # Navigate to previous round view or to seating if at round 1
        r = self._display_round()
        if r <= 1:
            # Go to seating screen for this event
            try:
                seat = self.manager.get_screen('seating')
                seat.load_existing_event(self.event_id)
                self.manager.current = 'seating'
            except Exception:
                # Fallback: just ignore
                pass
            return
        self.view_round = r - 1
        self.refresh_matches()

    def _on_match_score_changed(self, row_widget: 'MatchRow'):
        # Called after a score changes. If editing a past or closed event, purge future rounds and reactivate.
        try:
            edited_round = self._display_round()
        except Exception:
            edited_round = self.current_round or 1
        # Read event status and current_round
        ev = DB.execute("SELECT status, current_round FROM events WHERE id=?", (self.event_id,)).fetchone()
        if not ev:
            return
        status, cur_round = ev
        # If we edited a previous round or the event was closed, we must drop subsequent rounds and reactivate
        need_reopen = (status == 'closed') or (edited_round < (cur_round or 0))
        if need_reopen:
            # Delete matches for rounds greater than edited_round
            DB.execute("DELETE FROM matches WHERE event_id=? AND round>?", (self.event_id, edited_round))
            now_ts = int(time.time())
            DB.execute("UPDATE events SET status='active', current_round=?, round_start_ts=? WHERE id=?", (edited_round, now_ts, self.event_id))
            DB.commit()
            # Manager: upload DB after reopening/editing past round
            try:
                app = App.get_running_app()
                if app:
                    app._maybe_upload_after_write("edit_past_round")
            except Exception:
                pass
            self.current_round = edited_round
            self.view_round = None
            # Notify user briefly
            try:
                App.get_running_app().show_toast("Updated past round. Future rounds cleared and event re-opened.")
            except Exception:
                pass
            self.refresh_matches()
        else:
            # If editing the current round while viewing it, nothing else to do
            pass

    def next_round(self):
        """Advance the event to the next round or close if finished.

        Computes Swiss-ish pairings using pairing.compute_next_round_pairings,
        inserts matches for the next round, updates round_start_ts, and
        triggers a background upload (for managers). Guests cannot advance.
        """
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot advance rounds')
            except Exception:
                pass
            return
        # Ensure current matches saved (they are updated live on clicks)
        # Compute next pairings and insert matches for round+1 or finish
        e = DB.execute("SELECT rounds, current_round FROM events WHERE id=?", (self.event_id,)).fetchone()
        if not e:
            return
        total_rounds, cur_round = e
        # if cur_round >= total_rounds then closing
        if cur_round >= total_rounds:
            self.close_event(abort_current_round=False)
            return
        next_round = cur_round + 1
        # compute pairings for next_round
        pairings = compute_next_round_pairings(self.event_id)
        # insert into matches
        for p1, p2, is_bye in pairings:
            sc1 = 2 if is_bye else 0
            DB.execute("INSERT INTO matches (event_id, round, player1, player2, score_p1, score_p2, bye) VALUES (?, ?, ?, ?, ?, 0, ?)",
                       (self.event_id, next_round, p1, p2, sc1, 1 if is_bye else 0))
        now_ts = int(time.time())
        DB.execute("UPDATE events SET current_round=?, round_start_ts=? WHERE id=?", (next_round, now_ts, self.event_id))
        DB.commit()
        # Manager: upload DB after advancing to next round
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("next_round")
        except Exception:
            pass
        self.current_round = next_round
        self.refresh_matches()

    def close_event(self, abort_current_round=True):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot close events')
            except Exception:
                pass
            return
        # stop timer when closing event
        try:
            self.stop_timer()
        except Exception:
            pass
        # If abort_current_round is True, discard matches from the current (in-progress) round
        if abort_current_round:
            row = DB.execute("SELECT current_round FROM events WHERE id=?", (self.event_id,)).fetchone()
            if row:
                cur = int(row[0] or 0)
                if cur > 0:
                    # delete current round matches so standings only include completed previous rounds
                    DB.execute("DELETE FROM matches WHERE event_id=? AND round=?", (self.event_id, cur))
                    # decrement stored current_round for consistency, though event is closing
                    DB.execute("UPDATE events SET current_round=? WHERE id=?", (cur - 1, self.event_id))
        DB.execute("UPDATE events SET status='closed' WHERE id=?", (self.event_id,))
        DB.commit()
        # Manager: upload DB after closing event
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("close_event")
        except Exception:
            pass
        # show final standings when closing
        self.manager.get_screen("standings").show_for_event(self.event_id)
        self.manager.current = "standings"


class SeatingScreen(Screen):
    selected = ListProperty([])
    seating = ListProperty([])
    event_name = StringProperty("")
    event_type = StringProperty("draft")
    rounds = NumericProperty(3)
    round_time = NumericProperty(1800)
    event_id = NumericProperty(0)

    def set_data(self, selected_list, name, etype, rounds, round_time):
        # selected_list as list of tuples (player_id or None, display_name)
        self.selected = selected_list[:]
        self.event_name = name or f"Event {datetime.now().strftime('%Y%m%d_%H%M')}"
        self.event_type = etype
        try:
            self.rounds = int(rounds)
        except Exception:
            self.rounds = 3
        try:
            self.round_time = int(round_time)
        except Exception:
            self.round_time = 1800
        # reset any previous pending event context
        self.event_id = 0
        # show an initial random seating and persist the event immediately
        self.randomize()
        self._create_event_if_needed()

    def randomize(self):
        if len(self.selected) < 2:
            return
        self.seating = self.selected[:]
        random.shuffle(self.seating)
        cont = self.ids.seating_list
        cont.clear_widgets()
        for idx, (pid, name) in enumerate(self.seating, start=1):
            lbl = Label(text=f"{idx}. {name}" + (" (guest)" if pid is None else ""), size_hint_y=None, height=28, color=(1,1,1,1))
            cont.add_widget(lbl)
        # If an event is already created and still before Round 1, persist new seating order
        try:
            if getattr(self, 'event_id', 0) and DB.execute("SELECT current_round FROM events WHERE id=?", (self.event_id,)).fetchone()[0] == 0:
                for idx, (pid, name) in enumerate(self.seating):
                    if pid is None:
                        DB.execute("UPDATE event_players SET seating_pos=? WHERE event_id=? AND player_id IS NULL AND guest_name=?",
                                   (idx, self.event_id, name))
                    else:
                        DB.execute("UPDATE event_players SET seating_pos=? WHERE event_id=? AND player_id=?",
                                   (idx, self.event_id, pid))
                DB.commit()
                # Manager: upload DB after seating randomize
                try:
                    app = App.get_running_app()
                    if app:
                        app._maybe_upload_after_write("seating_randomize")
                except Exception:
                    pass
        except Exception:
            pass

    def _create_event_if_needed(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot create events')
            except Exception:
                pass
            return
        if getattr(self, 'event_id', 0):
            return
        # Create the event row and event_players from current seating
        cur = DB.cursor()
        cur.execute("INSERT INTO events (name, type, rounds, round_time, status, current_round) VALUES (?, ?, ?, ?, ?, ?)",
                    (self.event_name, self.event_type, int(self.rounds), int(self.round_time), "active", 0))
        self.event_id = cur.lastrowid
        for idx, (pid, name) in enumerate(self.seating):
            if pid is None:
                cur.execute("INSERT INTO event_players (event_id, player_id, guest_name, seating_pos) VALUES (?, ?, ?, ?)",
                            (self.event_id, None, name, idx))
            else:
                cur.execute("INSERT INTO event_players (event_id, player_id, guest_name, seating_pos) VALUES (?, ?, ?, ?)",
                            (self.event_id, pid, None, idx))
        DB.commit()
        # Manager: upload DB after event creation
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("event_created")
        except Exception:
            pass

    def load_existing_event(self, event_id):
        # Load an existing not-started event into the seating screen
        self.event_id = int(event_id)
        row = DB.execute("SELECT name, type, rounds, round_time, current_round FROM events WHERE id=?", (self.event_id,)).fetchone()
        if not row:
            return
        name, etype, rounds, rtime, cur_round = row
        self.event_name = name
        self.event_type = etype
        self.rounds = int(rounds or 3)
        self.round_time = int(rtime or 1800)
        # Load seating by seating_pos
        people = DB.execute("SELECT player_id, guest_name FROM event_players WHERE event_id=? ORDER BY seating_pos ASC", (self.event_id,)).fetchall()
        self.selected = []
        self.seating = []
        for pid, gname in people:
            if pid is None:
                self.selected.append((None, gname))
                self.seating.append((None, gname))
            else:
                pname = DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (pid,)).fetchone()
                pname = pname[0] if pname else f"Player {pid}"
                self.selected.append((pid, pname))
                self.seating.append((pid, pname))
        # Render list
        cont = self.ids.seating_list
        cont.clear_widgets()
        for idx, (pid, name) in enumerate(self.seating, start=1):
            cont.add_widget(Label(text=f"{idx}. {name}" + (" (guest)" if pid is None else ""), size_hint_y=None, height=28, color=(1,1,1,1)))

    def confirm_and_begin(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot start events')
            except Exception:
                pass
            return
        # If event already exists (created when arriving to seating), handle per current state
        if getattr(self, 'event_id', 0):
            # Read event state
            status, cur_round = 'active', 0
            try:
                row = DB.execute("SELECT status, current_round FROM events WHERE id=?", (self.event_id,)).fetchone()
                if row:
                    status = row[0]
                    cur_round = int(row[1] or 0)
            except Exception:
                pass
            # Check if Round 1 already exists
            round1_exists = False
            try:
                r = DB.execute("SELECT COUNT(*) FROM matches WHERE event_id=? AND round=1", (self.event_id,)).fetchone()
                round1_exists = bool(r and int(r[0]) > 0)
            except Exception:
                pass
            # If user presses Begin Round 1 while event is in round 2+ or closed, revert to Round 1
            if status == 'closed' or cur_round > 1:
                if not round1_exists:
                    # No Round 1 yet: generate it
                    generate_round_one(self.event_id)
                else:
                    # Keep Round 1 results, wipe subsequent rounds and reactivate at Round 1
                    try:
                        DB.execute("DELETE FROM matches WHERE event_id=? AND round>1", (self.event_id,))
                        now_ts = int(time.time())
                        DB.execute("UPDATE events SET status='active', current_round=1, round_start_ts=? WHERE id=?", (now_ts, self.event_id))
                        DB.commit()
                    except Exception:
                        pass
                # Manager: upload DB after preparing Round 1/reset
                try:
                    app = App.get_running_app()
                    if app:
                        app._maybe_upload_after_write("begin_round1_prepare")
                except Exception:
                    pass
                ev = self.manager.get_screen("event")
                ev.load_event(self.event_id)
                # Ensure round 1 is shown (view override does not change state)
                try:
                    ev.show_round(1)
                except Exception:
                    pass
                self.manager.current = "event"
                return
            # Else: event not started or already at Round 1
            if round1_exists:
                # Avoid duplicating Round 1; just go to the event
                self.manager.get_screen("event").load_event(self.event_id)
                self.manager.current = "event"
                return
            # Generate Round 1 for a fresh event
            generate_round_one(self.event_id)
            # Manager: upload DB after creating Round 1
            try:
                app = App.get_running_app()
                if app:
                    app._maybe_upload_after_write("begin_round1")
            except Exception:
                pass
            self.manager.get_screen("event").load_event(self.event_id)
            self.manager.current = "event"
            return
        # Fallback: create event now (should be rare)
        self._create_event_if_needed()
        generate_round_one(self.event_id)
        # Manager: upload DB after creating Round 1 (fallback)
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("begin_round1_fallback")
        except Exception:
            pass
        self.manager.get_screen("event").load_event(self.event_id)
        self.manager.current = "event"

    def close_event_reset(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot close events')
            except Exception:
                pass
            return
        # Close the event from seating: wipe all match results and set all players to 0 points, then mark closed
        if not getattr(self, 'event_id', 0):
            return
        try:
            # Remove all matches to guarantee standings show 0 points for everyone
            DB.execute("DELETE FROM matches WHERE event_id=?", (self.event_id,))
            # Mark event closed and reset round counters
            DB.execute("UPDATE events SET status='closed', current_round=0 WHERE id=?", (self.event_id,))
            DB.commit()
            # Manager: upload DB after closing event from seating
            try:
                app = App.get_running_app()
                if app:
                    app._maybe_upload_after_write("close_event_from_seating")
            except Exception:
                pass
            try:
                App.get_running_app().show_toast("Event closed. All results cleared.")
            except Exception:
                pass
        except Exception:
            pass
        # Navigate to standings (will show all players with 0 points)
        try:
            self.manager.get_screen('standings').show_for_event(self.event_id)
            self.manager.current = 'standings'
        except Exception:
            pass


class StandingsScreen(Screen):
    event_id = NumericProperty(0)

    def show_for_event(self, event_id):
        self.event_id = event_id
        row = DB.execute("SELECT name FROM events WHERE id=?", (event_id,)).fetchone()
        title = row[0] if row else "Standings"
        self.ids.standings_title.text = f"{title} — Final Standings"
        self.refresh()

    def back_to_last_round(self):
        # Go back to the last round page from standings
        # Determine last round that has matches
        row = DB.execute("SELECT MAX(round) FROM matches WHERE event_id=?", (self.event_id,)).fetchone()
        last_round = int(row[0]) if row and row[0] is not None else 0
        if last_round <= 0:
            # If no rounds, go to seating (first round seating)
            try:
                seat = self.manager.get_screen('seating')
                seat.load_existing_event(self.event_id)
                self.manager.current = 'seating'
            except Exception:
                pass
            return
        # Load event screen and show last round without altering state
        ev = self.manager.get_screen('event')
        ev.load_event(self.event_id)
        ev.show_round(last_round)
        self.manager.current = 'event'

    def refresh(self):
        grid = self.ids.standings_grid
        grid.clear_widgets()
        standings = compute_standings(self.event_id)
        # Define column size hints (sum doesn't have to be 1 for GridLayout)
        # Tighten MP and W-L-D a bit to free room for percentage headers
        col_sizes = [0.6, 3.0, 0.6, 1.0, 1.1, 1.1, 1.1]

        def add_cell(text, bold=False, halign='center', size_hint_x=1.0):
            lbl = Label(text=(f"[b]{text}[/b]" if bold else text),
                        markup=True,
                        size_hint_y=None,
                        height=dp(42),
                        color=(1,1,1,1),
                        halign=halign,
                        valign='middle')
            # Ensure halign takes effect
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            lbl.size_hint_x = size_hint_x
            grid.add_widget(lbl)

        # Header row (7 columns)
        headers = ['#', 'Name', 'MP', 'W-L-D', 'OMW%', 'GW%', 'OGW%']
        for i, h in enumerate(headers):
            add_cell(h, bold=True, halign=('left' if h == 'Name' else 'center'), size_hint_x=col_sizes[i])

        # Data rows
        from kivy.uix.scrollview import ScrollView
        for rank, st in enumerate(standings, start=1):
            name = st['name']
            mp = st['mp']
            w = st['wins']
            l = st['losses']
            d = st['draws']
            omwp = f"{st['omwp']:.2f}"
            gwp = f"{st['gwp']:.2f}"
            ogwp = f"{st['ogwp']:.2f}"

            row_values = [str(rank), name, str(mp), f"{w}-{l}-{d}", omwp, gwp, ogwp]
            for i, val in enumerate(row_values):
                if i == 1:
                    # Name column: make it horizontally scrollable if too long
                    sv = ScrollView(size_hint_y=None,
                                    height=dp(42),
                                    do_scroll_x=True,
                                    do_scroll_y=False,
                                    bar_width=0)
                    # Hard-disable any vertical scrolling/bounce on some devices
                    sv.effect_y = None
                    sv.scroll_wheel_distance = 0
                    sv.scroll_y = 1
                    sv.size_hint_x = col_sizes[i]
                    name_lbl = Label(text=val,
                                     markup=True,
                                     size_hint_y=None,
                                     height=dp(42),
                                     color=(1,1,1,1),
                                     halign='left',
                                     valign='middle',
                                     size_hint_x=None)
                    # Do not wrap; size to texture for horizontal scrolling
                    name_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'width', val[0] + dp(4)))
                    # Align text vertically
                    name_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (None, None)))
                    sv.add_widget(name_lbl)
                    grid.add_widget(sv)
                else:
                    hal = 'center'
                    add_cell(val, bold=False, halign=hal, size_hint_x=col_sizes[i])


class LeagueScreen(Screen):
    current_league_id = NumericProperty(0)

    def on_kv_post(self, base_widget):
        # Ensure leagues table exists, then load UI (do not auto-create an active league)
        try:
            from db import DB
            DB.execute("""
                CREATE TABLE IF NOT EXISTS leagues (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  start_ts INTEGER NOT NULL,
                  end_ts INTEGER
                )
            """)
            DB.commit()
        except Exception:
            pass
        # Load leagues and scoreboard
        self._load_leagues()
        self.refresh()

    def on_enter(self):
        # Refresh when entering
        self._load_leagues()
        self.refresh()

    def _load_leagues(self):
        try:
            from db import DB
            cur = DB.execute("SELECT id, name, start_ts, end_ts FROM leagues ORDER BY start_ts DESC")
            leagues = cur.fetchall()
            # Populate spinner
            sp = self.ids.get('league_spinner')
            if sp is not None:
                items = []
                self._league_map = {}
                for lid, name, s, e in leagues:
                    label = self._format_league_label(lid, name, s, e)
                    items.append(label)
                    self._league_map[label] = lid
                sp.values = items
                # Preserve selection if possible
                desired_id = int(self.current_league_id or 0)
                if desired_id and any(lid == desired_id for lid, *_ in leagues):
                    # Set spinner text to the matching label
                    for lid, name, s, e in leagues:
                        if lid == desired_id:
                            sp.text = self._format_league_label(lid, name, s, e)
                            break
                else:
                    # Default: choose active if any, else most recent
                    active = next((lid for lid, _, _, e in leagues if e is None), None)
                    if active is not None:
                        for lid, name, s, e in leagues:
                            if lid == active:
                                sp.text = self._format_league_label(lid, name, s, e)
                                self.current_league_id = active
                                break
                    elif leagues:
                        lid, name, s, e = leagues[0]
                        sp.text = self._format_league_label(lid, name, s, e)
                        self.current_league_id = lid
            # Update action button according to current selection
            self._update_action_button()
        except Exception:
            pass

    def _format_league_label(self, lid, name, start_ts, end_ts):
        def fmt(ts):
            try:
                return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')
            except Exception:
                return '?'
        if end_ts is None:
            if name:
                return f"Current: {name} (since {fmt(start_ts)})"
            return f"Current (since {fmt(start_ts)})"
        else:
            base = f"{fmt(start_ts)} to {fmt(end_ts)}"
            if name:
                base += f" — {name}"
            return base

    def on_league_selected(self, spinner_text):
        # Map spinner text back to league id
        lid = getattr(self, '_league_map', {}).get(spinner_text)
        if lid:
            self.current_league_id = lid
            self._update_action_button()
            self.refresh()

    def primary_action(self):
        """Main button depends on whether any active league exists, regardless of selection."""
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot manage leagues')
            except Exception:
                pass
            return
        try:
            from db import DB
            # Check if there is any active league (end_ts IS NULL)
            row = DB.execute("SELECT id FROM leagues WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                # There is an active league -> close confirmation
                self.confirm_close_league()
            else:
                # No active league -> prompt to start a new one
                self.prompt_new_league()
        except Exception:
            # Safe fallback: try starting a new league
            self.prompt_new_league()

    def confirm_close_league(self):
        # Show confirmation popup before closing current league
        try:
            box = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(6))
            msg = Label(text="Close the current league?", size_hint_y=None, height=dp(24), halign='center', valign='middle')
            msg.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            box.add_widget(msg)
            btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
            popup = Popup(title="Confirm", title_size=dp(18), content=box, size_hint=(0.9, None), height=dp(140), auto_dismiss=False)
            def do_yes(instance):
                popup.dismiss()
                self.close_current_league()
            def do_cancel(instance):
                popup.dismiss()
            yes = Button(text="Yes", on_release=do_yes, size_hint_y=None, height=dp(40))
            no = Button(text="Cancel", on_release=do_cancel, size_hint_y=None, height=dp(40))
            btns.add_widget(no)
            btns.add_widget(yes)
            box.add_widget(btns)
            popup.open()
        except Exception:
            # Fallback: directly close if popup fails
            self.close_current_league()

    def prompt_new_league(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot start leagues')
            except Exception:
                pass
            return
        # Popup to insert the league name
        try:
            from kivy.uix.textinput import TextInput
            from kivy.uix.widget import Widget
            # Explicit spacer below the title to avoid overlap with the title separator
            box = BoxLayout(orientation='vertical', padding=[dp(8), dp(8), dp(8), dp(8)], spacing=dp(6))
            spacer = Widget(size_hint_y=None, height=dp(40))
            lbl = Label(text="Insert the league name", size_hint_y=None, height=dp(24), halign='center', valign='middle')
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            ti = TextInput(hint_text="League name", multiline=False, size_hint_y=None, height=dp(36))
            btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
            popup = Popup(title="New League", title_size=dp(18), content=box, size_hint=(0.9, None), height=dp(200), auto_dismiss=False)
            def do_confirm(instance):
                name = ti.text.strip() or None
                popup.dismiss()
                self.create_new_league(name)
            def do_cancel(instance):
                popup.dismiss()
            ok = Button(text="Confirm", on_release=do_confirm, size_hint_y=None, height=dp(40))
            cancel = Button(text="Cancel", on_release=do_cancel, size_hint_y=None, height=dp(40))
            box.add_widget(spacer)
            box.add_widget(lbl)
            box.add_widget(ti)
            box.add_widget(btns)
            btns.add_widget(cancel)
            btns.add_widget(ok)
            popup.open()
        except Exception:
            # Fallback with empty name
            self.create_new_league(None)

    def create_new_league(self, name=None):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot start leagues')
            except Exception:
                pass
            return
        try:
            from db import DB
            now = int(time.time())
            # Close any existing active league silently if present? We only start when none is active; keep simple insert.
            DB.execute("INSERT INTO leagues (name, start_ts, end_ts) VALUES (?, ?, NULL)", (name, now))
            DB.commit()
            # Manager: upload DB after starting new league
            try:
                app = App.get_running_app()
                if app:
                    app._maybe_upload_after_write("start_new_league")
            except Exception:
                pass
            # Reload leagues, select the new one
            self._load_leagues()
            # Find active league id (new one)
            try:
                row = DB.execute("SELECT id FROM leagues WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1").fetchone()
                if row:
                    self.current_league_id = int(row[0])
            except Exception:
                pass
            self._update_action_button()
            self.refresh()
            app = App.get_running_app()
            if app:
                app.show_toast("New league started")
        except Exception:
            pass

    def _update_action_button(self):
        try:
            btn = self.ids.get('close_btn')
            if not btn:
                return
            from db import DB
            # Button reflects global state: if any active league exists -> Close League, else Start New League
            row = DB.execute("SELECT id FROM leagues WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                btn.text = 'Close League'
            else:
                btn.text = 'Start New League'
        except Exception:
            pass

    def show_db_path(self):
        # Display the actual database path in a small popup (and toast)
        try:
            from db import get_db_path
            path = get_db_path()
        except Exception:
            path = "(unknown)"
        # Try to copy to clipboard on button press
        box = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(6))
        msg = Label(text=f"Database file:\n{path}", size_hint_y=None, height=dp(64), halign='center', valign='middle')
        msg.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        popup = Popup(title="Database Path", title_size=dp(18), content=box, size_hint=(0.9, None), height=dp(180), auto_dismiss=True)
        def do_copy(instance):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(path)
                app = App.get_running_app()
                if app:
                    app.show_toast("Path copied to clipboard")
            except Exception:
                pass
            popup.dismiss()
        ok = Button(text="Copy & Close", on_release=do_copy, size_hint_y=None, height=dp(40))
        box.add_widget(msg)
        box.add_widget(btns)
        btns.add_widget(ok)
        popup.open()

    def close_current_league(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot close leagues')
            except Exception:
                pass
            return
        try:
            from db import DB
            now = int(time.time())
            cur = DB.execute("SELECT id FROM leagues WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                DB.execute("UPDATE leagues SET end_ts=? WHERE id=?", (now, row[0]))
                DB.commit()
                # Manager: upload DB after closing league
                try:
                    app = App.get_running_app()
                    if app:
                        app._maybe_upload_after_write("close_league")
                except Exception:
                    pass
            # Reload UI and keep selection on the just closed league
            self._load_leagues()
            self._update_action_button()
            self.refresh()
            app = App.get_running_app()
            if app:
                app.show_toast("League closed")
        except Exception:
            pass

    def refresh(self):
        # Render scoreboard for selected league
        grid = self.ids.get('league_grid')
        if grid is None:
            return
        grid.clear_widgets()
        # Header
        headers = ['#', 'Name', 'MP', 'W-L-D', 'Winrate %', 'League Score']
        col_sizes = [0.6, 3.0, 0.8, 1.1, 1.1, 1.2]
        def add_cell(text, bold=False, halign='center', size_hint_x=1.0):
            lbl = Label(text=(f"[b]{text}[/b]" if bold else text), markup=True, size_hint_y=None, height=dp(42), color=(1,1,1,1), halign=halign, valign='middle')
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            lbl.size_hint_x = size_hint_x
            grid.add_widget(lbl)
        for i, h in enumerate(headers):
            add_cell(h, bold=True, halign=('left' if h == 'Name' else 'center'), size_hint_x=col_sizes[i])
        # Data
        rows = self._compute_league_rows()
        from kivy.uix.scrollview import ScrollView
        for rank, st in enumerate(rows, start=1):
            name = st['name']
            mp = st['matches']
            w = st['wins']
            l = st['losses']
            d = st['draws']
            wr = f"{st['winrate']*100:.2f}"
            ls = f"{st['score']:.2f}"
            row_values = [str(rank), name, str(mp), f"{w}-{l}-{d}", wr, ls]
            for i, val in enumerate(row_values):
                if i == 1:
                    sv = ScrollView(size_hint_y=None, height=dp(42), do_scroll_x=True, do_scroll_y=False, bar_width=0)
                    sv.effect_y = None
                    sv.scroll_wheel_distance = 0
                    sv.scroll_y = 1
                    sv.size_hint_x = col_sizes[i]
                    name_lbl = Label(text=val, markup=True, size_hint_y=None, height=dp(42), color=(1,1,1,1), halign='left', valign='middle', size_hint_x=None)
                    name_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'width', val[0] + dp(4)))
                    name_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (None, None)))
                    sv.add_widget(name_lbl)
                    grid.add_widget(sv)
                else:
                    add_cell(val, bold=False, halign='center', size_hint_x=col_sizes[i])

    def _compute_league_rows(self):
        try:
            from db import DB
            # Find selected league window
            lid = int(self.current_league_id or 0)
            row = DB.execute("SELECT start_ts, end_ts FROM leagues WHERE id=?", (lid,)).fetchone()
            if not row:
                # fallback to active
                row = DB.execute("SELECT start_ts, end_ts, id FROM leagues WHERE end_ts IS NULL ORDER BY id DESC LIMIT 1").fetchone()
                if row and len(row) == 3:
                    self.current_league_id = row[2]
                    start_ts, end_ts = row[0], row[1]
                elif row:
                    start_ts, end_ts = row[0], row[1]
                else:
                    start_ts = int(time.time())
                    end_ts = None
            else:
                start_ts, end_ts = row
            # Load closed events within the league window based on when the event actually started (round_start_ts)
            # Guard against null/malformed start_ts; if missing, treat as now to avoid including older events.
            safe_start = int(start_ts) if start_ts is not None else int(time.time())
            params = [safe_start]
            where = "status='closed' AND round_start_ts IS NOT NULL AND round_start_ts >= ?"
            if end_ts is not None:
                where += " AND round_start_ts <= ?"
                params.append(int(end_ts))
            ev_rows = DB.execute(f"SELECT id FROM events WHERE {where}", tuple(params)).fetchall()
            event_ids = [int(r[0]) for r in ev_rows]
            if not event_ids:
                return []
            # Map event_players.id to a unified participant key and gather participants per event
            # Registered players use their integer player_id; guests use a synthetic key 'g:<name>'
            ep_map = {}  # eid -> {event_player_id: participant_key}
            participants = set()  # set of participant keys seen in eligible events
            qmarks = ','.join('?' for _ in event_ids)
            for (ep_id, ev_id, pid, guest) in DB.execute(
                f"SELECT id, event_id, player_id, guest_name FROM event_players WHERE event_id IN ({qmarks})",
                event_ids
            ).fetchall():
                if pid is not None:
                    key = int(pid)
                elif guest:
                    key = f"g:{guest}"
                else:
                    # Skip malformed entries
                    continue
                ep_map.setdefault(ev_id, {})[ep_id] = key
                participants.add(key)
            if not participants:
                return []
            # Initialize stats per participant
            stats = {key: {'pid': key, 'name': '', 'matches': 0, 'wins': 0, 'losses': 0, 'draws': 0} for key in participants}
            # Names: fill for registered and guest participants
            reg_ids = [k for k in participants if isinstance(k, int)]
            if reg_ids:
                for pid, name in DB.execute(
                    f"SELECT id, COALESCE(nickname, name) FROM players WHERE id IN ({','.join('?' for _ in reg_ids)})",
                    reg_ids
                ).fetchall():
                    if pid in stats:
                        stats[pid]['name'] = name
            # Guests
            for key in participants:
                if isinstance(key, str) and key.startswith('g:'):
                    stats[key]['name'] = key[2:] or 'Guest'
            # Iterate matches in eligible events
            for ev_id in event_ids:
                # BYEs and matches
                for p1, p2, s1, s2, bye in DB.execute("SELECT player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=?", (ev_id,)).fetchall():
                    s1 = int(s1 or 0)
                    s2 = int(s2 or 0)
                    if bye == 1:
                        # count as 1 match and a win for player1 if mapped
                        pid1 = ep_map.get(ev_id, {}).get(p1)
                        if pid1 is not None and pid1 in stats:
                            stats[pid1]['wins'] += 1
                            stats[pid1]['matches'] += 1
                        continue
                    pid1 = ep_map.get(ev_id, {}).get(p1)
                    pid2 = ep_map.get(ev_id, {}).get(p2)
                    if pid1 is None or pid2 is None:
                        continue
                    # both participants
                    stats[pid1]['matches'] += 1
                    stats[pid2]['matches'] += 1
                    if s1 > s2:
                        stats[pid1]['wins'] += 1
                        stats[pid2]['losses'] += 1
                    elif s2 > s1:
                        stats[pid2]['wins'] += 1
                        stats[pid1]['losses'] += 1
                    else:
                        stats[pid1]['draws'] += 1
                        stats[pid2]['draws'] += 1
            # Ensure players who registered but had 0 matches still appear
            # Already in stats via participants set
            # Compute winrate and score
            import math
            out = []
            # Factor for winrate over matches
            k = 0.3
            for st in stats.values():
                mp = st['matches']
                wr = ((st['wins'] + 0.5 * st['draws']) / mp) if mp > 0 else 0.0
                score = 100.0 * wr * (1.0 - math.e ** (-k * mp))
                st['winrate'] = wr
                st['score'] = score
                out.append(st)
            # Sort by league score desc, then winrate desc, then name asc
            out.sort(key=lambda r: (-r['score'], -r['winrate'], r['name']))
            return out
        except Exception:
            return []


class BingoScreen(Screen):
    current_player_id = NumericProperty(0)
    current_player_name = StringProperty("")
    status_text = StringProperty("")
    achievements = ListProperty([])  # 9 texts
    # state: { str(player_id): [bool]*9 }
    bingo_state = DictProperty({})
    # taken lines and winners
    taken = DictProperty({})  # {'rows':[bool]*3,'cols':[bool]*3,'diags':[bool]*2,'full': bool}
    winners = DictProperty({})  # {'rows':[pid or None]*3,...,'full': pid or None}

    def refresh_all(self):
        # Reload persistent state and players, then redraw everything
        try:
            self._load_state()
        except Exception:
            pass
        try:
            self.refresh_from_db()
        except Exception:
            pass

    def on_kv_post(self, base_widget):
        # Load data
        self._ensure_achievements()
        self._load_state()
        self._load_players()
        self._render_players_list()
        self._select_default_player()
        self._render_grid()
        self._update_status()

    def on_pre_enter(self, *args):
        # Refresh from DB each time we enter, so downloads are reflected
        try:
            self.refresh_from_db()
        except Exception:
            pass

    def refresh_from_db(self):
        # Reload bingo state and players, then reconcile current selection and redraw UI
        try:
            # Ensure in-memory bingo_state/taken/winners reflect the DB
            self._load_state()
        except Exception:
            pass
        try:
            self._load_players()
            self._render_players_list()
            # If current player no longer exists, reset selection
            cur = int(self.current_player_id) if self.current_player_id else 0
            if not any(int(p.get('id', 0)) == cur for p in self._players):
                self.current_player_id = 0
                self.current_player_name = ''
                self._select_default_player()
            # Redraw grid and status
            self._render_grid()
            self._update_status()
        except Exception:
            pass

    # ---- Paths and persistence ----
    def _achievements_path(self):
        # Always read the bundled project file so user edits to achievements.json are reflected
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'achievements.json')

    def _state_path(self):
        try:
            from db import _get_persistent_db_path
            return _get_persistent_db_path('bingo_state.json')
        except Exception:
            return os.path.join(os.path.expanduser('~'), '.draft_buddy', 'bingo_state.json')

    def _ensure_achievements(self):
        path = self._achievements_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                arr = data.get('achievements') or []
                if not isinstance(arr, list) or len(arr) != 9:
                    arr = [f"Achievement {i+1}" for i in range(9)]
                self.achievements = arr
            else:
                self.achievements = [f"Achievement {i+1}" for i in range(9)]
        except Exception:
            self.achievements = [f"Achievement {i+1}" for i in range(9)]

    def _load_state(self):
        """Load bingo state from the SQLite DB. If the bingo tables are empty
        but a legacy bingo_state.json exists, import it once and remove the file.
        Fallback to empty state on errors."""
        # Defaults
        self.bingo_state = {}
        self.taken = {'rows':[False]*3,'cols':[False]*3,'diags':[False]*2,'full': False}
        self.winners = {'rows':[None]*3,'cols':[None]*3,'diags':[None]*2,'full': None}
        try:
            from db import DB
            c = DB.cursor()
            # Check if tables exist
            try:
                c.execute("SELECT 1 FROM bingo_players LIMIT 1")
                tables_ok = True
            except Exception:
                tables_ok = False
            if not tables_ok:
                return
            # If empty, attempt legacy import
            try:
                cnt = c.execute("SELECT COUNT(*) FROM bingo_players").fetchone()[0]
            except Exception:
                cnt = 0
            if cnt == 0:
                try:
                    path = self._state_path()
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        players = data.get('players') or {}
                        taken = data.get('taken') or self.taken
                        winners = data.get('winners') or self.winners
                        # Write import into DB
                        for k, arr in players.items():
                            try:
                                pid = int(k)
                                vals = [1 if bool(x) else 0 for x in (arr + [False]*9)[:9]]
                                c.execute(
                                    """
                                    INSERT INTO bingo_players(player_id,c0,c1,c2,c3,c4,c5,c6,c7,c8)
                                    VALUES(?,?,?,?,?,?,?,?,?,?)
                                    """,
                                    [pid] + vals
                                )
                            except Exception:
                                pass
                        # Meta row
                        def _b(x):
                            return 1 if bool(x) else 0
                        rows = taken.get('rows',[False]*3)
                        cols = taken.get('cols',[False]*3)
                        diags = taken.get('diags',[False]*2)
                        c.execute(
                            """
                            UPDATE bingo_meta SET
                              row0=?, row1=?, row2=?,
                              col0=?, col1=?, col2=?,
                              diag0=?, diag1=?, full=?,
                              win_row0=?, win_row1=?, win_row2=?,
                              win_col0=?, win_col1=?, win_col2=?,
                              win_diag0=?, win_diag1=?, win_full=?
                            WHERE id=1
                            """,
                            [
                                _b(rows[0]), _b(rows[1]), _b(rows[2]),
                                _b(cols[0]), _b(cols[1]), _b(cols[2]),
                                _b(diags[0]), _b(diags[1]), _b(taken.get('full')),
                                (winners.get('rows',[None]*3)[0] if winners else None),
                                (winners.get('rows',[None]*3)[1] if winners else None),
                                (winners.get('rows',[None]*3)[2] if winners else None),
                                (winners.get('cols',[None]*3)[0] if winners else None),
                                (winners.get('cols',[None]*3)[1] if winners else None),
                                (winners.get('cols',[None]*3)[2] if winners else None),
                                (winners.get('diags',[None]*2)[0] if winners else None),
                                (winners.get('diags',[None]*2)[1] if winners else None),
                                (winners.get('full') if winners else None),
                            ]
                        )
                        DB.commit()
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                except Exception:
                    pass
            # Load from DB into memory
            for pid, c0,c1,c2,c3,c4,c5,c6,c7,c8 in c.execute("SELECT player_id,c0,c1,c2,c3,c4,c5,c6,c7,c8 FROM bingo_players").fetchall():
                self.bingo_state[str(int(pid))] = [bool(c0),bool(c1),bool(c2),bool(c3),bool(c4),bool(c5),bool(c6),bool(c7),bool(c8)]
            row = c.execute("SELECT row0,row1,row2,col0,col1,col2,diag0,diag1,full,win_row0,win_row1,win_row2,win_col0,win_col1,win_col2,win_diag0,win_diag1,win_full FROM bingo_meta WHERE id=1").fetchone()
            if row:
                r0,r1,r2,c0,c1,c2,d0,d1,full,wr0,wr1,wr2,wc0,wc1,wc2,wd0,wd1,wf = row
                self.taken = {'rows':[bool(r0),bool(r1),bool(r2)], 'cols':[bool(c0),bool(c1),bool(c2)], 'diags':[bool(d0),bool(d1)], 'full': bool(full)}
                self.winners = {'rows':[wr0,wr1,wr2], 'cols':[wc0,wc1,wc2], 'diags':[wd0,wd1], 'full': wf}
        except Exception:
            # Leave defaults on error
            pass

    def _save_state(self):
        """Persist current in-memory bingo state to SQLite DB."""
        try:
            from db import DB
            c = DB.cursor()
            # Upsert all players
            for k, arr in (self.bingo_state or {}).items():
                try:
                    pid = int(k)
                except Exception:
                    continue
                vals = [1 if bool(x) else 0 for x in (list(arr) + [False]*9)[:9]]
                c.execute(
                    """
                    INSERT INTO bingo_players(player_id,c0,c1,c2,c3,c4,c5,c6,c7,c8)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(player_id) DO UPDATE SET
                      c0=excluded.c0, c1=excluded.c1, c2=excluded.c2,
                      c3=excluded.c3, c4=excluded.c4, c5=excluded.c5,
                      c6=excluded.c6, c7=excluded.c7, c8=excluded.c8
                    """,
                    [pid] + vals
                )
            # Update meta
            t = self.taken or {'rows':[False]*3,'cols':[False]*3,'diags':[False]*2,'full': False}
            w = self.winners or {'rows':[None]*3,'cols':[None]*3,'diags':[None]*2,'full': None}
            def _b(x):
                return 1 if bool(x) else 0
            rows = t.get('rows',[False]*3)
            cols = t.get('cols',[False]*3)
            diags = t.get('diags',[False]*2)
            c.execute(
                """
                UPDATE bingo_meta SET
                  row0=?, row1=?, row2=?,
                  col0=?, col1=?, col2=?,
                  diag0=?, diag1=?, full=?,
                  win_row0=?, win_row1=?, win_row2=?,
                  win_col0=?, win_col1=?, win_col2=?,
                  win_diag0=?, win_diag1=?, win_full=?
                WHERE id=1
                """,
                [
                    _b(rows[0]), _b(rows[1]), _b(rows[2]),
                    _b(cols[0]), _b(cols[1]), _b(cols[2]),
                    _b(diags[0]), _b(diags[1]), _b(t.get('full')),
                    (w.get('rows',[None]*3)[0] if w else None),
                    (w.get('rows',[None]*3)[1] if w else None),
                    (w.get('rows',[None]*3)[2] if w else None),
                    (w.get('cols',[None]*3)[0] if w else None),
                    (w.get('cols',[None]*3)[1] if w else None),
                    (w.get('cols',[None]*3)[2] if w else None),
                    (w.get('diags',[None]*2)[0] if w else None),
                    (w.get('diags',[None]*2)[1] if w else None),
                    (w.get('full') if w else None),
                ]
            )
            DB.commit()
        except Exception:
            pass

    # ---- Players ----
    def _load_players(self):
        self._players = []
        try:
            from db import DB
            c = DB.cursor()
            rows = c.execute("SELECT id, COALESCE(nickname, name) as n FROM players ORDER BY n COLLATE NOCASE").fetchall()
            for pid, name in rows:
                self._players.append({'id': int(pid), 'name': name})
        except Exception:
            pass

    def _render_players_list(self):
        cont = self.ids.get('players_grid') or self.ids.get('players_list')
        if not cont:
            return
        cont.clear_widgets()
        for p in self._players:
            btn = Button(text=p['name'], size_hint_y=None, height=dp(42))
            def _mk_select(_pid=p['id'], _pname=p['name']):
                return lambda *_: self.select_player(_pid, _pname)
            btn.bind(on_release=_mk_select())
            cont.add_widget(btn)

    def _select_default_player(self):
        if self.current_player_id:
            return
        if self._players:
            p = self._players[0]
            self.select_player(p['id'], p['name'])

    def select_player(self, pid, name):
        self.current_player_id = int(pid)
        self.current_player_name = name
        # Ensure player state exists
        key = str(self.current_player_id)
        if key not in self.bingo_state:
            self.bingo_state[key] = [False]*9
            self._save_state()
        # Update UI
        self._render_grid()
        self._update_status()

    # ---- Grid ----
    def _render_grid(self):
        grid = self.ids.get('bingo_grid')
        if not grid:
            return
        grid.clear_widgets()
        # Create 9 buttons (larger); completed cells disabled
        for idx in range(9):
            done = False
            try:
                done = bool(self.bingo_state.get(str(self.current_player_id), [False]*9)[idx])
            except Exception:
                done = False
            txt = self.achievements[idx] if idx < len(self.achievements) else f"#{idx+1}"
            btn = Button(text=txt, halign='center', valign='middle')
            btn.text_size = (None, None)
            btn.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width - dp(8), inst.height - dp(8))))
            btn.size_hint_y = None
            btn.height = dp(120)
            btn.background_normal = ''
            btn.background_down = ''
            # Guests cannot update bingo cells; keep buttons visible for guests
            can_edit = _is_manager()
            # Only disable when the achievement is already done, so guests see normal opacity
            btn.disabled = done
            # Color: green if done, dark gray otherwise; no visual press feedback because background_down is blank
            btn.background_color = (0.16,0.64,0.28,1) if done else (0.26,0.26,0.26,1)
            if (not done) and can_edit:
                def _on_press(_i=idx, _txt=txt):
                    return lambda *_: self._confirm_mark(_i, _txt)
                btn.bind(on_release=_on_press())
            grid.add_widget(btn)

    def _confirm_mark(self, idx, ach_text):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot update bingo')
            except Exception:
                pass
            return
        if not self.current_player_id:
            return
        name = self.current_player_name or str(self.current_player_id)
        msg = f"Are you sure player {name} has completed this achievement:\n{ach_text}?"
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        # Use a ScrollView with a wrapping Label so long text stays inside the popup
        from kivy.uix.scrollview import ScrollView
        sv = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=0)
        lbl = Label(text=msg, halign='center', valign='top', size_hint_y=None)
        # Wrap text to the available width; update height from texture
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width - dp(8), None)))
        lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
        sv.add_widget(lbl)
        content.add_widget(sv)
        btns = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        yes = Button(text='Yes')
        no = Button(text='No')
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title='Confirm', content=content, size_hint=(0.9, 0.34), auto_dismiss=False)
        no.bind(on_release=lambda *_: popup.dismiss())
        def _do(*_):
            popup.dismiss()
            self._mark_done(idx)
        yes.bind(on_release=_do)
        popup.open()

    def _mark_done(self, idx):
        key = str(self.current_player_id)
        arr = list(self.bingo_state.get(key, [False]*9))
        if idx < 0 or idx >= 9:
            return
        if arr[idx]:
            # already done
            return
        arr[idx] = True
        self.bingo_state[key] = arr
        self._save_state()
        # Manager: upload DB after marking achievement done
        try:
            app = App.get_running_app()
            if app:
                app._maybe_upload_after_write("bingo_mark_done")
        except Exception:
            pass
        self._render_grid()
        # After marking, check winnings
        self._check_wins()
        self._update_status()

    # ---- Win logic ----
    def _check_wins(self):
        pid = self.current_player_id
        key = str(pid)
        arr = self.bingo_state.get(key, [False]*9)
        # Lines definitions
        lines = {
            ('row', 0): [0,1,2],
            ('row', 1): [3,4,5],
            ('row', 2): [6,7,8],
            ('col', 0): [0,3,6],
            ('col', 1): [1,4,7],
            ('col', 2): [2,5,8],
            ('diag', 0): [0,4,8],
            ('diag', 1): [2,4,6],
        }
        took_any = False
        for (typ, i), cells in lines.items():
            completed = all(arr[c] for c in cells)
            if not completed:
                continue
            if typ == 'row':
                if not self.taken['rows'][i]:
                    self.taken['rows'][i] = True
                    self.winners['rows'][i] = pid
                    took_any = True
                    self._announce_winner(f"{self.current_player_name} won row {i+1}!")
            elif typ == 'col':
                if not self.taken['cols'][i]:
                    self.taken['cols'][i] = True
                    self.winners['cols'][i] = pid
                    took_any = True
                    self._announce_winner(f"{self.current_player_name} won column {i+1}!")
            elif typ == 'diag':
                if not self.taken['diags'][i]:
                    self.taken['diags'][i] = True
                    self.winners['diags'][i] = pid
                    took_any = True
                    name = 'main diagonal' if i == 0 else 'anti-diagonal'
                    self._announce_winner(f"{self.current_player_name} won the {name}!")
        # Full grid
        if all(arr):
            if not self.taken.get('full'):
                self.taken['full'] = True
                self.winners['full'] = pid
                took_any = True
                self._announce_winner(f"{self.current_player_name} completed the whole grid!")
        if took_any:
            self._save_state()

    def _announce_winner(self, message):
        # Always show a popup to announce first completions; also try to show a toast
        try:
            Popup(title='Bingo', content=Label(text=message), size_hint=(0.7, 0.25)).open()
        except Exception:
            pass
        app = App.get_running_app()
        if app:
            try:
                app.show_toast(message, timeout=3.0)
            except Exception:
                pass

    def _update_status(self):
        # Build a small summary text
        parts = []
        try:
            def _nm(pid):
                if pid is None:
                    return None
                for p in self._players:
                    if p['id'] == pid:
                        return p['name']
                return f"#{pid}"
            rows = [(_nm(p), t) for p, t in zip(self.winners.get('rows', [None]*3), self.taken.get('rows', [False]*3))]
            cols = [(_nm(p), t) for p, t in zip(self.winners.get('cols', [None]*3), self.taken.get('cols', [False]*3))]
            diags = [(_nm(p), t) for p, t in zip(self.winners.get('diags', [None]*2), self.taken.get('diags', [False]*2))]
            if any(t for _, t in rows):
                s = ", ".join([f"{i+1}:{n}" for i,(n,t) in enumerate(rows) if t and n])
                parts.append(f"Rows: {s}")
            if any(t for _, t in cols):
                s = ", ".join([f"{i+1}:{n}" for i,(n,t) in enumerate(cols) if t and n])
                parts.append(f"Cols: {s}")
            if any(t for _, t in diags):
                s = ", ".join([f"{('D1' if i==0 else 'D2')}:{n}" for i,(n,t) in enumerate(diags) if t and n])
                parts.append(f"Diags: {s}")
            if self.taken.get('full'):
                nm = _nm(self.winners.get('full'))
                parts.append(f"Full grid: {nm}")
        except Exception:
            pass
        self.status_text = "  |  ".join(parts) if parts else ""

    # ---- Actions exposed to KV ----
    def open_completed_popup(self):
        # Read-only summary of global bingo progress: first winners and taken lines only.
        # This popup must be identical regardless of the selected player.
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(12))
        # Grid with achievements labels; color cells that belong to globally completed lines/diags
        gl = GridLayout(cols=3, rows=3, spacing=dp(6), size_hint_y=None)
        gl.bind(minimum_height=lambda inst, val: setattr(inst, 'height', val))
        # Determine which indices are part of completed lines
        taken = self.taken or {'rows':[False]*3,'cols':[False]*3,'diags':[False]*2,'full': False}
        completed_indices = set()
        lines = {
            ('row', 0): [0,1,2],
            ('row', 1): [3,4,5],
            ('row', 2): [6,7,8],
            ('col', 0): [0,3,6],
            ('col', 1): [1,4,7],
            ('col', 2): [2,5,8],
            ('diag', 0): [0,4,8],
            ('diag', 1): [2,4,6],
        }
        for i in range(3):
            if taken.get('rows', [False]*3)[i]:
                completed_indices.update(lines[('row', i)])
            if taken.get('cols', [False]*3)[i]:
                completed_indices.update(lines[('col', i)])
        for i in range(2):
            if taken.get('diags', [False]*2)[i]:
                completed_indices.update(lines[('diag', i)])
        # Build the grid labels
        for idx in range(9):
            txt = self.achievements[idx] if idx < len(self.achievements) else f"#{idx+1}"
            lbl = Label(text=txt, halign='center', valign='middle')
            lbl.text_size = (None, None)
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width - dp(8), inst.height - dp(8))))
            lbl.size_hint_y = None
            lbl.height = dp(90)
            # Color background via canvas
            def _add_bg(widget, taken_here):
                from kivy.graphics import Color, Rectangle
                with widget.canvas.before:
                    if taken_here:
                        Color(0.16, 0.64, 0.28, 0.35)
                    else:
                        Color(0.2, 0.2, 0.2, 0.2)
                    widget._bg_rect = Rectangle(pos=widget.pos, size=widget.size)
                widget.bind(pos=lambda w, v: setattr(widget._bg_rect, 'pos', v))
                widget.bind(size=lambda w, v: setattr(widget._bg_rect, 'size', v))
            _add_bg(lbl, idx in completed_indices)
            gl.add_widget(lbl)
        content.add_widget(gl)
        # Winners list (global, first to complete only)
        def _nm(pid):
            if pid is None:
                return None
            for p in getattr(self, '_players', []):
                if p['id'] == pid:
                    return p['name']
            return f"#{pid}"
        from kivy.uix.scrollview import ScrollView
        sv = ScrollView(size_hint=(1, 1))
        info = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        info.bind(minimum_height=lambda inst, val: setattr(inst, 'height', val))
        # Rows
        for i in range(3):
            if taken.get('rows', [False]*3)[i]:
                nm = _nm((self.winners or {}).get('rows', [None]*3)[i])
                info.add_widget(Label(text=f"Row {i+1}: {nm}", size_hint_y=None, height=dp(24)))
        # Cols
        for i in range(3):
            if taken.get('cols', [False]*3)[i]:
                nm = _nm((self.winners or {}).get('cols', [None]*3)[i])
                info.add_widget(Label(text=f"Column {i+1}: {nm}", size_hint_y=None, height=dp(24)))
        # Diags
        for i in range(2):
            if taken.get('diags', [False]*2)[i]:
                name = 'Main diagonal' if i == 0 else 'Anti-diagonal'
                nm = _nm((self.winners or {}).get('diags', [None]*2)[i])
                info.add_widget(Label(text=f"{name}: {nm}", size_hint_y=None, height=dp(24)))
        # Full grid
        if taken.get('full'):
            nm = _nm((self.winners or {}).get('full'))
            info.add_widget(Label(text=f"Full grid: {nm}", size_hint_y=None, height=dp(24)))
        # Empty state
        if len(info.children) == 0:
            info.add_widget(Label(text="No completed achievements yet.", size_hint_y=None, height=dp(24)))
        sv.add_widget(info)
        content.add_widget(sv)
        # Buttons
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        close = Button(text='Close')
        btns.add_widget(close)
        content.add_widget(btns)
        popup = Popup(title='Bingo Progress', content=content, size_hint=(0.9, 0.9))
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def reset_progress(self):
        if not _is_manager():
            try:
                App.get_running_app().show_toast('Guests cannot reset bingo')
            except Exception:
                pass
            return
        # Confirm (wrap long text to avoid overflow)
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(12))
        # Scrollable, wrapping message
        from kivy.uix.scrollview import ScrollView
        sv = ScrollView(size_hint=(1, 1))
        msg = Label(text='Reset all bingo progresses? This cannot be undone.', halign='center', valign='top', size_hint_y=None)
        # Bind width to wrap text and height to texture
        msg.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width - dp(16), None)))
        msg.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
        sv.add_widget(msg)
        content.add_widget(sv)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        yes = Button(text='Yes')
        no = Button(text='No')
        btns.add_widget(yes)
        btns.add_widget(no)
        content.add_widget(btns)
        popup = Popup(title='Confirm Reset', content=content, size_hint=(0.85, 0.32))
        no.bind(on_release=lambda *_: popup.dismiss())
        def _do(*_):
            popup.dismiss()
            # Hard reset both per-player cells and global winners in the database
            try:
                from db import DB
                c = DB.cursor()
                c.execute("DELETE FROM bingo_players")
                c.execute(
                    """
                    UPDATE bingo_meta SET
                      row0=0, row1=0, row2=0,
                      col0=0, col1=0, col2=0,
                      diag0=0, diag1=0, full=0,
                      win_row0=NULL, win_row1=NULL, win_row2=NULL,
                      win_col0=NULL, win_col1=NULL, win_col2=NULL,
                      win_diag0=NULL, win_diag1=NULL, win_full=NULL
                    WHERE id=1
                    """
                )
                DB.commit()
                # Manager: upload DB after bingo reset
                try:
                    app = App.get_running_app()
                    if app:
                        app._maybe_upload_after_write("bingo_reset")
                except Exception:
                    pass
            except Exception:
                # If DB reset fails, continue with in-memory reset so UI is coherent
                pass
            # Reset in-memory state and refresh UI
            self.bingo_state = {}
            self.taken = {'rows':[False]*3,'cols':[False]*3,'diags':[False]*2,'full': False}
            self.winners = {'rows':[None]*3,'cols':[None]*3,'diags':[None]*2,'full': None}
            self._render_grid()
            self._update_status()
            try:
                App.get_running_app().show_toast('Bingo has been fully reset')
            except Exception:
                pass
        yes.bind(on_release=_do)
        popup.open()


class LifeTrackerScreen(Screen):
    top_life = NumericProperty(20)
    bottom_life = NumericProperty(20)
    default_life = NumericProperty(20)

    def on_kv_post(self, base_widget):
        # Load default from persistent storage and initialize counters if first time
        try:
            self._load_default()
            # Initialize counters only the first time
            if not hasattr(self, '_initialized'):
                self.top_life = int(self.default_life)
                self.bottom_life = int(self.default_life)
                self._initialized = True
        except Exception:
            pass

    # -------------- Persistence --------------
    def _config_path(self):
        try:
            from db import _get_persistent_db_path
            cfg = _get_persistent_db_path('lifetracker.json')
            return cfg
        except Exception:
            # Fallback: home directory
            try:
                return os.path.join(os.path.expanduser('~'), '.draft_buddy', 'lifetracker.json')
            except Exception:
                return 'lifetracker.json'

    def _load_default(self):
        path = self._config_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                val = int(data.get('default_life', 20))
                if val <= 0:
                    val = 20
                self.default_life = val
            else:
                self.default_life = 20
        except Exception:
            self.default_life = 20

    def _save_default(self):
        path = self._config_path()
        try:
            d = os.path.dirname(path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'default_life': int(self.default_life)}, f)
        except Exception:
            pass

    # -------------- Actions --------------
    def reset_counters(self):
        try:
            self.top_life = int(self.default_life)
            self.bottom_life = int(self.default_life)
            App.get_running_app().show_toast(f"Life reset to {self.default_life}")
        except Exception:
            self.top_life = self.bottom_life = 20

    def inc_top(self):
        self.top_life += 1

    def dec_top(self):
        self.top_life -= 1

    def inc_bottom(self):
        self.bottom_life += 1

    def dec_bottom(self):
        self.bottom_life -= 1

    def open_settings_popup(self):
        # Simple numeric input popup
        try:
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.textinput import TextInput
            from kivy.uix.label import Label
            from kivy.uix.button import Button
            from kivy.uix.popup import Popup
            from kivy.metrics import dp
        except Exception:
            return
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=[dp(10), 0, dp(10), dp(10)])
        content.add_widget(Label(text='Starting life', size_hint_y=None, height=dp(24)))
        ti = TextInput(text=str(int(self.default_life)), multiline=False, input_filter='int', size_hint_y=None, height=dp(40))
        content.add_widget(ti)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        save_btn = Button(text='Save')
        cancel_btn = Button(text='Cancel')
        btns.add_widget(save_btn)
        btns.add_widget(cancel_btn)
        content.add_widget(btns)
        popup = Popup(title='Life Tracker Settings', content=content, size_hint=(0.8, 0.25))

        def _save(*_):
            try:
                v = int(ti.text.strip() or '20')
                if v <= 0:
                    v = 1
                self.default_life = v
                self._save_default()
                app = App.get_running_app()
                if app:
                    app.show_toast(f"Default life set to {v}")
            except Exception:
                pass
            popup.dismiss()

        save_btn.bind(on_release=_save)
        cancel_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


# -------------- Auth & Server Helpers --------------

def _auth_path() -> str:
    try:
        base_dir = os.path.dirname(get_db_path())
    except Exception:
        base_dir = os.path.join(os.path.expanduser('~'), '.draft_buddy')
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base_dir, 'auth.json')


def load_auth():
    try:
        p = _auth_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_auth(data: dict):
    try:
        p = _auth_path()
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return True
    except Exception:
        return False


def clear_auth():
    try:
        p = _auth_path()
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


def _get_base_url(auth: dict | None) -> str:
    # Fixed, non-configurable base URL per requirements
    return "https://draftbuddy.hackthep.it"


def _is_manager() -> bool:
    """Return True if the current user is a manager.
    Uses saved auth role and username prefix fallback (username startswith 'manager').
    """
    try:
        auth = load_auth() or {}
        role = (auth.get('role') or '').strip().lower()
        uname = (auth.get('username') or '').strip().lower()
        return bool(role == 'manager' or uname.startswith('manager'))
    except Exception:
        return False


class LoginScreen(Screen):
    server_url = StringProperty("")
    username = StringProperty("")
    playgroup = StringProperty("clandestini")
    status = StringProperty("")

    def on_pre_enter(self):
        try:
            auth = load_auth() or {}
            # server URL is fixed; no need to load from auth
            self.username = auth.get('username', self.username or '')
            self.playgroup = auth.get('playgroup', self.playgroup or 'clandestini') or 'clandestini'
            self.status = ''
        except Exception:
            pass

    def do_login(self, password: str, remember: bool):
        password = password or ''
        base = _get_base_url(None)
        user = (self.username or '').strip()
        if not user or not password:
            msg = 'Please fill in both username and password, or login as guest'
            try:
                self.status = msg
            except Exception:
                pass
            App.get_running_app().show_toast(msg)
            return
        url = f"{base}/auth/login"

        # Optional preflight to provide clearer feedback if server is unreachable
        def _preflight():
            try:
                h = requests.get(f"{base}/health", timeout=8)
                return h.status_code == 200
            except requests.exceptions.SSLError as se:
                try:
                    h = requests.get(f"{base}/health", timeout=8, verify=False)
                    return h.status_code == 200
                except Exception:
                    return False
            except Exception:
                return False

        try:
            pre_ok = _preflight()
            try:
                resp = requests.post(url, json={
                    'username': user,
                    'password': password,
                    'remember': bool(remember),
                    'playgroup': (self.playgroup or 'clandestini')
                }, timeout=25)
            except requests.exceptions.SSLError:
                # Retry without SSL verification on Android devices missing some CAs
                resp = requests.post(url, json={
                    'username': user,
                    'password': password,
                    'remember': bool(remember),
                    'playgroup': (self.playgroup or 'clandestini')
                }, timeout=25, verify=False)

            if resp.status_code != 200:
                # Include short server message if any
                extra = ''
                try:
                    t = resp.text
                    if t:
                        extra = f" - {t[:160]}"
                except Exception:
                    pass
                self.status = f"Login failed: {resp.status_code}{extra}"
                App.get_running_app().show_toast('Invalid credentials' if resp.status_code == 401 else f'Login failed: {resp.status_code}')
                return
            data = resp.json()
            token = data.get('access_token')
            manager_id = data.get('manager_id')
            exp = data.get('exp')
            role = data.get('role', 'guest')
            if not token or not manager_id:
                self.status = 'Unexpected server response'
                App.get_running_app().show_toast('Unexpected response')
                return
            save_auth({
                'base_url': base,
                'username': user,
                'playgroup': (self.playgroup or 'clandestini'),
                'token': token,
                'manager_id': manager_id,
                'exp': exp,
                'role': role,
            })
            # Go to main tab and show bottom nav
            app = App.get_running_app()
            try:
                if app:
                    app.refresh_auth_cache()
            except Exception:
                pass
            if app and app.root:
                sm = app.root.ids.sm
                sm.current = 'players'
                try:
                    app.root.ids.bottomnav.opacity = 1
                    app.root.ids.bottomnav.height = dp(56)
                    app.root.ids.bottomnav.disabled = False
                except Exception:
                    pass
            # Start/stop guest auto-download based on role
            try:
                if app:
                    if app.is_manager():
                        app._stop_guest_autodownload()
                    else:
                        app._start_guest_autodownload(fire_immediately=True)
            except Exception:
                pass
            app.show_toast('Logged in')
        except requests.exceptions.Timeout as e:
            self.status = f'Network timeout: {type(e).__name__}'
            App.get_running_app().show_toast('Network timeout while logging in')
        except requests.exceptions.ConnectionError as e:
            hint = '' if _preflight() else ' (server unreachable?)'
            self.status = f'Network error: {type(e).__name__}: {e}'
            App.get_running_app().show_toast('Network error while logging in' + hint)
        except Exception as e:
            self.status = f'Error: {type(e).__name__}: {e}'
            App.get_running_app().show_toast('Network error while logging in')

    def login_guest(self):
        try:
            self.username = 'guest'
        except Exception:
            pass
        # Use remember=True by default for guest for convenience
        self.do_login('guest', True)

    def diagnose_connection(self):
        # Run a few simple checks and show results in a popup and status
        try:
            import socket
            import traceback
        except Exception:
            socket = None
        base = _get_base_url(None)
        lines = []
        lines.append(f"Base URL: {base}")
        # Platform hint
        try:
            from kivy.utils import platform as _plat
            lines.append(f"Platform: {_plat}")
        except Exception:
            pass
        # DNS
        try:
            host = base.split('://', 1)[-1].split('/', 1)[0]
            addrs = []
            if socket:
                infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
                for fam, st, pr, cn, sa in infos:
                    addrs.append(sa[0])
            uniq = []
            for a in addrs:
                if a not in uniq:
                    uniq.append(a)
            lines.append(f"DNS: {host} -> {', '.join(uniq) if uniq else '(no results)'}")
        except Exception as e:
            lines.append(f"DNS error: {type(e).__name__}: {e}")
        # HTTPS /health
        import time as _t
        try:
            t0 = _t.time()
            r = requests.get(f"{base}/health", timeout=8)
            dt = int((_t.time() - t0) * 1000)
            lines.append(f"HTTPS /health: {r.status_code} in {dt} ms")
        except requests.exceptions.SSLError as e:
            lines.append(f"HTTPS /health SSL error: {e}")
            # Retry insecure
            try:
                t0 = _t.time()
                r = requests.get(f"{base}/health", timeout=8, verify=False)
                dt = int((_t.time() - t0) * 1000)
                lines.append(f"HTTPS /health (insecure): {r.status_code} in {dt} ms")
            except Exception as e2:
                lines.append(f"HTTPS /health (insecure) failed: {type(e2).__name__}: {e2}")
        except requests.exceptions.ConnectionError as e:
            lines.append(f"HTTPS /health connection error: {e}")
        except Exception as e:
            lines.append(f"HTTPS /health error: {type(e).__name__}: {e}")
        # Summarize
        report = "\n".join(lines)
        self.status = lines[-1] if lines else ""
        # Popup
        try:
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.label import Label
            from kivy.uix.button import Button
            from kivy.uix.scrollview import ScrollView
            from kivy.uix.popup import Popup
            from kivy.metrics import dp
        except Exception:
            return
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        sv = ScrollView(size_hint=(1, 1))
        lbl = Label(text=report, size_hint_y=None, halign='left', valign='top')
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width - dp(12), None)))
        lbl.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
        sv.add_widget(lbl)
        box.add_widget(sv)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        close = Button(text='Close')
        btns.add_widget(close)
        box.add_widget(btns)
        popup = Popup(title='Network diagnostics', content=box, size_hint=(0.9, 0.8))
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()


class SettingsScreen(Screen):
    from kivy.properties import BooleanProperty
    info_text = StringProperty("")
    can_upload = BooleanProperty(False)
    last_status = StringProperty("")

    def on_pre_enter(self):
        try:
            auth = load_auth() or {}
            base = _get_base_url(auth)
            user = auth.get('username', '')
            mid = auth.get('manager_id', '')
            have_token = bool(auth.get('token'))
            role = auth.get('role', 'guest')
            # Allow upload if authenticated and either server-reported role is manager or username starts with 'manager'
            uname = (user or '').strip().lower()
            self.can_upload = bool(have_token and (role == 'manager' or uname.startswith('manager')))
            try:
                from db import get_db_path as _gdp
                dbp = _gdp()
            except Exception:
                dbp = '(unknown)'
            self.info_text = f"Server: {base}\nUser: {user}\nRole: {role}\nManager ID: {mid}\nAuthenticated: {'yes' if have_token else 'no'}\nDB Path: {dbp}"
        except Exception:
            self.info_text = ""
            self.can_upload = False

    def do_logout(self):
        clear_auth()
        app = App.get_running_app()
        try:
            if app:
                app.refresh_auth_cache()
        except Exception:
            pass
        if app and app.root:
            try:
                app.root.ids.sm.current = 'login'
                app.root.ids.bottomnav.opacity = 0
                app.root.ids.bottomnav.height = 0
                app.root.ids.bottomnav.disabled = True
            except Exception:
                pass
        try:
            if app:
                app._stop_guest_autodownload()
        except Exception:
            pass
        app.show_toast('Logged out')

    def _replace_db_with_file(self, tmp_path: str):
        """Apply a downloaded DB file to the running app.
        Prefer a live copy into the existing SQLite connection to avoid
        invalidating imported DB references. Fallback to atomic file
        replacement + reload if needed.
        """
        # 1) Try live copy via sqlite3 backup API
        try:
            import sqlite3 as _sqlite
            import db as _dbmod
            src = _sqlite.connect(tmp_path)
            try:
                # Copy contents of src into the existing destination connection
                # This keeps the same connection object alive for all callers.
                src.backup(_dbmod.DB)
                try:
                    src.close()
                except Exception:
                    pass
                # Remove temp file after successful copy
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                App.get_running_app().show_toast('Database updated')
                return
            finally:
                try:
                    src.close()
                except Exception:
                    pass
        except Exception:
            # Proceed to fallback
            pass
        # 2) Fallback: atomic file replace + reload (may invalidate old DB refs)
        try:
            target = get_db_path()
            tmp = target + '.tmpdl'
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            os.replace(tmp_path, tmp)
            os.replace(tmp, target)
            try:
                from db import reload_db
                reload_db()
            except Exception:
                pass
            App.get_running_app().show_toast('Database updated')
        except Exception:
            App.get_running_app().show_toast('Failed to replace DB')

    def do_download(self):
        auth = load_auth() or {}
        base = _get_base_url(auth)
        if not base:
            App.get_running_app().show_toast('Set server in Login first')
            return
        token = auth.get('token')
        manager_id = auth.get('manager_id')
        # Helper to perform GET with optional SSL verify
        def _get(url, headers=None, allow_insecure_retry=True):
            try:
                return requests.get(url, headers=headers or {}, timeout=30, stream=True)
            except requests.exceptions.SSLError:
                if allow_insecure_retry:
                    try:
                        return requests.get(url, headers=headers or {}, timeout=30, stream=True, verify=False)
                    except Exception:
                        raise
                raise
        try:
            attempted_urls = []
            start_ts = time.time()
            used_public = False
            # 1) Try private download if we have a token
            if token:
                url = f"{base}/db/download"
                headers = {'Authorization': f'Bearer {token}'}
                attempted_urls.append(url)
                r = _get(url, headers=headers)
                # If we get 401/403/404, fall back to public snapshot (e.g., guest token or no upload yet)
                if r.status_code in (401, 403, 404) and manager_id:
                    try:
                        r.close()
                    except Exception:
                        pass
                    url_pub = f"{base}/public/{manager_id}/snapshot.sqlite"
                    attempted_urls.append(url_pub)
                    r = _get(url_pub)
                    used_public = True
            else:
                # No token: use public snapshot directly
                url = f"{base}/public/{manager_id}/snapshot.sqlite"
                attempted_urls.append(url)
                r = _get(url)
                used_public = True

            if r.status_code != 200:
                # Try include a short server message
                msg = ''
                try:
                    body = r.text
                    if body:
                        msg = f" - {body[:200]}"  # trim
                except Exception:
                    msg = ''
                err = f"Download failed: {r.status_code}{msg}\nTried: {' -> '.join(attempted_urls)}"
                self.last_status = err
                App.get_running_app().show_toast(f'Download failed: {r.status_code}')
                try:
                    r.close()
                except Exception:
                    pass
                return

            # Save to a temp file (stream to avoid large memory)
            import tempfile
            fd, path = tempfile.mkstemp(prefix='dbdl_', suffix='.sqlite')
            os.close(fd)
            bytes_written = 0
            with open(path, 'wb') as f:
                try:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)
                finally:
                    try:
                        r.close()
                    except Exception:
                        pass
            self._replace_db_with_file(path)
            # After DB update, reset Bingo persistent state so downloaded DB view reflects prior server state
            try:
                # Compute the bingo_state.json path without requiring the Bingo screen to be instantiated
                from db import _get_persistent_db_path as _pdb
                p = _pdb('bingo_state.json')
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
            # If the Bingo screen is present, refresh it to reflect the new DB
            try:
                app = App.get_running_app()
                if app and app.root and hasattr(app.root, 'ids'):
                    try:
                        b = app.root.ids.sm.get_screen('bingo')
                        if b and hasattr(b, 'refresh_all'):
                            b.refresh_all()
                    except Exception:
                        pass
            except Exception:
                pass
            dur_ms = int((time.time() - start_ts) * 1000)
            src = "public" if used_public else "private"
            # Post-apply sanity: count some rows to help diagnose
            counts = ""
            try:
                import db as _dbmod
                try:
                    pcount = _dbmod.DB.execute("SELECT COUNT(*) FROM players").fetchone()[0]
                except Exception:
                    pcount = 'n/a'
                try:
                    ecount = _dbmod.DB.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                except Exception:
                    ecount = 'n/a'
                counts = f" | players={pcount} events={ecount}"
            except Exception:
                counts = ""
            self.last_status = f"Downloaded {bytes_written} bytes from {src} in {dur_ms} ms{counts}\nURL: {attempted_urls[-1]}"
            app = App.get_running_app()
            if app:
                app.show_toast('Download complete')
                try:
                    # Proactively refresh Bingo screen to reflect new DB
                    sm = app.root.ids.sm if app.root and hasattr(app.root, 'ids') else None
                    if sm:
                        try:
                            scr = sm.get_screen('bingo')
                        except Exception:
                            scr = None
                        if scr and hasattr(scr, 'refresh_from_db'):
                            scr.refresh_from_db()
                except Exception:
                    pass
        except Exception as e:
            self.last_status = 'Network error during download'
            App.get_running_app().show_toast('Network error during download')

    def do_upload(self):
        auth = load_auth() or {}
        base = _get_base_url(auth)
        token = auth.get('token')
        if not base or not token:
            self.last_status = 'Upload unavailable: not authenticated as manager'
            App.get_running_app().show_toast('Login as manager to upload')
            return
        url = f"{base}/db/upload"
        # Be explicit with headers to avoid some proxy quirks
        headers = {
            'Authorization': f'Bearer {token}',
            'Connection': 'close',
            'Expect': ''
        }
        db_path = get_db_path()
        # Ensure DB file exists and is readable
        try:
            size = os.path.getsize(db_path)
        except FileNotFoundError:
            self.last_status = f"DB file not found: {db_path}"
            App.get_running_app().show_toast('Database file not found')
            return
        except Exception as e:
            self.last_status = f"Cannot access DB file: {db_path} - {e}"
            App.get_running_app().show_toast('Cannot access database file')
            return

        def _upload(verify=True):
            with open(db_path, 'rb') as f:
                files = {'file': (os.path.basename(db_path) or 'events.sqlite', f, 'application/octet-stream')}
                return requests.post(url, headers=headers, files=files, timeout=60, verify=verify)

        # Optional preflight to provide clearer feedback if server is unreachable
        def _preflight():
            try:
                health = requests.get(f"{base}/health", timeout=8)
                return health.status_code == 200
            except requests.exceptions.SSLError:
                try:
                    health = requests.get(f"{base}/health", timeout=8, verify=False)
                    return health.status_code == 200
                except Exception:
                    return False
            except Exception:
                return False

        try:
            pre_ok = _preflight()
            start_ts = time.time()
            try:
                resp = _upload(verify=True)
            except requests.exceptions.SSLError:
                # Retry without SSL verification (some Android environments lack full root CA store)
                resp = _upload(verify=False)
            dur_ms = int((time.time() - start_ts) * 1000)
            if resp.status_code == 200:
                # Parse server JSON for extra details
                det = {}
                try:
                    det = resp.json()
                except Exception:
                    pass
                ver = det.get('version') if isinstance(det, dict) else None
                stored = det.get('stored') if isinstance(det, dict) else None
                self.last_status = f"Uploaded {size if size is not None else '?'} bytes in {dur_ms} ms\nURL: {url}\nServer stored: {stored or '-'} ver={ver or '-'}"
                App.get_running_app().show_toast('Upload complete')
            else:
                # Include short server message to help diagnose (e.g., 403 Forbidden)
                extra = ''
                try:
                    txt = resp.text
                    if txt:
                        extra = f" - {txt[:200]}"
                except Exception:
                    pass
                self.last_status = f"Upload failed: {resp.status_code}{extra}\nURL: {url}"
                App.get_running_app().show_toast(f'Upload failed: {resp.status_code}')
        except requests.exceptions.Timeout as e:
            self.last_status = f"Network timeout during upload after {url}. {type(e).__name__}: {e}"
            App.get_running_app().show_toast('Network timeout while uploading')
        except requests.exceptions.ConnectionError as e:
            hint = '' if pre_ok else ' (server unreachable - check internet/DNS or server status)'
            self.last_status = f"Connection error during upload to {url}: {e}{hint}"
            App.get_running_app().show_toast('Network error while uploading')
        except Exception as e:
            # Any other unexpected error
            self.last_status = f"Error during upload: {type(e).__name__}: {e}\nURL: {url}"
            App.get_running_app().show_toast('Network error while uploading')

    def reset_data(self):
        # Manager-only: two-step confirmation and reset of non-player data
        app = App.get_running_app()
        if not _is_manager():
            if app:
                app.show_toast('Only managers can reset data')
            return
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.popup import Popup
        # Step 2 action
        def _do_reset(*_):
            try:
                # Perform DB cleanup
                try:
                    from db import reset_non_player_data
                    ok = reset_non_player_data()
                except Exception:
                    ok = False
                # Also remove legacy bingo state file (prevents re-import)
                try:
                    # Reuse BingoScreen logic to resolve path without importing full class
                    try:
                        from db import _get_persistent_db_path as _gpp
                        legacy_path = _gpp('bingo_state.json')
                    except Exception:
                        legacy_path = os.path.join(os.path.expanduser('~'), '.draft_buddy', 'bingo_state.json')
                    if os.path.exists(legacy_path):
                        os.remove(legacy_path)
                except Exception:
                    pass
                # Refresh affected screens
                try:
                    sm = app.root.ids.sm if app and app.root and hasattr(app.root, 'ids') else None
                except Exception:
                    sm = None
                if sm:
                    try:
                        bs = sm.get_screen('bingo')
                        if bs and hasattr(bs, 'refresh_all'):
                            bs.refresh_all()
                        elif bs and hasattr(bs, 'refresh_from_db'):
                            bs.refresh_from_db()
                    except Exception:
                        pass
                    try:
                        ls = sm.get_screen('league')
                        if ls and hasattr(ls, '_load_leagues'):
                            ls._load_leagues()
                    except Exception:
                        pass
                    try:
                        es = sm.get_screen('eventslist')
                        if es and hasattr(es, 'refresh'):
                            es.refresh()
                    except Exception:
                        pass
                if app:
                    app.show_toast('Reset complete' if ok else 'Reset failed')
            except Exception:
                try:
                    if app:
                        app.show_toast('Reset failed')
                except Exception:
                    pass
        # Step 2 popup (with swapped Yes/No positions)
        def _open_step2(*_):
            box2 = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
            lbl2 = Label(text='This will erase: events, leagues, and bingo progress.\nPlayers are kept.\nNo automatic upload will occur.\nProceed?', halign='center')
            lbl2.bind(size=lambda inst, v: setattr(inst, 'text_size', (inst.width, None)))
            box2.add_widget(lbl2)
            row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            # Swap button positions compared to step 1
            btn_no2 = Button(text='No')
            btn_yes2 = Button(text='Yes')
            row2.add_widget(btn_no2)
            row2.add_widget(btn_yes2)
            box2.add_widget(row2)
            pop2 = Popup(title='Confirm reset (2/2)', content=box2, size_hint=(0.8, 0.4))
            btn_yes2.bind(on_release=lambda *_: (pop2.dismiss(), _do_reset()))
            btn_no2.bind(on_release=lambda *_: pop2.dismiss())
            pop2.open()
        # Step 1 popup
        box1 = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        lbl1 = Label(text='Manager reset: delete all events, leagues, and bingo progress.\nPlayers will remain.\nThis does NOT push to server automatically.\nAre you absolutely sure?', halign='center')
        lbl1.bind(size=lambda inst, v: setattr(inst, 'text_size', (inst.width, None)))
        box1.add_widget(lbl1)
        row1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        # Intentionally place Yes on the left and No on the right (unusual) for step 1
        btn_yes1 = Button(text='Yes')
        btn_no1 = Button(text='No')
        row1.add_widget(btn_yes1)
        row1.add_widget(btn_no1)
        box1.add_widget(row1)
        pop1 = Popup(title='Confirm reset (1/2)', content=box1, size_hint=(0.8, 0.4))
        btn_yes1.bind(on_release=lambda *_: (pop1.dismiss(), _open_step2()))
        btn_no1.bind(on_release=lambda *_: pop1.dismiss())
        pop1.open()


class BottomNav(BoxLayout):
    def on_kv_post(self, base_widget):
        # After kv is applied and sizes are known, center on current tab
        Clock.schedule_once(lambda dt: self.center_on(getattr(App.get_running_app().root.ids.sm, 'current', 'players')), 0)

    def _buttons_per_group(self):
        return 7  # players, events, league, bingo, drafttimer, lifetracker, settings

    def _group_offset(self):
        # Number of widgets before the middle group starts
        return self._buttons_per_group()  # first group length

    def _find_middle_button(self, target):
        try:
            row = self.ids.nav_row
        except Exception:
            return None
        labels = ['players', 'eventslist', 'league', 'bingo', 'drafttimer', 'lifetracker', 'settings']
        try:
            idx_in_group = labels.index(target)
        except ValueError:
            return None
        # middle group starts at offset
        start = self._group_offset()
        target_index = start + idx_in_group
        try:
            return row.children[::-1][target_index]  # children are reversed order
        except Exception:
            # Fallback by scanning buttons with text
            for w in row.children:
                if isinstance(w, Button):
                    t = target
                    if w.text == 'Players' and t == 'players':
                        return w
                    if w.text == 'Events' and t == 'eventslist':
                        return w
                    if w.text == 'League Tracker' and t == 'league':
                        return w
                    if w.text == 'Bingo' and t == 'bingo':
                        return w
                    if w.text == 'Draft Timer' and t == 'drafttimer':
                        return w
                    if w.text == 'Life Tracker' and t == 'lifetracker':
                        return w
            return None

    def center_on(self, target):
        # Center the selected middle-group button inside the scroll view
        try:
            sv = self.ids.nav_scroll
            row = self.ids.nav_row
        except Exception:
            return
        def _do_center(_dt):
            btn = self._find_middle_button(target)
            if not btn:
                return
            try:
                # X position of btn center within row
                bx = btn.x + btn.width / 2.0
                # Desired left of ScrollView content so that bx aligns to center of sv
                desired_left = bx - sv.width / 2.0
                # Clamp within content bounds
                max_left = max(0, row.width - sv.width)
                desired_left = max(0, min(desired_left, max_left))
                # Convert to scroll_x in [0,1]
                sv.scroll_x = 0 if max_left == 0 else desired_left / max_left
            except Exception:
                pass
        Clock.schedule_once(_do_center, 0)

    def normalize_scroll(self):
        # If user scrolls too far into group 1 or 3, snap back an equivalent position into group 2
        try:
            sv = self.ids.nav_scroll
            row = self.ids.nav_row
            per = self._buttons_per_group()
        except Exception:
            return
        # Approximate width per group
        try:
            # Compute width of first 'per' children (from left): use reversed indexing
            children = row.children[::-1]
            group_width = sum(w.width for w in children[0:per])
            total_width = row.width
            view = sv.width
            left = sv.scroll_x * max(0, total_width - view)
            # If we are within first group region, shift by +group_width
            if left < group_width * 0.5:
                left += group_width
            # If we are within last group region, shift by -group_width
            elif left > total_width - view - group_width * 0.5:
                left -= group_width
            max_left = max(0, total_width - view)
            sv.scroll_x = 0 if max_left == 0 else max(0, min(left, max_left)) / max_left
        except Exception:
            pass


class DraftTimerScreen(Screen):
    from kivy.properties import BooleanProperty
    can_play = BooleanProperty(True)
    can_pause = BooleanProperty(False)
    can_reset = BooleanProperty(False)
    can_prev = BooleanProperty(False)
    can_next = BooleanProperty(False)

    def _recompute_controls(self, *_):
        try:
            tw = getattr(self, '_timer_widget', None)
            if not tw:
                self.can_play = True
                self.can_pause = False
                self.can_reset = False
                self.can_prev = False
                self.can_next = False
                return
            # Determine states
            initial = (tw.current_round <= 0)
            running = (tw.timer_event is not None) and (not tw.paused)
            paused = bool(tw.paused)
            # Controls logic
            if initial:
                self.can_play = True
                self.can_pause = False
                self.can_reset = False
            elif paused:
                self.can_play = True
                self.can_pause = False
                self.can_reset = True
            else:
                # running or between-phase short break
                self.can_play = False
                self.can_pause = True
                self.can_reset = True
            # Prev/Next availability based on timer's ability to move
            try:
                self.can_prev = bool(tw.has_prev_phase())
            except Exception:
                self.can_prev = False
            try:
                self.can_next = bool(tw.has_next_phase())
            except Exception:
                self.can_next = False
        except Exception:
            self.can_play = True
            self.can_pause = False
            self.can_reset = False
            self.can_prev = False
            self.can_next = False

    def on_enter(self):
        cont = getattr(self, 'ids', {}).get('timer_container')
        if cont is not None:
            if not hasattr(self, '_timer_widget'):
                try:
                    self._timer_widget = DraftTimer()
                except Exception:
                    self._timer_widget = Label(text="Draft Timer failed to load", color=(1,1,1,1))
            cont.clear_widgets()
            cont.add_widget(self._timer_widget)
        # Start polling control state while on this screen
        try:
            if not hasattr(self, '_ctrl_ev') or self._ctrl_ev is None:
                self._ctrl_ev = Clock.schedule_interval(self._recompute_controls, 0.2)
        except Exception:
            pass
        self._recompute_controls()

    def on_leave(self):
        # Keep timer running in background, but stop polling UI state
        try:
            if hasattr(self, '_ctrl_ev') and self._ctrl_ev is not None:
                self._ctrl_ev.cancel()
        except Exception:
            pass
        self._ctrl_ev = None

    # Controls API for kv IconButtons
    def play_timer(self):
        try:
            if hasattr(self, '_timer_widget') and self._timer_widget:
                self._timer_widget.start_sequence(None)
        except Exception:
            pass
        self._recompute_controls()

    def pause_timer(self):
        try:
            if hasattr(self, '_timer_widget') and self._timer_widget:
                self._timer_widget.pause_timer(None)
        except Exception:
            pass
        self._recompute_controls()

    def reset_timer(self):
        try:
            if hasattr(self, '_timer_widget') and self._timer_widget:
                self._timer_widget.reset_all(None)
        except Exception:
            pass
        self._recompute_controls()

    def next_phase(self):
        try:
            if hasattr(self, '_timer_widget') and self._timer_widget:
                self._timer_widget.go_next_phase()
        except Exception:
            pass
        self._recompute_controls()

    def prev_phase(self):
        try:
            if hasattr(self, '_timer_widget') and self._timer_widget:
                self._timer_widget.go_prev_phase()
        except Exception:
            pass
        self._recompute_controls()


# ----------------------
# Pairing helpers (moved to pairing.py)
# ----------------------

# ----------------------
# App Setup
# ----------------------
class EventsApp(App):
    # Theme scaffold (Phase 2): centralized color tokens
    theme = DictProperty({
        'primary': (0.16, 0.47, 0.96, 1),
        'on_primary': (1, 1, 1, 1),
        'surface': (0.95, 0.95, 0.95, 1),
        'on_surface': (0.1, 0.1, 0.1, 1),
        'background': (0.98, 0.98, 0.98, 1),
        'success': (0.20, 0.70, 0.30, 1),
        'warning': (1.00, 0.75, 0.00, 1),
        'error': (0.85, 0.22, 0.22, 1),
    })
    # Reactive auth cache to drive UI bindings
    auth_role = StringProperty('guest')
    auth_username = StringProperty('')
    is_mgr = BooleanProperty(False)

    def refresh_auth_cache(self):
        try:
            auth = load_auth() or {}
            role = (auth.get('role') or '').strip().lower()
            uname = (auth.get('username') or '').strip()
            # Fallback: username prefix
            if role != 'manager' and uname.lower().startswith('manager'):
                role = 'manager'
            self.auth_role = role or 'guest'
            self.auth_username = uname
            self.is_mgr = bool(self.auth_role == 'manager' or self.auth_username.lower().startswith('manager'))
        except Exception:
            self.auth_role = 'guest'
            self.auth_username = ''

    # --- Guest auto-download scheduler ---
    def _stop_guest_autodownload(self):
        try:
            ev = getattr(self, '_guest_dl_ev', None)
            if ev is not None:
                try:
                    ev.cancel()
                except Exception:
                    pass
            self._guest_dl_ev = None
        except Exception:
            self._guest_dl_ev = None

    def _do_guest_download(self, *args):
        # Guard: only in guest mode
        try:
            if self.is_manager():
                return
        except Exception:
            pass
        # Use unified debounce + background execution
        try:
            if self._should_trigger_download():
                self._start_background_download(reason="auto")
        except Exception:
            pass

    def _start_guest_autodownload(self, fire_immediately=True):
        # Ensure only one scheduler exists
        self._stop_guest_autodownload()
        try:
            if self.is_manager():
                return
        except Exception:
            return
        from kivy.clock import Clock as _Clock
        if fire_immediately:
            try:
                _Clock.schedule_once(lambda dt: self._do_guest_download(), 0)
            except Exception:
                pass
        try:
            self._guest_dl_ev = _Clock.schedule_interval(lambda dt: self._do_guest_download(), 15.0)
        except Exception:
            self._guest_dl_ev = None

    # --- Conditional background download used by auto-schedule and navbar clicks ---
    def _should_trigger_download(self) -> bool:
        try:
            # Only trigger for guests (non-managers)
            if self.is_manager():
                return False
        except Exception:
            return False
        now = time.time()
        last = getattr(self, "_last_dl_ts", 0) or 0
        in_prog = bool(getattr(self, "_dl_in_progress", False))
        # Debounce: avoid if a download is running or ran within the last 15 seconds
        if in_prog:
            return False
        if last and (now - float(last) < 15.0):
            return False
        return True

    def _start_background_download(self, reason: str = "auto"):
        # Mark pre-emptively to reduce race with multiple triggers
        try:
            self._dl_in_progress = True
            if not getattr(self, "_last_dl_ts", None):
                self._last_dl_ts = 0.0
        except Exception:
            pass
        def _worker():
            try:
                sm = self.root.ids.sm if self.root and hasattr(self.root, 'ids') else None
                scr = sm.get_screen('settings') if sm else None
                if scr and hasattr(scr, 'do_download'):
                    scr.do_download()
            except Exception:
                pass
            finally:
                # Mark completion and timestamp
                try:
                    self._last_dl_ts = time.time()
                    self._dl_in_progress = False
                except Exception:
                    pass
                # After download, refresh current relevant screen
                try:
                    if not self.root or not hasattr(self.root, 'ids'):
                        return
                    sm2 = self.root.ids.sm
                    current = sm2.current if sm2 else None
                    def _refresh(_dt):
                        try:
                            if not sm2:
                                return
                            if current == 'players':
                                try:
                                    sm2.get_screen('players').refresh()
                                except Exception:
                                    pass
                            elif current == 'eventslist':
                                try:
                                    sm2.get_screen('eventslist').refresh()
                                except Exception:
                                    pass
                            elif current == 'event':
                                try:
                                    ev = sm2.get_screen('event')
                                    if hasattr(ev, 'refresh_matches'):
                                        ev.refresh_matches()
                                except Exception:
                                    pass
                            elif current == 'league':
                                try:
                                    sm2.get_screen('league').refresh()
                                except Exception:
                                    pass
                            elif current == 'bingo':
                                try:
                                    b = sm2.get_screen('bingo')
                                    if hasattr(b, 'refresh_from_db'):
                                        b.refresh_from_db()
                                    elif hasattr(b, 'refresh_all'):
                                        b.refresh_all()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    Clock.schedule_once(_refresh, 0)
                except Exception:
                    pass
        try:
            import threading
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
        except Exception:
            # Fallback: run inline (may block UI)
            try:
                _worker()
            except Exception:
                pass

    def _maybe_upload_after_write(self, reason: str = ""):
        # Only for managers; guests never upload
        try:
            if not self.is_manager():
                return
        except Exception:
            return
        # Debounce and avoid overlapping uploads
        now = time.time()
        try:
            last = float(getattr(self, "_last_ul_ts", 0) or 0)
            if getattr(self, "_ul_in_progress", False):
                return
            if last and (now - last) < 2.0:
                return
        except Exception:
            pass
        def _worker():
            try:
                sm = self.root.ids.sm if self.root and hasattr(self.root, 'ids') else None
                scr = sm.get_screen('settings') if sm else None
                if scr and hasattr(scr, 'do_upload'):
                    scr.do_upload()
            except Exception:
                pass
            finally:
                try:
                    self._last_ul_ts = time.time()
                    self._ul_in_progress = False
                except Exception:
                    pass
        try:
            import threading
            self._ul_in_progress = True
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
        except Exception:
            try:
                _worker()
            except Exception:
                pass

    def build(self):
        Builder.load_file("ui.kv")
        # Create root container with fixed BottomNav and a ScreenManager (id: sm)
        from kivy.factory import Factory
        root = Factory.Root()
        sm = root.ids.sm
        # Ensure transition is SlideTransition with short duration
        sm.transition = SlideTransition(duration=0.18)
        # Add all screens to ScreenManager
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(PlayersScreen(name="players"))
        sm.add_widget(NewPlayerScreen(name="newplayer"))
        sm.add_widget(CreateEventDetailsScreen(name="createevent_details"))
        sm.add_widget(CreateEventScreen(name="createevent"))
        sm.add_widget(EventsListScreen(name="eventslist"))
        sm.add_widget(EventScreen(name="event"))
        sm.add_widget(SeatingScreen(name="seating"))
        sm.add_widget(StandingsScreen(name="standings"))
        sm.add_widget(LeagueScreen(name="league"))
        sm.add_widget(BingoScreen(name="bingo"))
        sm.add_widget(DraftTimerScreen(name="drafttimer"))
        sm.add_widget(LifeTrackerScreen(name="lifetracker"))
        # Set initial screen based on saved auth
        try:
            auth = load_auth()
            if auth and (auth.get('token') or auth.get('manager_id')):
                sm.current = 'players'
                try:
                    root.ids.bottomnav.opacity = 1
                    root.ids.bottomnav.height = dp(56)
                    root.ids.bottomnav.disabled = False
                except Exception:
                    pass
            else:
                sm.current = 'login'
                try:
                    root.ids.bottomnav.opacity = 0
                    root.ids.bottomnav.height = 0
                    root.ids.bottomnav.disabled = True
                except Exception:
                    pass
        except Exception:
            sm.current = 'login'
            try:
                root.ids.bottomnav.opacity = 0
                root.ids.bottomnav.height = 0
                root.ids.bottomnav.disabled = True
            except Exception:
                pass
        # Refresh auth cache to drive UI bindings
        try:
            self.refresh_auth_cache()
        except Exception:
            pass
        # Prefer the keyboard to overlap the UI (avoid panning the whole page)
        try:
            # below_target keeps the focused widget visible without moving the whole layout
            Window.softinput_mode = 'below_target'
        except Exception:
            pass
        # Bind back/escape key to close the keyboard instead of exiting
        try:
            Window.bind(on_keyboard=self._on_keyboard)
            # Some android providers deliver back via on_key_down and on_request_close as well
            Window.bind(on_key_down=self._on_key_down)
            Window.bind(on_request_close=self._on_request_close)
        except Exception:
            pass
        # Debounce storage for back handling
        self._back_debounce_until = 0
        # Start guest auto-download on app open if applicable
        try:
            if not self.is_manager():
                self._start_guest_autodownload(fire_immediately=True)
            else:
                self._stop_guest_autodownload()
        except Exception:
            pass
        return root

    def is_manager(self):
        try:
            role = (self.auth_role or '').strip().lower()
            uname = (self.auth_username or '').strip().lower()
            return bool(role == 'manager' or uname.startswith('manager'))
        except Exception:
            return _is_manager()

    def show_toast(self, message: str, timeout: float = 2.0):
        """Show a lightweight toast message at the bottom center, auto-dismiss."""
        try:
            layer = self.root.ids.toast_layer
        except Exception:
            return
        try:
            from kivy.factory import Factory
            toast = Factory.Toast(text=message)
        except Exception:
            return
        # Initial placement: bottom center above BottomNav (~56dp) with margin
        margin = dp(12)
        bottom_bar_h = dp(56)
        layer.add_widget(toast)
        # Position after next frame to get proper size
        def _place(_dt):
            try:
                toast.x = (layer.width - toast.width) / 2.0
                toast.y = bottom_bar_h + margin
            except Exception:
                pass
            # Fade in
            try:
                Animation.cancel_all(toast)
                Animation(opacity=1.0, d=0.18, t='out_quad').start(toast)
            except Exception:
                pass
            # Schedule fade out and removal
            def _dismiss(_dt2):
                try:
                    anim = Animation(opacity=0.0, d=0.18, t='out_quad')
                    def _remove(*_a):
                        try:
                            if toast.parent:
                                toast.parent.remove_widget(toast)
                        except Exception:
                            pass
                    anim.bind(on_complete=lambda *_: _remove())
                    anim.start(toast)
                except Exception:
                    try:
                        if toast.parent:
                            toast.parent.remove_widget(toast)
                    except Exception:
                        pass
            Clock.schedule_once(_dismiss, max(0.1, float(timeout)))
        Clock.schedule_once(_place, 0)

    def switch_tab(self, target: str):
        """Switch between bottom tabs with direction based on relative position.
        target: one of 'players','eventslist','league','bingo','drafttimer','lifetracker'
        """
        try:
            sm = self.root.ids.sm
        except Exception:
            return
        order = ['players', 'eventslist', 'league', 'bingo', 'drafttimer', 'lifetracker', 'settings']
        try:
            cur = sm.current
            i_cur = order.index(cur) if cur in order else None
            i_tgt = order.index(target)
            if i_cur is not None:
                n = len(order)
                d_fwd = (i_tgt - i_cur) % n   # moving rightward through list
                d_back = (i_cur - i_tgt) % n  # moving leftward through list
                if d_back < d_fwd:
                    sm.transition.direction = 'right'  # shorter to go backward
                elif d_fwd < d_back:
                    sm.transition.direction = 'left'   # shorter to go forward
                else:
                    # Equal distance (opposites in even-sized list) — default to left
                    sm.transition.direction = 'left'
            else:
                sm.transition.direction = 'left'
        except Exception:
            # Fallback to default left
            try:
                sm.transition.direction = 'left'
            except Exception:
                pass
        sm.current = target
        # Center the selected item in the bottom nav
        try:
            from kivy.clock import Clock as _Clock
            _Clock.schedule_once(lambda dt: self.root.ids.bottomnav.center_on(target), 0)
        except Exception:
            pass
        # Trigger background download on navbar click with 15s debounce (guest only)
        try:
            if self._should_trigger_download():
                self._start_background_download(reason="nav")
        except Exception:
            pass

    def _consume_back_if_keyboard(self):
        """Close soft keyboard (by unfocusing any TextInput) and report whether we consumed the back.
        Also handles a short debounce to swallow duplicate back events fired by some providers.
        """
        import time as _t
        # Debounce repeated back within 300ms
        try:
            if _t.time() < getattr(self, '_back_debounce_until', 0):
                return True
        except Exception:
            pass
        consumed = False
        try:
            from kivy.uix.textinput import TextInput
            def unfocus_in_tree(widget):
                nonlocal consumed
                try:
                    for w in widget.walk():
                        if isinstance(w, TextInput) and getattr(w, 'focus', False):
                            w.focus = False
                            consumed = True
                except Exception:
                    pass
            # Check popups/overlays first
            for child in list(Window.children):
                unfocus_in_tree(child)
            # Then the app root
            if self.root:
                unfocus_in_tree(self.root)
            # If the soft keyboard is visible, also consume
            try:
                if getattr(Window, 'keyboard_height', 0) and Window.keyboard_height > 0:
                    consumed = True
            except Exception:
                pass
        except Exception:
            return False
        if consumed:
            try:
                self._back_debounce_until = _t.time() + 0.3
            except Exception:
                pass
        return consumed

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        # Android back / Desktop Escape; some providers use 1001 for back
        if key in (27, 1001):
            return self._consume_back_if_keyboard()
        return False

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        # Mirror handling here for back key on platforms that call on_key_down instead
        if key in (27, 1001):
            return self._consume_back_if_keyboard()
        return False

    def _on_request_close(self, *args, **kwargs):
        # On Android, pressing back can request app close. If keyboard is up, close it instead.
        if self._consume_back_if_keyboard():
            return True  # prevent app close
        return False

    def on_pause(self):
        # Android: app is going to background; keep state, pause schedules if needed
        try:
            # Pause DraftTimer updates if present to save CPU (state is wall-clock based)
            scr = self.root.ids.sm.get_screen("drafttimer")
            if hasattr(scr, "_timer_widget") and hasattr(scr._timer_widget, "_cancel_schedule"):
                scr._timer_widget._cancel_schedule()
        except Exception:
            pass
        # Return True to allow pause on Android
        return True

    def on_resume(self):
        # Resync timers when app returns to foreground
        try:
            sm = self.root.ids.sm
            current = sm.current
        except Exception:
            current = None
        # Event round timer: recompute remaining and reschedule
        try:
            if current == "event":
                sm.get_screen("event").maybe_start_timer()
        except Exception:
            pass
        # DraftTimer: reschedule updates using wall-clock remaining
        try:
            if current == "drafttimer":
                scr = sm.get_screen("drafttimer")
                if hasattr(scr, "_timer_widget") and hasattr(scr._timer_widget, "on_app_resume"):
                    scr._timer_widget.on_app_resume()
        except Exception:
            pass
        # Ensure guest auto-download continues after resume (avoid duplicate schedules)
        try:
            if not self.is_manager():
                self._start_guest_autodownload(fire_immediately=False)
            else:
                self._stop_guest_autodownload()
        except Exception:
            pass

if __name__ == "__main__":
    EventsApp().run()