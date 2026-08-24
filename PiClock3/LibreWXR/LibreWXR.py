import datetime
import json
import logging
import time

from ..Plugin import Plugin
from ..Tiler import TileFetcher
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

INDEX_REFRESH = 300

# facts about the service, not settings: there is no other index this plugin
# could sensibly be pointed at, and the attribution names who supplied the
# data rather than whatever host the url happened to have
INDEX = 'https://api.librewxr.net/public/weather-maps.json'
ATTRIBUTION = 'LibreWXR'


class LibreWXR(Plugin):
    """LibreWXR's radar tiles.

    The index is the same shape RainViewer serves, and RainViewer has a
    plugin of its own.  The reading code is duplicated on purpose - neither
    service owes the other compatibility, and LibreWXR already returns a
    colorSchemes key and populates nowcast where RainViewer does neither.
    """

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.host = ''
        self.frames = {}
        self.order = []
        self.lastget = 0

    def start(self):
        self.getIndex()

    def pageChange(self):
        return

    def getIndex(self):
        self.lastget = time.time()
        WebGet(INDEX, self.gotIndex)

    def gotIndex(self, error, data, params):
        if error:
            logger.warning("%s index %s failed: %s", ATTRIBUTION, INDEX, error)
            return
        try:
            index = json.loads(bytes(data).decode('utf-8'))
        except ValueError:
            logger.warning("%s index %s is not json", ATTRIBUTION, INDEX)
            return
        self.host = index['host']
        radar = index.get('radar', {})
        frames = radar.get('past', []) + radar.get('nowcast', [])
        self.frames = {int(f['time']): f['path'] for f in frames}
        self.order = sorted(self.frames)
        logger.info("%s index: %d frames, newest %s", ATTRIBUTION,
                    len(self.order),
                    time.asctime(time.localtime(self.order[-1]))
                    if self.order else 'none')

    def freshen(self):
        if time.time() > self.lastget + INDEX_REFRESH:
            self.getIndex()

    def frameTimes(self, count):
        self.freshen()
        past = [t for t in self.order if t <= time.time()]
        return past[-count:]

    def tail(self, layerConfig):
        def setting(name, default):
            if name in layerConfig:
                return layerConfig[name]
            if name in self.config:
                return self.config[name]
            return default
        color = setting('color', 6)
        smooth = setting('smooth', 1)
        snow = setting('snow', 1)
        return "/256/%%d/%%d/%%d/%d/%d_%d.png" % (color, smooth, snow)

    def getFramePixmap(self, timeSlot, view, layerConfig, callback):
        self.freshen()
        path = self.frames.get(timeSlot)
        if path is None:
            logger.debug("no radar frame for %s",
                         time.asctime(time.localtime(timeSlot)))
            return
        tail = self.host + path + self.tail(layerConfig)

        def tileurl(z, x, y):
            return tail % (z, x, y)

        caption = "{0:%H:%M} ".format(
            datetime.datetime.fromtimestamp(timeSlot)) + ATTRIBUTION
        TileFetcher(view.center, view.zoom,
                    view.rect.width(), view.rect.height(),
                    tileurl, callback, caption=caption, params=timeSlot)
