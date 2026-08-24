"""A forecast down a column of cells, near hours first and then whole days.

This is the drawing half.  It asks a provider - named by forecast-provider -
for as many hourly and daily entries as its config says, and knows nothing
about where they came from.  Anything the provider hands over is already
normalised, so a second source is a second provider and not a branch here.

The shape follows PiClock v1: a picture on the left, the conditions in words
above a line of figures, and the day in the bottom corner.  The first cells
carry the next few hours, because what the weather is doing this afternoon
matters more than what Thursday looks like.
"""
import logging

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from ..Plugin import Plugin

logger = logging.getLogger(__name__)

ALIGN = {
    'left-top': Qt.AlignLeft | Qt.AlignTop,
    'right-bottom': Qt.AlignRight | Qt.AlignBottom,
    'center': Qt.AlignCenter,
}


class Forecast(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.provider = piclock.plugins[self.config['forecast-provider']]
        self.cells = []

    def start(self):
        want = int(self.config['hourly']) + int(self.config['daily'])
        if want > len(self.regions):
            logger.warning(
                '%s asks for %d cells (%s hourly + %s daily) but its region'
                ' has %d', self.name, want, self.config['hourly'],
                self.config['daily'], len(self.regions))

        for region in self.regions:
            self.cells.append({
                'icon': self.part(region, 'icon'),
                'wx': self.part(region, 'wx'),
                'day': self.part(region, 'day'),
            })

        # Open-Meteo's data is CC-BY and the credit is required
        credit = getattr(self.provider, 'attribution', '')
        if credit and 'attribution' in self.config['layout']:
            self.part(self.regions[-1], 'attribution').setText(credit)

        # drawn the moment a forecast lands, and again on every refresh
        self.provider.subscribe(self.draw)

    def pageChange(self):
        return

    def part(self, region, name):
        """one labelled part of one cell, placed by this plugin's layout.

        The geometry keys are the ones a page layout uses, resolved against
        the cell rather than against a page, so nothing about where these sit
        is written in the code.
        """
        spec = self.config['layout'][name]
        rr = region.frameRect()
        label = QLabel(region)
        label.setObjectName(name)
        style = 'background-color: transparent;'
        if 'font-size' in spec:
            props = self.piclock.scaleFont({'font-size': spec['font-size']},
                                           rr.height())
            style += ' color: %s; font-size: %s;' % (
                self.piclock.expand(self.config['color']), props['font-size'])
        label.setStyleSheet('#%s { %s }' % (name, style))
        if 'align' in spec:
            label.setAlignment(ALIGN.get(spec['align'], Qt.AlignCenter))
        if spec.get('wrap'):
            label.setWordWrap(True)
        label.setGeometry(self.piclock._regionRect(rr.width(), rr.height(),
                                                   spec))
        return label

    # ------------------------------------------------------------ drawing

    def draw(self):
        hours = int(self.config['hourly'])
        days = int(self.config['daily'])
        near = self.provider.hourly(hours, int(self.config['hourly-step']))
        far = self.provider.daily(days)

        for i, cell in enumerate(self.cells):
            if i < hours and i < len(near):
                self.fill(cell, near[i], self.config['hour-format'],
                          self.hourFigures(near[i]))
            elif hours <= i < hours + days and (i - hours) < len(far):
                day = far[i - hours]
                self.fill(cell, day, self.config['day-format'],
                          self.dayFigures(day))
            else:
                for key in ('icon', 'wx', 'day'):
                    cell[key].clear()

    def fill(self, cell, entry, when, figures):
        p = QtGui.QPixmap(self.icon(entry['icon']))
        cell['icon'].setPixmap(p.scaled(
            cell['icon'].width(), cell['icon'].height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        cell['wx'].setText(entry['description'] + '\n' + figures)
        stamp = entry['when'].strftime(when)
        # a leading zero on a 12 hour clock reads as a typo
        cell['day'].setText(stamp.lstrip('0') if '%I' in when else stamp)

    def hourFigures(self, hour):
        """chance, then any accumulation, then the temperature"""
        return (self.chance(hour) + self.accumulation(hour) +
                self.temperature(hour['temp']))

    def dayFigures(self, day):
        """chance, then any accumulation, then high over low"""
        return (self.chance(day) + self.accumulation(day) +
                self.temperature(day['high'], unit=False) + '/' +
                self.temperature(day['low'], unit=False))

    def chance(self, entry):
        pop = entry.get('precip')
        return '' if not pop else '%d%% ' % pop

    def accumulation(self, entry):
        """rain or snow, when it amounts to more than a rounded zero"""
        mm = entry.get('accum')
        if not mm:
            return ''
        shown = self.units('depth', 'mm', mm)
        if float(''.join(c for c in shown if c.isdigit() or c == '.')) == 0:
            return ''
        word = self.piclock.language(
            'snow' if entry['icon'] == 'snow' else 'rain')
        return '%s %s ' % (word, shown)

    def temperature(self, c, unit=True):
        """Celsius from the provider, in whole degrees"""
        if c is None:
            return ''
        t = self.units('temperature', 'C', c)
        return t if unit else t.rstrip('CF').rstrip('°')
