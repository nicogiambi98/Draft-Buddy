[app]
title = Draft Buddy
package.name = draftbuddy
package.domain = org.example
version = 0.1.0

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,svg,wav,ogg,mp3,txt,json
# Package assets (do not bundle the runtime DB)
source.include_patterns = assets/*

# Android build: include pyjnius explicitly
# Pin stack compatible with Cython 0.29.x
requirements = python3,kivy==2.2.1,sqlite3,pyjnius==1.4.2,cython==0.29.36,requests,certifi

orientation = portrait
fullscreen = 0
log_level = 2
p4a.bootstrap = sdl2

# Android API targets and permissions
android.api = 31
android.minapi = 21
android.permissions = INTERNET, ACCESS_NETWORK_STATE
# Force single-arch while stabilizing
android.archs = arm64-v8a
p4a.ndk_api = 21
# Ensure p4a uses Cython 0.29.x and only one arch
p4a.cython = 0.29.36
p4a.extra_args = --arch=arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
