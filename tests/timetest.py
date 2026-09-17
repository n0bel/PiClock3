"""Does a time default to the language's own way of writing one?

    python3 tests/timetest.py

The forecast corner and the digital face take their hour and minute from
the language file's time-format:, so a French clock reads 15:05 rather
than a 3:05 whose AM or PM its locale leaves blank.  This expands the
shipped defaults against the shipped language files.  Run on Windows, it
also checks that a %-I from a language file is converted before strftime
sees it.

Needs PyQt5, because Words lives in PiClock3.py, which imports Qt.  It opens
no window.
"""
import datetime
import os
import sys
from types import SimpleNamespace

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.DottedDict import DottedDict  # noqa: E402
from PiClock3.Languages import Languages  # noqa: E402
from PiClock3.Plugin import Plugin  # noqa: E402
from PiClock3.PiClock3 import Words  # noqa: E402

NOW = datetime.datetime(2026, 9, 17, 15, 5, 42)


def default(plugin, key):
    path = os.path.join('PiClock3', plugin, 'config.yaml')
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)[key]


def expander(code):
    """what a widget's expand() reaches, for a clock set to `code`"""
    piclock = SimpleNamespace(config={'language': code})
    piclock.languages = Languages(piclock)
    piclock.languages.load()
    values = DottedDict()
    values['language'] = Words(piclock)
    now = DottedDict()
    now['now'] = NOW
    values['plugin-data'] = now
    return values


def corner(code):
    """the forecast's hour corner, the way Forecast.start builds it"""
    values = expander(code)
    fmt = Plugin.strftimePortableFormat(
        values.expand(default('Forecast', 'hour-format')))
    return NOW.strftime(fmt)


def face(code):
    """the digital face's first line, the way DigitalClock.tick builds it"""
    values = expander(code)
    fmt = Plugin.strftimePortableFormat(default('DigitalClock', 'format'))
    return values.expand(fmt).split('\n')[0]


def cases():
    got = corner('en')
    # after the day's name and its space, so a padded 03:05 does not pass
    yield 'English forecast hours are twelve-hour', ' 3:05' in got, got
    for code in ('fr', 'de', 'nl'):
        got = corner(code)
        yield '%s forecast hours are 24-hour' % code, '15:05' in got, got
    got = face('en')
    yield 'the English face reads 3:05', got == '3:05', got
    got = face('fr')
    yield 'the French face reads 15:05', got == '15:05', got
    got = face('fr-CA')
    yield 'a region of French takes French', got == '15:05', got


def main():
    failed = 0
    found = list(cases())
    for name, ok, got in found:
        if ok:
            print('  ok    %s' % name)
        else:
            failed += 1
            print('  FAIL  %-44s got %r' % (name, got))
    print('\n  %d cases, %d failed' % (len(found), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
