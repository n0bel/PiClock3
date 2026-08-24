import logging
import os

logger = logging.getLogger(__name__)

from PyQt5.QtCore import (QObject)

class Plugin(QObject):

    def __init__(self, piclock, name, config):
        super().__init__()
        self.name = name
        self.piclock = piclock
        self.config = config
        self.plugin = config['plugin'] if 'plugin' in config else None
        self.pluginData = piclock.pluginData[name]
        if 'region' in config:
            self.regionName = config['region']
            # always a list; a plugin that only understands one cell uses
            # self.region and ignores the rest
            self.regions = piclock.regionList(self.regionName)
            self.region = self.regions[0]

    def start(self):
        return

    def pageChange(self):
        return

    def setting(self, name, provider, default):
        """this instance, then the provider it is asking, then the default.

        The provider tier is what lets a service that knows its own coverage
        supply a sensible center or zoom for any widget that does not say.
        """
        if name in self.config:
            return self.config[name]
        if provider is not None and name in provider.config:
            return provider.config[name]
        return default

    def expand(self, s):
        return self.piclock.expand(s)

    def icon(self, name, folder=None):
        """the file for a weather icon, yours before the shipped one.

        The name already says day or night: whatever supplied it knew
        whether the sun was up, which is not something a widget can work
        out from a picture.
        """
        folder = folder or self.config.get('icons-folder') or 'icons-lightblue'
        for base in ('icons', os.path.join('PiClock3', 'icons')):
            path = os.path.join(base, folder, name + '.png')
            if os.path.isfile(path):
                return path
        logger.warning('no icon %s in %s', name, folder)
        return ''

    def units(self, quantity, frm, value):
        """a value in `frm`, shown the way this instance asks for it.

        The set is this instance's units: if it has one, otherwise the
        clock's.  Precision is the table's unless a precision: block on
        the plugin or the instance says otherwise - a narrow column wants
        whole degrees where a big readout wants a tenth.
        """
        return self.piclock.units.format(
            quantity, frm, value,
            setName=self.unitSet(),
            precision=self.precision(quantity))

    def unitSet(self):
        chosen = self.config.get('units')
        if isinstance(chosen, str) and chosen:
            return chosen
        return self.piclock.units.setName()

    def precision(self, quantity):
        want = self.config.get('precision')
        if isinstance(want, dict) and quantity in want:
            return want[quantity]
        return None
