import re
import sys

from PyQt5.QtCore import QObject

DASH = re.compile(r'%-([a-zA-Z])')
WINDOWS = sys.platform == 'win32'


class Plugin(QObject):
    """what the core loads, in the role one of its subclasses names.

    Here is what holds whatever that role is: the config the instance was
    built from, the clock it belongs to, and the calls the core makes on it.
    What only a widget can use, or only a provider, lives with that role.
    """

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

    @staticmethod
    def strftimePortableFormat(fmt):
        """a strftime string this machine will accept.

        glibc drops a leading zero with %-d, the Windows CRT with %#d, and
        Windows raises on %-d rather than ignoring it.  A config travels
        between them, so it is written the glibc way and turned round here.

        Call it in start() and keep what it returns: the answer cannot
        change while the clock runs, and the widgets that draw a time
        redraw every second.
        """
        return DASH.sub(r'%#\1', fmt) if WINDOWS else fmt

    def expand(self, s):
        return self.piclock.expand(s)
