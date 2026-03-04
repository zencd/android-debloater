import os
from pathlib import Path

MIN_PY_VER = (3, 9)
APP_HOME = Path.home() / '.android-debloater'
APP_HOME.mkdir(parents=True, exist_ok=True)

UAD_URL = 'https://raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation/refs/heads/main/resources/assets/uad_lists.json'
CT_JSON = 'application/json'
HOST = 'localhost'
DEBUG = os.getenv('DEBUG', '').lower() in {'1', 'true'}
PORT = 59861  # (55000..60999] is ok

PROFILE_DIR = APP_HOME / 'profile1'
APKS_DIR = PROFILE_DIR / 'apk'
ALL_PERMISSIONS_FILE = PROFILE_DIR / 'permissions.txt'

PROJECT_DIR = Path(__file__).parent.parent

STD_PERM_PFX = 'android.permission.'

UAD_LOCAL = APP_HOME / 'uad_lists.json'
USER_PREFS = APP_HOME / 'user-prefs.txt'
APP_ICON_DIR = APP_HOME / 'icons'
APP_ICON_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = APP_HOME / 'audit.log'
MAIN_LOG_FILE = APP_HOME / 'main.log'
APP_REPO = 'https://github.com/zencd/debloater'
APP_META_PATH = APP_HOME / 'app-meta.json'