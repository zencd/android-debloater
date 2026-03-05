import os.path
import re
import tempfile

from src.defs import *
from src.logs import log

# module: custom file format for storing package permissions

class PermFileWriter:

    def __init__(self, path: Path):
        self.path = path
        self.temp_file = Path(tempfile.NamedTemporaryFile(suffix='.txt', delete=False).name)

    def __enter__(self):
        self.fp = open(self.temp_file, 'w', encoding='utf-8')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fp:
            self.fp.close()
        log.debug(f'Moving {self.temp_file} to ${self.path}')
        os.rename(self.temp_file, self.path)
        return False

    def write_line(self, package: str, perm: str, granted: bool):
        grant_str = 'grant' if granted else 'revoke'
        self.fp.write(f'{package}  {shorten_perm(perm)}  {grant_str}\n')


def shorten_perm(perm: str):
    if perm.startswith(STD_PERM_PFX):
        tail = perm[len(STD_PERM_PFX):]
        if tail and '.' not in tail:
            return tail
    return perm


def normalize_perm(perm: str):
    return perm if '.' in perm else f'{STD_PERM_PFX}{perm}'


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
                    log.warning(f'Cannot parse permission: {line}')
                else:
                    yield package, perm, grant
