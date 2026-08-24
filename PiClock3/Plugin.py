import logging
logger = logging.getLogger(__name__)

from PyQt5.QtCore import (QObject)

class Plugin(QObject):

    def __init__(self, piclock, name, config):
        super().__init__()
        self.name = name
        self.piclock = piclock
        self.config = config
        self.module = config.module
        self.pluginData = piclock.pluginData[name]
        if 'region' in config:
            self.regionName = config['region']
            self.region = piclock.regions[self.regionName]

    def start(self):
        return

    def pageChange(self):
        return

    def expand(self, s):
        return self.piclock.expand(s)
