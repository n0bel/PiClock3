import logging

from ..Plugin import Plugin
from ..WebGet import WebGet, safeurl

from PyQt5 import (QtGui, QtNetwork)
from PyQt5.QtCore import (QObject, QThread, pyqtSlot, pyqtSignal, Qt, QRect,
                          QSize, QUrl)
from PyQt5.QtGui import (QPixmap, QImage)
from PyQt5.QtWidgets import (QWidget, QLabel, QMessageBox, QListWidget,
                             QPushButton, QApplication, QTableWidget,
                             QGridLayout, QListWidgetItem, QTableWidgetItem,
                             QLineEdit, QFrame)
from PyQt5.QtNetwork import (QNetworkReply, QNetworkRequest)

logger = logging.getLogger(__name__)


class MapBox(Plugin):

    ATTRIBUTION = 'Mapbox'

    # the static image carries its own logo and credit along the bottom, and
    # the terms say they must not be obscured.  Measured 2026-08-31: 15px at
    # 200 wide, 17px through 384, stepping to 22-25px at 450 where a larger
    # asset takes over.  Rounded up past the spread - covering a little extra
    # hides some weather, covering too little hides attribution.
    BAND, WIDE_BAND, WIDE = 18, 26, 450

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        logger.debug("mapbox start")

        return
        
    def pageChange(self):
        return


    def getMapPixmap(self, view, radarConfig, callback):
        frameRect = view.rect
        logger.debug("mapbox getpixmap")
        #  note we're using google maps zoom factor.
        #  Mapbox equivilant zoom is one less
        #  They seem to be using 512x512 tiles instead of 256x256
        style = 'mapbox/satellite-streets-v10'
        if 'style' in self.config:
            style = self.config['style']
        if 'style' in radarConfig:
            style = radarConfig['style']
        rsize = frameRect.size()
        zoom = view.zoom - 1
        if rsize.width() > 640 or rsize.height() > 640:
            # QSize takes ints
            rsize = QSize(rsize.width() // 2, rsize.height() // 2)
            zoom -= 1        
        mapUrl = 'https://api.mapbox.com/styles/v1/' + \
               style + \
               '/static/' + \
               str(view.center.lng) + ',' + \
               str(view.center.lat) + ',' + \
               str(zoom) + ',0,0/' + \
               str(rsize.width()) + 'x' + str(rsize.height()) + \
               '?access_token=' + self.piclock.expand(self.config.apikey)
        logger.info("mapbox url %s", safeurl(mapUrl)) 
        params = { 'frameRect': frameRect, 'radarConfig': radarConfig, 'rsize': rsize }        
        WebGet(mapUrl,
                lambda error, data, parms: self.gotMapPixmap(error, data, callback, parms),
                params)

        return

    def gotMapPixmap(self, error, data, callback, params):
        logger.debug("mapbox gotpixmap %s", error)
        frameRect = params['frameRect']
        rsize = params['rsize']
        p = QPixmap()
        mask = None
        if error == QNetworkReply.NoError:
            p.loadFromData(data)
            logger.debug("mapPixmap %s", p.size())
            if p.size() != frameRect.size():
                p = p.scaled(frameRect.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation)
            if not p.isNull():
                band = self.WIDE_BAND if rsize.width() >= self.WIDE \
                    else self.BAND
                mask = self.bottomBandMask(p, rsize, band)
        callback(p, mask)
        return