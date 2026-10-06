"""What the air feels like, from the dew point or from the humidity.

    python3 tests/feelstest.py

The answers are checked against the US National Weather Service's own
heat index and wind chill tables, which give whole degrees Fahrenheit, so
each is allowed half a degree either way.  The dew point and the humidity
are two ways of saying one thing, so dewPoint() and humidity() must undo
each other, both feels-like functions must agree, and feelsLike() must
stay the dew point one for the plugins that call it.

Needs PyQt5, because Weather is a provider and a provider is a QObject.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.Weather import Weather  # noqa: E402

MPH = 1.609344


def celsius(f):
    return (f - 32.0) / 1.8


def fahrenheit(c):
    return c * 1.8 + 32.0


# (name, temp F, humidity %, wind mph, what the NWS table says, F)
TABLE = [
    ('heat index, 90F at 60%', 90, 60, 0, 100),
    ('heat index, 100F at 40%', 100, 40, 0, 109),
    ('heat index, 86F at 90%', 86, 90, 0, 105),
    ('wind chill, 0F in 15 mph', 0, 50, 15, -19),
    ('wind chill, -10F in 30 mph', -10, 50, 30, -39),
    ('wind chill, 30F in 10 mph', 30, 50, 10, 21),
    ('neither, 70F', 70, 50, 10, 70),
]


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

    for name, t, h, w, want in TABLE:
        got = fahrenheit(
            Weather.feelsLikeFromHumidity(celsius(t), h, w * MPH))
        check(name, abs(got - want) <= 0.5,
              'got %.2f, wanted %d' % (got, want))

    # the same air, said with a dew point.  Not at exactly 40%, where the
    # heat index starts: the dew point turns back into 39.9999999%
    for name, t, h, w, want in TABLE:
        if h == 40:
            continue
        temp = celsius(t)
        fromHumidity = Weather.feelsLikeFromHumidity(temp, h, w * MPH)
        dew = Weather.feelsLikeFromDewpoint(
            temp, Weather.dewPoint(temp, h), w * MPH)
        check('the dew point agrees: ' + name,
              abs(dew - fromHumidity) < 1e-6,
              '%.6f from the dew point, %.6f from the humidity'
              % (dew, fromHumidity))

    for t, h in ((-10, 80), (0, 50), (20, 52), (35, 15), (30, 100)):
        back = Weather.humidity(t, Weather.dewPoint(t, h))
        check('dewPoint and humidity undo each other, %dC at %d%%' % (t, h),
              abs(back - h) < 1e-6, 'came back as %.6f' % back)

    check('feelsLike is feelsLikeFromDewpoint',
          Weather.feelsLike is Weather.feelsLikeFromDewpoint,
          'they are different functions')
    check('a missing humidity is no answer',
          Weather.feelsLikeFromHumidity(20, None, 10) is None, 'an answer')
    check('a missing dew point is no answer',
          Weather.feelsLikeFromDewpoint(20, None, 10) is None, 'an answer')
    check('a missing wind is no answer',
          Weather.feelsLikeFromHumidity(20, 50, None) is None, 'an answer')

    print('%d cases, %d failed' % (checked, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
