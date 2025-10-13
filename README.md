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

## Android build on Windows using WSL (Ubuntu)
If you are on Windows, the most reliable way to build the Android APK is inside WSL (Windows Subsystem for Linux) using an Ubuntu distribution. Buildozer will download and use the Android SDK/NDK within WSL.

Prerequisites:
- Windows 10/11 with WSL enabled and an Ubuntu distro installed (see: https://learn.microsoft.com/windows/wsl/install)
- At least ~10–12 GB of free disk space for SDK/NDK and caches

Recommended project location:
- For best performance and fewer path/permission issues, keep the project inside the Linux filesystem, e.g. /home/<your-user>/Draft-Buddy rather than under /mnt/c/...
  - You can clone the repo directly in WSL: `git clone https://.../Draft-Buddy.git`

Install required packages inside WSL (Ubuntu):
- Open your Ubuntu (WSL) terminal and run:

```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git zip unzip openjdk-17-jdk \
  libffi-dev libssl-dev build-essential ccache zlib1g-dev liblzma-dev libncurses5 libtinfo5
python3 -m pip install --user --upgrade pip
python3 -m pip install --user buildozer cython virtualenv
# Ensure ~/.local/bin is on PATH for normal shells (optional convenience)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

Build the APK:
- From the project root inside WSL, run the sanitized environment command below to avoid Windows PATH leaking into the build (important on WSL):

```
env -i HOME="$HOME" \
  PATH="/usr/bin:/bin:/usr/local/bin:$HOME/.local/bin" \
  LANG="C.UTF-8" SHELL="/bin/bash" \
  buildozer -v android debug
```

Notes:
- The first build can take a long time as Buildozer downloads the Android SDK, NDK, and other tools.
- The resulting APK will be in the bin/ directory. You can copy it back to Windows with, for example:
  - `cp bin/*.apk /mnt/c/Users/<YourUser>/Desktop/` (adjust path as needed)
- If Java version issues arise, ensure Java 17 is active (OpenJDK 17 is installed above). You can check with `java -version`.
- If you encounter SSL or network issues during SDK download, try again or ensure your corporate proxy is configured inside WSL.

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



## Run the FastAPI server locally (no Docker/Railway)
If you don’t use Railway or Docker, you can run the bundled FastAPI server directly with Python. This is the simplest way to host the upload/download API and public snapshot on your own machine or VPS.

Quick start
- Create and activate a virtual environment (recommended)
  - Windows (PowerShell):
    - python -m venv .venv
    - .venv\Scripts\Activate.ps1
  - Linux/macOS:
    - python3 -m venv .venv
    - source .venv/bin/activate
- Install the server dependencies from the server folder:
  - pip install -r server/requirements.txt
- Optional: set environment variables to control behavior
  - HOST: bind address (default 0.0.0.0)
  - PORT or SERVER_PORT: port number (default 8000)
  - STORAGE_DIR: directory for uploaded DB snapshots (default ./storage)
  - JWT_SECRET: secret key for signing tokens (please change it in production!)
- Create server/users.txt with your users (one per line):
  - Example:
    manager:password@default
    judge:1234@leagueB
- Run the server
  - Windows:  python server\main.py
  - Linux/macOS:  python server/main.py
- Verify it is up
  - Open http://localhost:8000/health (or your chosen host/port)

Notes
- The Dockerfile and railway.toml at the project root are optional and can be ignored if you’re running the server directly.
- The Android/desktop app and this API are decoupled; you only need the API if you want remote upload/download and a public snapshot.

## Minimal server on Railway (upload/download + public snapshot)
This repo now contains a tiny FastAPI server you can deploy to Railway to enable:
- Manager login (one token per manager; offline-friendly)
- Upload your local SQLite to the server (overwrite)
- Download the server copy back to your device (overwrite local)
- Public, read-only snapshot for players

What you get
- Endpoints:
  - GET /health
  - POST /auth/login {username, password, remember}
  - POST /db/upload (Bearer token; multipart with the SQLite file)
  - GET  /db/download (Bearer token)
  - GET  /public/{manager_id}/snapshot.sqlite (public)
  - GET  /public/{manager_id}/version (public; integer timestamp)
- Ephemeral storage friendly: if Railway wipes storage after a restart, simply re-upload from the manager app.

Folder layout
- server/main.py          FastAPI app
- server/requirements.txt Python deps (fastapi, uvicorn, PyJWT)
- Dockerfile              Container for Railway
- railway.toml            Railway config (healthcheck, env hints)

Environment variables (set these in Railway → Variables)
- JWT_SECRET: change this to a long random secret
- USERS: comma-separated users; format username:password@manager_id
  - Example: manager:password@leagueA,judge:1234@leagueB
- STORAGE_DIR: where to store uploaded files (default /app/storage)

Deploy to Railway (which repo to import?)
Two ways to deploy on Railway. Pick ONE and follow its steps:

Option A — Import this monorepo (what you have now)
- What to import: this Draft-Buddy repo (root).
- Expected files in the imported repo root:
  - Dockerfile (builds and runs the FastAPI server from the server/ folder)
  - railway.toml (Railway service config)
  - server/ (contains main.py and requirements.txt)
- Steps:
  1) Push this repo to GitHub (or your remote).
  2) In Railway: New Project → Deploy from Repository → select this repo.
  3) Railway will detect Dockerfile at the root and build it.
  4) In Railway → Variables, set:
     - JWT_SECRET = a-very-long-secret
     - USERS = manager:password@default (or your own)
     - STORAGE_DIR = /app/storage
  5) Deploy and check https://<app>.up.railway.app/health

Option B — Use a separate, server-only repo (clean separation)
- What to import: a dedicated repo that contains ONLY the server files at its root.
- Expected files in that server repo root:
  - main.py (FastAPI app — the current server/main.py moved to repo root)
  - requirements.txt (the current server/requirements.txt moved to repo root)
  - Dockerfile (same content, adjusted to copy requirements.txt and main.py from repo root)
  - railway.toml
- Steps:
  1) Create a new repo (e.g., Draft-Buddy-Server) and copy the contents of server/ to its root.
  2) Move/adjust Dockerfile and railway.toml into that repo’s root.
  3) Push the server repo to GitHub.
  4) In Railway: New Project → Deploy from Repository → select the server repo.
  5) Set Variables as above and deploy; check /health.

Where should railway.toml and Dockerfile live?
- They must be at the ROOT of the repo you import into Railway.
  - If you import this monorepo: keep Dockerfile and railway.toml at this project’s root (already set up).
  - If you import a separate server repo: place Dockerfile and railway.toml at that server repo’s root.

Notes on storage
- Railway’s container filesystem may be ephemeral. This setup tolerates that: managers can re-upload their local DB at any time.
- If you later want persistence, switch STORAGE_DIR to a Railway volume or stream files to S3-compatible storage (R2/B2).

Quick test (PowerShell)
- Login (replace URL):
  $body = @{ username = 'manager'; password = 'password'; remember = $true } | ConvertTo-Json
  $resp = Invoke-RestMethod -Method Post -Uri 'https://<app>.up.railway.app/auth/login' -ContentType 'application/json' -Body $body
  $token = $resp.access_token

- Upload your local DB (replace path):
  Invoke-RestMethod -Method Post -Uri 'https://<app>.up.railway.app/db/upload' -Headers @{ Authorization = "Bearer $token" } -Form @{ file = Get-Item './events.db' }

- Download it back:
  Invoke-WebRequest -Method Get -Uri 'https://<app>.up.railway.app/db/download' -Headers @{ Authorization = "Bearer $token" } -OutFile './downloaded.db'

- Players read snapshot:
  Invoke-WebRequest -Uri 'https://<app>.up.railway.app/public/default/snapshot.sqlite' -OutFile './snapshot.sqlite'

Client integration notes
- Manager app can store the JWT (remember me) and work offline.
- On Publish: POST /db/upload with the local events.db file.
- On Pull: GET /db/download and overwrite local events.db.
- Guest/Player: download /public/{manager_id}/snapshot.sqlite read-only.

Persistence options
- By default, Railway container storage may be ephemeral. This setup accepts that (simply re-upload if lost).
- If you want durability later, swap the storage to an external S3-compatible bucket (Cloudflare R2/B2) and stream uploads/downloads there.


## Make server/ its own Git repo inside this project (submodule or subtree)
You have two clean ways to make the existing `server/` folder its own Git repository while keeping this app’s main repository intact.

Option A — Git submodule (recommended if you want an independent repo cloned inside this project)
- Outcome: `server/` is a separate repo with its own remote; the parent tracks a pointer to a specific commit of `server/`.
- When to pick: You want to version the server independently and maybe reuse it elsewhere.

Steps (PowerShell, from the project root):
1) Create a new empty repo on GitHub/GitLab, e.g. `Draft-Buddy-Server`.
2) Prepare current folder (temporarily stash server files so we can replace the folder with a submodule clone):
   - git status
   - git add .
   - git commit -m "Save work before converting server to submodule"
   - mkdir server_tmp
   - robocopy server server_tmp /E
   - git rm -r --cached server
   - Remove-Item -Recurse -Force server
3) Add the submodule (this will create a fresh `server/` checked out from the new remote):
   - git submodule add https://github.com/<your-user>/Draft-Buddy-Server.git server
4) Restore your existing files into the submodule and commit in the submodule:
   - robocopy server_tmp server /E
   - cd server
   - git add .
   - git commit -m "Initial import of FastAPI server"
   - git push -u origin main  # or master, depending on your default branch
   - cd ..
5) Commit and push the submodule reference in the parent repo:
   - git add .gitmodules server
   - git commit -m "Add server as a git submodule"
   - git push
6) Clean up temp folder:
   - Remove-Item -Recurse -Force server_tmp

Daily usage with submodules
- After cloning the parent: `git clone <parent>` then `git submodule update --init --recursive`
- To pull latest server changes from inside `server/`: `git pull` then in parent `git add server && git commit -m "Bump server submodule"`
- To switch the parent to a different server commit: `cd server && git checkout <sha-or-branch>` then commit the new pointer in parent.

Option B — Git subtree (single repo experience, remote history included)
- Outcome: Parent remains a single repo. `server/` content is pushed/pulled to a separate remote while staying part of the parent’s history.
- When to pick: You prefer not to manage submodules and want `git clone` to just work with no extra steps.

Initial setup (PowerShell):
1) Create a new empty repo for the server, e.g., `Draft-Buddy-Server` (no need to move files).
2) Add the server remote as a subtree and push the existing folder content:
   - git remote add server-remote https://github.com/<your-user>/Draft-Buddy-Server.git
   - git subtree push --prefix server server-remote main

Later: push new server-only changes upstream
- Make edits under `server/` in the parent repo as usual
- Push subtree changes: `git subtree push --prefix server server-remote main`

Pull changes from the server repo back into the parent
- `git subtree pull --prefix server server-remote main --squash`

Notes and pitfalls
- Do not nest a plain `.git` repo inside the parent unless it is a formal submodule; Git will ignore nested repos and it can be confusing.
- Submodules give you strict separation but require the extra `git submodule update --init` step after cloning.
- Subtrees keep life simple for collaborators who don’t want to deal with submodules, at the cost of slightly more complex push/pull commands for the `server/` part.
- On Windows, `robocopy` is used above for reliable folder copies. If `robocopy` is unavailable, you can use `Copy-Item -Recurse` instead.



## Server user configuration (users.txt file)

The server (server/main.py) now reads its user list from a file named server/users.txt. This keeps user lists out of source control. Do not commit this file.

Available variables and defaults
- STORAGE_DIR: Directory where uploaded SQLite files and public snapshots are stored. Default: ./storage
- JWT_SECRET: Secret key used to sign access tokens. Default: draftbuddyclandestini! (change this in production)
- HOST: Bind address when running server/main.py directly. Default: 0.0.0.0
- Port note: When running server/main.py directly, the port is currently fixed to 80. Use a reverse proxy, container port mapping, or run uvicorn explicitly if you need a different port.

users.txt format
- Path: server/users.txt (next to server/main.py)
- Each entry is username:password@manager_id
- Provide multiple entries separated by commas or newlines
- Example (single line): manager:superSecret123@clandestini,guest:guest@clandestini
- Example (multiline file):
  manager:superSecret123@clandestini
  player1:safePwd@clandestini
- Invalid lines are ignored and a warning is logged. If no valid users are provided, login will fail until you configure the file.

Security guidance
- Always set a strong JWT_SECRET in production; rotating it invalidates existing tokens.
- Keep server/users.txt out of version control. It is listed in .gitignore; verify it remains untracked.
- Use strict file permissions on server/users.txt if other users share the machine/container.

Quick setup examples

Windows PowerShell (local dev)
- Create server\users.txt with:
  manager:<pwd>@clandestini
  guest:guest@clandestini
- Optionally set STORAGE_DIR and JWT_SECRET:
  $env:STORAGE_DIR = "C:\\draftbuddy_storage"
  $env:JWT_SECRET = "<very-long-random>"
- Run:
  python server\main.py

Linux/macOS shell
- Create server/users.txt with entries (username:password@manager_id)
- export STORAGE_DIR=/var/lib/draftbuddy
- export JWT_SECRET="$(openssl rand -hex 32)"
- python3 server/main.py

Systemd service (Linux)
- Place credentials at /opt/Draft-Buddy/server/users.txt (or symlink to a root‑only file)
- /etc/systemd/system/draftbuddy.service:
  [Unit]
  Description=Draft Buddy Server
  After=network.target
  [Service]
  WorkingDirectory=/opt/Draft-Buddy
  Environment=JWT_SECRET=<very-long-random>
  Environment=STORAGE_DIR=/var/lib/draftbuddy
  ExecStart=/usr/bin/python3 server/main.py
  Restart=on-failure
  [Install]
  WantedBy=multi-user.target
- sudo systemctl daemon-reload && sudo systemctl enable --now draftbuddy

Docker
- Ensure the container has a file at /app/server/users.txt. Example docker-compose.yml:
  services:
    draftbuddy:
      image: python:3.11-slim
      working_dir: /app
      volumes:
        - ./:/app
        - draftbuddy_data:/storage
        - ./secrets/users.txt:/app/server/users.txt:ro
      environment:
        STORAGE_DIR: /storage
        JWT_SECRET: ${JWT_SECRET}
      command: ["python", "server/main.py"]
      ports:
        - "8080:80"  # hostPort:containerPort
  volumes:
    draftbuddy_data:
- Then: JWT_SECRET=$(openssl rand -hex 32) docker compose up -d

Railway/Render/Heroku-style platforms
- Ensure your deployment includes a file at /app/server/users.txt. Options:
  - Commit a placeholder users.txt locally but keep real credentials injected at build/deploy time (do not push secrets).
  - Use a platform secret/volume mechanism to place users.txt at /app/server/users.txt.
- Also set:
  STORAGE_DIR = /data (or platform-recommended persistent path)
  JWT_SECRET = <very-long-random>
- If the platform requires binding to a specific PORT env var, prefer running uvicorn explicitly via a start command, e.g.:
  uvicorn server.main:app --host 0.0.0.0 --port $PORT

Verifying your configuration
- Check health: curl http://<host>:<port>/health
- Attempt login: POST http://<host>:<port>/auth/login with JSON {"username":"manager","password":"<pwd>","remember":true}
- On successful login, you’ll receive an access_token; use it as: Authorization: Bearer <token>
- Upload DB (manager only): POST /db/upload multipart/form-data with file=<your.sqlite>
- Public snapshot: GET /public/<manager_id>/snapshot.sqlite and /public/<manager_id>/version

Troubleshooting
- No users configured: ensure server/users.txt exists and is readable; the server logs a warning at startup.
- Invalid users.txt entry: check format username:password@manager_id; see server logs for which entry was skipped.
- 401 on requests: verify Authorization header format (Bearer <token>) and that JWT_SECRET hasn’t been rotated since token issuance.


## Bingo persistence

Bingo progress is stored inside the main SQLite database (events.db) so it syncs with the server alongside other data. The app maintains:
- bingo_players: one row per player with 9 cells (c0..c8) marked 0/1
- bingo_meta: a single row tracking which rows/cols/diagonals/full are taken and who won them

On first run after this change, if a legacy bingo_state.json is found in the persistent app folder and the bingo tables are empty, the app will import that JSON into the DB and delete the file. You do not need to manage bingo_state.json anymore.
