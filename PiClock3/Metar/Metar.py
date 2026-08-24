"""A METAR station report, as a weather source.

METAR is an hourly observation from an airfield: what the sky is actually
doing at one point on the ground, rather than what a model expects.  It has
no forecast of any kind, so hourly() and daily() answer empty and a widget
asking for them gets nothing rather than a guess.

Reports come from the NWS text feed, one file per station:
    https://tgftp.nws.noaa.gov/data/observations/metar/stations/KLVN.TXT

Everything handed out is in Celsius, millibars, km/h and degrees; formatting
belongs to whatever draws it.
"""
import datetime
import logging
import random

from PyQt5.QtCore import QTimer
from metar import Metar as MetarModule

from ..Plugin import Plugin
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

FEED = 'https://tgftp.nws.noaa.gov/data/observations/metar/stations/%s.TXT'


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Metar(Plugin):
    # sky and weather groups, in worsening order: the highest priority match
    # in a report wins.  Columns are group, modifier, intensity, words, icon,
    # priority.
    metar_cond = [
        ('CLR', '', '', 'Clear', 'clear-day', 0),
        ('NSC', '', '', 'Clear', 'clear-day', 0),
        ('SKC', '', '', 'Clear', 'clear-day', 0),
        ('FEW', '', '', 'Few Clouds', 'partly-cloudy-day', 1),
        ('NCD', '', '', 'Clear', 'clear-day', 0),
        ('SCT', '', '', 'Scattered Clouds', 'partly-cloudy-day', 2),
        ('BKN', '', '', 'Mostly Cloudy', 'partly-cloudy-day', 3),
        ('OVC', '', '', 'Cloudy', 'cloudy', 4),

        ('///', '', '', '', 'cloudy', 0),
        ('UP', '', '', '', 'cloudy', 0),
        ('VV', '', '', '', 'cloudy', 0),
        ('//', '', '', '', 'cloudy', 0),

        ('DZ', '', '', 'Drizzle', 'rain', 10),

        ('RA', 'FZ', '+', 'Heavy Freezing Rain', 'sleet', 11),
        ('RA', 'FZ', '-', 'Light Freezing Rain', 'sleet', 11),
        ('RA', 'SH', '+', 'Heavy Rain Showers', 'sleet', 11),
        ('RA', 'SH', '-', 'Light Rain Showers', 'rain', 11),
        ('RA', 'BL', '+', 'Heavy Blowing Rain', 'rain', 11),
        ('RA', 'BL', '-', 'Light Blowing Rain', 'rain', 11),
        ('RA', 'FZ', '', 'Freezing Rain', 'sleet', 11),
        ('RA', 'SH', '', 'Rain Showers', 'rain', 11),
        ('RA', 'BL', '', 'Blowing Rain', 'rain', 11),
        ('RA', '', '+', 'Heavy Rain', 'rain', 11),
        ('RA', '', '-', 'Light Rain', 'rain', 11),
        ('RA', '', '', 'Rain', 'rain', 11),

        ('SN', 'FZ', '+', 'Heavy Freezing Snow', 'snow', 12),
        ('SN', 'FZ', '-', 'Light Freezing Snow', 'snow', 12),
        ('SN', 'SH', '+', 'Heavy Snow Showers', 'snow', 12),
        ('SN', 'SH', '-', 'Light Snow Showers', 'snow', 12),
        ('SN', 'BL', '+', 'Heavy Blowing Snow', 'snow', 12),
        ('SN', 'BL', '-', 'Light Blowing Snow', 'snow', 12),
        ('SN', 'FZ', '', 'Freezing Snow', 'snow', 12),
        ('SN', 'SH', '', 'Snow Showers', 'snow', 12),
        ('SN', 'BL', '', 'Blowing Snow', 'snow', 12),
        ('SN', '', '+', 'Heavy Snow', 'snow', 12),
        ('SN', '', '-', 'Light Snow', 'snow', 12),
        ('SN', '', '', 'Rain', 'snow', 12),

        ('SG', 'BL', '', 'Blowing Snow', 'snow', 12),
        ('SG', '', '', 'Snow', 'snow', 12),
        ('GS', 'BL', '', 'Blowing Snow Pellets', 'snow', 12),
        ('GS', '', '', 'Snow Pellets', 'snow', 12),

        ('IC', '', '', 'Ice Crystals', 'snow', 13),
        ('PL', '', '', 'Ice Pellets', 'snow', 13),

        ('GR', '', '+', 'Heavy Hail', 'thunderstorm', 14),
        ('GR', '', '', 'Hail', 'thunderstorm', 14),
    ]

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.observation = None
        self.listeners = []
        self.timer = None
        # what a reading from here should be credited to
        self.attribution = config['METAR']

    def start(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.getMetar)
        self.timer.start(int(60000 * self.config['refresh'] +
                             random.uniform(1000, 10000)))
        self.getMetar()

    def pageChange(self):
        return

    # ---------------------------------------------------------------- api

    def subscribe(self, fn):
        """call fn() whenever a new observation lands"""
        self.listeners.append(fn)
        if self.observation:
            fn()

    def current(self):
        """the latest observation, or None before the first one arrives"""
        return self.observation

    def hourly(self, count, step):
        """a station reports what is happening, not what will"""
        return []

    def daily(self, count):
        """a station reports what is happening, not what will"""
        return []

    # ------------------------------------------------------------ fetching

    def getMetar(self):
        url = FEED % self.config.METAR
        logger.info('metar url %s', url)
        WebGet(url, self.gotMetar)

    def gotMetar(self, error, data, params):
        if error:
            logger.warning('metar %s failed: %s', self.config.METAR, error)
            return
        text = bytes(data).decode('utf-8', 'replace')
        line = ''
        for candidate in text.splitlines():
            if candidate.startswith(self.config.METAR):
                line = candidate
        if not line:
            logger.warning('metar %s: no report in the feed', self.config.METAR)
            return
        logger.info('wxmetar: %s', line)

        f = MetarModule.Metar(line, strict=False)
        weather, icon = self.conditions(f)
        self.observation = {
            'when': f.time.replace(tzinfo=TimeZoneUTC()).astimezone(
                self.piclock.timezone()),
            'station': self.config.METAR,
            'icon': icon,
            'description': weather,
            'temp': f.temp.value('C') if f.temp else None,
            'dew': f.dewpt.value('C') if f.dewpt else None,
            'pressure': f.press.value('MB') if f.press else None,
            'wind': f.wind_speed.value('KMH') if f.wind_speed else None,
            'wind-dir': f.wind_dir.value() if f.wind_dir else None,
            'gust': f.wind_gust.value('KMH') if f.wind_gust else None,
            # a station reports temperature and dew point; the rest is derived
            'humidity': None,
            'feels-like': None,
        }
        for fn in self.listeners:
            fn()

    def conditions(self, f):
        """the worst thing the report mentions, as words and an icon name"""
        pri, weather, icon = -1, '', ''
        for s in f.sky:
            for c in self.metar_cond:
                if s[0] == c[0] and c[5] > pri:
                    pri, weather, icon = c[5], c[3], c[4]
        for w in f.weather:
            for c in self.metar_cond:
                if w[2] != c[0]:
                    continue
                if c[1] > '' and w[1] != c[1]:
                    continue
                if c[2] > '' and w[0][0:1] != c[2]:
                    continue
                if c[5] > pri:
                    pri, weather, icon = c[5], c[3], c[4]

        if pri < 0:
            # no sky group at all.  Read it from the visibility instead: the
            # word and the picture have to agree, whichever way it goes
            murk = f.vis is not None and f.vis.value('SM') < 6
            return ('Obscured', 'fog') if murk else ('Clear', 'clear-day')
        return weather, icon
