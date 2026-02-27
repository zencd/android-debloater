# Prepare

- PC
  - Download this Python script (address?)
  - Install Python 3.9+, add it to the PATH
  - Install adb, add it to the PATH
    - `brew install android-platform-tools` (macos)
    - https://developer.android.com/tools/releases/platform-tools (all systems)
- Android
  - Become developer, pressing a lot of times on the OS version
  - Developer options:
    - ☑ 'USB debugging'
    - ☑ 'USB Debugging Security Settings' (if exists, Poco)
    - ☑ 'Install via USB' (if exists, Poco)
    - Disable permission monitoring (if exists, ColorOS/OxygenOS)
    - Xiaomi/Poco: you may be required to insert a SIM 
- Attach a device to PC, allow it on PC, allow it on Android 

# Run

- `python3 web.py`
- you can try executable `python` also

# Usage

- A browser to be opened
- Tab 'Debloat':
  - Mark unwanted packages as 'Uninstall'
  - Press 'Debloat'
  - The selected packages will be uninstalled all at once
  - Your choices will be remembered
- Tab 'Apps':
  - Attach a device where all your favorite apps are installed
  - Press 'Backup apps'
  - Those apps/permissions will be saved locally
  - Attach a fresh device
  - Press 'Restore apps'
  - Those app/permissions will be enrolled onto the new device
  - Xiaomi/Poco: you might be required to confirm every app install, take a look at phone's display

# References

https://xdaforums.com/t/unable-to-grant-permissions-using-adb.3812658/

java.lang.SecurityException: grantRuntimePermission: Neither user 2000 nor current process has android.permission.GRANT_RUNTIME_PERMISSIONS.
