from .Provider import Provider


class Frames(Provider):
    """timestamped map tiles, animated by whatever draws them.

    Nothing here is weather.  Precipitation, cloud cover, satellite IR and
    sea ice all arrive the same way: tiles, each stamped with a time.
    """

    def frameCaption(self, timeSlot):
        """what to write over the frame for this time slot.

        A provider that knows more than the time - that this one is a
        nowcast rather than an observation, say - overrides this.
        """
        return "{0:%H:%M}".format(self.piclock.localtime(timeSlot))
