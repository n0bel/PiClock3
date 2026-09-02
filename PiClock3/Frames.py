from .Provider import Provider


class Frames(Provider):
    """timestamped map tiles, animated by whatever draws them.

    Nothing here is weather.  Precipitation, cloud cover, satellite IR and
    sea ice all arrive the same way: tiles, each stamped with a time.
    """

    def frameTimes(self, count):
        """the newest `count` time slots, oldest first.

        The caller animates them in the order given, so the last one is the
        most recent.  A slot is whatever this service stamps its tiles
        with, and only this provider need understand it.
        """
        raise NotImplementedError(
            '%s: %s supplies frames and has no frameTimes'
            % (self.name, type(self).__name__))

    def getFramePixmap(self, timeSlot, view, layerConfig, callback):
        """fetch one slot's tiles for `view` and answer
        callback(pixmap, timeSlot).

        The slot comes back so the caller can file a frame that arrives out
        of order, which they do: the tiles go out at once and land as they
        land.
        """
        raise NotImplementedError(
            '%s: %s supplies frames and has no getFramePixmap'
            % (self.name, type(self).__name__))
