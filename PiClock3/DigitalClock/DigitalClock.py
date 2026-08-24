import datetime
import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QLabel, QGraphicsDropShadowEffect

from ..Plugin import Plugin

logger = logging.getLogger(__name__)


class DigitalClock(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.ctimer = None
        self.lasttimestr = None
        self.glow = None
        self.clockrect = None
        self.clockface = None

    def fontCalc(self, size):
        return "%dpx" % (float(size) * self.region.frameRect().height())

    def start(self):
        self.clockface = QLabel(self.region)
        self.clockface.setObjectName("clockface")
        self.clockrect = self.region.frameRect()
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
            self.fontCalc(self.config['font-size']) +
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
        now = self.piclock.now()
        self.pluginData.now = now
        timestr = self.piclock.expand(self.config.format)
        if self.config.format.find("%I") > -1:
            if timestr[0] == '0':
                timestr = timestr[1:99]
        if self.lasttimestr != timestr:
            self.clockface.setText(
                timestr.lower() if self.config['lowercase'] else timestr)
        self.lasttimestr = timestr
