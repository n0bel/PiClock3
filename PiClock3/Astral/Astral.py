import datetime
import logging

import tzlocal
from PyQt5.QtCore import QTimer
from astral import LocationInfo
from astral import moon

from .. import Weather
from ..Plugin import Plugin

logger = logging.getLogger(__name__)


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Astral(Plugin):

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

        now = self.piclock.now()
        if now.day != self.lastDay:
            self.lastDay = now.day
        else:
            return

        locationInfo = LocationInfo('here', 'here',
                                    self.piclock.timezone().key,
                                    self.piclock.expand(
                                        self.config.location.lattitude),
                                    self.piclock.expand(self.config.location.longitude))
        s = Weather.sunTimes(now, locationInfo.latitude,
                             locationInfo.longitude, locationInfo.timezone)
        for key, _ in Weather.EVENTS:
            if key not in s:
                logger.info("no %s at %s,%s today", key,
                            locationInfo.latitude, locationInfo.longitude)

        for key, value in s.items():
            logger.info("sun info %s %s", key, value)
            self.pluginData[key] = value
        m = moon.phase(now)
        self.pluginData['moonphase'] = self.piclock.language(
            self.phaseWords(m))
        self.pluginData['moonage'] = m

        # A day with no sunrise has no time to print, and a format asking for
        # one comes back with its own braces still in it - so the day says
        # which of the two it is and a different format is used.
        polar = 'sunrise' not in s or 'sunset' not in s
        if polar:
            up = Weather.daytime(now, locationInfo.latitude,
                                 locationInfo.longitude,
                                 locationInfo.timezone)
            self.pluginData['sun'] = self.piclock.language(
                'polar_day' if up else 'polar_night')
        fmt = self.config['polar-format'] if polar else self.config.format

        try:
            ds = self.piclock.expand(fmt)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("almanac format %r: %s", fmt, e)
            ds = ''
        self.region.setText(ds)

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
