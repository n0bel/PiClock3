from .Plugin import Plugin


class Provider(Plugin):
    """supplies data and occupies no region.

    No theme reaches one, because a theme reaches a region and a provider
    has none.  One instance answers every widget that names it.
    """

    # what this service must be credited as.  It reaches the caption a map
    # carries and the corner of a forecast panel.  A service that needs no
    # credit says nothing and contributes nothing to the line.  A station
    # whose credit is its own id sets it in __init__ instead.
    attribution = ''
