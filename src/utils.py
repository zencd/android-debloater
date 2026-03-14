import dataclasses
import json
import os.path
import platform
import re
import shlex
import subprocess
import webbrowser
from typing import Optional

from src.defs import *
from src.logs import log


# module: abstract utils

@dataclasses.dataclass
class Counters:
    oks = 0
    fails = 0

    def increment_rc(self, rc: int):
        assert type(rc) == int
        if rc == 0:
            self.oks += 1
        else:
            self.fails += 1

    def increment_bool(self, ok: bool):
        assert type(ok) == bool
        if ok:
            self.oks += 1
        else:
            self.fails += 1


def is_url(url):
    return url.startswith('https:') or url.startswith('http:')


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
        log.info(f'Missing path: {path}')
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
    log.info(f'Exec: {shlex.join(cmd)}')
    p = subprocess.Popen(cmd, shell=False, stdout=stdout, stderr=stderr, text=True, encoding='utf-8')
    stdout, stderr = p.communicate()
    rc = p.returncode & 0xFF
    log.debug(f'Process exited with code {rc}')
    # if stdout:
    #     log.debug(f'Stdout: {stdout.strip()}')
    if stderr:
        log.debug(f'Stderr: {stderr.strip()}')
    return rc, stdout, stderr


def load_json_with_fallback(path, fallback):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fd:
            return json.load(fd)
    return fallback

def load_json(path):
    with open(path, encoding='utf-8') as fd:
        return json.load(fd)


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
