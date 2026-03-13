import json
import os
import tempfile
import urllib.request
from pathlib import Path

from src.defs import UAD_LOCAL, UAD_URL
from src.logs import log
from src.utils import load_json_with_fallback, load_json


# module: community-updated list of bloatware, UAD NG

def _validate_uad_json(file_path: Path) -> bool:
    required_keys = {'list', 'description', 'dependencies', 'neededBy', 'labels', 'removal'}
    data = load_json(file_path)
    max_checks = 5
    cnt = 0
    for package, details in data.items():
        if not required_keys.issubset(details.keys()):
            return False
        cnt += 1
        if cnt > max_checks:
            break
    return True


def _read_current_uad_len():
    try:
        old = load_json_with_fallback(UAD_LOCAL, dict())
        return len(old)
    except json.JSONDecodeError:
        return 0


def download_uad_list() -> tuple[int, int]:
    len_old = _read_current_uad_len()
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        urllib.request.urlretrieve(UAD_URL, temp_file.name)
        temp_file.close()
        new = load_json_with_fallback(temp_file.name, dict())
        len_new = len(new)

        if len_new == 0:
            Path(temp_file.name).unlink(missing_ok=True)
            return len_old, 0

        if not _validate_uad_json(new):
            log.error('Invalid UAD JSON data downloaded')
            Path(temp_file.name).unlink(missing_ok=True)
            return len_old, 0

        os.replace(temp_file.name, UAD_LOCAL)
        return len_old, len_new
