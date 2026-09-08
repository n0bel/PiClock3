"""OpenWeather's free tier, as a weather source.

Two requests: what the sky is doing now, and a forecast running five days in
three-hour steps.  Both are on the permanently free plan - a key, an email
address and no card.  One Call, which would answer all three questions in
one request and hand over a ready-made daily grid, is the pay-per-call plan
instead, so this asks for what the free key can have.

That shape is the whole difference from Open-Meteo.  There is no daily
forecast to read, so a day here is rolled up from its three-hour entries -
the high and the low, what falls in it, and the worst thing the sky does.
A step under three hours cannot be honored, because nothing finer was sent.

What v1 did with the icon string in the response - '10d' - is what this
does with the numeric id beside it: the id separates freezing rain from
rain and drizzle from showers, and the icon string does not, so the id is
what a table to WMO 4678 notation can be written against.

Everything handed out is Celsius, millibars, km/h and percent, and the
condition is notation rather than words, so a widget drawing it never
learns which service it came from.
"""
import collections
import json
import logging
import math

from PyQt5.QtCore import QTimer
from PyQt5.QtNetwork import QNetworkReply

from ..Weather import Weather
from ..WebGet import WebGet, safeurl

logger = logging.getLogger(__name__)

CURRENT = 'https://api.openweathermap.org/data/2.5/weather'
FORECAST = 'https://api.openweathermap.org/data/2.5/forecast'

# hours between forecast entries.  The free tier's only grid.
STEP = 3

# OpenWeather's condition ids onto an icon and a WMO 4678 notation.  The
# 8xx group is sky cover, which 4678 has no notation for, so those carry
# METAR cover codes the way OpenMeteo's do.
CODES = {
    200: ('thunderstorm',        '-TSRA'),
    201: ('thunderstorm',        'TSRA'),
    202: ('thunderstorm',        '+TSRA'),
    210: ('thunderstorm',        '-TS'),
    211: ('thunderstorm',        'TS'),
    212: ('thunderstorm',        '+TS'),
    221: ('thunderstorm',        'TS'),
    # 4678 has no thunderstorm with drizzle, so these read as the lightest
    # thunderstorm with rain rather than inventing a code
    230: ('thunderstorm',        '-TSRA'),
    231: ('thunderstorm',        '-TSRA'),
    232: ('thunderstorm',        'TSRA'),

    300: ('rain',                '-DZ'),
    301: ('rain',                'DZ'),
    302: ('rain',                '+DZ'),
    310: ('rain',                '-DZRA'),
    311: ('rain',                'DZRA'),
    312: ('rain',                '+DZRA'),
    313: ('rain',                'SHRA'),
    314: ('rain',                '+SHRA'),
    321: ('rain',                '-SHRA'),

    500: ('rain',                '-RA'),
    501: ('rain',                'RA'),
    502: ('rain',                '+RA'),
    503: ('rain',                '+RA'),
    504: ('rain',                '+RA'),
    511: ('sleet',               'FZRA'),
    520: ('rain',                '-SHRA'),
    521: ('rain',                'SHRA'),
    522: ('rain',                '+SHRA'),
    531: ('rain',                'SHRA'),

    600: ('snow',                '-SN'),
    601: ('snow',                'SN'),
    602: ('snow',                '+SN'),
    # OpenWeather's sleet is ice pellets; rain and snow together are 615
    # and 616, which is the other thing the word means
    611: ('sleet',               'PL'),
    612: ('sleet',               '-PL'),
    613: ('sleet',               'PL'),
    615: ('sleet',               '-RASN'),
    616: ('sleet',               'RASN'),
    620: ('snow',                '-SHSN'),
    621: ('snow',                'SHSN'),
    622: ('snow',                '+SHSN'),

    701: ('fog',                 'BR'),
    711: ('fog',                 'FU'),
    721: ('fog',                 'HZ'),
    731: ('wind',                'PO'),
    741: ('fog',                 'FG'),
    751: ('fog',                 'SA'),
    761: ('fog',                 'DU'),
    762: ('fog',                 'VA'),
    771: ('wind',                'SQ'),
    781: ('wind',                '+FC'),

    800: ('clear-day',           'SKC'),
    801: ('clear-day',           'FEW'),
    802: ('partly-cloudy-day',   'SCT'),
    803: ('partly-cloudy-day',   'BKN'),
    804: ('cloudy',              'OVC'),
}

# which group is worse, worst last.  The group and not the id: OpenWeather
# numbers within a group by intensity but not across them, so 771 squalls
# is not worse than 622 heavy shower snow the way its number says.  This
# ranks forecast entries against each other, and a forecast does not carry
# the violent end of 7xx - a tornado is something observed, not predicted
# three hours out - so 7xx sitting under rain here is haze and mist.
GROUPS = [8, 7, 3, 5, 6, 2]

# and inside a group, the notation's own sign says how much
INTENSITY = {'-': 0, '+': 2}

# what a transport error most likely means to somebody with a key.  Qt
# hands over the code and drops the body, so the service's own sentence
# about it never arrives - and a key that has not been activated yet looks
# exactly like a wrong one, which is worth saying, because a new key takes
# a couple of hours before it answers.
REFUSED = {
    QNetworkReply.AuthenticationRequiredError:
        'the key was refused - a new one takes a couple of hours to start'
        ' working',
    QNetworkReply.ContentAccessDenied:
        'the key was refused, or the free plan does not have this',
}


def dewPoint(temp, humidity):
    """dew point from temperature and relative humidity, Celsius.

    The inverse of Weather.humidity(), and here rather than beside it
    because this is the only source that reports one and not the other -
    every other provider either sends a dew point or has none to send.
    """
    if temp is None or humidity is None or humidity <= 0:
        return None
    g = ((17.625 * temp) / (243.04 + temp)
         + math.log(min(humidity, 100.0) / 100.0))
    return (243.04 * g) / (17.625 - g)


class OpenWeatherMap(Weather):

    # their terms require it on every plan, the free one included
    attribution = 'OpenWeather'

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

        Six on almost every run: 120 hours from the next three-hour
        boundary crosses six local dates, part days at both ends.  A feed
        that happens to start at midnight crosses five, so a widget
        asking for six is briefly one short - said once, because an empty
        cell in the column looks like a fault.
        """
        if self.days and count > len(self.days) and not self.saidShort:
            self.saidShort = True
            logger.warning('%s: asked for %d days and this forecast'
                           ' reaches %d - it runs 120 hours from %s',
                           self.attribution, count, len(self.days),
                           self.hours[0]['when'] if self.hours else 'now')
        return self.days[:count]

    def hourly(self, count, step):
        """`count` entries from now, `step` hours apart.

        Rounded to the three-hour grid, which is all the free tier sends:
        a widget asking for every hour gets every third one, each stamped
        with the hour it is really for.
        """
        now = self.piclock.now().replace(tzinfo=None)
        start = next((i for i, h in enumerate(self.hours) if h['when'] > now),
                     None)
        if start is None:
            return []
        every = max(1, int(round(float(step) / STEP)))
        return [self.hours[i] for i in
                range(start, min(len(self.hours), start + count * every),
                      every)]

    # ------------------------------------------------------------ fetching

    def url(self, host):
        return ('%s?lat=%s&lon=%s&units=metric&appid=%s'
                % (host,
                   self.piclock.expand(self.config.location.latitude),
                   self.piclock.expand(self.config.location.longitude),
                   self.piclock.expand(self.config.apikey)))

    def getWeather(self):
        # two requests rather than one: the free key has no One Call, and
        # what it does have is split across these
        for host, done in ((CURRENT, self.gotCurrent),
                           (FORECAST, self.gotForecast)):
            u = self.url(host)
            logger.info('%s url %s', self.attribution, safeurl(u))
            WebGet(u, done)

    def answer(self, error, data):
        """the json a reply carried, or None having said why not.

        Two ways to be told no.  An HTTP error arrives as a transport
        error with the body already thrown away, so REFUSED is what
        stands in for the sentence the service sent; anything else comes
        back as a 200 with cod: and message: in the json.
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
        if str(index.get('cod')) not in ('200', 'None'):
            logger.warning('%s said %s: %s', self.attribution,
                           index.get('cod'), index.get('message'))
            return None
        return index

    def gotCurrent(self, error, data, params):
        index = self.answer(error, data)
        if index is None:
            return

        main = index.get('main') or {}
        wind = index.get('wind') or {}
        sun = index.get('sys') or {}
        temp = main.get('temp')
        humidity = main.get('humidity')
        icon, notation = self.look(self.code(index))
        self.now = {
            'when': self.when(index.get('dt')),
            # the response says when the sun rises and sets today, so the
            # day or night picture comes from that rather than from Sun
            'icon': self.variant(icon, self.daylight(index.get('dt'), sun)),
            'condition': notation,
            'temp': temp,
            'dew': dewPoint(temp, humidity),
            'humidity': humidity,
            'feels-like': main.get('feels_like'),
            'pressure': main.get('pressure'),
            'wind': self.kmh(wind.get('speed')),
            'wind-dir': wind.get('deg'),
            'gust': self.kmh(wind.get('gust')),
            'raw': index,
        }
        logger.info('%s: conditions at %s', self.attribution,
                    self.now['when'])
        for fn in self.listeners:
            fn()

    def gotForecast(self, error, data, params):
        index = self.answer(error, data)
        if index is None:
            return

        hours = []
        for entry in index.get('list') or []:
            main = entry.get('main') or {}
            icon, notation = self.look(self.code(entry))
            pod = (entry.get('sys') or {}).get('pod')
            hours.append({
                'when': self.when(entry.get('dt')),
                'icon': self.variant(icon,
                                     None if pod is None else pod == 'd'),
                'condition': notation,
                'temp': main.get('temp'),
                'precip': self.percent(entry.get('pop')),
                'accum': self.fell(entry, 'rain'),
                'snow': self.fell(entry, 'snow'),
                'raw': entry,
            })
        self.hours = hours
        self.days = self.rollUp(index.get('list') or [])

        logger.info('%s: %d days and %d entries, first day %s',
                    self.attribution, len(self.days), len(hours),
                    self.days[0]['when'] if self.days else 'none')
        for fn in self.listeners:
            fn()

    # ------------------------------------------------------------- shaping

    def rollUp(self, entries):
        """the three-hour entries gathered into days.

        The first and last are part days - the forecast starts at the next
        three-hour boundary and runs 120 hours from there - which is what
        they are, so they are reported as they came rather than dropped.

        Midnight to midnight, where v1 used 6am to 6am and called it the
        weather day.  Both reach six dates out of 120 hours; a day the
        clock draws beside a date and a day name should start when the
        date does.
        """
        byDay = collections.OrderedDict()
        for entry in entries:
            when = self.when(entry.get('dt'))
            if when is not None:
                byDay.setdefault(when.date(), []).append(entry)

        days = []
        for date, day in list(byDay.items())[:int(
                self.config['forecast-days'])]:
            # temp rather than temp_max: the min and max beside it are the
            # spread across a city rather than across the three hours, and
            # OpenWeather's own advice is to leave them alone
            temps = [(e.get('main') or {}).get('temp') for e in day]
            temps = [t for t in temps if t is not None]
            pops = [self.percent(e.get('pop')) for e in day]
            pops = [p for p in pops if p is not None]
            icon, notation = self.look(self.worst(day))
            days.append({
                'when': date,
                # the day picture, whatever hour the worst of it fell in
                'icon': self.variant(icon, True),
                'condition': notation,
                'high': max(temps) if temps else None,
                'low': min(temps) if temps else None,
                'precip': max(pops) if pops else None,
                'accum': sum(self.fell(e, 'rain') or 0 for e in day),
                'snow': sum(self.fell(e, 'snow') or 0 for e in day),
                # a day is this plugin's construction rather than the
                # service's, so what it was built from is what raw holds
                'raw': day,
            })
        return days

    @classmethod
    def worst(cls, entries):
        """the condition id that decides what a day looked like.

        The worst of them, where v1 took the commonest.  A forecast is
        read to find out whether it will rain, and an afternoon of it
        under a mostly cloudy sky is a day the commonest calls cloudy.
        """
        codes = [cls.code(e) for e in entries]
        codes = [c for c in codes if c is not None]
        return max(codes, key=cls.rank) if codes else None

    @staticmethod
    def rank(code):
        """how bad a condition id is, against another from the same day.

        The group first, then the notation's own intensity sign, and the
        id last so that overcast outranks clear where neither says more.
        """
        notation = CODES.get(code, ('', ''))[1]
        group = code // 100
        return (GROUPS.index(group) if group in GROUPS else 0,
                INTENSITY.get(notation[:1], 1),
                code)

    @staticmethod
    def code(entry):
        """the condition id of an entry, or None.

        A location can meet more than one condition at once, and the first
        is the primary one.
        """
        weather = entry.get('weather') or [{}]
        return weather[0].get('id')

    @staticmethod
    def look(code):
        """an id as an icon and a notation, or as the fallback pair"""
        return CODES.get(code, ('cloudy', ''))

    def when(self, stamp):
        """a unix timestamp as a naive time where the clock is pointed.

        Naive because that is what every entry a widget compares against
        is, hourly() included.
        """
        if stamp is None:
            return None
        return self.piclock.localtime(stamp).replace(tzinfo=None)

    def daylight(self, stamp, sun):
        """was the sun up, from the sunrise and sunset in the response"""
        up, down = sun.get('sunrise'), sun.get('sunset')
        if stamp is None or up is None or down is None:
            return None
        return up <= stamp < down

    @staticmethod
    def kmh(speed):
        """metric here is meters a second; everything else is km/h"""
        return None if speed is None else speed * 3.6

    @staticmethod
    def percent(pop):
        """probability of precipitation, which arrives as a fraction"""
        return None if pop is None else float(pop) * 100.0

    @staticmethod
    def fell(entry, what):
        """how much rain or snow fell in an entry's three hours, in mm.

        The block is absent rather than zero when nothing did.
        """
        return (entry.get(what) or {}).get('3h')
