import datetime
import logging

from PyQt5.QtCore import QTimer

from ..Widget import Widget

logger = logging.getLogger(__name__)


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Date(Widget):

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.timer = None
        self.lastDay = -1
        self.format = None
        self.ordinal = {}

    def start(self):
        # the language's own line, unless a config said otherwise: the
        # default in config.yaml is {language.date-format}, so which one
        # arrives here is the merge's business rather than this method's
        self.format = self.strftimePortableFormat(
            self.piclock.expand(self.config['format']))
        self.ordinal = self.piclock.languages.setting('date-ordinal') or {}
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

        sup = self.ordinal.get(now.day, self.ordinal.get('default', ''))
        self.pluginData.sup = sup
        self.pluginData.now = now

        # the two tokens first: expand() reads anything in braces as a name
        # to look up, and would take these out before they could be filled.
        # Then expand, so a {plugin-data.now:%A} template still works, and
        # strftime last for the bare directives.
        text = self.format.replace('{day}', str(now.day)).replace('{sup}', sup)
        self.region.setText(now.strftime(self.piclock.expand(text)))
