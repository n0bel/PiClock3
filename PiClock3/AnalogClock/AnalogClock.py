import datetime
import locale
import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtWidgets import QFrame, QLabel

from ..Plugin import Plugin

logger = logging.getLogger(__name__)


class Plugin(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.ctimer = None
        self.lastmin = None
        self.secpixmap2 = None
        self.secpixmap = None
        self.minpixmap2 = None
        self.minpixmap = None
        self.hourpixmap2 = None
        self.hourpixmap = None
        self.sechand = None
        self.minhand = None
        self.hourhand = None
        self.clockrect = None
        self.clockface = None

    def start(self):
        self.clockface = QFrame(self.block)
        self.clockface.setObjectName("analogclockface")
        self.clockrect = self.block.frameRect()
        self.clockface.setGeometry(self.clockrect)
        imagesFolder = self.piclock.expand(
            self.config['clock-images-base-folder'] +
            '/' +
            self.config['clock-images-folder'] +
            '/')
        faceImage = imagesFolder + 'clock-face.png'
        hourImage = imagesFolder + 'hour-hand.png'
        minuteImage = imagesFolder + 'minute-hand.png'
        secondImage = imagesFolder + 'second-hand.png'

        self.clockface.setStyleSheet(
            "#analogclockface { background-color: transparent; " +
            "border-image: url(" +
            faceImage +
            ") 0 0 0 0 stretch stretch;}")
        logger.info(self.clockface.styleSheet())

        self.hourhand = QLabel(self.block)
        self.hourhand.setObjectName("hourhand")
        self.hourhand.setStyleSheet(
            "#hourhand { background-color: transparent; }")

        self.minhand = QLabel(self.block)
        self.minhand.setObjectName("minhand")
        self.minhand.setStyleSheet(
            "#minhand { background-color: transparent; }")

        self.sechand = QLabel(self.block)
        self.sechand.setObjectName("sechand")
        self.sechand.setStyleSheet(
            "#sechand { background-color: transparent; }")

        self.hourpixmap = QPixmap(hourImage)
        self.hourpixmap2 = QPixmap(hourImage)
        self.minpixmap = QPixmap(minuteImage)
        self.minpixmap2 = QPixmap(minuteImage)
        self.secpixmap = QPixmap(secondImage)
        self.secpixmap2 = QPixmap(secondImage)

        self.lastmin = 0
        self.ctimer = QTimer()
        self.ctimer.timeout.connect(self.tick)
        self.ctimer.start(1000)

    def pageChange(self):
        return

    def tick(self):
        time_now = datetime.datetime.now()
        if 'locale' in self.config:
            try:
                locale.setlocale(locale.LC_TIME, self.config.locale)
            except BaseException:
                pass
        angle = time_now.second * 6
        ts = self.secpixmap.size()
        self.secpixmap2 = self.secpixmap.transformed(
            QTransform().scale(
                float(self.clockrect.width()) / ts.height(),
                float(self.clockrect.height()) / ts.height()
            ).rotate(angle),
            Qt.SmoothTransformation
        )
        self.sechand.setPixmap(self.secpixmap2)
        ts = self.secpixmap2.size()
        self.sechand.setGeometry(
            int(self.clockrect.center().x() - ts.width() / 2),
            int(self.clockrect.center().y() - ts.height() / 2),
            ts.width(),
            ts.height()
        )
        if time_now.minute != self.lastmin:
            self.lastmin = time_now.minute
            angle = time_now.minute * 6
            ts = self.minpixmap.size()
            minpixmap2 = self.minpixmap.transformed(
                QTransform().scale(
                    float(self.clockrect.width()) / ts.height(),
                    float(self.clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            self.minhand.setPixmap(minpixmap2)
            ts = minpixmap2.size()
            self.minhand.setGeometry(
                int(self.clockrect.center().x() - ts.width() / 2),
                int(self.clockrect.center().y() - ts.height() / 2),
                ts.width(),
                ts.height()
            )

            angle = ((time_now.hour % 12) + time_now.minute / 60.0) * 30.0
            ts = self.hourpixmap.size()
            hourpixmap2 = self.hourpixmap.transformed(
                QTransform().scale(
                    float(self.clockrect.width()) / ts.height(),
                    float(self.clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            self.hourhand.setPixmap(hourpixmap2)
            ts = hourpixmap2.size()
            self.hourhand.setGeometry(
                int(self.clockrect.center().x() - ts.width() / 2),
                int(self.clockrect.center().y() - ts.height() / 2),
                ts.width(),
                ts.height()
            )
