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

    def expand(self, s):
        return self.piclock.expand(s)
