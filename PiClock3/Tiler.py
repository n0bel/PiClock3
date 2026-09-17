import logging

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtNetwork import QNetworkReply

from .Projection import tileGrid
from .WebGet import WebGet

logger = logging.getLogger(__name__)


class TileFetcher():
    """one frame's tiles, fetched at once and flattened into a pixmap.

    Answers callback(pixmap, params, failed=..., tiles=...): `failed` is
    the squares of the pixmap whose tile did not arrive, and `tiles` how
    many were asked for, so an empty square can be told from clear sky.
    """
    fetchers = []

    def __init__(self, center, zoom, width, height, tileurl, callback,
                 tilesize=256, params=None):
        self.center = center
        self.zoom = zoom
        self.width = width
        self.height = height
        self.tileurl = tileurl
        self.callback = callback
        self.tilesize = tilesize
        self.params = params

        TileFetcher.fetchers.append(self)

        grid = tileGrid(center, zoom, width, height, tilesize)
        self.origin = grid['origin']

        self.tiles = dict()
        for y in grid['y']:
            self.tiles[y] = dict()
            for x in grid['x']:
                self.tiles[y][x] = dict()

        self.yTiles = len(self.tiles)
        self.xTiles = len(list(self.tiles.values())[0])
        logger.debug("tiler %dx%d tiles for %dx%d px at zoom %d",
                     self.xTiles, self.yTiles, width, height, zoom)
        self.getTiles()

    def getTiles(self):
        """ask for every tile of this frame at once"""
        n = 2 ** self.zoom
        # a row off the top or bottom of the world is left empty and paints
        # transparent.  the key stays either way: the grid is laid out in the
        # order it is walked, so a missing entry would shift the rest.
        wanted = [(y, x) for y in self.tiles for x in self.tiles[y]
                  if 0 <= y < n]
        self.pending = len(wanted)
        self.asked = len(wanted)
        if not self.pending:
            self.finish()
            return
        for y, x in wanted:
            # east of the last column is the first one
            WebGet(self.tileurl(self.zoom, x % n, y),
                   self.gotTile, {'x': x, 'y': y})

    def gotTile(self, error, data, params):
        i = QImage()
        if error == QNetworkReply.NoError:
            i.loadFromData(data)
        else:
            logger.debug("tile %d,%d failed: %s",
                         params['x'], params['y'], error)
        entry = self.tiles[params['y']][params['x']]
        entry['image'] = i
        # an answer that is not a picture is as missing as no answer
        entry['failed'] = i.isNull()
        self.pending -= 1
        if self.pending < 1:
            self.finish()

    def finish(self):
        pixmap, failed = self.combineTiles()
        if self in TileFetcher.fetchers:
            TileFetcher.fetchers.remove(self)
        self.callback(pixmap, self.params, failed=failed, tiles=self.asked)

    def combineTiles(self):
        """the flattened pixmap, and the squares of it that are missing"""
        ts = self.tilesize
        full = QImage(self.xTiles * ts, self.yTiles * ts, QImage.Format_ARGB32)
        full.fill(Qt.transparent)
        xo = int((int(self.origin['X']) - self.origin['X']) * ts)
        yo = int((int(self.origin['Y']) - self.origin['Y']) * ts)
        view = QRect(0, 0, self.width, self.height)
        failed = []
        painter = QPainter()
        painter.begin(full)
        yp = 0
        for y in self.tiles:
            xp = 0
            for x in self.tiles[y]:
                tile = self.tiles[y][x].get('image')
                if tile is not None and not tile.isNull():
                    painter.drawImage(xp, yp, tile)
                elif self.tiles[y][x].get('failed'):
                    square = QRect(xp + xo, yp + yo, ts, ts) & view
                    if not square.isEmpty():
                        failed.append(square)
                xp += ts
            yp += ts
        painter.end()

        cropped = full.copy(-xo, -yo, self.width, self.height)

        return QPixmap(cropped), failed
