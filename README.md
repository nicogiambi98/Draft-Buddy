# Draft Buddy

Draft Buddy is a lightweight Kivy app to run casual or store events with Swiss-like rounds, a built-in draft timer, and quick player management. It works on desktop and mobile (Android via Buildozer) and stores data in a local SQLite database.

## Highlights (current state)
- Player management
  - Add/delete players and quick filtering
  - Support for guests alongside registered players
- Event creation and management
  - Create events (type: draft/sealed/cube), choose rounds and round time
  - Select players and randomize initial seating; supports odd counts (automatic BYE handling)
  - Round 1 pairings by seating (opposite-at-table rule)
  - Next-round pairings: Swiss-ish algorithm, avoids rematches when possible and assigns BYE fairly
  - Per-match score entry (game wins) with quick tap cycling 0–2
  - Event timer with pause/resume and auto-carry-over across app pause/resume
  - Close event and view standings at any time
- Standings
  - Match Points (Win=3, Draw=1, Loss=0; BYE counts as a win)
  - MW% and GW% with 0.33 floor where applicable
  - OMW% and OGW% (opponents’ averages), excluding BYEs
  - Sorted by MP, OMW%, GW%, OGW%, Name
- Draft Timer
  - Predefined timer sequences (e.g., draft phases) with visual countdown
  - Fun animal sound cues and assets packaged in the app
  - Pause/Reset; persists resume timing when app regains focus
- UI/UX
  - Centralized styles in ui.kv: typography tokens and Primary/Secondary buttons
  - Consistent spacing using dp(); keyboard-friendly TextInputs with hint_text
  - Simple bottom navigation across main screens
- Android packaging
  - Buildozer spec included with p4a/cython pinning and assets packaging

## Screens at a glance
- Players: manage roster and filter
- Events: list existing/open events and create new ones
- Seating: view randomized table seating before Round 1
- Event: track rounds, edit per-match scores, and control the timer
- Standings: computed tie-breakers and table
- Draft Timer: standalone multi-phase timer with sounds
- League and Bingo: placeholders for future features

## Project structure
```
Draft-Buddy/
├─ main.py          # App, screens logic, navigation, timer integration
├─ ui.kv            # Visual styles and screen layouts (typography, buttons, views)
├─ timer.py         # DraftTimer widget with sequences, sounds, and controls
├─ pairing.py       # Standings and Swiss-like pairing algorithms
├─ db.py            # SQLite initialization and migrations (events.db)
├─ events.db        # Local SQLite DB file (created on first run or prepackaged)
├─ assets/          # Sound assets (tick.wav, animal sounds, etc.)
├─ buildozer.spec   # Android build configuration (requirements, assets, arch)
└─ UI_TODO.md       # Roadmap and UI/UX improvement plan
```

## Installation (desktop)
Prerequisites:
- Python 3.10+ recommended
- pip and a working compiler toolchain (platform-specific)

1) Create and activate a virtual environment
- Windows (PowerShell)
  - python -m venv .venv
  - .venv\\Scripts\\Activate.ps1

2) Install dependencies
- pip install "kivy==2.2.1"

3) Run
- python main.py

Notes:
- The app will create an events.db SQLite database in the project directory on first run if not present.
- On desktop, the window is sized to a portrait-like ratio for easier mobile UI testing.

## Android build (via Buildozer)
Prerequisites (on Linux/macOS):
- Python 3.10+ (system), Buildozer, Android SDK/NDK toolchains pulled by buildozer
- See https://github.com/kivy/buildozer for environment setup

Steps:
1) Ensure requirements in buildozer.spec are suitable for your system
2) From the project root:
   - buildozer android debug
3) Find the generated APK in the bin/ directory and install to your device

Spec notes:
- requirements pins kivy==2.2.1, pyjnius, sqlite3, cython 0.29.x
- assets (sounds) and optional prebuilt events.db are packaged
- Currently configured to arm64-v8a for stability

## Database overview
Tables are created automatically on first run (db.py):
- players(id, name, created_at)
- events(id, name, type, rounds, round_time, status, current_round, created_at, round_start_ts)
- event_players(id, event_id, player_id, guest_name, seating_pos, UNIQUE(event_id, player_id, guest_name))
- matches(id, event_id, round, player1, player2, score_p1, score_p2, bye)

A small migration ensures events.round_start_ts exists when upgrading from older DBs.

## Pairings and standings details
- Round 1: players are seated, then paired opposite at table; odd counts get a random BYE (awarded as 2–0 win).
- Next rounds: players are sorted by Match Points; a backtracking algorithm pairs by closest MP, avoids rematches where possible, and falls back to a greedy approach if needed; if odd, the lowest-MP player without a previous BYE gets the BYE.
- Standings computation includes:
  - MP, record (W-L-D)
  - MWP = (wins + 0.5*draws)/matches
  - GWP with 0.33 floor; BYE counts as 2–0
  - OMW%/OGW% as averages of opponents’ MWP/GWP (with 0.33 floor), excluding BYEs

## Sounds and timer
- Assets in assets/ include tick.wav and animal sounds used for cues.
- The DraftTimer supports multiple modes/sequences and keeps time consistent when the app resumes from pause.

## What changed since the original README
This repository evolved significantly:
- Moved styling to ui.kv with reusable typography and button components
- Added comprehensive Create Event flow with player filtering, guest support, and randomized seating
- Implemented Event screen with per-match score entry and round control
- Added Swiss-like pairing and full standings with common tiebreakers
- Introduced a standalone Draft Timer with sequences and sound cues
- Added Buildozer configuration for Android packaging and pinned toolchain versions
- Added a simple migration path for the events table (round_start_ts)
- Documented a forward-looking UI/UX roadmap in UI_TODO.md

## Roadmap / TODO
See UI_TODO.md for a phased plan covering navigation polish, reusable components, light/dark theme scaffold, toasts, empty states, animations, accessibility, and performance hygiene. Highlights to come:
- BottomNav reusable widget across screens
- Theming tokens and dark mode
- Improved timer visualization (progress ring/bar)
- Toast/snackbar for non-blocking feedback
- Size classes and larger text option

## Contributing / Notes
- Keep DB work off the UI thread for longer operations; use Clock.schedule_once or threads as needed.
- Prefer dp() spacing and the provided token widgets in ui.kv to keep visuals consistent.
- PRs that move inline KV out of Python and introduce reusable UI components are welcome.

## License
This project is provided as-is; if you have specific licensing needs, please add a LICENSE file and update this section accordingly.

# Draft Buddy

This is a minimal events manager built with Kivy.

## Data storage (Where is the DB file?)

The app uses a persistent SQLite database named `events.db`.

- On desktop (Windows/macOS/Linux): it's stored in a per-user application folder under your home directory: `~/.draft_buddy/events.db` (on Windows: `C:\Users\<YourUser>\.draft_buddy\events.db`).
- On Android/iOS: it uses the app's private storage directory.

On first run, if no DB exists in the persistent location, the app will seed it by copying the `events.db` that ships alongside the source code (the one in the project folder). After that, the app reads and writes only the persistent copy.

Tip: If you want to inspect the live data on PC, open the file located at the path above. The `events.db` in the project root is just a seed and won’t be updated after the first run.

## League Tracker

- Only closed events count toward league stats.
- League Score = `100 * Winrate * (1 - e^(-0.05 * Matches))` where Winrate = `(wins + 0.5 * draws) / matches`.
- The league screen shows all participants who played at least one eligible match in the league window. Guests are included (by guest name).
- You can close the current league (with confirmation); closing a league automatically opens a new one starting now.
- Use the spinner to switch between current and past leagues.
