import re
import shlex
from functools import cache

from src import AbortException
from src.logs import audit, log
from src.utils import exec_, extract_block

# module: abstract adb utils

class PackageCache:
    def __init__(self, cmd: str):
        self.cmd = shlex.split(cmd)

    @cache
    def get(self) -> set[str]:
        rc, stdout, stderr = exec_(self.cmd)
        if rc != 0:
            raise AbortException(f'Command failed with rc: {rc}, text: {stderr}')
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


def grant_or_revoke(package: str, perm: str, grant: bool):
    str_cmd = 'grant' if grant else 'revoke'
    rc, _, _ = exec_(['adb', 'shell', 'pm', str_cmd, package, perm], stdout=None, stderr=None)
    return rc == 0


def set_permission_flag(package: str, perm: str, flag: str):
    rc, _, _ = exec_(['adb', 'shell', 'pm', 'set-permission-flags', package, perm, flag], stdout=None, stderr=None)
    return rc == 0


def install_multiple(apk_paths: list[str]):
    cmd = ['adb', 'install-multiple'] + apk_paths
    rc, _, _ = exec_(cmd, stdout=None, stderr=None)
    return rc


def pull_apk(apk_path):
    cmd = ['adb', 'pull', apk_path]
    rc, stdout, stderr = exec_(cmd, stdout=None, stderr=None)
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')


def read_user_set_permissions(package):
    lines = dumpsys_package(package)
    lines = extract_block(lines, r'^Packages:$', r'^\w.*$')
    for line in lines:
        if m := re.search(r'^\s*([a-zA-Z0-9._]+).+granted=(\w+).+flags=.*', line):
            manually_set = bool(re.search(r'\bUSER_SET\b', line))
            granted = {'true': True, 'false': False}.get(m.group(2).lower(), None)
            if granted is None:
                log.debug(f'Failed resolving if permission is granted or not: {line}')
            else:
                yield m.group(1), granted, manually_set


def dumpsys_package(package):
    cmd = ['adb', 'shell', 'dumpsys', 'package', package]
    rc, stdout, stderr = exec_(cmd)
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')
    return stdout.splitlines()


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


def list_device_enabled_packages():
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages -e --user 0'))
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_device_all_packages():
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages --user 0'))
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_device_user_installed_packages() -> set[str]:
    rc, stdout, stderr = exec_(shlex.split('adb shell pm list packages -3 --user 0'))
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def list_apk_paths_on_device(package):
    rc, stdout, stderr = exec_(['adb', 'shell', 'pm', 'path', package])
    if rc != 0:
        raise AbortException(f'ADB failed with code: {rc}')
    lines = stdout.splitlines()
    return set(extract_package_names(lines))


def extract_package_names(lines: list):
    lines = map(str.strip, lines)
    lines = map(lambda x: re.sub(r'^package:', '', x), lines)
    lines = map(str.strip, lines)
    lines = filter(bool, lines)
    return list(lines)


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
