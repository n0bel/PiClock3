import logging

import time
import datetime
import locale
import os
from ..Plugin import Plugin

from PyQt5 import QtGui, QtNetwork
from PyQt5.QtGui import QPixmap, QMovie, QBrush, QColor, QPainter, QTransform
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize, QRect, QBuffer, QIODevice, QByteArray
from PyQt5.QtWidgets import QFrame, QLabel, QGraphicsDropShadowEffect
logger = logging.getLogger(__name__)


class DigitalClock(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def fontCalc(self, size):
        return "%dpx" % (float(size) * self.block.frameRect().height())

    def start(self):
        self.clockface = QLabel(self.block)
        self.clockface.setObjectName("clockface")
        self.clockrect = self.block.frameRect()
        self.clockface.setGeometry(self.clockrect)
        dcolor = QColor(self.config.color).darker(0).name()
        lcolor = QColor(self.config.color).lighter(120).name()
        extraAttributes = ''
        if 'extra-font-attributes' in self.config:
            extraAttributes = self.config['extra-font-attributes']
        self.clockface.setStyleSheet(
            "#clockface { background-color: transparent; " +
            " font-family:sans-serif;" +
            " font-weight: light; color: " +
            lcolor +
            "; background-color: transparent; font-size: " +
            self.fontCalc(0.3) +
            extraAttributes +
            "}")
        logging.info(self.clockface.styleSheet())
        self.clockface.setAlignment(Qt.AlignCenter)
        self.clockface.setGeometry(self.clockrect)
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setOffset(0)
        self.glow.setBlurRadius(50)
        self.glow.setColor(QColor(dcolor))
        self.clockface.setGraphicsEffect(self.glow)
        self.lasttimestr = ""

        self.ctimer = QTimer()
        self.ctimer.timeout.connect(self.tick)
        self.ctimer.start(1000)

    def pageChange(self):
        return

    def tick(self):
        now = datetime.datetime.now()
        self.pluginData.now = now
        timestr = self.piclock.expand(self.config.format)
        if self.config.format.find("%I") > -1:
            if timestr[0] == '0':
                timestr = timestr[1:99]
        if self.lasttimestr != timestr:
            self.clockface.setText(timestr.lower())
        self.lasttimestr = timestr
