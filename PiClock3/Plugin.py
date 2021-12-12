import logging
logger = logging.getLogger(__name__)


class Plugin(object):

    def __init__(self, piclock, name, config):
        super().__init__()
        self.name = name
        self.piclock = piclock
        self.config = config
        self.module = config.module
        self.pluginData = piclock.pluginData[name]
        if 'block' in config:
            self.blockName = config['block']
            self.block = piclock.blocks[self.blockName]

    def start(self):
        return

    def pageChange(self):
        return

    def expand(self, s):
        return self.piclock.expand(s)
