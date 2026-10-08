from .Plugin import Plugin


class Service(Plugin):
    """runs on its own: draws in no region and answers nobody.

    Buttons on the gpio pins are one - what it does is call the clock,
    `self.piclock.nextPage(1)`, rather than be called.  Services start after
    every widget, so whatever they reach for is already there.
    """
