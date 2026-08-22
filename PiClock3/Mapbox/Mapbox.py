import logging

from ..Plugin import Plugin
from ..WebGet import WebGet

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

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        logger.debug("mapbox start")

        return
        
    def pageChange(self):
        return


    def getMapPixmap(self, radarConfig, frameRect, callback):
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
        zoom = int(self.piclock.expand(str(radarConfig.zoom))) - 1
        if rsize.width() > 640 or rsize.height() > 640:
            rsize = QSize(rsize.width() / 2, rsize.height() / 2)
            zoom -= 1        
        mapUrl = 'https://api.mapbox.com/styles/v1/' + \
               style + \
               '/static/' + \
               str(self.piclock.expand(radarConfig.center.longitude)) + ',' + \
               str(self.piclock.expand(radarConfig.center.lattitude)) + ',' + \
               str(zoom) + ',0,0/' + \
               str(rsize.width()) + 'x' + str(rsize.height()) + \
               '?access_token=' + self.piclock.expand(self.config.apikey)
        logger.info("mapbox url %s", mapUrl) 
        params = { 'frameRect': frameRect, 'radarConfig': radarConfig, 'rsize': rsize }        
        WebGet(mapUrl,
                lambda error, data, parms: self.gotMapPixmap(error, data, callback, parms),
                params)

        return

    def gotMapPixmap(self, error, data, callback, params):
        logger.debug("mapbox gotpixmap %s", error)   
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