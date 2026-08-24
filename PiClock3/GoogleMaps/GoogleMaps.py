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


class GoogleMaps(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        logger.debug("googlemaps start")

        return
        
    def pageChange(self):
        return

    def getMapPixmap(self, view, radarConfig, callback):
        frameRect = view.rect
        urlp = []
        if 'apikey' in self.config and len(self.config.apikey) > 0:
            urlp.append('key=' + self.piclock.expand(self.config.apikey))
        urlp.append('center=%s,%s' % (view.center.lat, view.center.lng))
        zoom = view.zoom
        rsize = frameRect.size()
        if rsize.width() > 640 or rsize.height() > 640:
            rsize = QSize(rsize.width() / 2, rsize.height() / 2)
            zoom -= 1
        urlp.append('zoom=' + str(zoom))
        urlp.append('size=' + str(rsize.width()) + 'x' + str(rsize.height()))
        urlp.append('maptype=hybrid')

        mapUrl = 'http://maps.googleapis.com/maps/api/staticmap?' + \
            '&'.join(urlp)
        
        logger.info("googlemaps url %s", safeurl(mapUrl))   
        
        logger.debug("googlemaps getpixmap")
        params = { 'frameRect': frameRect, 'radarConfig': radarConfig, 'rsize': rsize }
        WebGet(mapUrl,
                lambda error, data, parms: self.gotMapPixmap(error, data, callback, parms),
                params
                )
        return

    def gotMapPixmap(self, error, data, callback, params):
        logger.debug("googlemaps gotpixmap %s", error)
        frameRect = params['frameRect']
        p = QPixmap()
        if error == QNetworkReply.NoError:
            p.loadFromData(data)
            logger.debug("mapPixmap %s", p.size())
            if p.size() != frameRect.size():
                p = p.scaled(frameRect.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation)
        callback(p)
        return