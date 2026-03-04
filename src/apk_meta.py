import os.path
import os.path
import shutil
import tempfile
import traceback
from typing import Optional

import pyaxmlparser

from src.utils import exec_, ensure_dir
from src.defs import *
from src.db import app_meta_db
from src.logs import log
from src import adb

# this module is for gathering meta info about apk files like title, version and icon

class ExtractApkMeta:

    def __init__(self):
        db = app_meta_db
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
            log.error(f'pyaxmlparser failed parsing {local_apk_path}')  # pyaxmlparser is buggy
            return app_title, icon_data, icon_ext
        app_title = self.resolve_apk_title(apk_info)
        if not app_title:
            log.warning(f'Failed resolving app title from apk {local_apk_path}, using {local_apk_path.stem}')
            app_title = local_apk_path.stem
        if not app_title or app_title == 'base':
            log.warning(f'Failed resolving app title from apk {local_apk_path}, skipping')
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

    def resolve_apk_title(self, apk_info: pyaxmlparser.APK):
        try:
            return apk_info.get_app_name()
        except:
            return ''

    def extract(self, package: str):
        tmp_app_folder = None  # type: Optional[Path]
        try:
            apk_paths = adb.list_apk_paths_on_device(package)
            if not apk_paths:
                return False
            apk_paths = adb.list_apk_paths_on_device(package)
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
            log.error(f'Failed reading icon for {package}: {e}')
            traceback.print_exc()
            return False
        finally:
            if tmp_app_folder and tmp_app_folder.exists():
                shutil.rmtree(tmp_app_folder)
