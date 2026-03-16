import json
import os.path
import tempfile
from json import JSONDecodeError
from pathlib import Path
from typing import Callable

from src.defs import APP_META_PATH
from src.logs import log


class JsonDB:

    def __init__(self, path: Path, prepare_data: Callable[[dict], dict]):
        self.path = path
        self.data = prepare_data(self.__load())

    def __load(self):
        if self.path.exists():
            with open(self.path, encoding='utf-8') as fd:
                try:
                    data = json.load(fd)
                    if not isinstance(data, dict):
                        data = dict()
                except JSONDecodeError as e:
                    log.error(f'Failed parsing JSON from {self.path}: {e}')
                    data = dict()
        else:
            data = dict()
        return data

    def dump(self):
        # XXX writing to a temp file first, bcs once I randomly lost file content on ctrl+C
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False).name
        with open(tmp, 'w', encoding='utf-8') as fd:
            json.dump(self.data, fp=fd, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


def read_app_meta_db():
    def prepare_data(data: dict) -> dict:
        if not isinstance(data.get('packages'), dict):
            data['packages'] = dict()
        return data

    return JsonDB(APP_META_PATH, prepare_data)
