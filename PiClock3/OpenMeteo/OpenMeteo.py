"""Open-Meteo's daily forecast.

No key and no account.  The free tier asks only that non-commercial use stay
inside a daily volume that one clock, asking every half hour, is nowhere
near.

This supplies data and occupies no region, so it is a provider.  What it
hands back is normalized - a day, an icon name, a WMO 4678 condition, a
high and a low in Celsius - so a widget drawing it never learns which service
it came from, and a second source is a second plugin rather than a branch in
the drawing code.  Beside that, raw carries the service's own record for the
entry untouched, so normalizing costs nothing.
"""
import datetime
import json
import logging

from .. import Weather
from ..Plugin import Plugin
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

HOST = 'https://api.open-meteo.com/v1/forecast'
ATTRIBUTION = 'Open-Meteo'

# Open-Meteo's weather codes onto an icon and a WMO 4678 notation.  The
# codes are not 4678 and not quite 4677 either - 0 to 3 are sky cover, which
# 4678 has no notation for, so those carry METAR cover codes instead.
WMO = {
    0:  ('clear-day',         'SKC'),
    1:  ('clear-day',         'FEW'),
    2:  ('partly-cloudy-day', 'SCT'),
    3:  ('cloudy',            'OVC'),
    45: ('fog',               'FG'),
    48: ('fog',               'FZFG'),
    51: ('rain',              '-DZ'),
    53: ('rain',              'DZ'),
    55: ('rain',              '+DZ'),
    56: ('sleet',             '-FZDZ'),
    57: ('sleet',             'FZDZ'),
    61: ('rain',              '-RA'),
    63: ('rain',              'RA'),
    65: ('rain',              '+RA'),
    66: ('sleet',             '-FZRA'),
    67: ('sleet',             'FZRA'),
    71: ('snow',              '-SN'),
    73: ('snow',              'SN'),
    75: ('snow',              '+SN'),
    77: ('snow',              'SG'),
    80: ('rain',              '-SHRA'),
    81: ('rain',              'SHRA'),
    82: ('rain',              '+SHRA'),
    85: ('snow',              '-SHSN'),
    86: ('snow',              '+SHSN'),
    95: ('thunderstorm',      'TS'),
    96: ('thunderstorm',      'TSGR'),
    99: ('thunderstorm',      '+TSGR'),
}


class OpenMeteo(Plugin):

    # CC-BY 4.0: no key, but the credit is required
    attribution = ATTRIBUTION

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.days = []
        self.hours = []
        self.now = None
        self.listeners = []
        self.timer = None

    def start(self):
        from PyQt5.QtCore import QTimer
        self.timer = QTimer()
        self.timer.timeout.connect(self.getForecast)
        self.timer.start(int(60000 * self.config['refresh']))
        self.getForecast()

    def pageChange(self):
        return

    # ---------------------------------------------------------------- api

    def subscribe(self, fn):
        """call fn() whenever a new forecast lands"""
        self.listeners.append(fn)
        if self.now or self.days or self.hours:
            fn()

    def current(self):
        """conditions now, or None before the first answer arrives"""
        return self.now

    def daily(self, count):
        """the next `count` days, today first"""
        return self.days[:count]

    def hourly(self, count, step):
        """`count` entries from now, `step` hours apart.

        The grid starts at midnight, so the first future entry is found
        rather than assumed.
        """
        now = self.piclock.now().replace(tzinfo=None)
        start = next((i for i, h in enumerate(self.hours) if h['when'] > now),
                     None)
        if start is None:
            return []
        return [self.hours[i] for i in
                range(start, min(len(self.hours), start + count * step), step)]

    # ------------------------------------------------------------ fetching

    def url(self):
        # both grids in one request: the near hours in detail, then the days
        return (
            '%s?latitude=%s&longitude=%s'
            '&current=weather_code,is_day,temperature_2m,relative_humidity_2m,'
            'apparent_temperature,pressure_msl,wind_speed_10m,'
            'wind_direction_10m,wind_gusts_10m'
            '&hourly=weather_code,is_day,temperature_2m,precipitation_probability,'
            'precipitation,snowfall'
            '&daily=weather_code,temperature_2m_max,temperature_2m_min,'
            'precipitation_probability_max,precipitation_sum,snowfall_sum'
            '&temperature_unit=celsius&wind_speed_unit=kmh'
            '&timezone=%s&forecast_days=%d'
            % (HOST,
               self.piclock.expand(self.config.location.latitude),
               self.piclock.expand(self.config.location.longitude),
               self.piclock.timezone().key,
               int(self.config['forecast-days'])))

    def getForecast(self):
        u = self.url()
        logger.info('%s url %s', ATTRIBUTION, u)
        WebGet(u, self.gotForecast)

    @staticmethod
    def record(block, i):
        """everything the service said about one hour or one day.

        Un-normalized and provider-shaped on purpose: it is where anything
        this plugin does not translate remains reachable.
        """
        return {k: v[i] for k, v in block.items()
                if isinstance(v, list) and i < len(v)}

    def gotForecast(self, error, data, params):
        if error:
            logger.warning('%s failed: %s', ATTRIBUTION, error)
            return
        try:
            index = json.loads(bytes(data).decode('utf-8'))
        except ValueError:
            logger.warning('%s did not answer with json', ATTRIBUTION)
            return

        # Celsius, percent and millimeters throughout; converting is the
        # drawing side's business
        daily = index.get('daily') or {}
        days = []
        for i, when in enumerate(daily.get('time') or []):
            code = self.at(daily, 'weather_code', i)
            icon, notation = WMO.get(code, ('cloudy', ''))
            days.append({
                'when': datetime.date.fromisoformat(when),
                'icon': icon,
                'condition': notation,
                'high': self.at(daily, 'temperature_2m_max', i),
                'low': self.at(daily, 'temperature_2m_min', i),
                'precip': self.at(daily, 'precipitation_probability_max', i),
                'accum': self.at(daily, 'precipitation_sum', i),
                'snow': self.at(daily, 'snowfall_sum', i),
                'raw': self.record(daily, i),
            })
        self.days = days

        now = index.get('current') or {}
        if now:
            code = now.get('weather_code')
            icon, notation = WMO.get(code, ('cloudy', ''))
            self.now = {
                'when': datetime.datetime.fromisoformat(now['time']),
                'icon': Weather.variant(icon, now.get('is_day')),
                'condition': notation,
                'temp': now.get('temperature_2m'),
                'dew': None,
                'humidity': now.get('relative_humidity_2m'),
                'feels-like': now.get('apparent_temperature'),
                'pressure': now.get('pressure_msl'),
                'wind': now.get('wind_speed_10m'),
                'wind-dir': now.get('wind_direction_10m'),
                'gust': now.get('wind_gusts_10m'),
                'raw': now,
            }

        hourly = index.get('hourly') or {}
        hours = []
        for i, when in enumerate(hourly.get('time') or []):
            code = self.at(hourly, 'weather_code', i)
            icon, notation = WMO.get(code, ('cloudy', ''))
            hours.append({
                'when': datetime.datetime.fromisoformat(when),
                'icon': Weather.variant(icon, self.at(hourly, 'is_day', i)),
                'condition': notation,
                'temp': self.at(hourly, 'temperature_2m', i),
                'precip': self.at(hourly, 'precipitation_probability', i),
                'accum': self.at(hourly, 'precipitation', i),
                'snow': self.at(hourly, 'snowfall', i),
                'raw': self.record(hourly, i),
            })
        self.hours = hours

        logger.info('%s: %d days and %d hours, first day %s', ATTRIBUTION,
                    len(days), len(hours),
                    days[0]['when'] if days else 'none')
        for fn in self.listeners:
            fn()

    @staticmethod
    def at(daily, key, i):
        """one value out of one of Open-Meteo's parallel arrays.

        Any of them can be null for a day the model has nothing for, and a
        missing key is not an error worth stopping over.
        """
        col = daily.get(key) or []
        return col[i] if i < len(col) else None
