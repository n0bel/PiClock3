import json
import logging
import time

from ..Frames import Frames
from ..Tiler import TileFetcher
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

INDEX_REFRESH = 300

# facts about the service, not settings
INDEX = 'https://api.librewxr.net/public/weather-maps.json'

# satellite tiles take no palette, smoothing or snow
TAIL = '/256/%d/%d/%d/0/0_0.png'


class LibreWXRSatellite(Frames):
    """LibreWXR's infrared satellite tiles.

    Frame times come from the index: the service answers a time it has no
    frame for with its nearest frame, so a computed time can repeat another
    hour.
    """

    attribution = 'LibreWXR'

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
            logger.warning("%s index %s failed: %s",
                           self.attribution, INDEX, error)
            return
        try:
            index = json.loads(bytes(data).decode('utf-8'))
        except ValueError:
            logger.warning("%s index %s is not json", self.attribution, INDEX)
            return
        self.host = index['host']
        frames = index.get('satellite', {}).get('infrared', [])
        self.frames = {int(f['time']): f['path'] for f in frames}
        self.order = sorted(self.frames)
        logger.info("%s satellite index: %d frames, newest %s",
                    self.attribution, len(self.order),
                    time.asctime(time.localtime(self.order[-1]))
                    if self.order else 'none')

    def freshen(self):
        if time.time() > self.lastget + INDEX_REFRESH:
            self.getIndex()

    def frameTimes(self, count):
        self.freshen()
        past = [t for t in self.order if t <= time.time()]
        return past[-count:]

    def getFramePixmap(self, timeSlot, view, layerConfig, callback):
        self.freshen()
        path = self.frames.get(timeSlot)
        if path is None:
            logger.debug("no satellite frame for %s",
                         time.asctime(time.localtime(timeSlot)))
            return
        tail = self.host + path + TAIL

        def tileurl(z, x, y):
            return tail % (z, x, y)

        TileFetcher(view.center, view.zoom,
                    view.rect.width(), view.rect.height(),
                    tileurl, callback, params=timeSlot)
