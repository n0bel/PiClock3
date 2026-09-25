"""Do pages turn by themselves, for as long as each one says?

    python3 tests/pagetest.py

A page's dwell: wins, page-dwell: covers the rest, and 0 or nothing at
all is a page that waits to be turned.  Every turn restarts the timer, so
this turns pages through the clock's own nextPage and reads the timer it
leaves behind.

Needs PyQt5, because the timer is Qt's.  It opens no window.
"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from PiClock3.PiClock3 import PiClock3  # noqa: E402

app = QApplication(sys.argv)


class Page:
    """as much of a page frame as nextPage touches"""

    def __init__(self, number, visible):
        self.pageNumber = number
        self.visible = visible

    def isVisible(self):
        return self.visible

    def setVisible(self, visible):
        self.visible = visible


def clock(pages, pageDwell=None):
    """a stand-in for the clock, with pages given as {name: dwell}"""
    config = SimpleNamespace(pages={})
    config.get = lambda key: pageDwell if key == 'page-dwell' else None
    frames = {}
    for i, (name, dwell) in enumerate(pages.items()):
        config.pages[name] = {'order': i}
        if dwell != 'unset':
            config.pages[name]['dwell'] = dwell
        frames[name] = Page(i, i == 0)
    stub = SimpleNamespace(config=config, pages=frames, slideshows=[],
                           plugins={}, pageTimer=QTimer())
    stub.pageTimer.setSingleShot(True)
    stub.dwell = lambda name: PiClock3.dwell(stub, name)
    return stub


def after(stub, n):
    """turn n pages and say which is showing and how long it will stay"""
    PiClock3.nextPage(stub, n)
    showing = [name for name, page in stub.pages.items() if page.visible]
    active = stub.pageTimer.isActive()
    return showing, stub.pageTimer.interval() if active else None


# (name, pages as {name: dwell}, page-dwell, turns, what shows, ms or None)
CASES = [
    ('nothing set turns nothing', {'a': 'unset', 'b': 'unset'}, None, 0,
     ['a'], None),
    ('a page dwell starts at startup', {'a': 60, 'b': 20}, None, 0,
     ['a'], 60000),
    ('the next page gets its own', {'a': 60, 'b': 20}, None, 1,
     ['b'], 20000),
    ('and it wraps around', {'a': 60, 'b': 20}, None, 2, ['a'], 60000),
    ('page-dwell covers a page that says nothing',
     {'a': 'unset', 'b': 20}, 30, 0, ['a'], 30000),
    ('a page dwell wins over page-dwell', {'a': 60, 'b': 20}, 30, 0,
     ['a'], 60000),
    ('0 is a page that waits, whatever page-dwell says',
     {'a': 0, 'b': 20}, 30, 0, ['a'], None),
    ('a blank dwell is page-dwell', {'a': None, 'b': 20}, 30, 0,
     ['a'], 30000),
    ('a fraction of a second is kept', {'a': 2.5}, None, 0, ['a'], 2500),
]


def main():
    failed = 0
    for name, pages, pageDwell, turns, shows, ms in CASES:
        got = after(clock(pages, pageDwell), turns)
        if got == (shows, ms):
            print('ok   %s' % name)
        else:
            failed += 1
            print('FAIL %s: wanted %s for %s ms, got %s for %s ms'
                  % (name, shows, ms, got[0], got[1]))

    # a turn from a page that turns to one that waits stops the timer,
    # rather than letting the old page's dwell turn the new one on
    stub = clock({'a': 20, 'b': 0})
    PiClock3.nextPage(stub, 0)
    got = after(stub, 1)
    if got == (['b'], None):
        print('ok   turning to a page that waits stops the timer')
    else:
        failed += 1
        print('FAIL turning to a page that waits: got %s for %s ms' % got)

    print('%d cases, %d failed' % (len(CASES) + 1, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
