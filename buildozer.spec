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
requirements = python3,kivy==2.3.0,sqlite3,pyjnius==1.5.1,cython==3.0.10

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
android.api = 31
android.minapi = 21
android.archs = arm64-v8a
p4a.ndk_api = 21


# Ensure Cython 3 is used consistently (works with pyjnius >= 1.6.1)
p4a.cython = 3.0.10
p4a.extra_args = --cython=3.0.10

# If you need internet or other permissions, add here (not needed for internal DB)
# android.permissions = INTERNET

# Optional: use the latest p4a (can help with compatibility)
p4a.branch = develop

[app:python]
# Optional Python build flags (usually not needed)