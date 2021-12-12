
import datetime
import math
from compassheadinglib import Compass

from ..Plugin import Plugin


class WeatherCommon(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)

    def start(self):
        return

    def pageChange(self):
        return

    def daytime(self):
        hour = datetime.datetime.now().hour
        if hour >= 18 or hour < 6:
            return False
        return True

    def icon(self, icon):
        if not self.daytime():
            icon = icon.replace('-day', '-night')

        iconsFolder = self.piclock.expand(
            self.config['icons-base-folder'] +
            '/' +
            self.config['icons-folder'] + '/')
        return self.piclock.expand(iconsFolder + icon + ".png")

    def units(self, utype, uin, data):
        uout = self.config.units[utype]
        if utype == 'temperature':
            if uin == 'F' and uout == 'C':
                data = (data - 32.0) / 1.8
            elif uin == 'C' and uout == 'F':
                data = data * 1.8 + 32.0
            return '%.1f' % (data) + u'°' + uout
        if utype == 'pressure':
            if uin == 'mb' and uout == 'in':
                data = data / 33.863886666667
            elif uin == 'mb' and uout == 'mm':
                data = data / 1.3332239
            elif uin == 'mm' and (uout == 'mb' or uout == 'hPa'):
                data = data * 1.3332239
            elif uin == 'in' and (uout == 'mb' or uout == 'hPa'):
                data = data * 33.863886666667
            elif (uin == 'hPa' or uin == 'mb') and uout == 'in':
                data = data / 33.863886666667
            elif (uin == 'hPa' or uin == 'mb') and uout == 'mm':
                data = data / 1.3332239
            elif uin == 'in' and uout == 'mm':
                data = data * 25.4
            elif uin == 'mm' and uout == 'in':
                data = data / 25.4
            if uout == 'mm' or uout == 'mb' or uout == 'hPa':
                return '%.1f' % (data) + uout
            else:
                return '%.2f' % (data) + uout
        if utype == 'direction':
            if uin == 'deg' and uout == 'dir':
                return Compass.findHeading(data, 3).abbr
            else:
                return str(data) + u'°'
        if utype == 'speed':
            if uin == 'mph' and (uout == 'kph' or uout == 'km/h'):
                data = data * 1.609344
            elif (uin == 'kph' or uin == 'km/h') and uout == 'mph':
                data = data / 1.609344
            elif uin == 'mph' and (uout == 'mps' or uout == 'm/s'):
                data = data * 0.44704
            elif (uin == 'mps' or uin == 'm/s') and uout == 'mph':
                data = data / 0.44704
            return '%.1f' % (data) + uout

    def humidity(self, temp, dew):
        h = 100.0 * (math.exp((17.625 * dew) / (243.04 + dew)) /
                     math.exp((17.625 * temp) / (243.04 + temp)))
        return '%.0f%%' % h

    def feelsLike(self, temp, dew, wind):
        t = temp
        d = dew
        h = (math.exp((17.625 * d) / (243.04 + d)) /
             math.exp((17.625 * t) / (243.04 + t)))
        t = temp * 1.8 + 32.0  # C to F
        w = wind / 1.609344  # kph to mph
        if t > 80 and h >= 0.40:
            hi = (-42.379 + 2.04901523 * t + 10.14333127 * h - .22475541 * t * h -
                  .00683783 * t * t - .05481717 * h * h + .00122874 * t * t * h +
                  .00085282 * t * h * h - .00000199 * t * t * h * h)
            if h < 0.13 and t >= 80.0 and t <= 112.0:
                hi -= ((13 - h) / 4) * math.sqrt((17 - math.abs(t - 95)) / 17)
            if h > 0.85 and t >= 80.0 and t <= 112.0:
                hi += ((h - 85) / 10) * ((87 - t) / 5)
            return self.units('temperature', 'F', hi)
        if t < 50 and w >= 3:
            wc = 35.74 + 0.6215 * t - 35.75 * \
                (w ** 0.16) + 0.4275 * t * (w ** 0.16)
            return self.units('temperature', 'F', wc)
        return self.units('temperature', 'F', t)
