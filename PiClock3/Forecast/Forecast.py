"""A forecast down a column of cells, near hours first and then whole days.

This is the drawing half.  It asks a provider - named by forecast-provider -
for as many hourly and daily entries as its config says, and knows nothing
about where they came from.  Anything the provider hands over is already
normalized, so a second source is a second provider and not a branch here.

The shape follows PiClock v1: a picture on the left, the conditions in words
above a line of figures, and the day in the bottom corner.  The first cells
carry the next few hours, because what the weather is doing this afternoon
matters more than what Thursday looks like.
"""
import logging

from PyQt5 import QtGui
from PyQt5.QtCore import Qt

from ..Widget import Widget

logger = logging.getLogger(__name__)


class Forecast(Widget):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.provider = piclock.plugins[self.config['forecast-provider']]
        self.cells = []
        self.hourFormat = None
        self.dayFormat = None

    def start(self):
        self.hourFormat = self.strftimePortableFormat(
            self.config['hour-format'])
        self.dayFormat = self.strftimePortableFormat(
            self.config['day-format'])
        want = int(self.config['hourly']) + int(self.config['daily'])
        if want > len(self.regions):
            logger.warning(
                '%s asks for %d cells (%s hourly + %s daily) but its region'
                ' has %d', self.name, want, self.config['hourly'],
                self.config['daily'], len(self.regions))

        for region in self.regions:
            self.cells.append({
                'icon': self.part('icon', region),
                'wx': self.part('wx', region),
                'day': self.part('day', region),
            })

        # Open-Meteo's data is CC-BY and the credit is required
        credit = self.provider.attribution
        if credit and 'attribution' in self.config['layout']:
            self.part('attribution', self.regions[-1]).setText(credit)

        # drawn the moment a forecast lands, and again on every refresh
        self.provider.subscribe(self.draw)

    def pageChange(self):
        return

    # ------------------------------------------------------------ drawing

    def draw(self):
        hours = int(self.config['hourly'])
        days = int(self.config['daily'])
        near = self.provider.hourly(hours, int(self.config['hourly-step']))
        far = self.provider.daily(days)

        for i, cell in enumerate(self.cells):
            if i < hours and i < len(near):
                self.fill(cell, near[i], self.hourFormat,
                          self.hourFigures(near[i]))
            elif hours <= i < hours + days and (i - hours) < len(far):
                day = far[i - hours]
                self.fill(cell, day, self.dayFormat,
                          self.dayFigures(day))
            else:
                for key in ('icon', 'wx', 'day'):
                    cell[key].clear()

    def fill(self, cell, entry, when, figures):
        p = QtGui.QPixmap(self.icon(entry['icon']))
        cell['icon'].setPixmap(p.scaled(
            cell['icon'].width(), cell['icon'].height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        cell['wx'].setText(
            self.piclock.condition(entry.get('condition'))
            + '\n' + figures)
        cell['day'].setText(entry['when'].strftime(when))

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
        """how much is coming, when it rounds to more than nothing.

        A provider's precipitation figure is liquid water - snow melted -
        and snow lies several times deeper than the water in it, so snow is
        asked for separately and in its own depth.
        """
        snowy = entry['icon'] == 'snow'
        amount = entry.get('snow') if snowy else None
        frm = 'cm'
        if amount is None:
            amount, frm = entry.get('accum'), 'mm'
        if not amount:
            return ''
        shown = self.units('depth', frm, amount)
        if float(''.join(c for c in shown if c.isdigit() or c == '.')) == 0:
            return ''
        word = self.piclock.condition('SN' if snowy else 'RA')
        return '%s %s ' % (word, shown)

    def temperature(self, c, unit=True):
        """Celsius from the provider, in whole degrees"""
        if c is None:
            return ''
        t = self.units('temperature', 'C', c)
        return t if unit else t.rstrip('CF').rstrip('°')
