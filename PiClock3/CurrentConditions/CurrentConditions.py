"""What the weather is doing now, from whichever source is pointed at it.

The source is named by conditions-provider and can be a station report or a
model: both answer current() with the same shape, in Celsius, millibars and
km/h.  The bottom line carries the time of the observation and whatever the
source calls itself - a station id, or the name of a service.

Humidity and how it feels are taken from the source when it supplies them
and worked out from temperature, dew point and wind when it does not, which
is what a station report leaves to the reader.
"""
import logging

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from ..Plugin import Plugin

logger = logging.getLogger(__name__)


class CurrentConditions(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.provider = piclock.plugins[self.config['conditions-provider']]
        self.parts = {}
        self.observedFormat = None

    def start(self):
        self.observedFormat = self.strftimePortableFormat(
            self.config['observed-format'])
        for name in ('wxicon', 'wxdesc', 'temper', 'pressure', 'humidity',
                     'wind', 'feelslike', 'wdate'):
            self.parts[name] = self.part(name)
        self.provider.subscribe(self.draw)

    def pageChange(self):
        return

    def part(self, name):
        """one labeled part of this region, placed by this plugin's layout"""
        spec = self.config['layout'][name]
        rr = self.region.frameRect()
        label = QLabel(self.region)
        label.setObjectName(name)
        style = 'background-color: transparent;'
        if 'font-size' in spec:
            props = self.piclock.scaleFont({'font-size': spec['font-size']},
                                           rr.height())
            # not color: it arrives on the region and Qt inherits it
            style += ' font-size: %s;' % props['font-size']
        label.setStyleSheet('#%s { %s }' % (name, style))
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        label.setGeometry(self.piclock._regionRect(rr.width(), rr.height(),
                                                   spec))
        return label

    def draw(self):
        c = self.provider.current()
        if not c:
            return
        L = self.piclock.language
        temp, dew, wind = c.get('temp'), c.get('dew'), c.get('wind')

        p = QtGui.QPixmap(self.icon(c.get('icon') or 'cloudy'))
        icon = self.parts['wxicon']
        icon.setPixmap(p.scaled(icon.width(), icon.height(),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.parts['wxdesc'].setText(
            self.piclock.condition(c.get('condition')))

        self.parts['temper'].setText(
            '' if temp is None
            else self.units('temperature', 'C', temp))

        press = c.get('pressure')
        self.parts['pressure'].setText(
            '' if press is None
            else '%s %s' % (L('pressure'),
                            self.units('altimeter', 'mb', press)))

        self.parts['humidity'].setText(self.humidity(c, temp, dew))
        self.parts['wind'].setText(self.wind(c, wind))
        self.parts['feelslike'].setText(self.feels(c, temp, dew, wind))

        when = c.get('when')
        self.parts['wdate'].setText(
            '' if when is None
            else '%s %s' % (when.strftime(self.observedFormat),
                            getattr(self.provider, 'attribution', '')))

    def humidity(self, c, temp, dew):
        given = c.get('humidity')
        if given is None:
            return ''
        return '%s %.0f%%' % (self.piclock.language('humidity'), given)

    def wind(self, c, speed):
        if speed is None:
            return ''
        L = self.piclock.language
        s = L('wind')
        if c.get('wind-dir') is not None:
            s += ' ' + self.units('direction', 'deg', c['wind-dir'])
        s += ' ' + self.units('speed', 'kph', speed)
        if c.get('gust') is not None:
            s += ' %s %s' % (L('gusting'),
                             self.units('speed', 'kph', c['gust']))
        return s

    def feels(self, c, temp, dew, wind):
        given = c.get('feels-like')
        if given is None:
            return ''
        return '%s %s' % (self.piclock.language('feels_like'),
                          self.units('temperature', 'C', given))
