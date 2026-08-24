import logging
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
