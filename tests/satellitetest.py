"""Does the satellite provider animate only the frames the index lists?

    python3 tests/satellitetest.py

LibreWXR answers a time it has no satellite frame for with its nearest
frame, so every time the provider hands out has to come from the index.

The index is built here rather than fetched, so the cases do not depend on
what the service has this hour.

Needs PyQt5, because a provider is a QObject.  It opens no window.
"""
import json
import os
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from PiClock3.LibreWXRSatellite import LibreWXRSatellite  # noqa: E402

HOUR = 3600
NOW = int(time.time()) // HOUR * HOUR
# ends an hour before now, so a list computed from the clock includes an
# hour the index does not
LISTED = [NOW - (i + 1) * HOUR for i in reversed(range(12))]


def index(times):
    return json.dumps({
        'host': 'https://api.librewxr.net',
        'radar': {'past': [{'time': NOW - 600, 'path': '/v2/radar/x'}]},
        'satellite': {'infrared': [
            {'time': t, 'path': '/v2/satellite/%d' % t} for t in times]},
    }).encode('utf-8')


def provider(times):
    piclock = SimpleNamespace(pluginData={'satellite': {}})
    sat = LibreWXRSatellite(piclock, 'satellite',
                            {'plugin': 'PiClock3.LibreWXRSatellite'})
    sat.lastget = time.time()       # no fetch while the cases run
    sat.gotIndex(None, index(times), None)
    return sat


def urls(sat, timeSlot):
    """the tile urls a frame would fetch, without fetching them"""
    # the package's class shadows the module's name
    module = sys.modules['PiClock3.LibreWXRSatellite.LibreWXRSatellite']
    made = []

    def fetcher(center, zoom, width, height, tileurl, callback, params):
        made.append(tileurl(zoom, 3, 5))
    real, module.TileFetcher = module.TileFetcher, fetcher
    try:
        view = SimpleNamespace(center=None, zoom=4,
                               rect=SimpleNamespace(width=lambda: 256,
                                                    height=lambda: 256))
        sat.getFramePixmap(timeSlot, view, {}, None)
    finally:
        module.TileFetcher = real
    return made


def cases():
    sat = provider(LISTED)
    yield ('the newest seven are the newest seven listed',
           sat.frameTimes(7) == LISTED[-7:], sat.frameTimes(7))
    yield ('asking for more than exist gives what exists',
           sat.frameTimes(50) == LISTED, len(sat.frameTimes(50)))
    yield ('every time handed out is one the index lists',
           set(sat.frameTimes(50)) <= set(LISTED), sat.frameTimes(50))
    yield ('radar in the same index is not taken for satellite',
           NOW - 600 not in sat.frameTimes(50), sat.frameTimes(50))

    future = provider(LISTED + [NOW + HOUR])
    yield ('a listed time still to come is not animated',
           NOW + HOUR not in future.frameTimes(50), future.frameTimes(50))

    made = urls(sat, LISTED[-1])
    yield ('a listed frame fetches from its own path',
           made == ['https://api.librewxr.net/v2/satellite/%d'
                    '/256/4/3/5/0/0_0.png' % LISTED[-1]], made)

    made = urls(sat, NOW - 1800)
    yield ('a time between two frames fetches nothing',
           made == [], made)

    empty = provider([])
    yield ('an index with no satellite frames animates nothing',
           empty.frameTimes(7) == [], empty.frameTimes(7))


def main():
    failed = 0
    found = list(cases())
    for name, ok, got in found:
        if ok:
            print('  ok    %s' % name)
        else:
            failed += 1
            print('  FAIL  %-52s got %r' % (name, got))
    print('\n  %d cases, %d failed' % (len(found), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
