"""Is a frame with missing tiles told apart from clear sky?

    python3 tests/frametest.py

A radar tile that does not arrive paints transparent, which on a map is
exactly what no rain looks like.  So the tiler has to say which squares are
missing, and the map has to hatch them, leave out a frame where nothing
arrived, and ask again for one that lost tiles - or a service having a bad
morning reads as a dry one.

The tiles and the map are built here: no network, and no window.

Needs PyQt5, because a frame is a QPixmap.
"""
import logging
import os
import sys
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from PyQt5.QtCore import (QBuffer, QByteArray, QIODevice,  # noqa: E402
                          QObject, QRect)
from PyQt5.QtGui import QColor, QGuiApplication, QImage, QPixmap  # noqa: E402
from PyQt5.QtNetwork import QNetworkReply  # noqa: E402

app = QGuiApplication(sys.argv[:1])

import PiClock3.Tiler as Tiler  # noqa: E402
from PiClock3.MapLoop.MapLoop import MapLoop  # noqa: E402
from PiClock3.Projection import LatLng  # noqa: E402

WIDTH, HEIGHT = 300, 200
OK = QNetworkReply.NoError
TIMEOUT = QNetworkReply.OperationCanceledError


def png(color):
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(QColor(color))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(data)


RED = png('#ff0000')


def fetch(answer):
    """a frame's tiles, each answered by answer(index) as (error, data)"""
    asked = []

    class FakeGet:
        def __init__(self, url, callback, params):
            asked.append((callback, params))

    got = {}

    def callback(pixmap, params, **kwargs):
        got.update(kwargs, pixmap=pixmap)

    real, Tiler.WebGet = Tiler.WebGet, FakeGet
    try:
        Tiler.TileFetcher(LatLng(45, -93), 4, WIDTH, HEIGHT, lambda z, x, y:
                          '%d/%d/%d' % (z, x, y), callback, params=1)
    finally:
        Tiler.WebGet = real
    for i, (reply, params) in enumerate(asked):
        error, data = answer(i)
        reply(error, data, params)
    return got


def tilerCases():
    whole = fetch(lambda i: (OK, RED))
    yield ('a whole frame reports no missing squares',
           whole['failed'] == [] and whole['tiles'] > 0,
           (whole['failed'], whole['tiles']))

    half = fetch(lambda i: (OK, RED) if i % 2 else (TIMEOUT, b''))
    yield ('a timed-out tile is a missing square',
           len(half['failed']) > 0, half['failed'])
    inside = QRect(0, 0, WIDTH, HEIGHT)
    yield ('every missing square lies on the map',
           all(inside.contains(r) for r in half['failed']), half['failed'])
    if half['failed']:
        square = half['failed'][0]
        pixel = half['pixmap'].toImage().pixelColor(square.center())
        yield ('a missing square paints transparent',
               pixel.alpha() == 0, pixel.name(QColor.HexArgb))
    else:
        yield ('a missing square paints transparent', False, 'no squares')

    junk = fetch(lambda i: (OK, b'not a picture'))
    yield ('an answer that is not a picture is missing too',
           len(junk['failed']) == junk['tiles'],
           (len(junk['failed']), junk['tiles']))


class Region:
    def isVisible(self):
        return True


def loop(times):
    """a MapLoop with nothing but what frames and compositing touch"""
    m = MapLoop.__new__(MapLoop)
    QObject.__init__(m)
    asked = []
    m.name = 'radar'
    m.config = {'frame-opacity': 1.0}
    m.region = Region()
    m.frameCount = len(times)
    m.frameProvider = SimpleNamespace(
        frameTimes=lambda count: list(times),
        getFramePixmap=lambda t, view, config, cb: asked.append(t))
    m.view = None
    base = QPixmap(WIDTH, HEIGHT)
    base.fill(QColor('#000000'))
    m.mapPixmap = base
    m.overlayPixmap = m.markerPixmap = m.brandMark = None
    m.overlayFailed = False
    m.framePixmaps, m.finished, m.missing = {}, {}, {}
    m.drawCaptions = lambda painter, t, w, h: None
    m.mapLabel = SimpleNamespace(shown=None)
    m.mapLabel.setPixmap = lambda p: setattr(m.mapLabel, 'shown', p)
    return m, asked


def clear():
    pixmap = QPixmap(WIDTH, HEIGHT)
    pixmap.fill(QColor(0, 0, 0, 0))
    return pixmap


def lit(image, rect):
    return sum(1 for x in range(rect.left(), rect.right(), 3)
               for y in range(rect.top(), rect.bottom(), 3)
               if QColor(image.pixel(x, y)).value() > 0)


def loopCases():
    left, right = QRect(0, 0, 150, 200), QRect(150, 0, 150, 200)

    m, asked = loop([10, 20])
    m.gotFramePixmap(clear(), 20)
    yield ('a callback with the pixmap alone is a whole frame',
           20 in m.finished and not m.missing, sorted(m.missing))

    m, asked = loop([10, 20])
    m.gotFramePixmap(clear(), 20, failed=[left], tiles=2)
    drawn = m.finished.get(20)
    yield ('a frame missing some tiles is still shown',
           drawn is not None, sorted(m.finished))
    image = drawn.toImage() if drawn else QImage()
    yield ('its missing square is hatched',
           drawn is not None and lit(image, left) > 0,
           lit(image, left) if drawn else None)
    yield ('the square that arrived is not',
           drawn is not None and lit(image, right) == 0,
           lit(image, right) if drawn else None)

    # a square that does not start on the hatch's step, missing alone in one
    # frame and beside its neighbor in the next
    west, east = QRect(0, 0, 153, 200), QRect(153, 0, 147, 200)
    a, _ = loop([10, 20])
    b, _ = loop([10, 20])
    a.gotFramePixmap(clear(), 20, failed=[east], tiles=2)
    b.gotFramePixmap(clear(), 20, failed=[west, east], tiles=3)
    one, both = a.finished[20].toImage(), b.finished[20].toImage()
    # antialiasing rounds a shade either way; a shifted line differs by far
    # more
    differ = sum(1 for x in range(153, 300) for y in range(0, 200)
                 if abs(QColor(one.pixel(x, y)).value()
                        - QColor(both.pixel(x, y)).value()) > 8)
    yield ('frames missing different squares hatch a square the same way',
           differ == 0, differ)

    m, asked = loop([10, 20])
    m.gotFramePixmap(clear(), 20, failed=[left, right], tiles=2)
    yield ('a frame where nothing arrived is left out',
           20 not in m.finished, sorted(m.finished))
    shown = m.mapLabel.shown
    yield ('with no other frame, the map is hatched instead',
           shown is not None and lit(shown.toImage(), right) > 0,
           lit(shown.toImage(), right) if shown else None)

    m, asked = loop([10, 20])
    m.gotFramePixmap(clear(), 20)
    kept = m.finished[20]
    m.missing[20] = [left]
    m.framePixmaps.pop(20)
    m.gotFramePixmap(clear(), 20, failed=[left, right], tiles=2)
    yield ('a retry where nothing arrived keeps the copy already shown',
           m.finished.get(20) is kept, sorted(m.finished))

    m, asked = loop([10, 20])
    m.gotFramePixmap(clear(), 10)
    m.gotFramePixmap(clear(), 20, failed=[left], tiles=2)
    del asked[:]
    m.intervalTick()
    yield ('the next interval asks again for the frame that lost tiles',
           asked == [20], asked)
    yield ('and keeps showing what it had meanwhile',
           20 in m.finished, sorted(m.finished))

    m.gotFramePixmap(clear(), 20)
    yield ('a retry that arrives whole is no longer missing',
           20 not in m.missing, sorted(m.missing))


def main():
    # the warnings a missing tile is meant to raise, said once per case
    logging.disable(logging.WARNING)
    failed = 0
    found = list(tilerCases()) + list(loopCases())
    for name, ok, got in found:
        if ok:
            print('  ok    %s' % name)
        else:
            failed += 1
            print('  FAIL  %-56s got %r' % (name, got))
    print('\n  %d cases, %d failed' % (len(found), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
