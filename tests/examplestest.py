"""Does every shipped example pass --check without a word?

    python3 tests/examplestest.py

The examples are what people copy, so a problem or a warning in one is
one they copy too.  Each runs the way the docs say to, from the PiClock3
folder.

An example's !include ApiKeys.yaml is read from the PiClock3 folder.  If
there is none, this writes one for the run, with a stand-in for every key
examples/ApiKeys.yaml names, and removes it afterward.  The shipped
placeholders themselves are a problem to --check, as they should be for
somebody who forgot to fill them in.

Needs PyQt5, because --check is read by PyQtPiClock3.py, which imports
it.
"""
import glob
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# the last line --check writes
TALLY = re.compile(r': (\d+) problems?, (\d+) warnings?$')


def standIns():
    """write ApiKeys.yaml if there is none, and say whether this did"""
    if os.path.exists('ApiKeys.yaml'):
        return False
    with open('examples/ApiKeys.yaml', encoding='utf-8') as fh:
        names = yaml.safe_load(fh)
    with open('ApiKeys.yaml', 'w', encoding='utf-8') as fh:
        yaml.safe_dump({name: 'a-stand-in-key' for name in names}, fh)
    return True


def main():
    failed = 0
    examples = sorted(path for path in glob.glob('examples/*.yaml')
                      if os.path.basename(path) != 'ApiKeys.yaml')
    wrote = standIns()
    try:
        for path in examples:
            out = subprocess.run([sys.executable, 'PyQtPiClock3.py',
                                  '--check', path],
                                 capture_output=True, text=True)
            lines = [line for line in out.stdout.splitlines()
                     if line.strip()]
            tally = TALLY.search(lines[-1]) if lines else None
            if (out.returncode == 0 and tally
                    and tally.groups() == ('0', '0')):
                print('ok   %s' % path)
                continue
            failed += 1
            print('FAIL %s' % path)
            for line in lines or out.stderr.splitlines():
                print('       %s' % line)
    finally:
        if wrote:
            os.remove('ApiKeys.yaml')

    print('%d examples, %d failed' % (len(examples), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
