"""Does a weather provider ask again soon after a failure?

    python3 tests/retrytest.py

A refresh is half an hour, so a clock that starts while a service is slow
would otherwise show nothing for that long.  Each provider asks again a
minute after a request fails, Tomorrow.io five, since its free plan
allows 25 requests an hour; a refused key is left for the refresh, since
it will be refused again.  The requests are stand-ins that answer however
each case says, so this needs no network.

Needs PyQt5, because a retry is a QTimer and a provider is a QObject.
"""
import importlib
import os
import sys
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PyQt5.QtCore import QCoreApplication  # noqa: E402
from PyQt5.QtNetwork import QNetworkReply  # noqa: E402

app = QCoreApplication(sys.argv[:1])

from PiClock3.DottedDict import DottedDict  # noqa: E402

TIMEOUT = QNetworkReply.OperationCanceledError
REFUSED = QNetworkReply.AuthenticationRequiredError

# requests made, newest last, as (url, callback)
asked = []


def fakeWebGet(url, callback):
    asked.append((url, callback))


def dotted(values):
    out = DottedDict()
    for k, v in values.items():
        out[k] = dotted(v) if isinstance(v, dict) else v
    return out


def provider(name, settings):
    # by name, because each package lifts its class to PiClock3.<Name>, and
    # an import of the module through it finds the class
    module = importlib.import_module('PiClock3.%s.%s' % (name, name))
    module.WebGet = fakeWebGet
    piclock = SimpleNamespace(
        pluginData={name: {}}, expand=lambda s: s,
        timezone=lambda: SimpleNamespace(key='America/Chicago'))
    p = getattr(module, name)(piclock, name, dotted(settings))
    del asked[:]
    p.start()
    return p


def waiting(p, getter):
    timer = p.__dict__.get('retryTimers', {}).get(getter)
    return timer.interval() if timer is not None and timer.isActive() else 0


PLACE = {'latitude': '45', 'longitude': '-93'}
KEYED = {'apikey': 'a-key', 'refresh': 30, 'forecast-days': 6,
         'location': PLACE}


def main():
    failed = checked = 0

    def check(name, ok, said):
        nonlocal failed, checked
        checked += 1
        if ok:
            print('ok   %s' % name)
        else:
            failed += 1
            print('FAIL %s: %s' % (name, said))

    # Open-Meteo: one request
    p = provider('OpenMeteo', {'refresh': 30, 'forecast-days': 9,
                               'location': PLACE})
    asked[-1][1](TIMEOUT, None, None)
    check('Open-Meteo: a timeout asks again in a minute',
          waiting(p, p.getForecast) == 60000,
          'waiting %d ms' % waiting(p, p.getForecast))
    p.retryTimers[p.getForecast].timeout.emit()
    asked[-1][1](None, b'not json', None)
    check('Open-Meteo: an answer that is not json asks again too',
          waiting(p, p.getForecast) == 60000, 'not waiting')
    p.retryTimers[p.getForecast].timeout.emit()
    asked[-1][1](None, b'{"current": {}, "hourly": {}, "daily": {}}', None)
    check('Open-Meteo: an answer stops the asking',
          waiting(p, p.getForecast) == 0, 'still waiting')
    check('Open-Meteo: the refresh carries on',
          p.timer.isActive() and p.timer.interval() == 30 * 60000,
          'refresh every %d ms' % p.timer.interval())

    # Metar: one request
    p = provider('Metar', {'METAR': 'KMSP', 'refresh': 10})
    asked[-1][1](TIMEOUT, None, None)
    check('Metar: a timeout asks again in a minute',
          waiting(p, p.getMetar) == 60000,
          'waiting %d ms' % waiting(p, p.getMetar))
    p.retryTimers[p.getMetar].timeout.emit()
    check('Metar: and does', len(asked) == 2, '%d requests' % len(asked))

    # OpenWeatherMap and Tomorrow.io: two requests each, asked again apart
    for name, seconds in (('OpenWeatherMap', 60), ('TomorrowIO', 300)):
        p = provider(name, KEYED)
        current, forecast = asked[0][1], asked[1][1]
        forecast(TIMEOUT, None, None)
        check('%s: a timed-out forecast asks again in %ds' % (name, seconds),
              waiting(p, p.getForecast) == seconds * 1000,
              'waiting %d ms' % waiting(p, p.getForecast))
        check('%s: and leaves the current conditions alone' % name,
              waiting(p, p.getCurrent) == 0, 'conditions waiting too')
        current(REFUSED, None, None)
        check('%s: a refused key waits for the refresh' % name,
              waiting(p, p.getCurrent) == 0, 'asking again anyway')

    print('%d cases, %d failed' % (checked, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
