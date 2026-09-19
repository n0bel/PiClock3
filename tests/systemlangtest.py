"""Which language does a clock speak when its config names none?

    python3 tests/systemlangtest.py

It speaks the machine's, which means reading the same variables glibc
reads and turning what they hold into a code: de_AT.UTF-8@euro is de-at,
and a file claiming de answers it.  The parsing is the half that breaks
quietly, so most of these are a string in and a code out.

A regional file takes what it does not say from the language it is a
region of, which is checked here too, on files written in a folder of
their own.

The environment is faked, so the answers do not depend on the machine
this runs on.

Needs PyQt5, because Languages is imported through the package.
"""
import logging
import os
import shutil
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.Languages import Languages  # noqa: E402

NAMES = ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG')

# a folder of our own, beside the shipped languages, taken away at the end
FIXTURE = os.path.join('languages')
REGION = os.path.join(FIXTURE, 'en-ZZ.yaml')
REGIONAL = """\
code: [en-ZZ]
name: English (a region made up for this test)
units: nautical
date-format: '%A {day} %B %Y'
conditions:
  '+RASN': Sleet
"""


def chosen(config=None, **environment):
    """the code a clock lands on, with the environment saying that"""
    kept = {name: os.environ.pop(name, None) for name in NAMES}
    for name, value in environment.items():
        os.environ[name] = value
    try:
        piclock = SimpleNamespace(config=config or {})
        piclock.languages = Languages(piclock)
        # the file Debian keeps it in, and Windows, are the machine's own
        # answers and would make this depend on where it runs
        piclock.languages.fromFile = lambda: None
        piclock.languages.fromWindows = lambda: None
        piclock.languages.load()
        return piclock.languages.chosen()
    finally:
        for name, value in kept.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value


def reading():
    """the codes the parser makes of what a locale looks like"""
    for text, want in (('de_AT.UTF-8@euro', 'de-at'),
                       ('fr_FR.UTF-8', 'fr-fr'),
                       ('en_GB', 'en-gb'),
                       ('nl', 'nl'),
                       ('C', None), ('POSIX', None), ('', None),
                       ('C.UTF-8', None)):
        got = Languages.asCode(text)
        yield ('%r reads as %r' % (text, want), got == want, got)


def cases():
    for case in reading():
        yield case

    got = chosen(LANG='fr_FR.UTF-8')
    yield ('LANG French is a French clock', got == 'fr-fr', got)

    got = chosen(LANG='de_DE.UTF-8', LC_ALL='fr_FR.UTF-8')
    yield ('LC_ALL outranks LANG', got == 'fr-fr', got)

    got = chosen(LANG='de_DE.UTF-8', LC_ALL='fr_FR.UTF-8',
                 LANGUAGE='nl_NL:en')
    yield ('LANGUAGE outranks both', got == 'nl-nl', got)

    got = chosen(LANGUAGE='zz_ZZ:fr_FR')
    yield ('a LANGUAGE list takes the first one a file answers to',
           got == 'fr-fr', got)

    got = chosen(LC_ALL='C', LANG='C')
    yield ('C is no language, so English', got == 'en', got)

    got = chosen()
    yield ('nothing set is English', got == 'en', got)

    got = chosen(LANG='zz_ZZ.UTF-8')
    yield ('a language no file answers to is English', got == 'en', got)

    got = chosen({'language': 'de'}, LANG='fr_FR.UTF-8')
    yield ("the config's own language outranks the machine",
           got == 'de', got)

    got = chosen({'language': 'system'}, LANG='fr_FR.UTF-8')
    yield ('system asks the machine outright', got == 'fr-fr', got)

    got = chosen(LANG='en_GB.UTF-8')
    yield ('a British machine is a British clock', got == 'en-gb', got)


def british():
    """the shipped en-GB, which says little and inherits the rest"""
    piclock = SimpleNamespace(config={'language': 'en-GB'})
    piclock.languages = Languages(piclock)
    piclock.languages.load()
    words = piclock.languages
    yield ('British English measures in the uk set',
           words.setting('units') == 'uk', words.setting('units'))
    yield ('with the day before the month',
           words.setting('date-format') == '%A {day} %B %Y',
           words.setting('date-format'))
    yield ('and English words and twelve-hour times',
           words.strings().get('sunrise') == 'Sunrise'
           and words.setting('time-format') == '%-I:%M',
           (words.strings().get('sunrise'), words.setting('time-format')))


def regional():
    """a region inherits from the language it is a region of"""
    piclock = SimpleNamespace(config={'language': 'en-ZZ'})
    piclock.languages = Languages(piclock)
    piclock.languages.load()
    words = piclock.languages
    yield ('a region keeps its own condition',
           words.conditions().get('+RASN') == 'Sleet',
           words.conditions().get('+RASN'))
    yield ('and takes the rest from its base language',
           words.conditions().get('FG') == 'Fog',
           words.conditions().get('FG'))
    yield ('and the words it does not write',
           words.strings().get('sunrise') == 'Sunrise',
           words.strings().get('sunrise'))
    yield ('and the settings it does not write',
           words.setting('time-format') == '%-I:%M',
           words.setting('time-format'))
    yield ('while its own settings stand',
           words.setting('units') == 'nautical', words.setting('units'))
    yield ('and the locale of its base where it names none',
           'en_US.UTF-8' in (words.locales() or []), words.locales())


def main():
    # the warning a language nobody wrote is meant to raise
    logging.disable(logging.WARNING)
    if os.path.exists(REGION):
        print('  %s is already there; not overwriting it' % REGION)
        return 1
    made = not os.path.isdir(FIXTURE)
    os.makedirs(FIXTURE, exist_ok=True)
    with open(REGION, 'w', encoding='utf-8') as fh:
        fh.write(REGIONAL)
    try:
        failed = 0
        found = list(cases()) + list(regional()) + list(british())
        for name, ok, got in found:
            if ok:
                print('  ok    %s' % name)
            else:
                failed += 1
                print('  FAIL  %-52s got %r' % (name, got))
        print('\n  %d cases, %d failed' % (len(found), failed))
        return 1 if failed else 0
    finally:
        os.remove(REGION)
        if made:
            shutil.rmtree(FIXTURE, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
