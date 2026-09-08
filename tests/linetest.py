"""Does a finding say which file and which line it is about?

    python3 tests/linetest.py

Each case writes real files and runs --check the way somebody would, so
what is asserted is the output rather than an internal call.  A case says
which finding it is looking for, and what the parenthetical after the path
has to be.

`line` is looked up by searching the fixture for a marker rather than
counted by hand, so editing a fixture cannot silently move an assertion.

Needs PyQt5, because it runs the clock's own --check as a subprocess.  It
opens no window.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(HERE)
PY = sys.executable
CLOCK = os.path.join(HERE, 'PyQtPiClock3.py')

# a config that checks clean, for cases to break one thing in
BASE = """\
pages:
  clock-page: {order: 0, layout: %(layout)s, theme: %(theme)s}

location:
  latitude: 45
  longitude: -93

widgets:
  clock: {plugin: PiClock3.AnalogClock, region: clock}
"""


def written(text, **names):
    """the fixture, and the 1-based line each named marker sits on"""
    body = text % names if names else text
    lines = body.splitlines()
    return body, lines


def lineOf(body, marker):
    for n, line in enumerate(body.splitlines(), 1):
        if marker in line:
            return n
    return None


def check(configPath, extra=()):
    """--check, as the findings it printed"""
    out = subprocess.run(
        [PY, CLOCK, configPath, '--check'] + list(extra),
        cwd=HERE, capture_output=True, text=True)
    text = out.stdout + out.stderr
    # a clock that could not start is not five failing cases, and saying it
    # that way sends somebody looking at the wrong thing entirely
    if 'ModuleNotFoundError' in text:
        raise SystemExit('  the clock will not start under %s:\n  %s'
                         % (PY, text.strip().splitlines()[-1]))
    found = []
    for line in text.splitlines():
        m = re.match(r'^(problem|warning)\s+(.*?): (.*)$', line)
        if m:
            found.append((m.group(1), m.group(2), m.group(3)))
    return found


def where(found, startswith):
    """the `where` of the first finding whose path starts as given"""
    for _, at, _ in found:
        if at.startswith(startswith):
            return at
    return None


# a theme and a layout have to be found where the clock looks for them, so
# these are written into the checkout and taken away again.  The leading
# underscore is the whole safety of it: themes/ and layouts/ hold whatever
# somebody has installed, and a fixture named after a real one would be
# deleted at the end of the run.
THEME_NAME = LAYOUT_NAME = '_selftest'


class Fixture():
    """temp config, and any theme or layout a case needs, taken away
    again.  themes/ and layouts/ at the top of the checkout are ignored by
    git, so a fixture there leaves nothing behind."""

    def __init__(self, config, theme=None, layout=None):
        self.config = config
        self.theme = theme
        self.layout = layout
        self.paths = []

    def __enter__(self):
        handle, self.configPath = tempfile.mkstemp(suffix='.yaml', text=True)
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            fh.write(self.config)
        self.paths.append(self.configPath)
        if self.theme:
            folder = os.path.join(HERE, 'themes', THEME_NAME)
            self.reserve(folder)
            os.makedirs(folder)
            self.themePath = os.path.join(folder, 'theme.yaml')
            with open(self.themePath, 'w', encoding='utf-8') as fh:
                fh.write(self.theme)
        if self.layout:
            os.makedirs(os.path.join(HERE, 'layouts'), exist_ok=True)
            self.layoutPath = os.path.join(HERE, 'layouts',
                                           LAYOUT_NAME + '.yaml')
            self.reserve(self.layoutPath)
            with open(self.layoutPath, 'w', encoding='utf-8') as fh:
                fh.write(self.layout)
        return self

    @staticmethod
    def reserve(path):
        """never delete what this did not make"""
        if os.path.exists(path):
            raise SystemExit('%s is in the way - remove it and run again'
                             % path)

    def __exit__(self, *exc):
        for path in self.paths:
            if os.path.isfile(path):
                os.unlink(path)
        shutil.rmtree(os.path.join(HERE, 'themes', THEME_NAME),
                      ignore_errors=True)
        p = os.path.join(HERE, 'layouts', LAYOUT_NAME + '.yaml')
        if os.path.isfile(p):
            os.unlink(p)


THEME = """\
name: Linetest
description: a theme with one bad value in it

default:
  color: '#bef'

borders:
  default:
    art: 'frame.png'
    width: wide
"""

LAYOUT = """\
name: Linetest
description: a layout with one bad value in it

regions:
  clock: {left: 0.0, top: 0.0, width: nine, height: 1.0}
"""


def cases():
    out = []

    # 1. a bad value written in the config
    body = (BASE % {'layout': 'classic', 'theme': 'circuit'}
            ).replace('latitude: 45', 'latitude: fortyfive')
    out.append(('a bad value in the config',
                Fixture(body), (), 'location.latitude',
                'CONFIG line %d' % lineOf(body, 'fortyfive')))

    # 2. a bad value in a theme - the question Bert asked
    body = BASE % {'layout': 'classic', 'theme': THEME_NAME}
    out.append(('a bad value in a theme',
                Fixture(body, theme=THEME), (),
                'themes.%s.borders.default.width' % THEME_NAME,
                'themes/%s/theme.yaml line %d'
                % (THEME_NAME, lineOf(THEME, 'width: wide'))))

    # 3. a bad value in a layout
    body = BASE % {'layout': LAYOUT_NAME, 'theme': 'circuit'}
    out.append(('a bad value in a layout',
                Fixture(body, layout=LAYOUT), (),
                'layouts.%s.regions.clock.width' % LAYOUT_NAME,
                'layouts/%s.yaml line %d'
                % (LAYOUT_NAME, lineOf(LAYOUT, 'width: nine'))))

    # 4. something absent has no line to give, and must not invent one
    body = '\n'.join(line for line in (BASE % {'layout': 'classic',
                                               'theme': 'circuit'}
                                       ).splitlines()
                     if 'widgets' not in line and 'clock:' not in line) + '\n'
    out.append(('a setting that is not set names no line',
                Fixture(body), (), 'widgets', 'NO LINE'))

    # 5. a value from the command line, on a path the file also holds a
    # good value for.  Naming the file's line here points at the wrong
    # thing entirely
    body = BASE % {'layout': 'classic', 'theme': 'circuit'}
    out.append(('a value from --set says so',
                Fixture(body), ('--set', 'widgets.clock.region=nosuchregion'),
                'widgets.clock.region', '(--set)'))

    return out


def main():
    failed = 0
    for name, fixture, extra, path, want in cases():
        with fixture as f:
            found = check(f.configPath, extra)
            at = where(found, path)
        if at is None:
            print('  FAIL  %s' % name)
            print('          no finding at %s' % path)
            print('          got: %s' % [a for _, a, _ in found])
            failed += 1
            continue
        if want == 'NO LINE':
            expect, ok = 'no line in the path', ' line ' not in at
        elif want.startswith('CONFIG '):
            # the config arrives as whatever path was on the command
            # line, so its name is asked for rather than spelled out
            expect = '%s and %s' % (os.path.basename(f.configPath), want[7:])
            ok = os.path.basename(f.configPath) in at and want[7:] in at
        else:
            expect = want
            ok = expect in at or expect.replace('/', os.sep) in at
        if ok:
            print('  ok    %-42s %s' % (name, at))
        else:
            failed += 1
            print('  FAIL  %s' % name)
            print('          wanted %s' % expect)
            print('          got    %s' % at)

    print('\n  %d cases, %d failed' % (len(cases()), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
