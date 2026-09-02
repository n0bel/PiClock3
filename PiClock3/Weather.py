import math

from .Provider import Provider


class Weather(Provider):
    """what the sky is doing, or will be.

    One interface behind two kinds - `weather-source` and `forecast-source`
    - because a station reports what is happening and a model reports what
    will.  Which of those a provider can answer is its own to declare.

    The sums below are the ones a station leaves to its reader: it reports
    temperature, dew point and wind and nothing more.  Doing them here is
    what lets a provider hand out numbers and a widget go back to only
    formatting.  They take and return numbers - Celsius, km/h, percent -
    and none of them formats.
    """

    def subscribe(self, fn):
        """call fn() whenever fresh data lands.

        A widget draws from what conditions(), hourly() and daily() answer, so
        this is how it learns there is anything new to draw.
        """
        raise NotImplementedError(
            '%s: %s reports weather and has no subscribe'
            % (self.name, type(self).__name__))

    # The three below are each a question a source may not be able to
    # answer, so each has an answer meaning it cannot: a station reports
    # what is happening rather than what will, and a model can forecast
    # without observing anything.  A provider says which it does by
    # implementing those and leaving the rest alone.

    def conditions(self):
        """what the sky is doing now, or None."""
        return None

    def hourly(self, count, step):
        """`count` entries from now, `step` hours apart, or empty."""
        return []

    def daily(self, count):
        """`count` days ahead, today first, or empty."""
        return []

    @staticmethod
    def humidity(temp, dew):
        """relative humidity from temperature and dew point, both Celsius"""
        if temp is None or dew is None:
            return None
        return 100.0 * (math.exp((17.625 * dew) / (243.04 + dew)) /
                        math.exp((17.625 * temp) / (243.04 + temp)))

    @staticmethod
    def feelsLike(temp, dew, wind):
        """what the air feels like: heat index when hot, wind chill when cold.

        Both formulae are the US National Weather Service ones and are defined
        in Fahrenheit and mph, so the conversion in and out is theirs, not a
        display choice.  Returns Celsius.
        """
        if temp is None or dew is None or wind is None:
            return None
        h = Weather.humidity(temp, dew) / 100.0
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

    @staticmethod
    def variant(icon, isDay):
        """the day or night picture of the same condition"""
        if isDay is None:
            return icon
        return (icon.replace('-night', '-day') if isDay
                else icon.replace('-day', '-night'))
