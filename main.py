# main.py
# Minimal Companion-lite Events MVP
# Requires: kivy

import sqlite3
import random
import os
import time
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from pairing import get_name_for_event_player, compute_standings, generate_round_one, compute_next_round_pairings
from timer import DraftTimer
from kivy.core.window import Window
from kivy.utils import platform
from kivy.metrics import dp

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
        Label:
            markup: True
            text: "[b]Table Seating[/b]"
        ScrollView:
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
        Label:
            id: standings_title
            markup: True
            text: "[b]Standings[/b]"
        ScrollView:
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
# UI Widgets
# ----------------------
class MatchRow(BoxLayout):
    p1_name = StringProperty("")
    p2_name = StringProperty("")
    score1 = NumericProperty(0)
    score2 = NumericProperty(0)
    match_id = NumericProperty(0)
    bye = NumericProperty(0)

    def cycle_score(self, side):
        # cycles 0 -> 1 -> 2 -> 0 and writes to DB
        if self.bye:
            return
        if side == 1:
            self.score1 = (self.score1 + 1) % 3
            DB.execute("UPDATE matches SET score_p1 = ? WHERE id = ?", (self.score1, self.match_id))
        else:
            self.score2 = (self.score2 + 1) % 3
            DB.execute("UPDATE matches SET score_p2 = ? WHERE id = ?", (self.score2, self.match_id))
        DB.commit()
        # visually update (buttons bound to values)


# ----------------------
# Screens
# ----------------------
class PlayersScreen(Screen):
    def on_enter(self):
        self.refresh()

    def open_add_player(self):
        # Create a lightweight popup to add a new player without leaving the list
        try:
            from kivy.uix.textinput import TextInput
            content = BoxLayout(orientation='vertical', spacing=8, padding=10)
            ti = TextInput(hint_text='Player name', multiline=False)
            # Trim leading spaces as user types
            def _lstrip(_inst, _val):
                try:
                    _inst.text = _inst.text.lstrip()
                except Exception:
                    pass
            ti.bind(text=_lstrip)
            # Buttons row
            btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=8)
            btn_save = Button(text='Save')
            btn_cancel = Button(text='Cancel')
            btns.add_widget(btn_save)
            btns.add_widget(btn_cancel)
            content.add_widget(ti)
            content.add_widget(btns)
            pop = Popup(title='Add New Player', content=content, size_hint=(0.9, 0.4))
            
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
        name = (name or '').strip()
        if not name:
            try:
                popup.dismiss()
            except Exception:
                pass
            return
        DB.execute("INSERT INTO players (name) VALUES (?)", (name,))
        DB.commit()
        try:
            popup.dismiss()
        except Exception:
            pass
        self.refresh()

    def _add_player_row(self, pid, name):
        row = BoxLayout(size_hint_y=None, height=dp(56))
        lbl = Label(text=f"{name} (id:{pid})", color=(1,1,1,1))
        btn_del = Button(text="Delete", size_hint_x=None, width=dp(200))
        try:
            btn_del.text_size = (None, None)
            btn_del.shorten = True
            btn_del.font_size = '18sp'
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
        self.refresh()


class NewPlayerScreen(Screen):
    def save_player(self, name):
        if not name or not name.strip():
            return
        DB.execute("INSERT INTO players (name) VALUES (?)", (name.strip(),))
        DB.commit()
        self.manager.current = "players"


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
        cur = DB.execute("SELECT id, name FROM players ORDER BY name")
        rows = cur.fetchall()
        for pid, name in rows:
            # Skip players already added to the event (they will appear in the Selected list)
            if pid in self.selected_ids:
                continue
            if filt and filt not in name.lower():
                continue
            row = BoxLayout(size_hint_y=None, height=dp(56))
            lbl = Label(text=name)
            def add_player(instance, _pid=pid):
                self.selected_ids.add(_pid)
                # Rebuild lists so the player disappears here and appears in Selected
                self.refresh_players()
                self.update_selected_view()
            btn = Button(text="Add", size_hint_x=None, width=dp(120))
            try:
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
                    name = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
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
                row = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
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

    def start_event(self, name, etype, rounds, round_time):
        # collect selected players and guests, then navigate to SeatingScreen
        chosen = []
        # Build from selected_ids to avoid dependence on filter/UI list
        if not hasattr(self, 'selected_ids'):
            self.selected_ids = set()
        for pid in self.selected_ids:
            row = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
            if row:
                chosen.append((pid, row[0]))
        # plus any guests explicitly added
        chosen.extend(self.guest_list)
        if len(chosen) < 2:
            return
        # Let seating screen handle event creation and round 1
        seat_screen = self.manager.get_screen("seating")
        # sanitize rounds and round_time
        r = int(rounds) if rounds and str(rounds).isdigit() else 3
        rt_mins = int(round_time) if round_time and str(round_time).isdigit() else 30
        rt = rt_mins * 60
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
        # load sounds
        try:
            self.tick_sound = SoundLoader.load("assets/tick.wav")
        except Exception:
            self.tick_sound = None
        self.animal_sounds = []
        for name in ["bark", "meow", "geese", "bird", "cow"]:
            try:
                snd = SoundLoader.load(f"assets/{name}.wav")
                if snd:
                    self.animal_sounds.append(snd)
            except Exception:
                pass

    def load_event(self, event_id):
        self.event_id = event_id
        row = DB.execute("SELECT name, rounds, current_round, status FROM events WHERE id=?", (event_id,)).fetchone()
        if not row:
            return
        name, rounds, current_round, status = row
        self.event_title = name
        self.current_round = current_round
        # fetch round duration
        try:
            rt = DB.execute("SELECT round_time FROM events WHERE id=?", (event_id,)).fetchone()
            self.round_duration = int(rt[0]) if rt and rt[0] is not None else 0
        except Exception:
            self.round_duration = 0
        self.ids.matches_grid.clear_widgets()
        self.refresh_matches()

    def refresh_matches(self):
        self.ids.matches_grid.clear_widgets()
        cur = DB.execute("SELECT id, round, player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=? AND round=?",
                        (self.event_id, self.current_round if self.current_round>0 else 1))
        rows = cur.fetchall()
        if not rows:
            # load round 1 if current_round is 0
            if self.current_round == 0:
                self.current_round = 1
                DB.execute("UPDATE events SET current_round=? WHERE id=?", (1, self.event_id))
                DB.commit()
                rows = DB.execute("SELECT id, round, player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=? AND round=?", (self.event_id,1)).fetchall()
        for mid, rnd, p1, p2, s1, s2, bye in rows:
            p1name = get_name_for_event_player(self.event_id, p1)
            p2name = get_name_for_event_player(self.event_id, p2) if p2 else "BYE"
            row_widget = MatchRow()
            row_widget.p1_name = p1name
            row_widget.p2_name = p2name
            row_widget.score1 = s1
            row_widget.score2 = s2
            row_widget.match_id = mid
            row_widget.bye = bye
            self.ids.matches_grid.add_widget(row_widget)
        # update round label
        self.ids.round_label.text = f"Round: {self.current_round}"
        # update next button label depending on last round
        e = DB.execute("SELECT rounds FROM events WHERE id=?", (self.event_id,)).fetchone()
        if e:
            total_rounds = e[0]
            if self.current_round >= total_rounds:
                self.ids.next_btn.text = "Finish Event"
            else:
                self.ids.next_btn.text = "Next Round"
        # start or reset the round timer when the round changes
        self.maybe_start_timer()

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
                if self.animal_sounds:
                    snd = random.choice(self.animal_sounds)
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

    def next_round(self):
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
        self.current_round = next_round
        self.refresh_matches()

    def close_event(self, abort_current_round=True):
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
        except Exception:
            pass

    def _create_event_if_needed(self):
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
                pname = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
                pname = pname[0] if pname else f"Player {pid}"
                self.selected.append((pid, pname))
                self.seating.append((pid, pname))
        # Render list
        cont = self.ids.seating_list
        cont.clear_widgets()
        for idx, (pid, name) in enumerate(self.seating, start=1):
            cont.add_widget(Label(text=f"{idx}. {name}" + (" (guest)" if pid is None else ""), size_hint_y=None, height=28, color=(1,1,1,1)))

    def confirm_and_begin(self):
        # If event already exists (created when arriving to seating), just generate round one and go
        if getattr(self, 'event_id', 0):
            generate_round_one(self.event_id)
            self.manager.get_screen("event").load_event(self.event_id)
            self.manager.current = "event"
            return
        # Fallback: create event now (should be rare)
        self._create_event_if_needed()
        generate_round_one(self.event_id)
        self.manager.get_screen("event").load_event(self.event_id)
        self.manager.current = "event"


class StandingsScreen(Screen):
    event_id = NumericProperty(0)

    def show_for_event(self, event_id):
        self.event_id = event_id
        row = DB.execute("SELECT name FROM events WHERE id=?", (event_id,)).fetchone()
        title = row[0] if row else "Standings"
        self.ids.standings_title.text = f"[b]{title} — Final Standings[/b]"
        self.refresh()

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
                        height=28,
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
        from kivy.metrics import dp
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
                                    height=28,
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
                                     height=28,
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
    pass


class BingoScreen(Screen):
    pass


class DraftTimerScreen(Screen):
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

    def on_leave(self):
        # Do not auto-pause when leaving the screen; allow timer to continue running in background
        # This ensures switching pages does not stop the draft timer.
        return


# ----------------------
# Pairing helpers (moved to pairing.py)
# ----------------------

# ----------------------
# App Setup
# ----------------------
class EventsApp(App):
    def build(self):
        Builder.load_file("ui.kv")
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(PlayersScreen(name="players"))
        sm.add_widget(NewPlayerScreen(name="newplayer"))
        sm.add_widget(CreateEventScreen(name="createevent"))
        sm.add_widget(EventsListScreen(name="eventslist"))
        sm.add_widget(EventScreen(name="event"))
        sm.add_widget(SeatingScreen(name="seating"))
        sm.add_widget(StandingsScreen(name="standings"))
        sm.add_widget(LeagueScreen(name="league"))
        sm.add_widget(BingoScreen(name="bingo"))
        sm.add_widget(DraftTimerScreen(name="drafttimer"))
        return sm

    def on_pause(self):
        # Android: app is going to background; keep state, pause schedules if needed
        try:
            # Pause DraftTimer updates if present to save CPU (state is wall-clock based)
            scr = self.root.get_screen("drafttimer")
            if hasattr(scr, "_timer_widget") and hasattr(scr._timer_widget, "_cancel_schedule"):
                scr._timer_widget._cancel_schedule()
        except Exception:
            pass
        # Return True to allow pause on Android
        return True

    def on_resume(self):
        # Resync timers when app returns to foreground
        try:
            current = self.root.current
        except Exception:
            current = None
        # Event round timer: recompute remaining and reschedule
        try:
            if current == "event":
                self.root.get_screen("event").maybe_start_timer()
        except Exception:
            pass
        # DraftTimer: reschedule updates using wall-clock remaining
        try:
            if current == "drafttimer":
                scr = self.root.get_screen("drafttimer")
                if hasattr(scr, "_timer_widget") and hasattr(scr._timer_widget, "on_app_resume"):
                    scr._timer_widget.on_app_resume()
        except Exception:
            pass

if __name__ == "__main__":
    EventsApp().run()