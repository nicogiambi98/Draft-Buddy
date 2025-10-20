[app]
title = Draft Buddy
device = iphone
package.name = draftbuddy
package.domain = org.example
version = 0.1.0

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,svg,wav,ogg,mp3,txt,json
# Package assets
source.include_patterns = assets/*

# iOS build: DO NOT include pyjnius
# Keep requirements platform-neutral
requirements = python3,kivy==2.2.1,sqlite3,cython==0.29.36,requests,certifi

orientation = portrait
fullscreen = 0
log_level = 2

# Optional iOS-specific hints (uncomment and set as needed)
# ios.codesign.allowed = true
# ios.codesign.development_team = YOUR_TEAM_ID
# ios.codesign.provisioning_profile = Your_Provisioning_Profile
# ios.kivy_ios_url = https://github.com/kivy/kivy-ios

[buildozer]
log_level = 2
warn_on_root = 1
