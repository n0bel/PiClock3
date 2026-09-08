"""Tomorrow.io, as a weather source.

Two requests: `weather/realtime` for what the sky is doing, and
`weather/forecast` for the hours and the days, which arrive in one answer.
v1 used the older `timelines` endpoint and spent three requests on the same
ground; two matters here, because the free plan allows 25 an hour.

Their `weatherCode` is the finest-grained of the sources this project
talks to - it separates light freezing rain from heavy, and ice pellets
from both - so the table below is close to one-for-one with WMO 4678
rather than an approximation of it.  What it does not say is whether rain
is falling in showers or steadily, and its thunderstorms have no intensity,
so those go across as the plain notation.

Everything handed out is Celsius, millibars, km/h and percent, and the
condition is notation rather than words, so a widget drawing it never
learns which service it came from.
"""
import datetime
import json
import logging

from PyQt5.QtCore import QTimer
from PyQt5.QtNetwork import QNetworkReply

from .. import Sun
from ..Weather import Weather
from ..WebGet import WebGet, safeurl

logger = logging.getLogger(__name__)

REALTIME = 'https://api.tomorrow.io/v4/weather/realtime'
FORECAST = 'https://api.tomorrow.io/v4/weather/forecast'

# Tomorrow.io's weatherCode onto an icon and a WMO 4678 notation.  The
# 1xxx codes are sky cover, which 4678 has no notation for, so those carry
# METAR cover codes the way OpenMeteo's do.
CODES = {
    1000: ('clear-day',          'SKC'),
    1100: ('clear-day',          'FEW'),
    1101: ('partly-cloudy-day',  'SCT'),
    1102: ('partly-cloudy-day',  'BKN'),
    1001: ('cloudy',             'OVC'),
    2000: ('fog',                'FG'),
    2100: ('fog',                'BR'),
    4000: ('rain',               'DZ'),
    4001: ('rain',               'RA'),
    4200: ('rain',               '-RA'),
    4201: ('rain',               '+RA'),
    5000: ('snow',               'SN'),
    5001: ('snow',               '-SHSN'),
    5100: ('snow',               '-SN'),
    5101: ('snow',               '+SN'),
    6000: ('sleet',              'FZDZ'),
    6001: ('sleet',              'FZRA'),
    6200: ('sleet',              '-FZRA'),
    6201: ('sleet',              '+FZRA'),
    7000: ('sleet',              'PL'),
    7101: ('sleet',              '+PL'),
    7102: ('sleet',              '-PL'),
    8000: ('thunderstorm',       'TS'),
}

# what a transport error most likely means to somebody with a key.  Qt
# hands over the code and drops the body, so the service's own sentence
# about it never arrives - and the two worth telling apart, a key that is
# wrong and a key that is spent, are both just a number by the time they
# reach here.
REFUSED = {
    QNetworkReply.AuthenticationRequiredError: 'the key was refused',
    QNetworkReply.ContentAccessDenied: 'the key was refused',
    QNetworkReply.ContentOperationNotPermittedError:
        'the key is not allowed this',
    QNetworkReply.UnknownContentError:
        'out of requests for the hour or the day, most likely',
}

# which code is worse, worst last, for saying what a day looked like.
# Tomorrow.io's numbering is nearly this already - 8000 over 7101 over
# 6201 and down - but it puts 1001 Cloudy under 1100 Mostly Clear, and
# weatherCodeMax, which is the daily summary the service sends, is not
# that max: measured against Minneapolis on 2026-09-08 it called three
# overcast days Clear and called a day with 13mm of rain Overcast.  So
# the days here are read off their own hours, and this is the order.
SEVERITY = [1000, 1100, 1101, 1102, 1001,
            2100, 2000,
            4000, 4200, 4001, 4201,
            6000, 6200, 6001, 6201,
            5001, 5100, 5000, 5101,
            7102, 7000, 7101,
            8000]


class TomorrowIO(Weather):

    attribution = 'Tomorrow.io'

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.days = []
        self.hours = []
        self.now = None
        self.listeners = []
        self.timer = None
        # daily() says once when it is asked for more days than exist
        self.saidShort = False

    def start(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.getWeather)
        self.timer.start(int(60000 * self.config['refresh']))
        self.getWeather()

    def pageChange(self):
        return

    # ---------------------------------------------------------------- api

    def subscribe(self, fn):
        """call fn() whenever a new answer lands"""
        self.listeners.append(fn)
        if self.now or self.days or self.hours:
            fn()

    def conditions(self):
        """conditions now, or None before the first answer arrives"""
        return self.now

    def daily(self, count):
        """the next `count` days, today first.

        Six of them: the free plan's page says five days and the endpoint
        sends today and five ahead, which is what the forecast widget
        asks for.  Coming up short is said once, because an empty cell in
        the column looks like a fault rather than a plan's limit.
        """
        if self.days and count > len(self.days) and not self.saidShort:
            self.saidShort = True
            logger.warning('%s: asked for %d days and the plan gave %d.'
                           '  Set daily: %d on the forecast widget and'
                           ' give the spare cells to hourly:',
                           self.attribution, count, len(self.days),
                           len(self.days))
        return self.days[:count]

    def hourly(self, count, step):
        """`count` entries from now, `step` hours apart.

        The grid is hourly and starts at the top of the current hour, so
        the first future entry is found rather than assumed.
        """
        now = self.piclock.now().replace(tzinfo=None)
        start = next((i for i, h in enumerate(self.hours) if h['when'] > now),
                     None)
        if start is None:
            return []
        return [self.hours[i] for i in
                range(start, min(len(self.hours), start + count * step), step)]

    # ------------------------------------------------------------ fetching

    def url(self, host, extra=''):
        return ('%s?location=%s,%s&units=metric%s&apikey=%s'
                % (host,
                   self.piclock.expand(self.config.location.latitude),
                   self.piclock.expand(self.config.location.longitude),
                   extra,
                   self.piclock.expand(self.config.apikey)))

    def getWeather(self):
        # the forecast carries both grids, so two requests answer all
        # three questions - which is what keeps a clock inside 25 an hour
        for u, done in ((self.url(REALTIME), self.gotCurrent),
                        (self.url(FORECAST, '&timesteps=1h&timesteps=1d'),
                         self.gotForecast)):
            logger.info('%s url %s', self.attribution, safeurl(u))
            WebGet(u, done)

    def answer(self, error, data):
        """the json a reply carried, or None having said why not.

        Two ways to be told no.  An HTTP error arrives as a transport
        error with the body already thrown away, so REFUSED is what
        stands in for the sentence the service sent; anything the service
        reports with a 200 arrives as a code and a message in the json.
        """
        if error:
            logger.warning('%s failed: %s%s', self.attribution, error,
                           ' - %s' % REFUSED[error]
                           if error in REFUSED else '')
            return None
        try:
            index = json.loads(bytes(data).decode('utf-8'))
        except ValueError:
            logger.warning('%s did not answer with json', self.attribution)
            return None
        if index.get('code'):
            logger.warning('%s said %s: %s %s', self.attribution,
                           index.get('code'), index.get('type'),
                           index.get('message'))
            return None
        return index

    def gotCurrent(self, error, data, params):
        index = self.answer(error, data)
        if index is None:
            return

        entry = index.get('data') or {}
        values = entry.get('values') or {}
        when = self.when(entry.get('time'))
        icon, notation = self.look(values.get('weatherCode'))
        self.now = {
            'when': when,
            'icon': self.variant(icon, self.daylight(when)),
            'condition': notation,
            'temp': values.get('temperature'),
            'dew': values.get('dewPoint'),
            'humidity': values.get('humidity'),
            'feels-like': values.get('temperatureApparent'),
            'pressure': values.get('pressureSeaLevel'),
            'wind': self.kmh(values.get('windSpeed')),
            'wind-dir': values.get('windDirection'),
            'gust': self.kmh(values.get('windGust')),
            'raw': entry,
        }
        logger.info('%s: conditions at %s', self.attribution, when)
        for fn in self.listeners:
            fn()

    def gotForecast(self, error, data, params):
        index = self.answer(error, data)
        if index is None:
            return
        timelines = index.get('timelines') or {}

        hours = []
        for entry in timelines.get('hourly') or []:
            values = entry.get('values') or {}
            when = self.when(entry.get('time'))
            icon, notation = self.look(values.get('weatherCode'))
            hours.append({
                'when': when,
                'icon': self.variant(icon, self.daylight(when)),
                'condition': notation,
                'temp': values.get('temperature'),
                'precip': values.get('precipitationProbability'),
                'accum': values.get('rainAccumulation'),
                'snow': values.get('snowAccumulation'),
                'raw': entry,
            })
        self.hours = hours

        days = []
        for entry in (timelines.get('daily')
                      or [])[:int(self.config['forecast-days'])]:
            values = entry.get('values') or {}
            when = self.when(entry.get('time'))
            icon, notation = self.look(self.worst(when, values))
            days.append({
                'when': when.date() if when else None,
                # the day picture, whatever hour the worst of it fell in
                'icon': self.variant(icon, True),
                'condition': notation,
                'high': values.get('temperatureMax'),
                'low': values.get('temperatureMin'),
                'precip': values.get('precipitationProbabilityMax'),
                'accum': values.get('rainAccumulationSum'),
                'snow': values.get('snowAccumulationSum'),
                'raw': entry,
            })
        self.days = days

        logger.info('%s: %d days and %d hours, first day %s',
                    self.attribution, len(days), len(hours),
                    days[0]['when'] if days else 'none')
        for fn in self.listeners:
            fn()

    # ------------------------------------------------------------- shaping

    def worst(self, when, values):
        """the code that decides what a day looked like.

        Read off the day's own hours, the two grids covering the same six
        days, and off weatherCodeMax only where there are no hours to
        read - which is a poor second, for the reason SEVERITY gives.
        """
        codes = [(h['raw'].get('values') or {}).get('weatherCode')
                 for h in self.hours
                 if when and h['when'] and h['when'].date() == when.date()]
        codes = [c for c in codes if c in CODES]
        if not codes:
            return values.get('weatherCodeMax')
        return max(codes, key=SEVERITY.index)

    @staticmethod
    def look(code):
        """a code as an icon and a notation, or as the fallback pair.

        0 is Tomorrow.io's own word for having nothing to say, and lands
        here with everything else it has not got a name for.
        """
        return CODES.get(code, ('cloudy', ''))

    def when(self, stamp):
        """an ISO time as a naive one where the clock is pointed.

        Naive because that is what every entry a widget compares against
        is, hourly() included.  The Z has to go first: fromisoformat did
        not read one until 3.11, and Bullseye ships 3.9.
        """
        if not stamp:
            return None
        parsed = datetime.datetime.fromisoformat(
            stamp.replace('Z', '+00:00'))
        return parsed.astimezone(self.piclock.timezone()).replace(tzinfo=None)

    def daylight(self, when):
        """was the sun up then, where the clock is pointed.

        Asked of the sun rather than read out of the response: the codes
        these endpoints return carry no day or night, unlike the
        five-digit ones the timelines endpoint can send.  The zone goes
        back on for the comparison, sunrise and sunset having one.
        """
        if when is None:
            return None
        return Sun.daytime(when.replace(tzinfo=self.piclock.timezone()),
                           self.piclock.expand(
                               self.config.location.latitude),
                           self.piclock.expand(
                               self.config.location.longitude),
                           self.piclock.timezone().key)

    @staticmethod
    def kmh(speed):
        """metric here is meters a second; everything else is km/h"""
        return None if speed is None else speed * 3.6
