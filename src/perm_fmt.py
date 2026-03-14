import os.path
import re
import tempfile

from src.defs import *
from src.logs import log


# module: custom file format for storing package permissions

class PermFileWriter:

    def __init__(self, path: Path):
        self.path = path
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8')
        self.cnt = 0

    def write_permission(self, package: str, perm: str, granted: bool):
        grant_str = 'grant' if granted else 'revoke'
        self.temp_file.write(f"{package}  {shorten_perm(perm)}  {grant_str}\n")
        self.cnt += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.temp_file.close()
        if exc_type is None:
            log.debug(f'Move {self.temp_file} to ${self.path}')
            os.replace(self.temp_file.name, self.path)
        else:
            log.debug(f'Remove {self.temp_file}')
            os.remove(self.temp_file.name)


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
                    continue
                perm = normalize_perm(perm)
                yield package, perm, grant
