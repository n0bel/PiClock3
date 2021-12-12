import logging

import time
import datetime
import locale
import os
import random
import tzlocal

from ..Plugin import Plugin

from PyQt5.QtCore import QTimer

logger = logging.getLogger(__name__)


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Date(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.lastDay = -1

    def start(self):
        timer = QTimer()
        timer.timeout.connect(self.doDate)
        timer.start(1000)

        self.doDate()

    def pageChange(self):
        return

    def doDate(self):
        if 'locale' in self.piclock.config:
            try:
                locale.setlocale(locale.LC_TIME, self.piclock.config.locale)
            except BaseException:
                pass

        now = datetime.datetime.now()
        if now.day != self.lastDay:
            self.lastDay = now.day
        else:
            return

        # date
        sup = 'th'
        if (now.day == 1 or now.day == 21 or now.day == 31):
            sup = 'st'
        if (now.day == 2 or now.day == 22):
            sup = 'nd'
        if (now.day == 3 or now.day == 23):
            sup = 'rd'
        if 'locale' in self.config:
            sup = ""
        self.pluginData.sup = sup
        self.pluginData.now = now
        ds = self.piclock.expand(self.config.format)
        self.block.setText(ds)
