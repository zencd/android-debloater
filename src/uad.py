import json
import os
import tempfile
import urllib.request
from pathlib import Path

from src.defs import UAD_LOCAL, UAD_URL
from src.logs import log
from src.utils import load_json


# module: community-updated list of bloatware, UAD NG

def _validate_uad_json(file_path: Path) -> bool:
    required_keys = {"list", "description", "dependencies", "neededBy", "labels", "removal"}

    with file_path.open('r', encoding='utf-8') as file:
        data = json.load(file)

    for package, details in data.items():
        if not required_keys.issubset(details.keys()):
            return False

    return True


def _read_current_uad_len():
    try:
        old = load_json(UAD_LOCAL, dict())
        return len(old)
    except json.JSONDecodeError:
        return 0


def download_uad_list() -> tuple[int, int]:
    len_old = _read_current_uad_len()
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        urllib.request.urlretrieve(UAD_URL, temp_file.name)
        temp_file.close()
        new = load_json(temp_file.name, dict())
        if _validate_uad_json(new):
            os.replace(temp_file.name, UAD_LOCAL)
        else:
            os.remove(temp_file.name)
            log.error('Invalid UAD JSON data downloaded')
            return len_old, 0
        len_new = len(new)
        if len_new == 0:
            return len_old, len_new
        return len_old, len_new
