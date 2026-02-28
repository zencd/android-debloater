# Android Debloat & Backup

## Prepare

- Download this Python script:
  - unpack https://github.com/zencd/debloater/archive/refs/heads/master.zip
  - or `git clone --branch master --depth 1 https://github.com/zencd/debloater`
- Install Python 3.9+, add it to the PATH
- Install `adb`, add it to the PATH
  - `brew install android-platform-tools` (macos)
  - https://developer.android.com/tools/releases/platform-tools (all systems)

## Run

- `python3 web.py`

## Features

- Debloat unwanted software in one-pass
- User preferences are remembered
- Backup/restore user-installed apps
- Backup/restore permissions that user set manually
