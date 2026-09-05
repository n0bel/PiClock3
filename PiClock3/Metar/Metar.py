"""A METAR station report, as a weather source.

METAR is an hourly observation from an airfield: what the sky is actually
doing at one point on the ground, rather than what a model expects.  It has
no forecast of any kind, so hourly() and daily() answer empty and a widget
asking for them gets nothing rather than a guess.

Reports come from the NWS text feed, one file per station:
    https://tgftp.nws.noaa.gov/data/observations/metar/stations/KMSP.TXT

Everything handed out is in Celsius, millibars, km/h and degrees; formatting
belongs to whatever draws it.  The report string itself travels under raw,
so anything not read here is still reachable by whoever wants it.
"""
import datetime
import logging
import random

from PyQt5.QtCore import QTimer
from metar import Metar as MetarModule

from .. import Sun
from ..Weather import Weather
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

FEED = 'https://tgftp.nws.noaa.gov/data/observations/metar/stations/%s.TXT'


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Metar(Weather):
    # present weather onto the eleven icon names the shipped sets have,
    # tried in order so the first match wins
    ICONS = [
        ('TS', 'thunderstorm'), ('GR', 'thunderstorm'), ('GS', 'thunderstorm'),
        ('FZ', 'sleet'), ('PL', 'sleet'),
        ('SN', 'snow'), ('SG', 'snow'), ('IC', 'snow'),
        ('RA', 'rain'), ('DZ', 'rain'), ('UP', 'rain'),
        ('FG', 'fog'), ('BR', 'fog'), ('HZ', 'fog'), ('FU', 'fog'),
        ('VA', 'fog'), ('DU', 'fog'), ('SA', 'fog'),
        ('SQ', 'wind'), ('PO', 'wind'), ('DS', 'wind'), ('SS', 'wind'),
        ('BL', 'wind'), ('DR', 'wind'),
    ]
    # sky cover, when there is no present weather to describe instead
    COVER = {'CAVOK': 'clear-day',
             'SKC': 'clear-day', 'CLR': 'clear-day', 'NCD': 'clear-day',
             'NSC': 'clear-day', 'FEW': 'clear-day',
             'SCT': 'partly-cloudy-day', 'BKN': 'partly-cloudy-day',
             'OVC': 'cloudy', 'VV': 'cloudy'}

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

    def conditions(self):
        """the latest observation, or None before the first one arrives"""
        return self.observation

    # no hourly() or daily(): a station reports what is happening rather
    # than what will, and Weather answers both with an empty list already.

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
        notation, cover = self.decode(f)
        when = f.time.replace(tzinfo=TimeZoneUTC()).astimezone(
            self.piclock.timezone())
        temp = f.temp.value('C') if f.temp else None
        dew = f.dewpt.value('C') if f.dewpt else None
        wind = f.wind_speed.value('KMH') if f.wind_speed else None

        self.observation = {
            'when': when,
            'station': self.config.METAR,
            'icon': self.variant(self.iconFor(notation, cover),
                                    self.daytime(when)),
            'condition': notation or cover,
            'temp': temp,
            'dew': dew,
            'pressure': f.press.value('MB') if f.press else None,
            'wind': wind,
            'wind-dir': f.wind_dir.value() if f.wind_dir else None,
            'gust': f.wind_gust.value('KMH') if f.wind_gust else None,
            # a station reports temperature and dew point and leaves the rest
            # to the reader; the reader should not have to be a widget
            'humidity': self.humidity(temp, dew),
            'feels-like': self.feelsLike(temp, dew, wind),
            'raw': line,
        }
        for fn in self.listeners:
            fn()

    def daytime(self, when):
        """was the sun up over the station when it reported"""
        return Sun.daytime(
            when,
            self.piclock.expand(self.piclock.config.location.latitude),
            self.piclock.expand(self.piclock.config.location.longitude),
            self.piclock.timezone().key)

    # sky cover, worst last: a report lists several layers and the highest
    # one is what the sky looks like.  4678 has no notation for cloud
    # amount, so these codes are carried as themselves.
    SKY = ('SKC', 'CLR', 'NCD', 'NSC', 'FEW', 'SCT', 'BKN', 'OVC', 'VV')

    def decode(self, f):
        """the report as a WMO 4678 notation, and the sky cover beside it.

        Present weather wins over cloud: a station reporting fog at half a
        mile is describing fog, whatever the ceiling is doing.  Both travel
        so whatever draws them can choose.

        A report lists present weather in decreasing significance, so the
        first group is the one to show - -RA BR is rain seen through mist,
        not mist.  Cloud is the other way round and the last layer is the
        highest.
        """
        cover = ''
        for group in f.sky:
            if group[0] in self.SKY:
                cover = group[0]
        # CAVOK replaces the cloud group outright, and the parser keeps only
        # the visibility it implies, so it is read off the report itself
        if not cover and 'CAVOK' in f.code.split():
            cover = 'CAVOK'
        weather = [self.notation(w) for w in f.weather]
        weather = [w for w in weather if w]
        return (weather[0] if weather else cover), cover

    @staticmethod
    def notation(w):
        """one parsed weather group back into 4678 notation.

        The library hands back five slots - intensity, descriptor,
        precipitation, obscuration, other - and all of them matter: fog,
        mist and haze arrive in the obscuration slot.
        """
        intensity, descriptor = (w[0] or ''), (w[1] or '')
        phenomena = ''.join(x for x in (w[2], w[3], w[4]) if x)
        if not (descriptor or phenomena):
            return ''
        if intensity not in ('-', '+', 'VC'):
            intensity = ''
        return intensity + descriptor + phenomena

    def iconFor(self, notation, cover):
        """the picture for a notation, falling back to the cloud amount"""
        if notation:
            for code, icon in self.ICONS:
                if code in notation:
                    return icon
        return self.COVER.get(cover, 'cloudy')
