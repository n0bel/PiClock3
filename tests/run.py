"""Every suite in here, one after another.

    python3 tests/run.py

Each is a program in its own right and says its own results; this runs
them and answers with an exit code, for the times you want one number.

A suite that cannot run - no PyQt5 for the two that need it - is reported
as skipped rather than failed, since not having Qt installed is a fact
about the machine rather than about the change being tested.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SUITES = ('importtest.py', 'checktest.py', 'logtest.py', 'linetest.py')


def run(name):
    """one suite, as (how it went, its last line)"""
    out = subprocess.run([sys.executable, os.path.join(HERE, name)],
                         cwd=ROOT, capture_output=True, text=True)
    text = out.stdout + out.stderr
    if 'ModuleNotFoundError' in text and 'PyQt5' in text:
        return 'skip', 'no PyQt5 on this python'
    tail = [line for line in text.splitlines() if line.strip()]
    return ('ok' if out.returncode == 0 else 'FAIL',
            tail[-1].strip() if tail else 'said nothing')


def main():
    worst = 0
    for name in SUITES:
        how, said = run(name)
        print('  %-5s %-14s %s' % (how, name, said))
        if how == 'FAIL':
            worst = 1
    return worst


if __name__ == '__main__':
    sys.exit(main())
