"""Is the version a date, and does the clock say it?

    python3 tests/versiontest.py

The version is the date of the release, YYYY.MM.DD with an optional .N
for a second release that day, zero-padded so a plugin can compare two
with a plain string comparison.  --version prints it and exits 0, the way
--help does.

Needs PyQt5, because --version is read by PyQtPiClock3.py, which imports
it.
"""
import datetime
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3 import __version__  # noqa: E402

SHAPE = re.compile(r'^(\d{4})\.(\d{2})\.(\d{2})(\.[1-9]\d*)?$')


def main():
    failed = checked = 0

    def check(name, ok, said):
        nonlocal failed, checked
        checked += 1
        if ok:
            print('ok   %s' % name)
        else:
            failed += 1
            print('FAIL %s: %s' % (name, said))

    found = SHAPE.match(__version__)
    check('the version is YYYY.MM.DD', found, repr(__version__))
    if found:
        try:
            datetime.date(*(int(found.group(n)) for n in (1, 2, 3)))
            real = True
        except ValueError:
            real = False
        check('the version is a real date', real, repr(__version__))

    # what a plugin's README asks for, against what ships
    check('a later date compares as later',
          '2026.10.09' < '2026.10.10' < '2026.11.01' < '2026.11.01.1'
          < '2027.01.01', 'the strings do not sort as dates')

    out = subprocess.run([sys.executable, 'PyQtPiClock3.py', '--version'],
                         capture_output=True, text=True)
    check('--version says it and exits 0',
          out.returncode == 0
          and out.stdout.strip() == 'PiClock3 %s' % __version__,
          'exit %d, said %r' % (out.returncode, out.stdout.strip()))

    print('%d cases, %d failed' % (checked, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
