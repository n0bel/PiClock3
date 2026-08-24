import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtNetwork import QNetworkReply

from .Projection import getCorners, getTileXY, LatLng
from .WebGet import WebGet

logger = logging.getLogger(__name__)


class TileFetcher():
    fetchers = []

    def __init__(self, center, zoom, width, height, tileurl, callback,
                 caption=None, tilesize=256, params=None):
        self.center = center
        self.zoom = zoom
        self.width = width
        self.height = height
        self.tileurl = tileurl
        self.callback = callback
        self.caption = caption
        self.tilesize = tilesize
        self.params = params

        TileFetcher.fetchers.append(self)

        corners = getCorners(center, zoom, width, height)
        nw = getTileXY(LatLng(corners['N'], corners['W']), zoom)
        ne = getTileXY(LatLng(corners['N'], corners['E']), zoom)
        sw = getTileXY(LatLng(corners['S'], corners['W']), zoom)
        self.origin = nw

        self.tiles = dict()
        for y in range(int(nw['Y']), int(sw['Y']) + 1):
            self.tiles[y] = dict()
            for x in range(int(nw['X']), int(ne['X']) + 1):
                self.tiles[y][x] = dict()

        self.yTiles = len(self.tiles)
        self.xTiles = len(list(self.tiles.values())[0])
        logger.debug("tiler %dx%d tiles for %dx%d px at zoom %d",
                     self.xTiles, self.yTiles, width, height, zoom)
        self.getTiles()

    def getTiles(self):
        """ask for every tile of this frame at once"""
        wanted = [(y, x) for y in self.tiles for x in self.tiles[y]]
        self.pending = len(wanted)
        if not self.pending:
            self.finish()
            return
        for y, x in wanted:
            WebGet(self.tileurl(self.zoom, x, y),
                   self.gotTile, {'x': x, 'y': y})

    def gotTile(self, error, data, params):
        i = QImage()
        if error == QNetworkReply.NoError:
            i.loadFromData(data)
        else:
            logger.debug("tile %d,%d failed: %s", params['x'], params['y'], error)
        self.tiles[params['y']][params['x']]['image'] = i
        self.pending -= 1
        if self.pending < 1:
            self.finish()

    def finish(self):
        pixmap = self.combineTiles()
        if self in TileFetcher.fetchers:
            TileFetcher.fetchers.remove(self)
        self.callback(pixmap, self.params)

    def combineTiles(self):
        ts = self.tilesize
        full = QImage(self.xTiles * ts, self.yTiles * ts, QImage.Format_ARGB32)
        full.fill(Qt.transparent)
        painter = QPainter()
        painter.begin(full)
        yp = 0
        for y in self.tiles:
            xp = 0
            for x in self.tiles[y]:
                tile = self.tiles[y][x].get('image')
                if tile is not None and not tile.isNull():
                    painter.drawImage(xp, yp, tile)
                xp += ts
            yp += ts
        painter.end()

        xo = int((int(self.origin['X']) - self.origin['X']) * ts)
        yo = int((int(self.origin['Y']) - self.origin['Y']) * ts)
        cropped = full.copy(-xo, -yo, self.width, self.height)

        if self.caption:
            self.drawCaption(cropped)
        return QPixmap(cropped)

    def drawCaption(self, image):
        painter = QPainter()
        painter.begin(image)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(QFont("Arial", 8))
        x = int(self.width * 0.03)
        y = int(self.height * 0.03)
        painter.setPen(QColor(63, 63, 63, 255))
        painter.drawText(x - 1, y - 1, self.caption)
        painter.drawText(x + 2, y + 1, self.caption)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(x, y, self.caption)
        painter.drawText(x + 1, y, self.caption)
        painter.end()
