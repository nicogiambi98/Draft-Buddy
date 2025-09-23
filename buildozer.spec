[app]
title = Draft Buddy
package.name = draftbuddy
package.domain = org.example
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,svg,db,wav,ogg,mp3,txt,json
# Include folders/files (relative to project root) into the APK
source.include_patterns = assets/*, events.db

version = 0.1.0
requirements = python3,kivy,sqlite3
orientation = portrait
fullscreen = 0
log_level = 2

# If you have an icon/presplash, set the paths here (optional)
# icon.filename = assets/icon.png
# presplash.filename = assets/presplash.png

# Kivy bootstrap (default)
p4a.bootstrap = sdl2

# If your app needs internet, you can add permissions here (none needed for internal DB)
# android.permissions = INTERNET

# If you want to keep the screen on during app usage (optional)
# android.wakelock = True

# If you use Android scoped storage or external files (not recommended unless needed)
# manage_external_storage = 0

# Set this to the main entry point file of your app
# If your app's main module is "main.py", leave as is
# (Buildozer will find main.py automatically)

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
# Target and min API. Match your installed SDK if you’ve pre-installed it; otherwise, p4a will download.
android.api = 31
android.minapi = 21

# Build a single architecture first (faster and simpler). Add others later if needed.
android.archs = arm64-v8a

# Use NDK API 21 for maximum compatibility (default for p4a)
p4a.ndk_api = 21

# Optional: speed up Gradle by disabling daemon in CI contexts
# android.gradle_daemon = False

# If you see Java heap errors, you can raise this:
# android.gradle_args = -Xmx4096m

# Enable copy-libs to ship Python stdlib in the APK (p4a handles this by default on modern versions)
# p4a.local_recipes =

[app:python]
# If you need to pass environment flags to your Python build, you can do it here
# (usually not needed for a basic Kivy + sqlite3 app)