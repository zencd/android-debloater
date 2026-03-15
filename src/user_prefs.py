import dataclasses
import re
import shutil
import tempfile
from pathlib import Path

from src.utils import ensure_dir


# module: custom file format for user prefs (debloat, keep, review)


@dataclasses.dataclass
class Resolution:
    resolution: str
    package: str
    unparsed: list[str]
    comment: str


@dataclasses.dataclass
class ResolutionList:
    __items: list[Resolution]
    __item_by_package: dict[str, Resolution]

    def __init__(self):
        self.__items = []
        self.__item_by_package = dict()

    @property
    def items(self):
        return self.__items

    def get_resolution(self, package):
        return self.__item_by_package.get(package)

    def add(self, r: Resolution):
        self.__items.append(r)
        self.__item_by_package[r.package] = r


class UserPrefsReader:
    def load_plain_resolutions(self, in_file: Path) -> ResolutionList:
        res = ResolutionList()
        if in_file.exists():
            with open(in_file, encoding='utf-8') as fp:
                for line in fp:
                    if r := self._parse_plain_resolution(line):
                        res.add(r)
        return res

    def _parse_plain_resolution(self, line: str):
        sharp = line.find('#')
        comment = ''
        if sharp >= 0:
            comment = line[sharp + 1:].lstrip('# \t').rstrip()
            line = line[0:sharp].strip()
        if not line:
            return None
        words = re.split(r'\s+', line)
        if len(words) < 2:
            return None
        resolution = words[0]
        package = words[1]
        unparsed = words[2:]
        return Resolution(resolution=resolution, package=package, comment=comment, unparsed=unparsed)


class UserPrefsWriter:
    def dump_resolutions(self, out_file: Path, resolutions: ResolutionList):
        # XXX using a temp file to prevent data loss on abort
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            ensure_dir(out_file.parent)
            debloat, keep, review, others = [], [], [], []
            for r in resolutions.items:
                if r.resolution == 'new':
                    continue
                list_ = debloat if r.resolution == 'del' \
                    else keep if r.resolution == 'keep' \
                    else review if r.resolution == 'review' \
                    else others
                list_.append(r)
            groups = [debloat, keep, review, others]
            with open(temp_file.name, 'w', encoding='utf-8') as fp:
                for group in groups:
                    for r in sorted(group, key=lambda x: x.package):
                        print(self._resolution_to_str(r), file=fp)
        shutil.move(temp_file.name, out_file)

    def _resolution_to_str(self, r: Resolution):
        s = f'{r.resolution}  {r.package}'
        for word in r.unparsed:
            s += f'  {word}'
        comment = self._convert_multi_line_description_to_one_line(r.comment)
        if comment:
            grid = 8  # to beautify comments
            s += ' ' * (grid - (len(s) % grid))
            s += f'# {comment}'
        return s

    def _convert_multi_line_description_to_one_line(self, s: str):
        lines = s.splitlines()
        lines = map(str.strip, lines)
        lines = filter(bool, lines)
        res = ''
        for line in lines:
            if res:
                res += ' ' if res[-1] == '.' else ' - '
            res += line
        return res
