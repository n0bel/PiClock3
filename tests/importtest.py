"""Does every module still import?

    python3 tests/importtest.py

The other suites reach eleven of the thirty-odd modules here, because the
clock loads a plugin only when a config names it - so a broken import in a
provider nothing in the tests uses goes unnoticed until the clock is started
with a config that wants it.

That is a narrow question and worth asking on its own: it catches a syntax
error anywhere in the tree, a name used at import time that is no longer
imported, and a circular import.  It says nothing about whether anything
works.

Needs PyQt5, since most of these import it.  It opens no window.
"""
import importlib
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

PACKAGE = 'PiClock3'


def modules():
    """every module in the package, and every plugin installed beside it.

    A folder holding an __init__.py is imported as the package, the way a
    config names it - `PiClock3.Mapbox`, not `PiClock3.Mapbox.Mapbox` - so
    what is tested is what the loader will do.
    """
    found = []
    for base, dotted in ((PACKAGE, PACKAGE), ('plugins', 'plugins')):
        if not os.path.isdir(base):
            continue
        for leaf in sorted(os.listdir(base)):
            path = os.path.join(base, leaf)
            if os.path.isdir(path):
                if os.path.isfile(os.path.join(path, '__init__.py')):
                    found.append('%s.%s' % (dotted, leaf))
            elif (leaf.endswith('.py') and leaf != '__init__.py'
                  and base == PACKAGE):
                found.append('%s.%s' % (dotted, leaf[:-3]))
    return found


def main():
    failed = 0
    for name in modules():
        try:
            importlib.import_module(name)
        except Exception as e:
            failed += 1
            print('  FAIL  %-28s %s: %s' % (name, type(e).__name__, e))
        else:
            print('  ok    %s' % name)

    # the clock itself is a module too, and the one a contributor is most
    # likely to have edited
    try:
        spec = importlib.util.spec_from_file_location(
            'clock', os.path.join(ROOT, 'PyQtPiClock3.py'))
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    except Exception as e:
        failed += 1
        print('  FAIL  %-28s %s: %s' % ('PyQtPiClock3.py',
                                        type(e).__name__, e))
    else:
        print('  ok    PyQtPiClock3.py')

    print('\n  %d modules, %d failed' % (len(modules()) + 1, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
