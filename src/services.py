import os.path
import shutil
import tempfile

from src import adb
from src.db import app_meta_db
from src.defs import *
from src.logs import log
from src.perm_fmt import normalize_perm, parse_perm_file, PermFileWriter
from src.user_prefs import ResolutionList, Resolution, dump_resolutions
from src.user_prefs import load_plain_resolutions
from src.utils import ensure_dir, ensure_key, load_json


# module for business logics


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
    pak_meta = (app_meta_db.data or dict()).get('packages') or dict()
    local_packages = list_apps_in_local_folder()
    is_device_connected = True
    device_packages = []
    try:
        device_packages = adb.list_device_enabled_packages()
    except Exception as e:
        # case: device not plugged
        is_device_connected = False
    res = []
    for package in local_packages:
        pak_dict = pak_meta.get(package) or dict()
        title = pak_dict.get('title') or ''
        icon_file = pak_dict.get('icon') or ''
        is_installed = package in device_packages
        res.append([package, is_installed, title, icon_file])
    return res, is_device_connected


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


def backup_apks_for_package(package: str) -> bool:
    final_app_folder = APKS_DIR / package
    if final_app_folder.exists():
        return False
    apk_paths = adb.list_apk_paths_on_device(package)
    if not apk_paths:
        return False
    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        cwd_before = os.getcwd()
        try:
            os.chdir(tmp_dir)
            for apk_path in apk_paths:
                adb.pull_apk(apk_path)
            ensure_dir(APKS_DIR)
            if final_app_folder.exists():
                shutil.rmtree(final_app_folder)
            os.chdir(cwd_before)  # XXX windows: we must leave the folder before renaming it
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
    packages = adb.list_device_user_installed_packages()
    for package in packages:
        if backup_apks_for_package(package):
            num_apps_downloaded += 1
    return num_apps_downloaded, ''


def backup_permissions():
    packages = adb.list_device_enabled_packages()
    perm_file = ALL_PERMISSIONS_FILE
    perm_cnt = 0
    with PermFileWriter(perm_file) as perm_writer:
        for package in packages:
            perms = list(adb.read_user_set_permissions(package))
            perms = sorted(perms, key=lambda tup: tup[0])
            for perm, granted, manually_set in perms:
                perm_writer.write_line(package, perm, granted)
                perm_cnt += 1
    log.info(f'Rewritten: {perm_file}')
    return perm_cnt


def restore_app_install_apks(package):
    app_local_folder = APKS_DIR / package
    assert app_local_folder.exists()
    apks = app_local_folder.glob('*.apk')
    apks = list(map(str, apks))
    rc = 1
    if apks:
        rc = adb.install_multiple(apks)
    return rc


def restore_all_apps_permissions():
    assert ALL_PERMISSIONS_FILE.exists(), f'No permissions file found. Backup them first.'
    oks, fails = 0, 0
    device_packages = adb.list_device_enabled_packages()
    for package, perm, grant in parse_perm_file(ALL_PERMISSIONS_FILE):
        if package not in device_packages:
            continue
        if restore_app_permission(package, perm, grant):
            oks += 1
        else:
            fails += 1
    return oks, fails


def restore_app_permission(package, perm, grant: bool):
    perm = normalize_perm(perm)

    if not adb.grant_or_revoke(package, perm, grant):
        return False

    if not adb.set_permission_flag(package, perm, 'user-set'):
        return False

    if not adb.set_permission_flag(package, perm, 'user-fixed'):
        return False

    return True


def restore_apps():
    device_packages = adb.list_device_all_packages()
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


class ListPackages:
    FILTER_TO_STATUS = {'deviceUninstalled': 'uninstalled', 'deviceDisabled': 'disabled'}

    def list_packages_by_filter(self, filter_: str):
        resolutions = load_plain_resolutions(USER_PREFS)
        if filter_ in {'keep', 'del', 'review'}:
            resolution = filter_
            packages_list = list(self.filter_packages_by_user_prefs(resolutions, resolution))
        else:
            caches = adb.PackageCaches()
            uad_packages: dict = load_json(UAD_LOCAL, dict())
            common_package_status = self.__class__.FILTER_TO_STATUS.get(filter_) or ''
            packages = self.filter_packages(caches, uad_packages, resolutions, filter_)
            packages_list = [
                self.package_to_dict(caches, package, uad_packages, resolutions, common_package_status)
                for package in packages]
        packages_list = list(self.enrich_packages_with_known_meta(packages_list))
        packages_list = sorted(packages_list, key=lambda x: x['package'])
        return packages_list

    def filter_packages_by_user_prefs(self, user_prefs: ResolutionList, action: str):
        for r in user_prefs.items:
            if r.resolution == action:
                yield {'package': r.package,
                       'action': r.resolution,
                       'description': r.comment}

    def filter_packages(self, caches: adb.PackageCaches, uad_packages: dict, resolutions: ResolutionList,
                        filter_: str) -> list[
        str]:
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

    def package_to_dict(self, caches: adb.PackageCaches, pak_name: str, uad_packages: dict, resolutions: ResolutionList,
                        status: str):
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
        uad_entry['status'] = status or self.resolve_package_status(pak_name, caches)
        uad_entry['package'] = pak_name
        return uad_entry

    def resolve_package_status(self, package: str, caches: adb.PackageCaches):
        if package in caches.get_uninstalled():
            return 'uninstalled'
        if package in caches.get_disabled():
            return 'disabled'
        if package in caches.get_enabled():
            return 'enabled'
        return ''

    def enrich_packages_with_known_meta(self, packages: list):
        packages_meta = ensure_key(app_meta_db.data, 'packages', lambda: dict())
        for pak_data in packages:
            pak_name = pak_data['package']
            pak_meta = packages_meta.get(pak_name) or dict()
            pak_data['title'] = pak_meta.get('title')
            pak_data['icon'] = pak_meta.get('icon')
            yield pak_data


def debloat_packages():
    def list_device_packages_to_debloat():
        caches = adb.PackageCaches()
        enabled_packages = caches.enabled.get()
        user_to_del = list_packages_user_want_delete()
        packages_to_delete = user_to_del.intersection(enabled_packages)
        return sorted(packages_to_delete)

    def list_packages_user_want_delete():
        resolutions = load_plain_resolutions(USER_PREFS)
        packages: list[str] = [r.package
                               for r in resolutions.items
                               if r.resolution == 'del']
        return set(packages)

    oks, fails = 0, 0
    packages = list_device_packages_to_debloat()
    packages = sorted(packages)
    for package in packages:
        log.debug(f'Deleting package: {package}')
        rc, stdout, stderr = adb.uninstall_or_disable_package(package)
        if rc == 0:
            log.debug('OK')
            oks += 1
        else:
            log.debug('FAIL')
            fails += 1
    return oks, fails
