"""Enough of the Mapbox Vector Tile format to walk a tile.

MVT is a protobuf, and this reads the wire format by hand.  Three message
shapes, all small, against a dependency a Pi would have to build - and the
hand-written one can do the thing that makes this affordable at all, which
is to decode a source layer once however many times a style names it.

Version 2.1, https://github.com/mapbox/vector-tile-spec:

    Tile    { repeated Layer layers = 3 }
    Layer   { name = 1, features = 2, keys = 3, values = 4, extent = 5 }
    Feature { id = 1, tags = 2 packed, type = 3, geometry = 4 packed }

Geometry is a command stream rather than a list of coordinates: an integer
carrying a command and a repeat count, then that many zigzag varint pairs,
each one a delta from the point before it.

**Decode a source layer once.**  Liberty names `transportation` in 61 of
its 111 style layers, and decoding per style layer re-walks those varints
61 times.  Measured under cProfile on a zoom 9 tile of Minneapolis: 2.17s
per view when it did, 0.72s when it did not.  That is the difference
between this being usable and not, so `layer()` caches and the caller is
expected to ask for a name as often as it likes.

Not read, deliberately: a feature's id, and float and double attribute
values.  Neither OpenMapTiles nor Shortbread carries one, and a value this
does not understand answers None rather than losing the tile.
"""
import logging

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPolygonF

logger = logging.getLogger(__name__)

# geometry types, as the spec numbers them
POINT, LINESTRING, POLYGON = 1, 2, 3

# and the three commands a geometry is built from
MOVE_TO, LINE_TO, CLOSE_PATH = 1, 2, 7

# protobuf wire types: what follows a field number
VARINT, FIXED64, LENGTH, FIXED32 = 0, 1, 2, 5

# a tile's coordinates run 0..extent, and every schema in the wild says
# 4096.  A layer that says otherwise is believed rather than assumed.
DEFAULT_EXTENT = 4096


class Feature():
    """one thing on the map, with its attributes and its shape.

    `rings` is what the shape is drawn from, already in pixels: a list of
    QPointF for a point, and of QPolygonF for anything else.  A polygon's
    exterior rings and holes are all in that one list, undistinguished,
    because the fill rule sorts them out and classifying them would cost
    a signed area per ring for nothing.

    **The shape is decoded when it is asked for, and not before.**  A
    style filters on the attributes and most features fail: a trimmed
    style keeps four road classes out of a dozen, and a place label is
    decided by a zoom the feature never reaches.  Walking the geometry of
    a feature nobody draws was the single largest cost on a Pi Zero, so
    the bytes are kept and read at the first use, once.
    """

    __slots__ = ('type', 'tags', '_at', '_rings', '_bounds')

    def __init__(self, kind, tags, at):
        self.type = kind
        self.tags = tags
        self._at = at              # (data, start, end, scale, step)
        self._rings = None
        self._bounds = None

    @property
    def bounds(self):
        """(left, top, right, bottom) in pixels, without building it.

        The deltas are read and added up and nothing is constructed, so
        this costs about a tenth of what the shape costs - which is what
        makes it worth asking before deciding to draw something.  A tile
        is 512 pixels and a radar shows perhaps a third of one, so most
        of what a tile carries is off screen.
        """
        if self._bounds is None:
            self._bounds = _extent(*self._at[:4])
        return self._bounds

    @property
    def rings(self):
        if self._rings is None:
            self._rings = _geometry(*self._at, kind=self.type)
        return self._rings

    def __repr__(self):
        return 'Feature(%d, %r)' % (self.type, self.tags)


class VectorTile():
    """one .pbf, indexed by source layer name.

    Nothing is decoded until a layer is asked for, and a layer is decoded
    once.  A style that names a layer the tile does not carry gets an
    empty list, which is ordinary: a tile of open water has no buildings.
    """

    def __init__(self, data, size=512):
        """`size` is how many pixels wide the tile will be drawn"""
        self.data = bytes(data)
        self.size = float(size)
        self.spans = {}          # layer name -> (start, end) in self.data
        self.decoded = {}        # layer name -> [Feature, ...]
        self._index()

    def names(self):
        """every source layer the tile carries"""
        return list(self.spans)

    def layer(self, name, keys=None):
        """the features of one source layer, decoded at most once.

        `keys` is the attributes anything is going to read, or None for
        all of them.  A place in OpenMapTiles carries its name in about
        eighty languages and a style asks for four, so building the other
        seventy-six into a dict is most of what a label costs.  The
        answer is cached under the name, so every caller has to ask for
        the same set - which MapStyle does, by taking the union across
        the style before it draws anything.
        """
        if name not in self.decoded:
            span = self.spans.get(name)
            self.decoded[name] = ([] if span is None
                                  else self._features(span[0], span[1], keys))
        return self.decoded[name]

    # -------------------------------------------------------- wire format

    def _index(self):
        """find each layer's bytes, without decoding any of them"""
        data, pos, end = self.data, 0, len(self.data)
        while pos < end:
            key, pos = _varint(data, pos)
            field, wire = key >> 3, key & 7
            if field == 3 and wire == LENGTH:
                size, pos = _varint(data, pos)
                name = self._name(pos, pos + size)
                if name is not None:
                    self.spans[name] = (pos, pos + size)
                pos += size
            else:
                pos = _skip(data, pos, wire)

    def _name(self, pos, end):
        """a layer's name = 1, read without walking its features"""
        data = self.data
        while pos < end:
            key, pos = _varint(data, pos)
            field, wire = key >> 3, key & 7
            if field == 1 and wire == LENGTH:
                size, pos = _varint(data, pos)
                return data[pos:pos + size].decode('utf-8', 'replace')
            pos = _skip(data, pos, wire)
        return None

    def _features(self, pos, end, keys=None):
        """one layer: its keys and values, then its features"""
        data = self.data
        names, values, extent, at = [], [], DEFAULT_EXTENT, []
        while pos < end:
            key, pos = _varint(data, pos)
            field, wire = key >> 3, key & 7
            if field == 3 and wire == LENGTH:            # keys
                size, pos = _varint(data, pos)
                name = data[pos:pos + size].decode('utf-8', 'replace')
                # a name nobody reads becomes None, and _tags drops the
                # pair rather than building it
                names.append(name if keys is None or name in keys else None)
                pos += size
            elif field == 4 and wire == LENGTH:          # values
                size, pos = _varint(data, pos)
                values.append(_value(data, pos, pos + size))
                pos += size
            elif field == 5 and wire == VARINT:          # extent
                extent, pos = _varint(data, pos)
            elif field == 2 and wire == LENGTH:          # a feature
                size, pos = _varint(data, pos)
                at.append((pos, pos + size))
                pos += size
            else:
                pos = _skip(data, pos, wire)

        # the features are read last because a key or a value may follow
        # them in the message, and a tag is an index into both
        extent = extent or DEFAULT_EXTENT
        scale = self.size / extent
        # how far apart two points have to be, in the tile's own units,
        # to be worth keeping: half of what one screen pixel covers
        step = max(1, int(extent / max(1.0, self.size * 2)))
        out = []
        for start, stop in at:
            found = self._feature(start, stop, names, values, scale,
                                  step)
            if found is not None:
                out.append(found)
        return out

    def _feature(self, pos, end, names, values, scale, step):
        data = self.data
        kind, tags, at = 0, {}, None
        while pos < end:
            key, pos = _varint(data, pos)
            field, wire = key >> 3, key & 7
            if field == 2 and wire == LENGTH:            # tags, packed
                size, pos = _varint(data, pos)
                tags = _tags(data, pos, pos + size, names, values)
                pos += size
            elif field == 3 and wire == VARINT:          # geometry type
                kind, pos = _varint(data, pos)
            elif field == 4 and wire == LENGTH:          # geometry, packed
                size, pos = _varint(data, pos)
                at = (data, pos, pos + size, scale, step)
                pos += size
            else:
                pos = _skip(data, pos, wire)
        if at is None:
            return None
        return Feature(kind, tags, at)


def _extent(data, pos, end, scale):
    """how far a geometry reaches, in pixels, building nothing.

    The same walk _geometry does with the QPointF left out.  On a Pi Zero
    a QPointF costs about eighty microseconds through the bindings and
    reading a delta costs about ten, so answering "is this on screen"
    before answering "what shape is it" is most of what makes a vector
    map affordable there.
    """
    x = y = 0
    left = top = 1 << 30
    right = bottom = -(1 << 30)
    while pos < end:
        header, pos = _varint(data, pos)
        command, count = header & 7, header >> 3
        if command == CLOSE_PATH:
            continue
        for _ in range(count):
            dx, pos = _varint(data, pos)
            dy, pos = _varint(data, pos)
            x += (dx >> 1) ^ -(dx & 1)
            y += (dy >> 1) ^ -(dy & 1)
            if x < left:
                left = x
            if x > right:
                right = x
            if y < top:
                top = y
            if y > bottom:
                bottom = y
    if right < left:
        return (0.0, 0.0, -1.0, -1.0)          # nothing at all
    return (left * scale, top * scale, right * scale, bottom * scale)


def _varint(data, pos):
    """a base-128 varint, and where it ended"""
    result = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7f) << shift
        if byte < 0x80:
            return result, pos
        shift += 7


def _skip(data, pos, wire):
    """past a field this does not read"""
    if wire == VARINT:
        while data[pos] >= 0x80:
            pos += 1
        return pos + 1
    if wire == LENGTH:
        size, pos = _varint(data, pos)
        return pos + size
    if wire == FIXED32:
        return pos + 4
    if wire == FIXED64:
        return pos + 8
    # an unknown wire type cannot be skipped over, and guessing would
    # walk into the middle of a field: give up on the rest of the message
    raise ValueError('vector tile: wire type %d at %d' % (wire, pos))


def _value(data, pos, end):
    """one entry of a layer's value table"""
    while pos < end:
        key, pos = _varint(data, pos)
        field, wire = key >> 3, key & 7
        if field == 1 and wire == LENGTH:                # string
            size, pos = _varint(data, pos)
            return data[pos:pos + size].decode('utf-8', 'replace')
        if field == 4 and wire == VARINT:                # int64
            return _varint(data, pos)[0]
        if field == 5 and wire == VARINT:                # uint64
            return _varint(data, pos)[0]
        if field == 6 and wire == VARINT:                # sint64, zigzag
            raw = _varint(data, pos)[0]
            return (raw >> 1) ^ -(raw & 1)
        if field == 7 and wire == VARINT:                # bool
            return _varint(data, pos)[0] != 0
        # float = 2 and double = 3 are the two nothing here uses
        pos = _skip(data, pos, wire)
    return None


def _tags(data, pos, end, names, values):
    """packed pairs of indices, into the layer's own two tables.

    A name the layer table holds as None is one nothing is going to
    read, and the pair is stepped over rather than built.
    """
    out = {}
    nkeys, nvalues = len(names), len(values)
    while pos < end:
        k, pos = _varint(data, pos)
        if pos >= end:
            break
        v, pos = _varint(data, pos)
        if k < nkeys and v < nvalues and names[k] is not None:
            out[names[k]] = values[v]
    return out


def _geometry(data, pos, end, scale, step, kind):
    """the command stream, as rings already scaled into pixels.

    The varint reader is written out rather than called, because this is
    the loop the whole thing is spent in: a zoom 9 tile is around 300,000
    of these and the call overhead alone was most of a second.

    `step` drops points the screen cannot tell apart.  A tile is 4096
    units across and drawn 512 pixels wide, so eight units are one pixel
    and a coastline carrying every one of them costs eight QPointF for
    each pixel of itself.  The deltas are still read - they are relative,
    so skipping one would move everything after it - but a point closer
    than half a pixel to the last one kept is not built.  The first point
    of a ring and the last are always kept, so nothing changes shape at
    its ends or fails to close.
    """
    rings = []
    ring = None
    x = y = 0
    keptX = keptY = 0
    while pos < end:
        # command integer: the low three bits say which, the rest how many
        header = data[pos]
        pos += 1
        if header >= 0x80:
            result, shift = header & 0x7f, 7
            while True:
                byte = data[pos]
                pos += 1
                result |= (byte & 0x7f) << shift
                if byte < 0x80:
                    break
                shift += 7
            header = result
        command, count = header & 7, header >> 3

        if command == CLOSE_PATH:
            if ring:
                ring.append(ring[0])
            continue

        for step_ in range(count):
            # two zigzag varints, a delta each
            byte = data[pos]
            pos += 1
            if byte < 0x80:
                dx = byte
            else:
                dx, shift = byte & 0x7f, 7
                while True:
                    byte = data[pos]
                    pos += 1
                    dx |= (byte & 0x7f) << shift
                    if byte < 0x80:
                        break
                    shift += 7
            byte = data[pos]
            pos += 1
            if byte < 0x80:
                dy = byte
            else:
                dy, shift = byte & 0x7f, 7
                while True:
                    byte = data[pos]
                    pos += 1
                    dy |= (byte & 0x7f) << shift
                    if byte < 0x80:
                        break
                    shift += 7
            x += (dx >> 1) ^ -(dx & 1)
            y += (dy >> 1) ^ -(dy & 1)

            if command == MOVE_TO:
                # a move starts a ring, and a point layer is all moves
                ring = [QPointF(x * scale, y * scale)]
                rings.append(ring)
                keptX, keptY = x, y
            elif ring is not None:
                dx = x - keptX
                dy = y - keptY
                if (step_ == count - 1 or dx >= step or -dx >= step
                        or dy >= step or -dy >= step):
                    ring.append(QPointF(x * scale, y * scale))
                    keptX, keptY = x, y

    if kind == POINT:
        # one point per ring, and a caller wants them as points
        return [r[0] for r in rings if r]
    return [QPolygonF(r) for r in rings if len(r) > 1]
