"""Is a wind direction written in the clock's language?

    python3 tests/compasstest.py

The sixteen points are letters in English and something else nearly
everywhere: O for ouest in French, Z for zuid in Dutch.  A language file
says its own in compass:, keyed by the English abbreviation, and a
language that says nothing keeps the English letters.

The degrees are turned into points against the shipped language files,
which is also a check that the shipped tables have all sixteen.

Needs PyQt5, because Units is loaded through the clock.
"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.Languages import Languages  # noqa: E402
from PiClock3.Units import Units  # noqa: E402

# degree -> the English point, the compass the clock asks for
POINTS = [(0, 'N'), (22.5, 'NNE'), (45, 'NE'), (67.5, 'ENE'),
          (90, 'E'), (112.5, 'ESE'), (135, 'SE'), (157.5, 'SSE'),
          (180, 'S'), (202.5, 'SSW'), (225, 'SW'), (247.5, 'WSW'),
          (270, 'W'), (292.5, 'WNW'), (315, 'NW'), (337.5, 'NNW')]

# what a few degrees read as in each language, from that language's own
# compass rose: fr.wikipedia Rose des vents, nl.wikipedia Kompasroos, and
# the German sixteen-point table
SAYS = {
    'en': {0: 'N', 90: 'E', 270: 'W', 202.5: 'SSW', 112.5: 'ESE'},
    'fr': {0: 'N', 90: 'E', 270: 'O', 202.5: 'SSO', 112.5: 'ESE'},
    'de': {0: 'N', 90: 'O', 270: 'W', 202.5: 'SSW', 112.5: 'OSO'},
    'nl': {0: 'N', 90: 'O', 270: 'W', 202.5: 'ZZW', 112.5: 'OZO'},
}


def units(code):
    piclock = SimpleNamespace(config={'language': code, 'units': 'default'})
    piclock.languages = Languages(piclock)
    piclock.languages.load()
    found = Units(piclock)
    found.load()
    return found


def cases():
    for code, wanted in sorted(SAYS.items()):
        found = units(code)
        for degrees, point in sorted(wanted.items()):
            got = found.format('direction', 'deg', degrees)
            yield ('%s: %g degrees is %s' % (code, degrees, point),
                   got == point, got)

    # every point, so a table that forgets one is caught rather than
    # quietly falling back to English
    for code in ('fr', 'de', 'nl'):
        found = units(code)
        drawn = [found.format('direction', 'deg', d) for d, _ in POINTS]
        english = [p for _, p in POINTS]
        same = [p for p, e in zip(drawn, english) if p == e]
        # N and a few others are the same word in these languages, but not
        # all sixteen are
        yield ('%s translates the points that differ' % code,
               len(same) < len(english), drawn)
        yield ('%s draws sixteen different points' % code,
               len(set(drawn)) == 16, drawn)

    found = units('nosuch')
    got = found.format('direction', 'deg', 270)
    yield ('a language with no table keeps the English letters',
           got == 'W', got)


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
