import logging

from ..BaseMap import BaseMap
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

# what Google will accept as a maptype.  Facts about the service, not settings.
MAPTYPES = ('roadmap', 'satellite', 'terrain', 'hybrid')


class GoogleMaps(BaseMap):

    attribution = 'Google'

    # the static image carries the Google logo bottom left and a data credit
    # bottom right, and the terms say they must never be obscured.  Measured
    # 2026-08-31: exactly 20px at every size from 200x200 to 640x640 - it does
    # not scale - and 16px at 160 wide, where the credit is dropped entirely.
    BAND = 20

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        logger.debug("googlemaps start")

        return
        
    def pageChange(self):
        return

    def getMapPixmap(self, view, layerConfig, callback):
        frameRect = view.rect
        urlp = []
        if 'apikey' in self.config and len(self.config.apikey) > 0:
            urlp.append('key=' + self.piclock.expand(self.config.apikey))
        urlp.append('center=%s,%s' % (view.center.lat, view.center.lng))
        zoom = view.zoom
        rsize = frameRect.size()
        if rsize.width() > 640 or rsize.height() > 640:
            rsize = QSize(rsize.width() // 2, rsize.height() // 2)
            zoom -= 1
        urlp.append('zoom=' + str(zoom))
        urlp.append('size=' + str(rsize.width()) + 'x' + str(rsize.height()))
        maptype = self.config['style']
        if 'style' in layerConfig:
            maptype = layerConfig['style']
        if maptype not in MAPTYPES:
            # Google answers 200 and quietly draws a roadmap for anything it
            # does not know, so a style meant for another provider - a config
            # that swapped base-provider and left style: alone - would show a
            # plain map with nothing anywhere saying why
            logger.warning("%s: no Google maptype called '%s' - using %s.  "
                           "Try one of %s", self.name, maptype,
                           self.config['style'], ', '.join(sorted(MAPTYPES)))
            maptype = self.config['style']
        urlp.append('maptype=' + maptype)

        mapUrl = 'https://maps.googleapis.com/maps/api/staticmap?' + \
            '&'.join(urlp)
        
        logger.info("googlemaps url %s", safeurl(mapUrl))   
        
        logger.debug("googlemaps getpixmap")
        params = { 'frameRect': frameRect, 'rsize': rsize }
        WebGet(mapUrl,
                lambda error, data, parms: self.gotMapPixmap(error, data, callback, parms),
                params
                )
        return

    def gotMapPixmap(self, error, data, callback, params):
        logger.debug("googlemaps gotpixmap %s", error)
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
                mask = self.bottomBandMask(p, rsize, self.BAND)
        callback(p, mask)
        return