# Android Debloat & Backup

## Prepare

- Download this Python script:
  - unpack https://github.com/zencd/debloater/archive/refs/heads/master.zip
  - or `git clone --branch master --depth 1 "https://github.com/zencd/debloater"`
- Install Python 3.9+, add it to the PATH
- Install `adb`, add it to the PATH
  - `brew install android-platform-tools` (macos)
  - https://developer.android.com/tools/releases/platform-tools (all systems)

## Run

- `python3 web.py`

## Features & benefits

- Keep your personal list of bloatware 
- Debloat smartphone in one pass
- Disable, enable, uninstall and reinstall packages individually
- Description of every important package is available via [UAD](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation) community
- Backup/restore user-installed apps
- Backup permissions that user have set manually, restore them

## Tested with

- Xiaomi 12x, Poco X4 GT, Poco X7 Pro, Pixel 5a, Pixel 7, Oneplus 13T, Oneplus 15, Moto X50 Ultra
- ADB 36.0.2, protocol 1.0.41 
- MacOS 15.7, Windows 10
