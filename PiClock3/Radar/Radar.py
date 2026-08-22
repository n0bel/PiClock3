import logging
import os
import time

from ..Plugin import Plugin

from PyQt5 import (QtGui, QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QTimer)
from PyQt5.QtGui import (QPixmap, QImage, QPainter, QColor)
from PyQt5.QtWidgets import (QWidget, QLabel, QMessageBox, QListWidget,
                             QPushButton, QApplication, QTableWidget,
                             QGridLayout, QListWidgetItem, QTableWidgetItem,
                             QLineEdit, QFrame)

from ..Projection import (getCorners, getPoint, getTileXY, LatLng)

logger = logging.getLogger(__name__)

class Radar(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.baseProvider = self.piclock.plugins[self.config['base-provider']]
        self.radarProvider = self.piclock.plugins[self.config['radar-provider']]
        self.mapPixmap = None
        self.markerPixmap = None
        self.radarPixmaps = dict()
        self.frame = 0

    def start(self):
        self.radarMap = QLabel(self.block)
        self.radarMap.setObjectName("radarMap")
        rr = self.block.frameRect()
        self.radarMap.setGeometry(rr)
        self.radarMap.setStyleSheet("#radarMap { background-color: transparent; }")
        self.radarMap.setAlignment(Qt.AlignCenter)

        self.radar = QLabel(self.radarMap)
        self.radar.setObjectName("radarx")
        self.radar.setGeometry(0, 0, rr.width(), rr.height())
        logger.debug("radar geom %s", self.radar.frameRect())
        self.radar.setStyleSheet("#radarx { background-color: transparent; }")

        self.radarOverlay = QLabel(self.radar)
        self.radarOverlay.setObjectName("radarOverlay")
        self.radarOverlay.setGeometry(0, 0, rr.width(), rr.height())
        self.radarOverlay.setStyleSheet("#radarOverlay { background-color: transparent; }")

        logger.debug("radar get map pixmap")        
        self.baseProvider.getMapPixmap(self.config, self.block.frameRect(), self.gotMapPixmap)
        self.interval = 60 * self.config.interval
        self.frames = self.config.frames
        self.intervalTimer = QTimer()
        self.intervalTimer.timeout.connect(self.intervalTick)
        self.intervalTimer.start(1000  * self.interval)
        self.intervalTick()
        self.animationTimer = QTimer()
        self.animationTimer.timeout.connect(self.animationTick)
        self.animationTimer.start(200)
        return


    def pageChange(self):
        self.intervalTick()
        return

    def timeSlot(self, slot, time=int(time.time())):
        t = (int(time / self.interval) - slot) * self.interval
        return t

    def intervalTick(self):
        logger.debug("tick %s %s", self.name, self.block.isVisible())
        if not self.block.isVisible():
            return
        timeToDrop = int(time.time()) - self.interval * (self.config.frames-1)
        frameTimes = sorted(self.radarPixmaps)
        while len(frameTimes) > 0 and frameTimes[0] < timeToDrop:
            self.radarPixmaps.pop(frameTimes[0])
            frameTimes.pop(0)
            
        self.getNextNeededFrame()

    def animationTick(self):
        if not self.block.isVisible():
            return;
        frameTimes = sorted(self.radarPixmaps)
        if len(frameTimes) < 1: return
        if self.frame >= len(frameTimes):
            self.frame = -6;
        f = self.frame
        if f < 0:
            f = len(frameTimes) - 1
        self.radar.setPixmap(self.radarPixmaps[frameTimes[f]])
        self.frame += 1
        
    def gotMapPixmap(self, pixmap):
        logger.info("radar got map pixmap");
        self.mapPixmap = pixmap;
        logger.debug("radar %s", pixmap.size())
        self.radarMap.setPixmap(pixmap)
        self.makeMarkerPixmap()
        
    def makeMarkerPixmap(self):
        self.markerPixmap = QPixmap(self.mapPixmap.size())
        self.markerPixmap.fill(Qt.transparent)
        #br = QBrush(QColor(Config.dimcolor))
        painter = QPainter()
        painter.begin(self.markerPixmap)
        #painter.fillRect(0, 0, self.mkpixmap.width(),
        #                 self.mkpixmap.height(), br)
        center = LatLng(float(self.piclock.expand(self.config.center.lattitude)),
                float(self.piclock.expand(self.config.center.longitude)))
        for marker in self.config.markers:
            if 'visible' not in marker or marker['visible'] == 1:
                loc = LatLng(float(self.piclock.expand(marker["location"]["lattitude"])),
                             float(self.piclock.expand(marker["location"]["longitude"])))
                pt = getPoint(
                    loc,
                    center,
                    int(self.piclock.expand(str(self.config.zoom))),
                    self.mapPixmap.width(), self.mapPixmap.height())
                mk2 = QImage()
                mkfile = 'teardrop'
                if 'image' in marker:
                    mkfile = self.piclock.expand(marker['image'])
                if os.path.dirname(mkfile) == '':
                    mkfile = os.path.join(self.piclock.expand('{folders.marker}'), mkfile)
                if os.path.splitext(mkfile)[1] == '':
                    mkfile += '.png'
                mk2.load(mkfile)
                if mk2.format != QImage.Format_ARGB32:
                    mk2 = mk2.convertToFormat(QImage.Format_ARGB32)
                logger.debug("yy size %s", mk2.size())
                mkh = 80  # self.rect.height() / 5
                if 'size' in marker:
                    if marker['size'] == 'small':
                        mkh = 64
                    if marker['size'] == 'mid':
                        mkh = 70
                    if marker['size'] == 'tiny':
                        mkh = 40
                if 'color' in marker:
                    c = QColor(marker['color'])
                    (cr, cg, cb, ca) = c.getRgbF()
                    for x in range(0, mk2.width()):
                        for y in range(0, mk2.height()):
                            (r, g, b, a) = QColor.fromRgba(
                                           mk2.pixel(x, y)).getRgbF()
                            r = r * cr
                            g = g * cg
                            b = b * cb
                            mk2.setPixel(x, y, QColor.fromRgbF(r, g, b, a)
                                         .rgba())
                mk2 = mk2.scaledToHeight(mkh, 1)
                logger.debug("drawImage %d %d ", pt.x-mkh/2, pt.y-mkh/2)
                painter.drawImage(pt.x-mkh/2, pt.y-mkh/2, mk2)
        painter.end()

        self.radarOverlay.setPixmap(self.markerPixmap)

    def getNextNeededFrame(self):
        if not self.block.isVisible():
            return
        frameTimes = sorted(self.radarPixmaps)
        for i in range(0, self.frames):
            t = self.timeSlot(i)
            if not t in frameTimes:
                logger.debug("radar next needed frame %s", time.asctime(time.localtime(t)))
                self.radarProvider.getRadarPixmap(t, self.config, self.block.frameRect(), self.gotRadarPixmap)
                return

    def gotRadarPixmap(self, pixmap, timeSlot):
        logger.debug("got radar pixmap %s %s %s", pixmap, timeSlot, time.asctime(time.localtime(timeSlot)))
        self.radarPixmaps[timeSlot] = pixmap
        self.makeAnimation()
        self.getNextNeededFrame()

    def makeAnimation(self):
        logger.debug("make animation of %d pixmaps", len(self.radarPixmaps))