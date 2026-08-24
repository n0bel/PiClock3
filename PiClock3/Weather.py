"""Derivations a weather source can do for itself.

A station reports temperature, dew point and wind and leaves the rest to the
reader.  These are the sums that reader has to do, so a provider can hand
out numbers and a widget can go back to only formatting.

Everything here takes and returns numbers - Celsius, km/h, percent.  Nothing
formats.
"""
import datetime
import math

from astral import LocationInfo
from astral.sun import sun


def humidity(temp, dew):
    """relative humidity from temperature and dew point, both Celsius"""
    if temp is None or dew is None:
        return None
    return 100.0 * (math.exp((17.625 * dew) / (243.04 + dew)) /
                    math.exp((17.625 * temp) / (243.04 + temp)))


def feelsLike(temp, dew, wind):
    """what the air feels like: heat index when hot, wind chill when cold.

    Both formulae are the US National Weather Service ones and are defined
    in Fahrenheit and mph, so the conversion in and out is theirs, not a
    display choice.  Returns Celsius.
    """
    if temp is None or dew is None or wind is None:
        return None
    h = humidity(temp, dew) / 100.0
    t = temp * 1.8 + 32.0
    w = wind / 1.609344

    if t > 80 and h >= 0.40:
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * h * 100
              - .22475541 * t * h * 100 - .00683783 * t * t
              - .05481717 * h * 100 * h * 100 + .00122874 * t * t * h * 100
              + .00085282 * t * h * 100 * h * 100
              - .00000199 * t * t * h * 100 * h * 100)
        return (hi - 32.0) / 1.8
    if t < 50 and w >= 3:
        wc = (35.74 + 0.6215 * t - 35.75 * (w ** 0.16)
              + 0.4275 * t * (w ** 0.16))
        return (wc - 32.0) / 1.8
    return temp


def daytime(when, latitude, longitude, zone):
    """is the sun up at `when`, where the clock is pointed.

    The sun rather than a rule about six o'clock, which is wrong by hours in
    summer and by half the year above the arctic circle.  A place where the
    sun does not rise or set that day answers by hemisphere and season.
    """
    try:
        here = LocationInfo('here', 'here', zone, latitude, longitude)
        s = sun(here.observer, date=when.date(), tzinfo=here.timezone)
        return s['sunrise'] <= when <= s['sunset']
    except ValueError:
        # polar day or polar night: no sunrise to compare against
        summer = 4 <= when.month <= 9
        return summer if float(latitude) >= 0 else not summer
    except Exception:
        return 6 <= when.hour < 18


def variant(icon, isDay):
    """the day or night picture of the same condition"""
    if isDay is None:
        return icon
    return (icon.replace('-night', '-day') if isDay
            else icon.replace('-day', '-night'))
