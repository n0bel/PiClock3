import logging
import datetime

from ..Plugin import Plugin
from ..WebGet import WebGet


from PyQt5 import (QtGui, QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QUrl)
from PyQt5.QtGui import (QPixmap, QImage, QPainter, QFont, QColor)
from PyQt5.QtWidgets import (QWidget, QLabel, QMessageBox, QListWidget,
                             QPushButton, QApplication, QTableWidget,
                             QGridLayout, QListWidgetItem, QTableWidgetItem,
                             QLineEdit, QFrame)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest)

from ..Projection import (getCorners, getPoint, getTileXY, LatLng)

logger = logging.getLogger(__name__)

class GetRadarPixmap():
    getRadarPixmaps = []

    def __init__(self, timeSlot, center, width, height, radarConfig, config, callback):
        super().__init__()
        self.timeSlot = timeSlot
        self.center = center
        self.width = width
        self.height = height
        self.zoom = radarConfig.zoom
        self.radarConfig = radarConfig
        self.config = config
        self.callback = callback
        
        GetRadarPixmap.getRadarPixmaps.append(self)

        self.corners = getCorners(self.center, self.zoom,
                                  width, height)
        self.cornerTiles = {
         "NW": getTileXY(LatLng(self.corners["N"],
                                self.corners["W"]), self.zoom),
         "NE": getTileXY(LatLng(self.corners["N"],
                                self.corners["E"]), self.zoom),
         "SE": getTileXY(LatLng(self.corners["S"],
                                self.corners["E"]), self.zoom),
         "SW": getTileXY(LatLng(self.corners["S"],
                                self.corners["W"]), self.zoom) }
        self.tiles = dict()
        for y in range(int(self.cornerTiles["NW"]["Y"]),
                       int(self.cornerTiles["SW"]["Y"])+1):
            self.tiles[y] = dict()
            for x in range(int(self.cornerTiles["NW"]["X"]),
                           int(self.cornerTiles["NE"]["X"])+1):
                self.tiles[y][x] = dict()
                radarColor = 6
                radarSmooth = 1
                radarSnow = 1
                radarOldColor = False;
                if 'color' in config:
                    radarColor = config.color
                if 'smooth' in config:
                    radarSmooth = config.smooth
                if 'snow' in config:
                    radarSnow = config.snow
                if 'oldcolor' in config:
                    radarOldColor = config.oldcolor
                if 'color' in radarConfig:
                    radarColor = radarConfig.color
                if 'smooth' in radarConfig:
                    radarSmooth = radarConfig.smooth
                if 'snow' in radarConfig:
                    radarSnow = radarConfig.snow
                if 'oldcolor' in radarConfig:
                    radarOldColor = radarConfig.oldcolor
                    
                tail = "/256/%d/%d/%d/%d/%d_%d.png" % (self.zoom, x, y,
                                                       radarColor,
                                                       radarSmooth,
                                                       radarSnow)
                if radarOldColor:
                    tail = "/256/%d/%d/%d.png?color=%d" % (self.zoom, x, y,
                                                           radarColor
                                                           )
                self.tiles[y][x]['tail'] = tail

        self.yTiles = len(self.tiles)
        self.xTiles = len(list(self.tiles.values())[0])

        logger.debug("tiles xlen=%d ylen=%d %s", self.xTiles, self.yTiles, self.tiles)
        self.getNextNeededTile()

    def getNextNeededTile(self):
        for y in self.tiles:
            for x in self.tiles[y]:
                if not 'image' in self.tiles[y][x]:
                    params = { 'x': x, 'y': y }
                    logger.debug("getNextNeededTile %d %d", x, y)
                    url = "https://tilecache.rainviewer.com/v2/radar/%d/%s" % (self.timeSlot, self.tiles[y][x]['tail'])                    
                    WebGet(url, self.gotNextNeededTile, params)
                    return
        logger.debug("getNextNeededTile got all tiles")
        # time to combine, crop, return
        p = self.combineTiles()
        self.callback(p, self.timeSlot)

    def gotNextNeededTile(self, error, data, params):
        y = params['y']
        x = params['x']
        logger.debug("gotNextNeededTile error=%s %d %d", error, x, y)
        i = QImage()
        if error == QNetworkReply.NoError:
            i.loadFromData(data)
            logger.debug("image size %s", i.size())
        self.tiles[y][x]['image'] = i
        self.getNextNeededTile()
        
    def combineTiles(self):
        fullImage = QImage(self.xTiles*256, self.yTiles*256,
                    QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(fullImage)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.setFont(QFont("Arial", 10))
        xo = self.cornerTiles["NW"]["X"]
        xo = int((int(xo) - xo)*256)
        yo = self.cornerTiles["NW"]["Y"]
        yo = int((int(yo) - yo)*256)
        yp = 0
        for y in self.tiles:
            xp = 0
            for x in self.tiles[y]:
                tileImage = self.tiles[y][x]['image']
                if tileImage.format() == 5:
                    painter.drawImage(xp, yp, tileImage)
                # painter.drawRect(x, y, 255, 255)
                # painter.drawText(x+3, y+12, self.tiletails[i])
                xp += 256
            yp += 256
        painter.end()
        painter = None
        croppedImage = fullImage.copy(-xo, -yo, self.width, self.height)
        painter2 = QPainter()
        painter2.begin(croppedImage)
        timestamp = "{0:%H:%M} rainvewer.com".format(
                    datetime.datetime.fromtimestamp(self.timeSlot))
        painter2.setPen(QColor(63, 63, 63, 255))
        painter2.setFont(QFont("Arial", 8))
        xt = int(self.width * 0.03)
        yt = int(self.height * 0.03)
        painter2.setRenderHint(QPainter.TextAntialiasing)
        painter2.drawText(xt-1, yt-1, timestamp)
        painter2.drawText(xt+2, yt+1, timestamp)
        painter2.setPen(QColor(255, 255, 255, 255))
        painter2.drawText(xt, yt, timestamp)
        painter2.drawText(xt+1, yt, timestamp)
        painter2.end()
        painter2 = None
        pixmap = QPixmap(croppedImage)
        return pixmap
        
class RainViewer(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        logger.debug("rainviewer start")

        return
        
    def pageChange(self):
        return

    def getRadarPixmap(self, timeSlot, radarConfig, frameRect, callback):
        logger.debug("rainviewer getpixmap %s", timeSlot)
        GetRadarPixmap(timeSlot,
                LatLng(float(self.piclock.expand(radarConfig.center["lattitude"])),
                             float(self.piclock.expand(radarConfig.center["longitude"]))),
                frameRect.width(),
                frameRect.height(), 
                radarConfig,
                self.config,
                callback)
        return

    def gotRadarPixmap(self, error, data, callback, parms):
        logger.debug("rainviewer gotpixmap %s", error)    
        if error != QNetworkReply.NoError:
            return
        self.mapPixmap = QPixmap()
        #self.mapPixmap.loadFromData(data)
        #logger.debug("mapPixmap %s", self.mapPixmap.size())
        #if self.mapPixmap.size() != self.frameRect.size():
        #    self.mapPixmap = self.mapPixmap.scaled(self.frameRect.size(),
        #                                             Qt.KeepAspectRatio,
        #                                             Qt.SmoothTransformation)
        callback(self.mapPixmap)
        return