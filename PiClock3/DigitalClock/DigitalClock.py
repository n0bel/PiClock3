import datetime
import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel

from ..Widget import Widget

logger = logging.getLogger(__name__)


class DigitalClock(Widget):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.ctimer = None
        self.lasttimestr = None
        self.clockrect = None
        self.clockface = None
        self.format = None

    def start(self):
        self.format = self.strftimePortableFormat(self.config.format)
        self.clockface = QLabel(self.region)
        self.clockface.setObjectName("clockface")
        self.clockrect = self.region.frameRect()
        self.clockface.setGeometry(self.clockrect)
        # only the size.  color, font-family and font-weight arrive on the
        # region and Qt inherits them, so the face draws in the color the
        # theme actually wrote rather than a lightened one.
        props = self.scaleFont({
            'font-size': self.config['font-size'],
        }, self.clockrect.height())
        extra = str(self.config['extra-font-attributes'] or '').strip().lstrip(';')
        self.clockface.setStyleSheet(
            "#clockface {%s%s }"
            % (self.piclock._buildStyleString(props),
               ' ' + extra.rstrip(';') + ';' if extra else ''))
        logging.info(self.clockface.styleSheet())
        self.clockface.setAlignment(Qt.AlignCenter)
        self.clockface.setGeometry(self.clockrect)
        self.lasttimestr = ""

        self.ctimer = QTimer()
        self.ctimer.timeout.connect(self.tick)
        self.ctimer.start(1000)

    def pageChange(self):
        return

    def tick(self):
        now = self.piclock.now()
        self.pluginData.now = now
        timestr = self.piclock.expand(self.format)
        if self.lasttimestr != timestr:
            self.clockface.setText(
                timestr.lower() if self.config['lowercase'] else timestr)
        self.lasttimestr = timestr
