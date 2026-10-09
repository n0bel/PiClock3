"""Which unit set does a clock use when its config names none?

    python3 tests/unitsettest.py

A language file names the set a clock in that language measures in, so
`language: fr` alone is metric.  `units:` in the config outranks it, since
a French speaker in Minnesota still wants Fahrenheit.

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


def units(config):
    piclock = SimpleNamespace(config=config)
    piclock.languages = Languages(piclock)
    piclock.languages.load()
    found = Units(piclock)
    found.load()
    return found


def cases():
    for code, set_, speed in (('en', 'default', '10.0mph'),
                              ('en-GB', 'uk', '10.0mph'),
                              ('fr', 'metric', '16.1km/h'),
                              ('de', 'metric', '16.1km/h'),
                              ('nl', 'metric', '16.1km/h')):
        found = units({'language': code})
        yield ('%s measures in %s' % (code, set_),
               found.setName() == set_, found.setName())
        # 4.4704 m/s is 10 mph, and the set decides which of the two shows
        got = found.format('speed', 'mps', 4.4704, setName=found.setName())
        yield ('%s shows a wind speed as %s' % (code, speed),
               got == speed, got)
        # the way a provider calls it, with no set: the clock's, not the
        # default set's
        got = found.format('speed', 'mps', 4.4704)
        yield ('%s with no set named still shows %s' % (code, speed),
               got == speed, got)

    found = units({'units': 'metric'})
    got = found.format('temperature', 'C', 22.5)
    yield ("no set named follows the config's units:",
           got.endswith('°C'), got)
    got = found.format('altimeter', 'mb', 1013.2)
    yield ('and its pressure too', got.endswith('hPa'), got)

    found = units({'units': 'metric'})
    got = found.format('temperature', 'C', 22.5, setName='default')
    yield ('a set named outright still wins over the clock',
           got.endswith('°F'), got)

    found = units({'language': 'en-GB'})
    got = found.format('temperature', 'C', 20, setName=found.setName())
    yield ('British English is Celsius beside its mph',
           got.endswith('°C'), got)

    found = units({'language': 'fr', 'units': 'default'})
    yield ("a config's own units: outranks the language",
           found.setName() == 'default', found.setName())

    found = units({'language': 'nosuch'})
    yield ('a language with no units: measures in the default set',
           found.setName() == 'default', found.setName())


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
