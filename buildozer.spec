[app]
title = Draft Buddy
package.name = draftbuddy
package.domain = org.example

version = 0.1.0

# Project source
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,svg,db,wav,ogg,mp3,txt,json
# Package assets and the optional prebuilt database into the APK
source.include_patterns = assets/*, events.db

# Core requirements (SQLite is needed at runtime)
requirements = python3,kivy,sqlite3

# UI settings
orientation = portrait
fullscreen = 0

# Logging
log_level = 2

# Kivy bootstrap
p4a.bootstrap = sdl2

# Optional: icon/presplash (uncomment if you have them)
# icon.filename = assets/icon.png
# presplash.filename = assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
# Target and min API
android.api = 31
android.minapi = 21

# Build a single architecture first (faster and simpler)
android.archs = arm64-v8a

# NDK API level used by recipes
p4a.ndk_api = 21

# Pin Cython used by p4a recipes (fixes pyjnius build with Cython 3)
p4a.cython = 0.29.36
# Extra arg to ensure the pin is applied across build chains
p4a.extra_args = --cython=0.29.36

# If you need internet or other permissions, add here (not needed for internal DB)
# android.permissions = INTERNET

# Optional: use the latest p4a (can help with compatibility)
# p4a.branch = develop

[app:python]
# Optional Python build flags (usually not needed)