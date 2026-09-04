"""Converting and formatting quantities, for any plugin that shows a number.

Core, not a weather feature: a tide plugin wants feet and a market plugin
wants a currency symbol, and neither should have to reach into a weather
plugin to get one.  Reached through Plugin.units(), so nothing declares a
dependency and nothing is wired in a config.

The table is data - see PiClock3/units/quantities.yaml.  Files are found the
way themes and layouts are found, and merged rather than first-wins, so a
plugin can add a quantity and you can override any of it:

    PiClock3/units/     shipped
    plugins/*/units/    what a plugin brought with it
    units/             yours
    Config.yaml        units: names the set, unit-sets: may define one

Merged at load time, so a malformed file is a readable startup message
rather than a KeyError inside a Qt callback with nothing in the log.
"""
import glob
import logging
import os
import re

import yaml
from compassheadinglib import Compass

logger = logging.getLogger(__name__)


def compass(value, unit):
    """degrees as a point of the compass - a lookup, not arithmetic"""
    return Compass.findHeading(value, 3).abbr


VIA = {'compass': compass}

# a number, then whatever is left is the unit.  Not letters-only: a unit
# may hold anything the table's own key does, and rate: is mm/h.
MEASURE = re.compile(r'^([-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*(.*)$')


class Units():

    def __init__(self, piclock):
        self.piclock = piclock
        self.quantities = {}
        self.sets = {}

    @staticmethod
    def _merge(source, destination):
        """dicts merge, anything else replaces - as Config does"""
        for key, value in source.items():
            if isinstance(value, dict):
                Units._merge(value, destination.setdefault(key, {}))
            else:
                destination[key] = value
        return destination

    # ----------------------------------------------------------- loading

    def folders(self):
        """every place a units file can be, least specific first.

        Plugins are found on disk rather than from imported modules,
        because the table has to exist before the first widget draws and
        modules are not imported until then.
        """
        found = [os.path.join('PiClock3', 'units')]
        for base in (os.path.join('PiClock3', '*'),
                     os.path.join('plugins', '*')):
            found += sorted(glob.glob(os.path.join(base, 'units')))
        found.append('units')
        # PiClock3/units also matches the PiClock3/* glob
        return [f for i, f in enumerate(found) if f not in found[:i]]

    def load(self):
        """every units file there is, merged, least specific first"""
        for folder in self.folders():
            self.merge(folder)

        # the config selects a set and may define one; editing the table
        # itself belongs in a units/ folder, which is what the path is for
        sets = self.piclock.config.get('unit-sets')
        if sets:
            self._merge(sets, self.sets)

        logger.info('units: %d quantities, %d sets, using %s',
                    len(self.quantities), len(self.sets), self.setName())

    def setName(self):
        """the set this clock is using"""
        chosen = self.piclock.config.get('units')
        if isinstance(chosen, str) and chosen:
            return chosen
        return 'default'

    def merge(self, folder):
        if not os.path.isdir(folder):
            return
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.yaml'):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding='utf-8') as fh:
                part = yaml.safe_load(fh) or {}
            logger.debug('units from %s', path)
            sets = part.pop('sets', None)
            if sets:
                self._merge(sets, self.sets)
            self._merge(part, self.quantities)

    # ------------------------------------------------------------ using

    def unit(self, quantity, setName):
        """which unit of `quantity` the named set asks for.

        A set that does not mention it gets the quantity's own base, which
        is the only answer available when a plugin has added a quantity no
        set has heard of.
        """
        q = self.quantities.get(quantity)
        if q is None:
            raise SystemExit('\nunknown quantity %r.  Known: %s\n'
                             % (quantity, ', '.join(sorted(self.quantities))))
        chosen = (self.sets.get(setName) or self.sets.get('default') or {})
        return chosen.get(quantity, q['base'])

    def convert(self, quantity, frm, to, value):
        """through the base, so a quantity needs one entry per unit"""
        q = self.quantities[quantity]
        a, b = q['units'].get(frm), q['units'].get(to)
        for name, u in ((frm, a), (to, b)):
            if u is None:
                raise SystemExit('\nunknown unit %r for quantity %r.'
                                 '  Known: %s\n'
                                 % (name, quantity, ', '.join(sorted(q['units']))))
        base = (value - a.get('offset', 0)) / a.get('factor', 1)
        return base * b.get('factor', 1) + b.get('offset', 0)

    def measure(self, quantity, value, default=None):
        """what a config wrote, as a number in `quantity`'s base unit.

        The other way round from format(): that takes a number a provider
        gave us and shows it the way the set asks, this takes what somebody
        typed and gets a number out of it.  A bare one is already the base,
        so altitude: 1600 is 1600 meters; '5280ft' names a unit the
        quantity defines and is converted.  A set converts what is shown
        and never this, or choosing metric would move a mountain.

        Blank is `default`, which is how a setting says it was not given
        rather than saying zero.  Case matters, because the table's own
        names do - K is kelvin, and inHg is not inhg.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return default

        q = self.quantities.get(quantity)
        if q is None:
            raise SystemExit('\nunknown quantity %r.  Known: %s\n'
                             % (quantity, ', '.join(sorted(self.quantities))))

        # bool first: yaml reads yes and on as True, and True is an int
        if isinstance(value, bool):
            raise SystemExit('\ncannot read %r as %s\n' % (value, quantity))
        if isinstance(value, (int, float)):
            return float(value)

        found = MEASURE.match(str(value).strip())
        if found is None:
            raise SystemExit("\ncannot read %r as %s: give a number, or a"
                             " number with a unit as '900%s' is\n"
                             % (value, quantity, q['base']))

        number, unit = float(found.group(1)), found.group(2).strip()
        if not unit:
            return number
        return self.convert(quantity, unit, q['base'], number)

    def format(self, quantity, frm, value, setName=None, precision=None):
        """a value in `frm`, shown the way the set asks for it"""
        if value is None:
            return ''
        to = self.unit(quantity, setName)
        spec = self.quantities[quantity]['units'][to]

        if 'via' in spec:
            fn = VIA.get(spec['via'])
            if fn is None:
                raise SystemExit('\nunits: no function registered for via: %r\n'
                                 % spec['via'])
            return fn(self.convert(quantity, frm, self.quantities[quantity]['base'],
                                   value), to)

        out = self.convert(quantity, frm, to, value)
        if precision is None:
            precision = spec.get('precision', 1)
        return '%s%.*f%s' % (spec.get('prefix', ''), int(precision), out,
                             spec.get('suffix', ''))
