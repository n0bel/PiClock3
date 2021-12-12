import logging

import time
import datetime
import locale
import os
import random
import tzlocal

from ..Plugin import Plugin

from astral import LocationInfo
from astral.sun import sun
from astral import moon

from PyQt5.QtCore import QTimer

logger = logging.getLogger(__name__)


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Plugin(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.lastDay = -1

    def start(self):
        timer = QTimer()
        timer.timeout.connect(self.doAstral)
        timer.start(1000)

        self.doAstral()

    def pageChange(self):
        return

    def doAstral(self):

        now = datetime.datetime.today()
        if now.day != self.lastDay:
            self.lastDay = now.day
        else:
            return

        locationInfo = LocationInfo('here', 'here',
                                    tzlocal.get_localzone().zone,
                                    self.piclock.expand(
                                        self.config.location.lattitude),
                                    self.piclock.expand(self.config.location.longitude))
        s = sun(locationInfo.observer, date=now, tzinfo=locationInfo.timezone)

        for key, value in s.items():
            logger.info("sun info %s %s", key, value)
            self.pluginData[key] = value
        m = moon.phase(now)
        self.pluginData['moonphase'] = self.piclock.language(
            self.phaseWords(m))
        self.pluginData['moonage'] = m
        #self.pluginData['sunrise'] = s['sunrise']
        ds = self.piclock.expand(self.config.format)
        self.block.setText(ds)

    def phaseWords(self, phase):
        f = phase / 28.0
        pp = 'new_moon'
        if (f > 0.9375):
            pp = 'new_moon'
        elif (f > 0.8125):
            pp = 'waning_crecent'
        elif (f > 0.6875):
            pp = 'last_quarter'
        elif (f > 0.5625):
            pp = 'waning_gibbous'
        elif (f > 0.4375):
            pp = 'full_moon'
        elif (f > 0.3125):
            pp = 'waxing_gibbous'
        elif (f > 0.1875):
            pp = 'first_quarter'
        elif (f > 0.0625):
            pp = 'waxing_crecent'
        return pp
