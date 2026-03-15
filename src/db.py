import json
import os.path
import tempfile
from json import JSONDecodeError
from pathlib import Path

from src.defs import APP_META_PATH
from src.logs import log


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
                    log.error(f'Failed reading JSON from {self.path}: {e}')
                    data = dict()
                self.data = data
                return data
        else:
            self.data = dict()
            return self.data

    def dump(self):
        # XXX writing to a temp file first, bcs once I randomly lost file content on ctrl+C
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False).name
        assert self.data is not None
        with open(tmp, 'w', encoding='utf-8') as fd:
            json.dump(self.data, fp=fd, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


APP_META_DB = JsonDB(APP_META_PATH)
