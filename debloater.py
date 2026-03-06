import gzip
import logging
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


# todo embed resources
# todo ERR_CONNECTION_REFUSED not toasted
# todo verify uad_lists.json before rewriting it
# todo recommended => safe
# todo reload packages once at backend?
# todo set PYTHONIOENCODING?


def is_running_in_venv():
    return sys.prefix != sys.base_prefix


def restart_process_in_venv():
    # here we force execution in a venv bcs we can fail installing extra modules otherwise
    from src.defs import APP_HOME
    print(f'Python interpreter: {sys.executable}, not suitable')
    venv = APP_HOME / 'venv'
    exes = [venv / 'bin/python', venv / 'Scripts/python.exe']
    python_exe = next(iter(exe for exe in exes if exe.exists()), None)
    if not python_exe:
        cmd = [sys.executable, '-m', 'venv', str(venv)]
        print(f'Exec: {shlex.join(cmd)}')
        p = subprocess.Popen(cmd, shell=False, stdout=None, stderr=None, text=True, encoding='utf-8')
        p.communicate()
        rc = p.returncode & 0xFF
        assert rc == 0, f'Failed creating venv: {venv}'
        python_exe = next(iter(exe for exe in exes if exe.exists()), None)
        assert python_exe, f'Failed creating venv: {venv}'
    cmd = [str(python_exe)] + sys.argv
    print(f'Exec: {shlex.join(cmd)}')
    p = subprocess.Popen(cmd, shell=False, stdout=None, stderr=None, text=True, encoding='utf-8')
    p.communicate()
    rc = p.returncode & 0xFF
    sys.exit(rc)


def ensure_pyaxmlparser():
    try:
        # pyaxmlparser reads apk file meta: title, version, icon
        # pyaxmlparser 0.3.31 is current at the moment of writing
        import pyaxmlparser
    except ImportError:
        print('Installing module pyaxmlparser...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyaxmlparser~=0.3'])
        import pyaxmlparser
        print('Module pyaxmlparser successfully installed')
    logging.getLogger('pyaxmlparser').setLevel(logging.ERROR)  # fighting frequent warning "res1 is not zero"


def compress_file(src, dst):
    with open(src, "rb") as f_in, gzip.open(dst, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)


def decompress_gzip(src: Path, dst: Path):
    with gzip.open(src, "rb") as f_in, open(dst, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)


def start_web():
    # using local import because deps like `pyaxmlparser` could be not installed yet
    from src import web
    web.main_vanilla()


def main():
    from src.defs import MIN_PY_VER, UAD_LOCAL, UAD_PROJECT
    from src.logs import log
    assert sys.version_info >= MIN_PY_VER, f'Python {".".join(map(str, MIN_PY_VER))} or newer is required. You have: {sys.version}'
    if not is_running_in_venv():
        restart_process_in_venv()
    log.info(f'Python interpreter: {sys.executable}')
    ensure_pyaxmlparser()
    if not UAD_LOCAL.exists():
        shutil.copyfile(UAD_PROJECT, UAD_LOCAL)
    # compress_file(Path('uad_lists.json'), Path('uad_lists.json.gz'))
    start_web()


if __name__ == '__main__':
    main()
