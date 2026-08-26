import datetime
import logging
import re
import sys

from PyQt5.QtCore import QTimer

from ..Plugin import Plugin

logger = logging.getLogger(__name__)

# glibc drops a leading zero with %-d, the Windows CRT with %#d, and Windows
# raises on %-d rather than ignoring it.  A language file travels between
# them, so it is written the glibc way and turned round here.
DASH = re.compile(r'%-([a-zA-Z])')


def portable(fmt):
    """a strftime string the machine this is running on will accept"""
    return DASH.sub(r'%#\1', fmt) if sys.platform == 'win32' else fmt


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Date(Plugin):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.timer = None
        self.lastDay = -1

    def start(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.doDate)
        self.timer.start(1000)

    def pageChange(self):
        return

    def doDate(self):
        now = self.piclock.now()
        if now.day != self.lastDay:
            self.lastDay = now.day
        else:
            return

        ordinal = self.piclock.languages.setting('date-ordinal') or {}
        sup = ordinal.get(now.day, ordinal.get('default', ''))
        self.pluginData.sup = sup
        self.pluginData.now = now

        # the two tokens first: expand() reads anything in braces as a name
        # to look up, and would take these out before they could be filled.
        # {day} rather than %-d because that is a ValueError on Windows.
        # Then expand, so a {plugin-data.now:%A} template still works, and
        # strftime last for the bare directives.
        fmt = (self.config.get('format')
               or self.piclock.languages.setting('date-format',
                                                 '%A %B {day} %Y'))
        text = fmt.replace('{day}', str(now.day)).replace('{sup}', sup)
        self.region.setText(now.strftime(portable(self.piclock.expand(text))))
