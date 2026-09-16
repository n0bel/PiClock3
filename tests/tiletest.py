"""Does a tile give each caller the attributes it asked for?

    python3 tests/tiletest.py

A source layer is decoded once and kept, and two styles on one clock can
want different attributes of the same tile: two maps labeled in different
languages, or - as the shipped `mapstyles.yaml` does - one style that
filters on `rank` beside one that does not.  Whoever asks first must not
decide what the second one gets, and the failure is silent when it does:
no error, just a filter comparing against a missing attribute and dropping
every label it should have kept.

The tile is built here rather than downloaded.  A real one is a third of a
megabyte of somebody else's data, under a license with its own attribution
terms, and it would go stale the next time their schema moved.  Three
features say what a case needs.

Needs PyQt5, because VectorTile builds a QPointF.  It opens no window.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from PiClock3.VectorTile import POINT, VectorTile      # noqa: E402

EXTENT = 4096


# ------------------------------------------------------- the wire format

def varint(number):
    out = bytearray()
    while True:
        byte = number & 0x7f
        number >>= 7
        if number:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def key(field, wire):
    return varint((field << 3) | wire)


def block(field, payload):
    """a length-delimited field"""
    return key(field, 2) + varint(len(payload)) + payload


def zigzag(number):
    return (abs(number) << 1) - 1 if number < 0 else number << 1


def point(x, y):
    """a geometry of one MoveTo, the command stream the spec describes"""
    return varint((1 << 3) | 1) + varint(zigzag(x)) + varint(zigzag(y))


def value(what):
    """one entry of a layer's value table"""
    if isinstance(what, int):
        return block(4, key(5, 0) + varint(what))       # uint64
    return block(4, block(1, what.encode('utf-8')))     # string


def feature(number, pairs, geometry, kind=POINT):
    body = key(1, 0) + varint(number)
    body += block(2, b''.join(varint(n) for n in pairs))
    body += key(3, 0) + varint(kind)
    body += block(4, geometry)
    return body


def layer(name, names, values, features, extent=EXTENT):
    body = block(1, name.encode('utf-8'))
    for one in features:
        body += block(2, one)
    for one in names:
        body += block(3, one.encode('utf-8'))
    for one in values:
        body += value(one)
    body += key(5, 0) + varint(extent)
    return body


def tile(layers):
    return b''.join(block(3, one) for one in layers)


# ----------------------------------------------------------- the fixture

# one place layer, three cities, each with a name in two languages and a
# rank.  `rank` is the attribute liberty's country labels filter on, which
# is what made this worth a test rather than an argument.
NAMES = ['name', 'name:en', 'name:de', 'rank']
VALUES = ['Munich', 'Munich', 'München',
          'Vienna', 'Vienna', 'Wien',
          'Zurich', 'Zurich', 'Zürich', 1, 2, 3]

WANT = {
    'Munich': {'name': 'Munich', 'name:en': 'Munich', 'name:de': 'München',
               'rank': 1},
    'Vienna': {'name': 'Vienna', 'name:en': 'Vienna', 'name:de': 'Wien',
               'rank': 2},
    'Zurich': {'name': 'Zurich', 'name:en': 'Zurich', 'name:de': 'Zürich',
               'rank': 3},
}


def fixture():
    """a tile of three places, built from the tables above"""
    features = []
    for i in range(3):
        base = i * 3
        pairs = [0, base, 1, base + 1, 2, base + 2, 3, 9 + i]
        features.append(feature(i + 1, pairs, point(100 * (i + 1), 200)))
    return tile([layer('place', NAMES, VALUES, features)])


def tags(features):
    """what came back, keyed by the name every case can rely on"""
    return {f.tags['name']: dict(f.tags) for f in features}


# ------------------------------------------------------------- the cases

def cases(data):
    """(name, how it went, what it found) for each thing asserted"""
    out = []

    # the fixture has to decode at all before anything else means much
    whole = tags(VectorTile(data, 512).layer('place'))
    out.append(('every attribute, nothing asked for',
                whole == WANT, sorted(whole)))

    # two styles, one tile: the English one asks first
    one = VectorTile(data, 512)
    english = tags(one.layer('place', {'name', 'name:en'}))
    german = tags(one.layer('place', {'name', 'name:de'}))

    out.append(('the first caller gets its own attributes',
                all(f.get('name:en') == WANT[n]['name:en']
                    and 'name:de' not in f for n, f in english.items()),
                sorted(english['Munich'])))

    out.append(('the second caller is not handed the first set',
                all(f.get('name:de') == WANT[n]['name:de']
                    and 'name:en' not in f for n, f in german.items()),
                sorted(german['Munich'])))

    # the country-label case: a filter reads an attribute the other style
    # never asked for, and a missing one compares as nothing at all
    two = VectorTile(data, 512)
    without = two.layer('place', {'name'})
    withrank = two.layer('place', {'name', 'rank'})
    out.append(('an attribute nobody asked for stays absent',
                all(f.tags.get('rank') is None for f in without),
                'rank absent'))
    out.append(('and is there for the caller that wants it',
                [f.tags.get('rank') for f in withrank] == [1, 2, 3],
                [f.tags.get('rank') for f in withrank]))

    # the same set twice is the cached answer, not a second walk
    three = VectorTile(data, 512)
    first = three.layer('place', {'name', 'rank'})
    again = three.layer('place', {'name', 'rank'})
    out.append(('the same set twice is decoded once',
                first is again, 'one entry' if first is again else 'two'))

    # and every set sees the same features, in the same order
    out.append(('every caller sees the same features',
                len(english) == len(german) == len(whole) == 3,
                '%d, %d, %d' % (len(english), len(german), len(whole))))

    return out


def main():
    data = fixture()
    failed = 0
    found = cases(data)
    for name, ok, said in found:
        if ok:
            print('  ok    %-46s %s' % (name, said))
        else:
            failed += 1
            print('  FAIL  %-46s %s' % (name, said))
    print('\n  %d cases, %d failed' % (len(found), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
