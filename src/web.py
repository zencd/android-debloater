import dataclasses
import json
import os.path
import platform
import sys
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from src import adb
from src.apk_meta import ExtractApkMeta
from src.defs import *
from src.logs import log
from src.services import debloat_packages, backup_user_apps, backup_permissions, \
    restore_apps, restore_all_apps_permissions, update_package_prefs, restore_app_install_apks, \
    list_apps_in_local_folder_ex, ListPackages
from src.utils import load_json, open_browser, open_local_file_or_folder, is_url

# web ui in this module

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

STATIC_URL_PREFIX = '/static/'


@dataclasses.dataclass
class Request:
    path: str
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
        handler = None
        if path.startswith(STATIC_URL_PREFIX):
            handler = serve_static
        if not handler:
            handler = routes.get(path)
        status_code = 200
        query: dict[str, str] = dict()
        for key, values in query_params.items():
            query[key] = values[0]
        request = Request(path, query)
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

        resp_ct = ''
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


class MyServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


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
    packages_list = ListPackages().list_packages_by_filter(filter_)
    response.content_type = CT_JSON
    device_name, warn_msg = adb.read_device_name()
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
    packages, is_device_connected = list_apps_in_local_folder_ex()
    packages = sorted(packages, key=lambda x: x[0])
    response.content_type = CT_JSON
    device_name, warn_msg = adb.read_device_name()
    return {'status': 'OK',
            'deviceTitle': device_name,
            'warnMsg': warn_msg,
            'packages': packages,
            'deviceConnected': is_device_connected}


def serve_read_device_apps_meta(request, response):
    extractor = ExtractApkMeta()
    oks, fails = 0, 0
    for package in adb.list_device_all_packages():
        if package not in extractor.app_meta_packages:
            ok = extractor.extract(package)
            if ok:
                oks += 1
            else:
                fails += 1
    response.content_type = CT_JSON
    return {'status': 'OK', 'oks': oks, 'fails': fails}


def static_file(fname: str, mode='rb', base_dir='.'):
    encoding = 'utf-8' if mode == 'r' else None
    fname = os.path.join(base_dir, fname)
    with open(fname, mode=mode, encoding=encoding) as fd:
        return fd.read()


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
        'enable': adb.enable_package,
        'disable': adb.disable_package,
        'uninstall': adb.uninstall_package,
        'reinstall': adb.install_existing_package,
    }
    func = mapping.get(action)
    assert func
    rc, stdout, stderr = func(package)
    ok = rc == 0
    msg = f'Package {package} switched to {action} successfully' if ok else f'{stderr}'
    return {'ok': ok, 'msg': msg}


def serve_open_file(request, response):
    code_name = request.query.get('what')
    path = EXPOSED_FILES.get(code_name)
    if path:
        path = str(path)
        if not is_url(path):
            open_local_file_or_folder(path)
    return {'OK': True}


def serve_settings(request, response):
    res = {k: str(v) for k, v in EXPOSED_FILES.items()}
    return res


def serve_index(request, response):
    response.content_type = 'text/html'
    fname = os.path.join(PROJECT_DIR, 'static', 'index.html')
    return static_file(fname)


def serve_static(request: Request, response):
    sub_path = request.path[len(STATIC_URL_PREFIX):]
    if sub_path.endswith('.css'):
        response.content_type = 'text/css'
    elif sub_path.endswith('.js'):
        response.content_type = 'text/javascript'
    fname = os.path.join(PROJECT_DIR, 'static', sub_path)
    if not os.path.exists(fname):
        response.content_type = 'text/plain'
        response.status_code = 404
        return 'Not found'
    return static_file(fname)


routes = {
    '/': serve_index,
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


def main_vanilla():
    try:
        server = MyServer((HOST, PORT), MyWebHandler)
        server.socket.settimeout(60)
        url = f'http://{HOST}:{PORT}/'
        log.info(f'Web server starting: {url}')
        if not DEBUG:
            open_browser(url)
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('Bye')
