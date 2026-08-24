import time

from ..Plugin import Plugin
from ..Tiler import TileFetcher

# facts about the service, not settings
HOST = 'https://api.librewxr.net'
ATTRIBUTION = 'LibreWXR'

# Every frame is named after its own timestamp on a ten minute grid, so the
# frame list is arithmetic and needs no index.  The current slot always
# answers: until its radar lands the service serves its nowcast for that
# minute, and a slot outside the window 404s.
INTERVAL = 600


class LibreWXR(Plugin):
    """LibreWXR's radar tiles.

    RainViewer has a plugin of its own, and the two have grown apart: this
    one needs no index at all, because a frame is named after its own
    timestamp on a fixed grid, while RainViewer names each frame with an
    opaque hash that can only be learned by fetching one.  Keeping them
    separate is what lets this one be arithmetic.
    """

    def start(self):
        return

    def pageChange(self):
        return

    def frameTimes(self, count):
        """the newest `count` frames, oldest first.

        The caller animates them in the order given, so the last one is the
        most recent - the same order the index-driven providers return.
        """
        newest = (int(time.time()) // INTERVAL) * INTERVAL
        return [newest - i * INTERVAL
                for i in reversed(range(count))]

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
        tail = "%s/v2/radar/%d%s" % (HOST, timeSlot, self.tail(layerConfig))

        def tileurl(z, x, y):
            return tail % (z, x, y)

        # the radar frame is stamped in the clock's zone, so a London
        # config reads London time on the radar too
        caption = "{0:%H:%M} ".format(
            self.piclock.localtime(timeSlot)) + ATTRIBUTION
        TileFetcher(view.center, view.zoom,
                    view.rect.width(), view.rect.height(),
                    tileurl, callback, caption=caption, params=timeSlot)
