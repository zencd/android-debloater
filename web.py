import dataclasses
import json
import logging
import os.path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.request
from datetime import datetime
from functools import cache
from json import JSONDecodeError
from pathlib import Path
from typing import Optional
import webbrowser

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

APP_HOME = Path.home() / '.android-fast-tuner'
APP_HOME.mkdir(parents=True, exist_ok=True)


def running_in_venv():
    return sys.prefix != sys.base_prefix


def ensure_running_in_venv():
    print(f'Python interpreter: {sys.executable}, not suitable')
    # force execution in a venv bcs we can fail installing extra packages otherwise
    venv = APP_HOME / 'venv'
    exes = [venv / 'bin/python', venv / 'Scripts/python.exe']
    python_exe = next(iter(exe for exe in exes if exe.exists()), None)
    if not python_exe:
        cmd = [sys.executable, '-m', 'venv', str(venv)]
        print(f'Exec: {shlex.join(cmd)}')
        p = subprocess.Popen(cmd, shell=False, stdout=None, stderr=None, text=True, encoding='utf-8')
        stdout, stderr = p.communicate()
        rc = p.returncode & 0xFF
        assert rc == 0, f'Failed creating venv: {venv}'
        python_exe = next(iter(exe for exe in exes if exe.exists()), None)
        assert python_exe, f'Failed creating venv: {venv}'
    cmd = [str(python_exe)] + sys.argv
    print(f'Exec: {shlex.join(cmd)}')
    p = subprocess.Popen(cmd, shell=False, stdout=None, stderr=None, text=True, encoding='utf-8')
    stdout, stderr = p.communicate()
    rc = p.returncode & 0xFF
    sys.exit(rc)


if not running_in_venv():
    ensure_running_in_venv()

print(f'Python interpreter: {sys.executable}')

try:
    import pyaxmlparser  # it reads apk file meta
except ImportError:
    print('Installing module pyaxmlparser...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyaxmlparser'])
    print('Module pyaxmlparser successfully installed')
    import pyaxmlparser

logging.getLogger('pyaxmlparser').setLevel(logging.ERROR)  # fighting warning "res1 is not zero"


# todo embed resources
# todo ERR_CONNECTION_REFUSED not toasted
# todo show local apps even if no device connected
# todo verify uad_lists.json before rewriting it
# todo have a local uad_lists.json copy
# todo recommended => safe
# todo reload packages once at backend?


class JsonDB:

    def __init__(self, path: Path):
        self.path = path
        self.data = dict()
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, encoding='utf-8') as fd:
                try:
                    data = json.load(fd)
                except JSONDecodeError as e:
                    print(f'ERROR: failed reading JSON from {self.path}: {e}')
                    data = dict()
                self.data = data
                return data
        else:
            self.data = dict()
            return self.data

    def dump(self):
        # todo write to a temp file first, bcs once I lost file content after ctrl+C
        assert self.data is not None
        with open(self.path, 'w', encoding='utf-8') as fd:
            json.dump(self.data, fp=fd, ensure_ascii=False, indent=2)


class PackageCache:
    def __init__(self, cmd: str):
        self.cmd = shlex.split(cmd)

    @cache
    def get(self) -> set[str]:
        rc, stdout, stderr = exec_(self.cmd)
        assert rc == 0, f'Command failed with rc: {rc}, text: {stderr}'
        lines = stdout.splitlines()
        return set(extract_package_names(lines))


class PackageCaches:

    def __init__(self):
        self.enabled = PackageCache('adb shell pm list packages -e --user 0')
        self.enabled_and_disabled = PackageCache('adb shell pm list packages --user 0')
        self.enabled_and_uninstalled = PackageCache('adb shell pm list packages -u --user 0')
        self.user_installed = PackageCache('adb shell pm list packages -3 --user 0')

    @cache
    def get_enabled(self):
        return self.enabled.get()

    @cache
    def get_disabled(self):
        return self.enabled_and_disabled.get() - self.enabled.get()

    @cache
    def get_uninstalled(self):
        return self.enabled_and_uninstalled.get() - self.enabled_and_disabled.get()

    @cache
    def get_user_installed(self):
        return self.user_installed.get()


UAD_URL = 'https://raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation/refs/heads/main/resources/assets/uad_lists.json'
CT_JSON = 'application/json'
HOST = 'localhost'
DEBUG = os.getenv('DEBUG', '').lower() in {'1', 'true'}
PORT = 59861  # (55000..60999] is ok

# PROFILE_DIR = APP_HOME / 'profile-empty'
PROFILE_DIR = APP_HOME / 'profile1'
# PROFILE_DIR = APP_HOME / 'profile-mama-12x'
APKS_DIR = PROFILE_DIR / 'apk'
ALL_PERMISSIONS_FILE = PROFILE_DIR / 'permissions.txt'

FAKE_ANSWERS_DIR = Path(__file__).parent / 'fake-answers'
FAKE_ANSWERS_MODE = 'none'
# FAKE_ANSWERS_MODE = 'record'
# FAKE_ANSWERS_MODE = 'play'

STD_PERM_PFX = 'android.permission.'

APP_META_FILE = JsonDB(APP_HOME / 'app-meta.json')
UAD_LOCAL = APP_HOME / 'uad_lists.json'
USER_PREFS = APP_HOME / 'user-prefs.txt'
APP_ICON_DIR = APP_HOME / 'icons'
APP_ICON_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = APP_HOME / 'audit.log'
APP_REPO = 'https://github.com/zencd/debloater'

FILTER_TO_STATUS = {'deviceUninstalled': 'uninstalled', 'deviceDisabled': 'disabled'}


def create_audit_logger():
    level = logging.INFO
    log_file = AUDIT_LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('audit_logger')
    logger.setLevel(level)
    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)
    return logger


audit = create_audit_logger()


####################################################
## ABSTRACT UTILS
####################################################

def ensure_key(data: dict, key: str, default_maker):
    if key in data:
        return data[key]
    else:
        data[key] = default_maker()
        return data[key]


def open_browser(url):
    webbrowser.open(url)


def open_local_file_or_folder(path: str):
    if not os.path.exists(path):
        print(f'Missing path: {path}')
        return
    system = platform.system()
    if system == 'Windows':
        if os.path.isdir(path):
            subprocess.Popen(['explorer', path])
        else:
            os.startfile(path)
    elif system == 'Darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])  # Linux


def ensure_dir(path: Path):
    if path.exists():
        assert path.is_dir()
    else:
        path.mkdir(parents=True, exist_ok=True)


def read_file(fname):
    with open(fname, 'r', encoding='utf-8') as fd:
        return fd.read()


def write_file(fname, content):
    ensure_dir(fname.parent)
    with open(fname, 'w', encoding='utf-8') as fd:
        fd.write(content)


def exec_(cmd: list, stdout: Optional[int] = subprocess.PIPE, stderr: Optional[int] = subprocess.PIPE):
    cmd_join = ' '.join(cmd)
    slug = cmd_join.replace(' ', '_')
    slug = re.sub(r'[^a-zA-Z0-9_]+', '_', slug)
    slug = re.sub(r'__+', '_', slug).strip('_')
    fake_answer_file_stdout = FAKE_ANSWERS_DIR / f'{slug}.out.txt'
    fake_answer_file_stderr = FAKE_ANSWERS_DIR / f'{slug}.err.txt'
    print('Exec:', cmd_join)
    if FAKE_ANSWERS_MODE == 'play':
        stdout = read_file(fake_answer_file_stdout) if fake_answer_file_stdout.exists() else ''
        stderr = read_file(fake_answer_file_stderr) if fake_answer_file_stderr.exists() else ''
        return 0, stdout, stderr
    else:
        p = subprocess.Popen(cmd, shell=False, stdout=stdout, stderr=stderr, text=True, encoding='utf-8')
        stdout, stderr = p.communicate()
        if FAKE_ANSWERS_MODE == 'record':
            write_file(fake_answer_file_stdout, stdout or '')
            write_file(fake_answer_file_stderr, stderr or '')
        rc = p.returncode & 0xFF
        return rc, stdout, stderr


def load_json(fname, fallback):
    if os.path.exists(fname):
        with open(fname, encoding='utf-8') as fd:
            return json.load(fd)
    return fallback


def read_text_lines(fname):
    with open(fname, encoding='utf-8') as fd:
        return fd.readlines()


def extract_block(lines: list, start_inclusive, end_exclusive):
    result = []

    start_found = False
    for i, line in enumerate(lines):
        if re.match(start_inclusive, line):
            result.append(line)
            lines = lines[i + 1:]
            start_found = True
            break

    if not start_found:
        return []

    for line in lines:
        if re.match(end_exclusive, line):
            break
        else:
            result.append(line)

    return result


####################################################
## USER PREFS, A CUSTOM DATA FORMAT
####################################################

@dataclasses.dataclass
class Resolution:
    resolution: str
    package: str
    unparsed: list[str]
    comment: str


@dataclasses.dataclass
class ResolutionList:
    __items: list[Resolution]
    __item_by_package: dict[str, Resolution]

    def __init__(self):
        self.__items = []
        self.__item_by_package = dict()

    @property
    def items(self):
        return self.__items

    def get_resolution(self, package):
        return self.__item_by_package.get(package)

    def add(self, r: Resolution):
        self.__items.append(r)
        self.__item_by_package[r.package] = r


def parse_plain_resolution(line: str):
    sharp = line.find('#')
    comment = ''
    if sharp >= 0:
        comment = line[sharp + 1:].lstrip('# \t').rstrip()
        line = line[0:sharp].strip()
    if not line:
        return None
    words = re.split(r'\s+', line)
    if len(words) < 2:
        return None
    resolution = words[0]
    package = words[1]
    unparsed = words[2:]
    return Resolution(resolution=resolution, package=package, comment=comment, unparsed=unparsed)


def load_plain_resolutions(in_file: Path) -> ResolutionList:
    res = ResolutionList()
    if in_file.exists():
        with open(in_file, encoding='utf-8') as fp:
            for line in fp:
                if r := parse_plain_resolution(line):
                    res.add(r)
    return res


def resolution_to_str(r: Resolution):
    s = f'{r.resolution}  {r.package}'
    for word in r.unparsed:
        s += f'  {word}'
    comment = convert_multi_line_description_to_one_line(r.comment)
    if comment:
        grid = 8  # beautify comments
        s += ' ' * (grid - (len(s) % grid))
        s += f'# {comment}'
    return s


def convert_multi_line_description_to_one_line(s: str):
    lines = s.splitlines()
    lines = map(str.strip, lines)
    lines = filter(bool, lines)
    res = ''
    for line in lines:
        if res:
            res += ' ' if res[-1] == '.' else ' - '
        res += line
    return res


def dump_resolutions(out_file: Path, resolutions: ResolutionList):
    # XXX using a temp file to prevent data loss on abort
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        ensure_dir(out_file.parent)
        debloat, keep, review, others = [], [], [], []
        for r in resolutions.items:
            if r.resolution == 'new':
                continue
            list_ = debloat if r.resolution == 'del' \
                else keep if r.resolution == 'keep' \
                else review if r.resolution == 'review' \
                else others
            list_.append(r)
        groups = [debloat, keep, review, others]
        with open(temp_file.name, 'w', encoding='utf-8') as fp:
            for group in groups:
                for r in sorted(group, key=lambda x: x.package):
                    print(resolution_to_str(r), file=fp)
    shutil.move(temp_file.name, out_file)


####################################################
## READ-ONLY HELPERS
####################################################

def read_app_permissions(package):
    cmd = ['adb', 'shell', 'dumpsys', 'package', package]
    rc, stdout, stderr = exec_(cmd)
    assert rc == 0, f'ADB failed with code: {rc}'
    lines = stdout.splitlines()
    lines = extract_block(lines, r'^Packages:$', r'^\w.*$')
    for line in lines:
        if m := re.search(r'^\s*([a-zA-Z0-9._]+).+granted=(\w+).+flags=.*', line):
            manually_set = bool(re.search(r'\bUSER_SET\b', line))
            granted = m.group(2).lower() == 'true'
            yield m.group(1), granted, manually_set


def filter_packages_by_user_prefs(user_prefs: ResolutionList, action: str):
    for r in user_prefs.items:
        if r.resolution == action:
            yield {'package': r.package,
                   'action': r.resolution,
                   'description': r.comment}


def list_device_enabled_packages():
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages -e --user 0'))
    assert rc == 0, f'ADB failed with code: {rc}'
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_device_all_packages():
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages --user 0'))
    assert rc == 0, f'ADB failed with code: {rc}'
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_device_user_installed_packages() -> set[str]:
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages -3 --user 0'))
    assert rc == 0, f'ADB failed with code: {rc}'
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_apk_paths_on_device(package):
    rc, stdout, stderr = exec_(['adb', 'shell', 'pm', 'path', package])
    assert rc == 0, f'ADB failed with code: {rc}'
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def extract_package_names(lines: list):
    lines = map(str.strip, lines)
    lines = map(lambda x: re.sub(r'^package:', '', x), lines)
    lines = map(str.strip, lines)
    lines = filter(bool, lines)
    return list(lines)


def list_packages_user_want_delete():
    resolutions = load_plain_resolutions(USER_PREFS)
    packages: list[str] = [r.package
                           for r in resolutions.items
                           if r.resolution == 'del']
    return set(packages)


def list_device_packages_to_debloat():
    caches = PackageCaches()
    enabled_packages = caches.enabled.get()
    user_to_del = list_packages_user_want_delete()
    packages_to_delete = user_to_del.intersection(enabled_packages)
    return sorted(packages_to_delete)


def enrich_packages_with_known_meta(packages: list):
    packages_meta = ensure_key(APP_META_FILE.data, 'packages', lambda: dict())
    for pak_data in packages:
        pak_name = pak_data['package']
        pak_meta = packages_meta.get(pak_name) or dict()
        pak_data['title'] = pak_meta.get('title')
        pak_data['icon'] = pak_meta.get('icon')
        yield pak_data


def read_device_name():
    rc, stdout, stderr = exec_(shlex.split('adb shell getprop ro.product.brand'))
    if rc != 0:
        return '', stderr.strip()
    brand = stdout.strip()

    rc, stdout, stderr = exec_(shlex.split('adb shell getprop ro.product.model'))
    if rc != 0:
        return '', stderr.strip()
    model = stdout.strip()

    return f'{brand} {model}', ''


def list_apps_in_local_folder() -> set[str]:
    if not APKS_DIR.exists():
        return set()
    packages = set()
    for child in APKS_DIR.iterdir():
        if not child.is_dir():
            continue
        if not list(child.glob('*.apk')):
            continue
        packages.add(child.name)
    return packages


def list_apps_in_local_folder_ex():
    pak_meta = (APP_META_FILE.data or dict()).get('packages') or dict()
    local_packages = list_apps_in_local_folder()
    device_packages = list_device_enabled_packages()
    res = []
    for package in local_packages:
        pak_dict = pak_meta.get(package) or dict()
        title = pak_dict.get('title') or ''
        icon_file = pak_dict.get('icon') or ''
        is_installed = package in device_packages
        res.append([package, is_installed, title, icon_file])
    return res


def resolve_apk_title(apk_info: pyaxmlparser.APK):
    try:
        return apk_info.get_app_name()
    except:
        return ''


####################################################
## SERVICE LAYER
####################################################

def update_package_prefs(package, action):
    resolutions = load_plain_resolutions(USER_PREFS)
    r = resolutions.get_resolution(package)
    if r:
        r.resolution = action
    else:
        uad_package = load_json(UAD_LOCAL, dict()).get(package) or dict()
        comment = uad_package.get('description', '')
        r = Resolution(action, package, [], comment)
        resolutions.add(r)
    dump_resolutions(USER_PREFS, resolutions)


def uninstall_package(package):
    cmd = ['adb', 'shell', 'pm', 'uninstall', '--user', '0', package]
    rc, stdout, stderr = exec_(cmd)
    if rc == 0:
        audit.info(f'OK uninstall {package}')
    return rc, stdout, stderr


def install_existing_package(package):
    cmd = ['adb', 'shell', 'cmd', 'package', 'install-existing', '--user', '0', package]
    rc, stdout, stderr = exec_(cmd)
    if rc == 0:
        audit.info(f'OK install-existing {package}')
    return rc, stdout, stderr


def disable_package(package):
    cmd = ['adb', 'shell', 'pm', 'disable-user', '--user', '0', package]
    rc, stdout, stderr = exec_(cmd)
    if rc == 0:
        audit.info(f'OK disable {package}')
    return rc, stdout, stderr


def enable_package(package):
    cmd = ['adb', 'shell', 'pm', 'enable', '--user', '0', package]
    rc, stdout, stderr = exec_(cmd)
    if rc == 0:
        audit.info(f'OK enable {package}')
    return rc, stdout, stderr


def uninstall_or_disable_package(package):
    rc, stdout, stderr = uninstall_package(package)
    if rc != 0:
        rc, stdout, stderr = disable_package(package)
    return rc, stdout, stderr


def backup_apks_for_package(package: str) -> bool:
    final_app_folder = APKS_DIR / package
    if final_app_folder.exists():
        return False
    apk_paths = list_apk_paths_on_device(package)
    if not apk_paths:
        return False
    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        cwd_before = os.getcwd()
        try:
            os.chdir(tmp_dir)
            for apk_path in apk_paths:
                cmd = ['adb', 'pull', apk_path]
                rc, stdout, stderr = exec_(cmd, stdout=None, stderr=None)
                assert rc == 0, f'ADB failed with code: {rc}'
            ensure_dir(APKS_DIR)
            if final_app_folder.exists():
                shutil.rmtree(final_app_folder)
            os.chdir(cwd_before)
            shutil.move(tmp_dir, final_app_folder)
        finally:
            os.chdir(cwd_before)
    return True


def backup_user_apps():
    num_local_apps = len(list_apps_in_local_folder())
    if num_local_apps > 0:
        return 0, f'There are {num_local_apps} local apps already downloaded in {APKS_DIR}. Remove them first if you want a new backup procedure.'
    num_apps_downloaded = 0
    ensure_dir(APKS_DIR)
    packages = list_device_user_installed_packages()
    for package in packages:
        if backup_apks_for_package(package):
            num_apps_downloaded += 1
    return num_apps_downloaded, ''


def shorten_perm(perm: str):
    if perm.startswith(STD_PERM_PFX):
        tail = perm[len(STD_PERM_PFX):]
        if tail and '.' not in tail:
            return tail
    return perm


def normalize_perm(perm: str):
    return perm if '.' in perm else f'{STD_PERM_PFX}{perm}'


def backup_permissions():
    packages = list_device_enabled_packages()
    perm_file = ALL_PERMISSIONS_FILE
    perm_cnt = 0
    out_lines = []
    for package in packages:
        perms = list(read_app_permissions(package))
        perms = [(shorten_perm(perm), granted, user_set) for perm, granted, user_set in perms if user_set]
        if perms:
            perms = sorted(perms, key=lambda tup: tup[0])
            perm_max = max(len(perm) for perm, granted, user_set in perms)
            for perm, granted, manually_set in perms:
                grant_str = 'grant' if granted else 'revoke'
                out_lines.append(f'{package}  {perm.ljust(perm_max)}  {grant_str}')
                perm_cnt += 1
    with open(perm_file, 'w', encoding='utf-8') as fd:
        fd.write('\n'.join(sorted(out_lines)))
    print(f'Rewritten {perm_file}')
    return perm_cnt


def restore_app_install_apks(package):
    app_local_folder = APKS_DIR / package
    assert app_local_folder.exists()
    apks = app_local_folder.glob('*.apk')
    apks = list(map(str, apks))
    rc = 1
    if apks:
        cmd = ['adb', 'install-multiple'] + apks
        rc, _, _ = exec_(cmd, stdout=None, stderr=None)
        # print(f'install-multiple exited with {rc}')
    return rc


def restore_all_apps_permissions():
    assert ALL_PERMISSIONS_FILE.exists(), f'No permissions file found. Backup them first.'
    oks, fails = 0, 0
    device_packages = list_device_enabled_packages()
    for package, perm, grant in parse_perm_file(ALL_PERMISSIONS_FILE):
        if package not in device_packages:
            continue
        perm = normalize_perm(perm)
        print('restoring permission', package, perm, grant)
        if restore_app_permission(package, perm, grant):
            oks += 1
        else:
            fails += 1
    return oks, fails


def restore_app_permission(package, perm, grant: bool):
    grant_or_revoke = 'grant' if grant else 'revoke'
    rc, _, _ = exec_(['adb', 'shell', 'pm', grant_or_revoke, package, perm], stdout=None, stderr=None)
    if rc != 0:
        return False

    exec_(['adb', 'shell', 'pm', 'set-permission-flags', package, perm, 'user-set'],
          stdout=None, stderr=None)
    if rc != 0:
        return False

    exec_(['adb', 'shell', 'pm', 'set-permission-flags', package, perm, 'user-fixed'],
          stdout=None, stderr=None)
    if rc != 0:
        return False

    return True


def restore_apps():
    device_packages = list_device_all_packages()
    local_packages = list_apps_in_local_folder()
    missing_on_device = local_packages - device_packages
    num_ok, num_fail = 0, 0
    for package in missing_on_device:
        rc = restore_app_install_apks(package)
        if rc == 0:
            num_ok += 1
        else:
            num_fail += 1
    # for package in local_packages:
    #     restore_app_permissions(package)
    return num_ok, num_fail


def parse_perm_file(f: Path):
    with open(f, encoding='utf-8') as fd:
        for line in fd:
            line = line.strip()
            words = re.split(r'\s+', line)
            if len(words) >= 3:
                package = words[0]
                perm = words[1]
                grant_str = words[2].lower()
                grant = {'grant': True, 'revoke': False}.get(grant_str)
                if grant is None:
                    print(f'WARN: cannot parse permission: {line}')
                    continue
                yield package, perm, grant


def filter_packages(caches: PackageCaches, uad_packages: dict, resolutions: ResolutionList, filter_: str) -> list[str]:
    filter_ = filter_ or 'deviceSafe'
    if filter_ == 'deviceUninstalled':
        packages = list(caches.get_uninstalled())
    elif filter_ == 'deviceDisabled':
        packages = list(caches.get_disabled())
    else:
        enabled_packages = caches.get_enabled()
        packages = []
        for pak_name in enabled_packages:
            uad_entry = uad_packages.get(pak_name)
            user_entry = resolutions.get_resolution(pak_name)
            mapping = {
                'deviceEnabled': lambda: True,
                'deviceAllBloatware': lambda: bool(uad_entry),
                'deviceAdvanced': lambda: uad_entry and uad_entry.get('removal') == 'Advanced',
                'deviceSafe': lambda: uad_entry and uad_entry.get('removal') == 'Recommended',
                'deviceUserInstalled': lambda: pak_name in caches.get_user_installed(),
                'deviceDebloat': lambda: user_entry and user_entry.resolution == 'del',
                'deviceNonBloatware': lambda: pak_name not in uad_packages,
            }
            func = mapping.get(filter_)
            filter_ok = func() if func else False
            if filter_ok:
                packages.append(pak_name)
    return packages


def package_to_dict(caches: PackageCaches, pak_name: str, uad_packages: dict, resolutions: ResolutionList, status: str):
    uad_entry = uad_packages.get(pak_name)
    r = resolutions.get_resolution(pak_name)
    uad_entry = uad_entry or {
        'description': '', 'removal': '', 'list': '', 'dependencies': [], 'neededBy': [], 'labels': []
    }
    if not uad_entry.get('removal') and pak_name in caches.get_user_installed():
        if not uad_entry.get('description'):
            uad_entry['description'] = 'User installed this app (likely)'
    if pak_name in caches.get_user_installed():
        uad_entry['tags'] = uad_entry.get('tags') or []
        if 'User' not in uad_entry['tags']:
            uad_entry['tags'].append('User')
    uad_entry['action'] = r.resolution if r else ''
    uad_entry['status'] = status or resolve_package_status(pak_name, caches)
    uad_entry['package'] = pak_name
    return uad_entry


def resolve_package_status(package: str, caches: PackageCaches):
    if package in caches.get_uninstalled():
        return 'uninstalled'
    if package in caches.get_disabled():
        return 'disabled'
    if package in caches.get_enabled():
        return 'enabled'
    return ''


def debloat_packages():
    oks, fails = 0, 0
    packages = list_device_packages_to_debloat()
    packages = sorted(packages)
    for package in packages:
        print(f'Deleting package: {package}')
        rc, stdout, stderr = uninstall_or_disable_package(package)
        if rc == 0:
            print('OK')
            oks += 1
        else:
            print('FAIL')
            fails += 1

        if rc != 0:
            print(f'rc: {rc}')
            print(f'stdout: {stdout}')
            print(f'stderr: {stderr}')
    return oks, fails


####################################################
## WEB ROUTES
####################################################

def serve_download_uad_list(request, response):
    try:
        old = load_json(UAD_LOCAL, dict())
    except json.JSONDecodeError:
        old = dict()
    urllib.request.urlretrieve(UAD_URL, UAD_LOCAL)
    new = load_json(UAD_LOCAL, dict())
    ok = len(new) > 0
    msg_to_user = 'New data received' \
        if len(new) != len(old) \
        else f'Downloaded info about {len(new)} packages' if ok else 'x_x'
    response.content_type = CT_JSON
    return {'status': 'OK',
            'ok': ok,
            'msg': msg_to_user,
            'numPackagesBefore': len(old),
            'numPackagesAfter': len(new)}


def serve_list_packages(request, response):
    # todo exception here not shown in UI
    filter_ = request.query.get('filter', '')
    resolutions = load_plain_resolutions(USER_PREFS)
    uad_packages: dict = load_json(UAD_LOCAL, dict())
    caches = PackageCaches()
    filter_to_resolution = {  # todo useless now
        'keep': 'keep',
        'del': 'del',
        'unsure': 'review',
    }
    if filter_ in {'keep', 'del', 'unsure'}:
        resolution = filter_to_resolution.get(filter_, filter_)
        packages_list = list(filter_packages_by_user_prefs(resolutions, resolution))
    else:
        common_package_status = FILTER_TO_STATUS.get(filter_) or ''
        packages = filter_packages(caches, uad_packages, resolutions, filter_)
        packages_list = [
            package_to_dict(caches, package, uad_packages, resolutions, common_package_status)
            for package in packages]
    packages_list = list(enrich_packages_with_known_meta(packages_list))
    packages_list = sorted(packages_list, key=lambda x: x['package'])
    response.content_type = CT_JSON
    device_name, warn_msg = read_device_name()
    return {'status': 'OK',
            'deviceTitle': device_name,
            'warnMsg': warn_msg,
            'packages': packages_list}


def serve_change_package_resolution(request, response):
    package = request.query.get('package', '')
    action = request.query.get('action', '')
    assert package
    assert action
    update_package_prefs(package, action)
    response.content_type = CT_JSON
    return {'status': 'OK'}


def serve_debloat(request, response):
    oks, fails = debloat_packages()
    response.content_type = CT_JSON
    return {'oks': oks, 'fails': fails}


def serve_backup_apps(request, response):
    num_apps_downloaded, msg = backup_user_apps()
    response.content_type = CT_JSON
    return {'status': 'OK',
            'numAppsDownloaded': num_apps_downloaded,
            'msg': msg}


def serve_backup_app_permissions(request, response):
    num_perm = backup_permissions()
    response.content_type = CT_JSON
    return {'status': 'OK',
            'numPermWritten': num_perm,
            'msg': ''}


def serve_restore_apps(request, response):
    num_ok, num_fail = restore_apps()
    response.content_type = CT_JSON
    return {'status': 'OK', 'oks': num_ok, 'fails': num_fail}


def serve_restore_all_apps_permissions(request, response):
    total_oks, total_fails = restore_all_apps_permissions()
    response.content_type = CT_JSON
    return {'oks': total_oks, 'fails': total_fails}


def serve_restore_app(request, response):
    package = request.query.get('package')
    rc = restore_app_install_apks(package)
    response.content_type = CT_JSON
    return {'ok': rc == 0}


def serve_load_local_apps(request, response):
    packages = list_apps_in_local_folder_ex()
    packages = sorted(packages, key=lambda x: x[0])
    response.content_type = CT_JSON
    device_name, warn_msg = read_device_name()
    return {'status': 'OK', 'deviceTitle': device_name, 'warnMsg': warn_msg,
            'packages': packages, 'localAppsFolder': str(PROFILE_DIR)}


class ExtractApkMeta:

    def __init__(self):
        db = APP_META_FILE
        db.load()
        db.data = db.data if db.data else dict()
        app_meta_packages = db.data.get('packages')
        if not app_meta_packages:
            app_meta_packages = dict()
            db.data['packages'] = app_meta_packages
        self.db = db
        self.app_meta_packages = app_meta_packages

    def __find_one_remote_apk(self, apk_paths):
        apk_path = ''
        if len(apk_paths) == 1:
            apk_path = next(iter(apk_paths))
        if not apk_path:
            apk_paths_2 = list(filter(lambda x: x.endswith('/base.apk'), apk_paths))
            if apk_paths_2:
                apk_path = apk_paths_2[0]
        return apk_path

    def __extract_meta_from_local_apk(self, local_apk_path: Path):
        app_title, icon_data, icon_ext = '', '', ''
        try:
            apk_info = pyaxmlparser.APK(str(local_apk_path))
        except Exception as e:
            print(f'ERROR: pyaxmlparser failed parsing {local_apk_path}')  # pyaxmlparser is buggy
            return app_title, icon_data, icon_ext
        app_title = resolve_apk_title(apk_info)
        if not app_title:
            print(f'WARN: failed resolving app title from apk {local_apk_path}, using {local_apk_path.stem}')
            app_title = local_apk_path.stem
        if not app_title or app_title == 'base':
            print(f'WARN: failed resolving app title from apk {local_apk_path}, skipping')
            return app_title, icon_data, icon_ext
        icon_data = self.__extract_icon_data(apk_info)
        icon_info = self.__extract_icon_path_in_apk(apk_info)
        if icon_data and icon_info and isinstance(icon_data, bytes):
            icon_ext = os.path.splitext(icon_info)[1]
        return app_title, icon_data, icon_ext

    def __extract_icon_data(self, apk_info: pyaxmlparser.APK):
        try:
            return apk_info.icon_data
        except:
            return b''

    def __extract_icon_path_in_apk(self, apk_info: pyaxmlparser.APK):
        try:
            return apk_info.icon_info
        except:
            return ''

    def __pull_apk_into_temp_folder(self, apk_path: str):
        cwd = os.getcwd()
        try:
            tmp_app_folder = Path(tempfile.mkdtemp())
            os.chdir(tmp_app_folder)
            cmd = ['adb', 'pull', apk_path]
            rc, stdout, stderr = exec_(cmd, stdout=None, stderr=None)
            if rc != 0:
                return False, ''
            return True, tmp_app_folder
        finally:
            os.chdir(cwd)

    def __persist_icon(self, icon_data, app_icon_file_short):
        icon_file = APP_ICON_DIR / app_icon_file_short
        ensure_dir(icon_file.parent)
        with open(icon_file, 'wb') as fp:
            fp.write(icon_data)

    def extract(self, package: str):
        tmp_app_folder = None  # type: Optional[Path]
        try:
            apk_paths = list_apk_paths_on_device(package)
            if not apk_paths:
                return False
            apk_paths = list_apk_paths_on_device(package)
            if not apk_paths:
                return False
            apk_path = self.__find_one_remote_apk(apk_paths)
            if not apk_path:
                return False
            ok, tmp_app_folder = self.__pull_apk_into_temp_folder(apk_path)
            if not ok:
                return False
            local_apk_path = tmp_app_folder / os.path.basename(apk_path)
            app_icon_file_short = ''
            app_title, icon_data, icon_ext = self.__extract_meta_from_local_apk(local_apk_path)
            if not app_title:
                return False
            if icon_data and icon_ext:
                app_icon_file_short = f'{package}{icon_ext}'
                self.__persist_icon(icon_data, app_icon_file_short)
            pak_data = {'title': app_title}
            if app_icon_file_short:
                pak_data['icon'] = app_icon_file_short
            self.app_meta_packages[package] = pak_data
            self.db.dump()
            return True
        except Exception as e:
            print(f'ERROR: Failed reading icon for {package}: {e}')
            traceback.print_exc()
            return False
        finally:
            if tmp_app_folder and tmp_app_folder.exists():
                shutil.rmtree(tmp_app_folder)


def serve_read_device_apps_meta(request, response):
    extractor = ExtractApkMeta()
    oks, fails = 0, 0
    for package in list_device_all_packages():
        if package not in extractor.app_meta_packages:
            ok = extractor.extract(package)
            if ok:
                oks += 1
            else:
                fails += 1
    response.content_type = CT_JSON
    return {'status': 'OK', 'oks': oks, 'fails': fails}


def static_file(fname):
    with open(fname, encoding='utf-8') as fd:
        return fd.read()


def serve_index(request, response):
    response.content_type = 'text/html'
    return static_file('index.html')


def serve_main_css(request, response):
    response.content_type = 'text/css'
    return static_file('main.css')


def serve_main_js(request, response):
    response.content_type = 'text/javascript'
    return static_file('main.js')


def serve_app_icon(request, response):
    response.content_type = 'image'
    fname = request.query.get('file')
    if not fname:
        response.status_code = 404
        return ''
    path = APP_ICON_DIR / fname
    if not path.exists():
        response.status_code = 404
        return ''
    with open(path, 'rb') as fp:
        return fp.read()


def serve_change_package_status(request, response):
    package = request.query.get('package')
    action = request.query.get('action')
    mapping = {
        'enable': enable_package,
        'disable': disable_package,
        'uninstall': uninstall_package,
        'reinstall': install_existing_package,
    }
    func = mapping.get(action)
    assert func
    rc, stdout, stderr = func(package)
    ok = rc == 0
    msg = f'Package {package} switched to {action} successfully' if ok else f'{stderr}'
    return {'ok': ok, 'msg': msg}


EXPOSED_FILES = {
    'appProfileFolder': PROFILE_DIR,
    'userDebloatFile': USER_PREFS,
    'communityDebloatFile': UAD_LOCAL,
    'communityDebloatUrl': UAD_URL,
    'auditFile': AUDIT_LOG_FILE,
    'venv': sys.prefix,
    'pythonVersion': platform.python_version(),
    'iconCacheFolder': APP_ICON_DIR,
    'appRepo': APP_REPO,
}


def serve_open_file(request, response):
    code_name = request.query.get('what')
    path = EXPOSED_FILES.get(code_name)
    if path:
        path = str(path)
        if not path.startswith('https:') and not path.startswith('http:'):
            open_local_file_or_folder(str(path))
    return {'OK': True}


def serve_settings(request, response):
    res = {k: str(v) for k, v in EXPOSED_FILES.items()}
    return res


routes = {
    '/': serve_index,
    '/main.css': serve_main_css,
    '/main.js': serve_main_js,
    '/appIcon': serve_app_icon,
    '/readAppMeta': serve_read_device_apps_meta,
    '/loadLocalApps': serve_load_local_apps,
    '/backupAppApks': serve_backup_apps,
    '/backupAppPerms': serve_backup_app_permissions,
    '/restoreApps': serve_restore_apps,
    '/restoreApp': serve_restore_app,
    '/restoreAppPermissions': serve_restore_all_apps_permissions,
    '/debloat': serve_debloat,
    '/packages': serve_list_packages,
    '/loadUad': serve_download_uad_list,
    '/changePackageResolution': serve_change_package_resolution,
    '/changePackageStatus': serve_change_package_status,
    '/openFile': serve_open_file,
    '/settings': serve_settings,
}


####################################################
## VANILLA WEB
####################################################

@dataclasses.dataclass
class Request:
    query: dict


@dataclasses.dataclass
class Response:
    content_type: str
    status_code: int


class MyWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        path = parsed_url.path
        handler = routes.get(path)
        status_code = 200
        query: dict[str, str] = dict()
        for key, values in query_params.items():
            query[key] = values[0]
        request = Request(query)
        response = Response('', 200)

        if handler:
            try:
                resp_obj = handler(request, response)
                status_code = response.status_code or status_code
            except Exception as exc:
                traceback.print_exc()
                response.content_type = 'application/json; charset=utf-8'
                status_code = 500
                resp_obj = {'message': str(exc).strip(),
                            'type': exc.__class__.__name__}
        else:
            resp_obj = 'Not found'
            status_code = 404

        if isinstance(resp_obj, dict) or isinstance(resp_obj, list):
            resp_ct = 'application/json; charset=utf-8'
            indent = 2 if DEBUG else None
            resp_bin = json.dumps(resp_obj, indent=indent, ensure_ascii=False).encode('utf-8')
        elif isinstance(resp_obj, bytes):
            resp_bin = resp_obj
        else:
            resp_ct = 'text/plain; charset=utf-8'
            resp_bin = str(resp_obj).encode('utf-8')

        resp_ct = response.content_type or resp_ct

        self.send_response(status_code)
        self.send_header('Content-Type', resp_ct)
        self.end_headers()
        self.wfile.write(resp_bin)

    def log_message(self, fmt, *args):
        if DEBUG:
            super().log_message(fmt, *args)


def main_vanilla():
    try:
        server = ThreadingHTTPServer((HOST, PORT), MyWebHandler)
        url = f'http://{HOST}:{PORT}/'
        print(f'Web server starting: {url}')
        if not DEBUG:
            open_browser(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print('Bye')


if __name__ == '__main__':
    main_vanilla()
