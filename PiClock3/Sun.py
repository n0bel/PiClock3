"""Where the sun is, for anything that needs to know.

Not weather and not a role: a widget works out its own sunrise from a
latitude, and a weather source picks a day or night icon from the same
sums.  Both ask here.

Everything takes and returns times and booleans.  Nothing formats.
"""

from astral import LocationInfo
from astral.sun import dawn, dusk, noon, sunrise, sunset

EVENTS = (('dawn', dawn), ('sunrise', sunrise), ('noon', noon),
          ('sunset', sunset), ('dusk', dusk))


def sunTimes(day, latitude, longitude, zone):
    """what the sun does that day, each event asked for on its own.

    astral offers them as one bundle, but dawn and dusk are the sun six
    degrees under and never happen through a northern summer - a bundle
    loses a sunrise that is perfectly well defined along with them.
    Whatever the day genuinely has is what comes back.
    """
    here = LocationInfo('here', 'here', zone, latitude, longitude)
    found = {}
    for name, fn in EVENTS:
        try:
            found[name] = fn(here.observer, day, tzinfo=here.timezone)
        except ValueError:
            continue
    return found


def daytime(when, latitude, longitude, zone):
    """is the sun up at `when`, where the clock is pointed.

    The sun rather than a rule about six o'clock, which is wrong by hours in
    summer and by half the year above the arctic circle.  A place where the
    sun does not rise or set that day answers by hemisphere and season.
    """
    try:
        s = sunTimes(when.date(), latitude, longitude, zone)
    except Exception:
        return 6 <= when.hour < 18
    up, down = s.get('sunrise'), s.get('sunset')
    if up is None or down is None:
        # polar day or polar night: no sunrise to compare against
        summer = 4 <= when.month <= 9
        return summer if float(latitude) >= 0 else not summer
    if down < up:
        # far enough north for the sun to set after midnight, so the dark
        # of this day is its two ends rather than its middle
        return when <= down or up <= when
    return up <= when <= down
