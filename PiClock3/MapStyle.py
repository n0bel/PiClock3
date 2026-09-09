"""A MapLibre style, evaluated and drawn with QPainter.

The style language is the Mapbox GL Style Specification, now maintained by
MapLibre and read by Maputnik, OpenLayers and most tile vendors - so what
is written here is a standard rather than one service's format, and a
style from anywhere else has a fair chance of drawing.

A style layer is three things: a source layer to read, a filter deciding
which of its features to draw, and paint values that are expressions of
the zoom and sometimes of the feature.

**Expressions compile to closures once, at load.**  Interpreting the JSON
tree per feature was the second largest cost after decoding, and most of
it is avoidable twice over: an expression is compiled once, and one that
does not read the feature is *evaluated* once, because a view has a single
zoom.  `line-width: ["interpolate", ..., ["zoom"], ...]` is a number for
the whole render rather than an arithmetic tree walked per road.

## What is not implemented, and what each costs

- `symbol-placement: line`.  Road names sit at the middle vertex of their
  road instead of following it, which looks wrong on a long curve.  This
  is the largest visible gap.
- `icon-image` on a layer with no text of its own - a one-way arrow, a
  station marker.  An icon *behind* text is drawn, which is what a route
  shield is, so the numbers come out on their plates.
- `fill-extrusion`.  Liberty's one 3D layer does not draw.
- `line-blur`, `text-halo-blur`.  Edges are hard rather than soft.
- `fill-pattern`, `fill-translate`, `text-translate`.

Anything else in a style is read and obeyed, and a paint property this
does not know is ignored rather than fatal - a style is data from
somewhere else, and refusing to draw a map over one unknown key would be
the wrong trade.
"""
import logging
import re
import time

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter,
                         QPainterPath, QPen)

from .VectorTile import LINESTRING, POINT, POLYGON

logger = logging.getLogger(__name__)

# what geometry-type answers.  Every style seen lists the Multi- form
# beside the plain one in the same match, so the plain one is enough.
SHAPES = {POINT: 'Point', LINESTRING: 'LineString', POLYGON: 'Polygon'}

CAPS = {'butt': Qt.FlatCap, 'round': Qt.RoundCap, 'square': Qt.SquareCap}
JOINS = {'bevel': Qt.BevelJoin, 'round': Qt.RoundJoin, 'miter': Qt.MiterJoin}

# a text-font entry names a face this has no copy of, so what is taken
# from it is the weight and the slant; the family is the clock's own.
BOLD = re.compile(r'bold', re.I)
ITALIC = re.compile(r'italic|oblique', re.I)

RGB = re.compile(r'^rgba?\(([^)]*)\)$', re.I)
HSL = re.compile(r'^hsla?\(([^)]*)\)$', re.I)

# a legacy style writes text-field: '{name}' rather than an expression
TOKEN = re.compile(r'\{([^{}]+)\}')


def color(spec):
    """anything a style writes a color as, or None.

    Hex, rgb(), rgba(), hsl(), hsla() and Qt's own names, mixed freely
    within one style - Liberty writes '#f8f4f0', 'rgb(158,189,255)' and
    'hsl(26,87%,62%)' in three layers running.
    """
    if spec is None:
        return None
    if isinstance(spec, QColor):
        return spec
    if not isinstance(spec, str):
        return None
    text = spec.strip()

    found = RGB.match(text)
    if found:
        parts = _numbers(found.group(1))
        if len(parts) >= 3:
            return QColor(_byte(parts[0]), _byte(parts[1]), _byte(parts[2]),
                          _alpha(parts[3] if len(parts) > 3 else 1.0))
        return None

    found = HSL.match(text)
    if found:
        parts = _numbers(found.group(1))
        if len(parts) >= 3:
            out = QColor()
            out.setHsvF(*_hslToHsv(parts[0], parts[1], parts[2]))
            out.setAlphaF(min(1.0, max(0.0, parts[3]
                                       if len(parts) > 3 else 1.0)))
            return out
        return None

    out = QColor(text)
    return out if out.isValid() else None


def _numbers(text):
    """the numbers in an rgb() or hsl() argument list, percents scaled"""
    out = []
    for part in text.replace('/', ',').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if part.endswith('%'):
                out.append(float(part[:-1]) / 100.0)
            else:
                out.append(float(part))
        except ValueError:
            return []
    return out


def _byte(value):
    # rgb() takes 0-255, and a percent has already been scaled to 0-1
    return int(round(min(255.0, max(0.0, value * 255 if value <= 1.0
                                    and isinstance(value, float)
                                    and value != int(value) else value))))


def _alpha(value):
    return int(round(min(255.0, max(0.0, value * 255.0))))


def _hslToHsv(h, s, lightness):
    """css hsl to what QColor.setHsvF takes, all 0-1"""
    h = (h % 360.0) / 360.0
    v = lightness + s * min(lightness, 1.0 - lightness)
    return (h, 0.0 if v <= 0 else 2.0 * (1.0 - lightness / v),
            min(1.0, max(0.0, v)))


# ------------------------------------------------------------ expressions

class Compiled():
    """an expression as a function, and whether it reads the feature.

    The second half is what makes a view affordable: a view has one zoom,
    so an expression that does not read the feature is evaluated once for
    the whole layer rather than once per road.
    """

    __slots__ = ('fn', 'feature')

    def __init__(self, fn, feature):
        self.fn = fn
        self.feature = feature

    def __call__(self, zoom, tags, shape):
        return self.fn(zoom, tags, shape)


def constant(value):
    return Compiled(lambda z, t, s: value, False)


def compile(expr):                                  # noqa: A001
    """a style expression as a Compiled, in either syntax.

    The modern one wraps a property read - ["==", ["get", "class"], "x"] -
    and the legacy one names it bare - ["==", "class", "x"].  A bare
    string in the first operand of a comparison is the only thing that
    tells them apart, which is the same test every other reader uses.
    """
    if not isinstance(expr, list) or not expr:
        if isinstance(expr, str) and TOKEN.search(expr):
            return _tokens(expr)
        return constant(expr)
    if not isinstance(expr[0], str):
        return constant(expr)

    builder = OPERATORS.get(expr[0])
    if builder is None:
        # a list whose first word is not an operator is a plain array,
        # which is what text-font: ["Noto Sans Regular"] and text-offset:
        # [0, 0.6] are.  Reading one as a failed expression is how a
        # style loses every one of its fonts.
        return constant(expr)
    return builder(expr[1:])


def _tokens(text):
    """'{name} ({ref})' - a legacy text-field, read from the feature"""
    def run(zoom, tags, shape):
        return TOKEN.sub(
            lambda m: str(tags.get(m.group(1), '')), text)
    return Compiled(run, True)


def _operand(node):
    """an argument, allowing the legacy bare-property spelling"""
    if isinstance(node, str):
        if node == '$type':
            return Compiled(lambda z, t, s: s, True)
        return Compiled(lambda z, t, s, k=node: t.get(k), True)
    return compile(node)


def _all(args):
    parts = [compile(a) for a in args]
    needs = any(p.feature for p in parts)

    def run(zoom, tags, shape):
        for part in parts:
            if not part.fn(zoom, tags, shape):
                return False
        return True
    return Compiled(run, needs)


def _any(args):
    parts = [compile(a) for a in args]
    needs = any(p.feature for p in parts)

    def run(zoom, tags, shape):
        for part in parts:
            if part.fn(zoom, tags, shape):
                return True
        return False
    return Compiled(run, needs)


def _not(args):
    inner = compile(args[0]) if args else constant(False)
    return Compiled(lambda z, t, s: not inner.fn(z, t, s), inner.feature)


def _comparison(how):
    def build(args):
        if len(args) < 2:
            return constant(False)
        left, right = _operand(args[0]), compile(args[1])
        needs = left.feature or right.feature

        def run(zoom, tags, shape):
            return how(left.fn(zoom, tags, shape),
                       right.fn(zoom, tags, shape))
        return Compiled(run, needs)
    return build


def _ordered(how):
    """<, <=, > and >= - a missing property is not smaller, it is absent"""
    def compare(a, b):
        if a is None or b is None:
            return False
        try:
            return how(a, b)
        except TypeError:
            return False
    return compare


def _get(args):
    if not args:
        return constant(None)
    key = compile(args[0])
    if not key.feature:
        name = key.fn(0, {}, '')
        return Compiled(lambda z, t, s: t.get(name), True)
    return Compiled(lambda z, t, s: t.get(key.fn(z, t, s)), True)


def _has(args):
    if not args:
        return constant(False)
    key = compile(args[0])
    name = key.fn(0, {}, '') if not key.feature else None
    if name is not None:
        return Compiled(lambda z, t, s: name in t, True)
    return Compiled(lambda z, t, s: key.fn(z, t, s) in t, True)


def _in(args):
    """legacy ["in", "class", "a", "b"] and modern ["in", needle, list]"""
    if len(args) == 2 and isinstance(args[1], list):
        needle, hay = compile(args[0]), compile(args[1])
        return Compiled(
            lambda z, t, s: needle.fn(z, t, s) in (hay.fn(z, t, s) or ()),
            needle.feature or hay.feature)
    if not args:
        return constant(False)
    left = _operand(args[0])
    wanted = set(args[1:])
    return Compiled(lambda z, t, s: left.fn(z, t, s) in wanted, True)


def _match(args):
    """["match", input, label(s), out, ..., default]"""
    if len(args) < 2:
        return constant(None)
    subject = compile(args[0])
    default = compile(args[-1])
    table, cases = {}, []
    needs = subject.feature or default.feature
    for i in range(1, len(args) - 1, 2):
        labels, result = args[i], compile(args[i + 1])
        needs = needs or result.feature
        for label in (labels if isinstance(labels, list) else [labels]):
            try:
                table[label] = result
            except TypeError:                       # an unhashable label
                cases.append((label, result))

    def run(zoom, tags, shape):
        value = subject.fn(zoom, tags, shape)
        try:
            found = table.get(value)
        except TypeError:
            found = None
        if found is None:
            for label, result in cases:
                if label == value:
                    found = result
                    break
        return (found or default).fn(zoom, tags, shape)
    return Compiled(run, needs)


def _case(args):
    """["case", test, out, test, out, ..., default]"""
    pairs = [(compile(args[i]), compile(args[i + 1]))
             for i in range(0, len(args) - 1, 2)]
    default = compile(args[-1]) if args else constant(None)
    needs = default.feature or any(t.feature or o.feature for t, o in pairs)

    def run(zoom, tags, shape):
        for test, out in pairs:
            if test.fn(zoom, tags, shape):
                return out.fn(zoom, tags, shape)
        return default.fn(zoom, tags, shape)
    return Compiled(run, needs)


def _step(args):
    """["step", input, below, stop, out, stop, out, ...]"""
    if len(args) < 2:
        return constant(None)
    subject = compile(args[0])
    below = compile(args[1])
    stops = [(args[i], compile(args[i + 1]))
             for i in range(2, len(args) - 1, 2)]
    needs = subject.feature or below.feature or any(o.feature
                                                    for _, o in stops)

    def run(zoom, tags, shape):
        value = subject.fn(zoom, tags, shape)
        found = below
        if value is not None:
            for at, out in stops:
                if value < at:
                    break
                found = out
        return found.fn(zoom, tags, shape)
    return Compiled(run, needs)


def _interpolate(args):
    """["interpolate", ["linear"]|["exponential", b], input, stop, out, ...]

    The whole zoom-dependent look of every style is this one operator, so
    it carries colors as well as numbers - and a color interpolated in
    sRGB is what every other reader does.
    """
    if len(args) < 3:
        return constant(None)
    kind = args[0] if isinstance(args[0], list) else ['linear']
    base = 1.0
    if len(kind) > 1 and kind[0] == 'exponential':
        base = float(kind[1])
    subject = compile(args[1])
    stops = [(float(args[i]), compile(args[i + 1]))
             for i in range(2, len(args) - 1, 2)]
    needs = subject.feature or any(o.feature for _, o in stops)
    if not stops:
        return constant(None)

    def run(zoom, tags, shape):
        value = subject.fn(zoom, tags, shape)
        if value is None:
            return stops[0][1].fn(zoom, tags, shape)
        if value <= stops[0][0]:
            return stops[0][1].fn(zoom, tags, shape)
        if value >= stops[-1][0]:
            return stops[-1][1].fn(zoom, tags, shape)
        for i in range(len(stops) - 1):
            low, high = stops[i][0], stops[i + 1][0]
            if low <= value <= high:
                a = stops[i][1].fn(zoom, tags, shape)
                b = stops[i + 1][1].fn(zoom, tags, shape)
                return _mix(a, b, _fraction(value, low, high, base))
        return stops[-1][1].fn(zoom, tags, shape)
    return Compiled(run, needs)


def _fraction(value, low, high, base):
    if high <= low:
        return 0.0
    if base == 1.0:
        return (value - low) / (high - low)
    return ((base ** (value - low) - 1.0)
            / (base ** (high - low) - 1.0))


def _mix(a, b, t):
    """between two stop outputs, whatever kind they are"""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_mix(x, y, t) for x, y in zip(a, b)]
    ca, cb = color(a), color(b)
    if ca is not None and cb is not None:
        return QColor(
            int(round(ca.red() + (cb.red() - ca.red()) * t)),
            int(round(ca.green() + (cb.green() - ca.green()) * t)),
            int(round(ca.blue() + (cb.blue() - ca.blue()) * t)),
            int(round(ca.alpha() + (cb.alpha() - ca.alpha()) * t)))
    return a if t < 0.5 else b


def _coalesce(args):
    parts = [compile(a) for a in args]
    needs = any(p.feature for p in parts)

    def run(zoom, tags, shape):
        for part in parts:
            found = part.fn(zoom, tags, shape)
            if found is not None:
                return found
        return None
    return Compiled(run, needs)


def _concat(args):
    parts = [compile(a) for a in args]
    needs = any(p.feature for p in parts)

    def run(zoom, tags, shape):
        out = []
        for part in parts:
            found = part.fn(zoom, tags, shape)
            if found is not None:
                out.append(str(found))
        return ''.join(out)
    return Compiled(run, needs)


def _product(args):
    """["*", a, b, ...] - the one arithmetic operator anything here needs.

    A style's line widths are zoom curves and a config wanting thinner
    roads should not have to restate one, so `weight:` multiplies what
    the source style already worked out.
    """
    parts = [compile(a) for a in args]
    needs = any(p.feature for p in parts)

    def run(zoom, tags, shape):
        out = 1.0
        for part in parts:
            found = part.fn(zoom, tags, shape)
            if not isinstance(found, (int, float)):
                return None
            out *= found
        return out
    return Compiled(run, needs)


def _unary(how):
    def build(args):
        inner = compile(args[0]) if args else constant(None)

        def run(zoom, tags, shape):
            return how(inner.fn(zoom, tags, shape))
        return Compiled(run, inner.feature)
    return build


def _toNumber(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


OPERATORS = {
    'literal': lambda args: constant(args[0] if args else None),
    'get': _get,
    'has': _has,
    '!has': lambda args: _not([['has'] + list(args)]),
    'in': _in,
    '!in': lambda args: _not([['in'] + list(args)]),
    'geometry-type': lambda args: Compiled(lambda z, t, s: s, True),
    'zoom': lambda args: Compiled(lambda z, t, s: z, False),
    'all': _all,
    'any': _any,
    'none': lambda args: _not([['any'] + list(args)]),
    '!': _not,
    '==': _comparison(lambda a, b: a == b),
    '!=': _comparison(lambda a, b: a != b),
    '<': _comparison(_ordered(lambda a, b: a < b)),
    '<=': _comparison(_ordered(lambda a, b: a <= b)),
    '>': _comparison(_ordered(lambda a, b: a > b)),
    '>=': _comparison(_ordered(lambda a, b: a >= b)),
    '*': _product,
    'match': _match,
    'case': _case,
    'step': _step,
    'interpolate': _interpolate,
    'coalesce': _coalesce,
    'concat': _concat,
    'to-string': _unary(lambda v: '' if v is None else str(v)),
    'to-number': _unary(_toNumber),
    'to-boolean': _unary(bool),
}


def _reads(node, found):
    """every attribute name a ["get"] or ["has"] in this tree asks for.

    None where one of them is computed rather than written down, which
    means the reader cannot know what to keep and has to keep all of it.
    """
    if isinstance(node, dict):
        for value in node.values():
            if _reads(value, found) is None:
                return None
        return found
    if not isinstance(node, list):
        return found
    if node and node[0] in ('get', 'has', '!has'):
        if len(node) > 1 and isinstance(node[1], str):
            found.add(node[1])
        else:
            return None
    elif node and node[0] in ('==', '!=', '<', '<=', '>', '>=', 'in', '!in'):
        # the legacy spelling names the attribute bare
        if len(node) > 1 and isinstance(node[1], str):
            found.add(node[1])
    for item in node:
        if _reads(item, found) is None:
            return None
    return found


# ---------------------------------------------------------------- drawing

class Layer():
    """one style layer, with its filter and paint already compiled"""

    __slots__ = ('id', 'kind', 'source', 'sourceLayer', 'minzoom', 'maxzoom',
                 'filter', 'paint', 'layout')

    def __init__(self, spec):
        self.id = spec.get('id') or ''
        self.kind = spec.get('type') or ''
        self.source = spec.get('source')
        self.sourceLayer = spec.get('source-layer')
        self.minzoom = spec.get('minzoom')
        self.maxzoom = spec.get('maxzoom')
        found = spec.get('filter')
        self.filter = compile(found) if found is not None else None
        self.paint = {k: compile(v)
                      for k, v in (spec.get('paint') or {}).items()}
        self.layout = {k: compile(v)
                       for k, v in (spec.get('layout') or {}).items()}

    def drawn(self, zoom):
        """whether this layer draws at all at this zoom.

        minzoom and maxzoom are the style's own way of saying a layer is
        for other scales, and honoring them here saves filtering every
        feature of a layer that would draw nothing.
        """
        if (self.layout.get('visibility')
                and self.layout['visibility'].fn(zoom, {}, '') == 'none'):
            return False
        if self.minzoom is not None and zoom < self.minzoom:
            return False
        if self.maxzoom is not None and zoom >= self.maxzoom:
            return False
        return True

    def value(self, where, name, zoom, default=None):
        """a paint or layout value, for a layer whose value is not per
        feature - which is nearly all of them, a view having one zoom"""
        found = (self.paint if where == 'paint' else self.layout).get(name)
        if found is None:
            return default
        out = found.fn(zoom, {}, '')
        return default if out is None else out


class MapStyle():
    """a parsed style, ready to draw a view with.

    `render` is handed the tiles rather than fetching them, because what
    a tile costs and how it is cached is the provider's business and how
    it is drawn is this one's.
    """

    def __init__(self, style, sprite=None):
        """`sprite` is (index, atlas) - what icon-image draws from.

        A style names one sheet holding every icon it uses, and the index
        says where each is in it.  Without one, a layer that would have
        drawn an icon draws only its text, which for a route shield is a
        number with nothing behind it.
        """
        self.style = style or {}
        self.sprite, self.atlas = sprite if sprite else (None, None)
        self.sources = self.style.get('sources') or {}
        self.layers = [Layer(spec)
                       for spec in (self.style.get('layers') or [])]
        self.fonts = {}
        self.keys = self._keys()

    def _keys(self):
        """which attributes the style reads, per source layer.

        The union across every layer reading that source layer, so the
        decoder builds one dict per feature and every caller agrees about
        what is in it.  A `get` whose key is itself computed cannot be
        known ahead, and answers None for that source layer - meaning
        every attribute, which is what the decoder did before this.
        """
        out = {}
        for spec in (self.style.get('layers') or []):
            name = spec.get('source-layer')
            if not name:
                continue
            found = out.setdefault(name, set())
            if found is None:
                continue
            for node in (spec.get('filter'), spec.get('paint'),
                         spec.get('layout')):
                if _reads(node, found) is None:
                    out[name] = None
                    break
        return out

    def wanted(self, kind):
        """which sources of a kind - 'vector', 'raster' - are drawn from"""
        used = {layer.source for layer in self.layers if layer.source}
        return [name for name, spec in self.sources.items()
                if name in used and spec.get('type') == kind]

    def sourceLayers(self, source):
        """which source layers are read, so a decoder can be told"""
        return {layer.sourceLayer for layer in self.layers
                if layer.source == source and layer.sourceLayer}

    # ------------------------------------------------------------- render

    def render(self, painter, zoom, placed, rect, family=None):
        """draw the whole style into `painter`, without stopping.

        For anything with a clock to keep running, drive steps() instead.
        """
        for _ in self.steps(painter, zoom, placed, rect, family):
            pass

    def steps(self, painter, zoom, placed, rect, family=None):
        """draw the style, stopping often enough to be interrupted.

        `placed` maps a source name to a list of (x, y, thing, size) - a
        VectorTile for a vector source and a QImage for a raster one -
        each at its own offset in the painter's coordinates.

        A generator rather than a plain call, because on one core this is
        the difference between a clock and a frozen screen.  A Pi Zero
        spends seconds in here - 110 microseconds a vertex through the
        bindings is the floor, and a view has tens of thousands of them -
        and a second of blocked event loop is a second of stopped second
        hand.  The caller decides how long a slice is; on a fast machine
        the whole thing is one.

        It stops after every feature rather than every few, because a
        slice is only ever as short as the last thing it started and one
        feature can be a lake with five hundred vertices.  Measured on a
        Pi Zero drawing a classic radar: stopping every fourth feature
        held the loop 2.3 seconds at worst, every feature 0.5.  What that
        costs is a generator resumed per feature, which is nothing beside
        the QPointF it was going to build anyway.
        """
        painter.setRenderHint(QPainter.Antialiasing, True)
        started = time.monotonic()
        labels = []
        drawn = 0
        for layer in self.layers:
            if not layer.drawn(zoom):
                continue
            if layer.kind == 'background':
                self._background(painter, layer, zoom, rect)
            elif layer.kind == 'raster':
                self._raster(painter, layer, zoom,
                             placed.get(layer.source) or ())
            elif layer.kind in ('fill', 'line', 'symbol'):
                for _ in self._features(painter, layer, zoom,
                                        placed.get(layer.source) or (),
                                        labels, family, rect):
                    yield
            else:
                continue                # fill-extrusion, and anything new
            drawn += 1
            yield
        # the number that decides how many layers a slow machine can
        # afford, which is why it is logged rather than measured by hand
        logger.debug('map style: %d of %d layers at zoom %g, %d labels,'
                     ' %.0f ms', drawn, len(self.layers), zoom, len(labels),
                     (time.monotonic() - started) * 1000.0)

    def _background(self, painter, layer, zoom, rect):
        paint = color(layer.value('paint', 'background-color', zoom))
        if paint is None:
            return
        opacity = layer.value('paint', 'background-opacity', zoom, 1.0)
        painter.save()
        painter.setOpacity(opacity)
        painter.fillRect(rect, paint)
        painter.restore()

    def _raster(self, painter, layer, zoom, tiles):
        opacity = layer.value('paint', 'raster-opacity', zoom, 1.0)
        if opacity <= 0:
            return
        painter.save()
        painter.setOpacity(opacity)
        for x, y, image, size in tiles:
            if image is None or image.isNull():
                continue
            # into a rect rather than onto a point, so an over-zoomed
            # tile is scaled as it is drawn.  Building the enlarged image
            # instead would be a 256 pixel relief tile allocated at 8192
            # square - 256MB, for a wash
            painter.drawImage(QRectF(x, y, size, size), image)
        painter.restore()

    def _features(self, painter, layer, zoom, tiles, labels, family, rect):
        """one vector layer, over every tile that carries it"""
        if not layer.sourceLayer:
            return
        style = self._prepare(layer, zoom, family)
        if style is None:
            return
        test = layer.filter
        constantly = None
        if test is not None and not test.feature:
            constantly = bool(test.fn(zoom, {}, ''))
            if not constantly:
                return

        for x, y, tile, _ in tiles:
            features = tile.layer(layer.sourceLayer,
                                  self.keys.get(layer.sourceLayer))
            if not features:
                continue
            if layer.kind == 'symbol':
                for _ in self._symbols(painter, layer, zoom, features, x, y,
                                       style, labels, test, constantly,
                                       rect):
                    yield
                continue
            painter.save()
            painter.translate(x, y)
            shapes = self._fills if layer.kind == 'fill' else self._lines
            # the painter keeps whatever the loop set on it across a
            # slice boundary, which is why the pen is not set per feature
            for _ in shapes(painter, zoom, features, style, test, constantly,
                            x, y, rect):
                yield
            painter.restore()

    @staticmethod
    def _passes(test, constantly, zoom, feature):
        if constantly is not None:
            return constantly
        if test is None:
            return True
        return bool(test.fn(zoom, feature.tags,
                            SHAPES.get(feature.type, '')))

    @staticmethod
    def _onScreen(feature, ox, oy, rect):
        """whether a feature reaches the view at all.

        Asked after the filter and before the shape, which is the order
        that matters: the filter reads attributes already built, this
        reads deltas and builds nothing, and only what survives both
        costs a QPointF a vertex.  A tile is 512 pixels wide and a
        classic radar is 370, so most of a tile is off screen.
        """
        left, top, right, bottom = feature.bounds
        if right < left:
            return False
        return not (left + ox > rect.right() or right + ox < rect.left()
                    or top + oy > rect.bottom() or bottom + oy < rect.top())

    def _prepare(self, layer, zoom, family):
        """everything about a layer that does not vary per feature"""
        if layer.kind == 'fill':
            fill = color(layer.value('paint', 'fill-color', zoom, '#000'))
            if fill is None:
                return None
            opacity = layer.value('paint', 'fill-opacity', zoom, 1.0)
            outline = color(layer.value('paint', 'fill-outline-color', zoom))
            return {'brush': QBrush(fill), 'opacity': opacity,
                    'outline': None if outline is None
                    else QPen(outline, 0),
                    'antialias': layer.value('paint', 'fill-antialias',
                                             zoom, True)}

        if layer.kind == 'line':
            stroke = color(layer.value('paint', 'line-color', zoom, '#000'))
            if stroke is None:
                return None
            width = layer.value('paint', 'line-width', zoom, 1.0)
            gap = layer.value('paint', 'line-gap-width', zoom, 0.0)
            if gap:
                # a gap draws the road's two edges; one line of the total
                # width is the nearest thing to it that is one pass
                width = gap + 2.0 * width
            if width is None or width <= 0:
                return None
            pen = QPen(stroke, max(0.1, float(width)))
            pen.setCapStyle(CAPS.get(
                layer.value('layout', 'line-cap', zoom, 'butt'), Qt.FlatCap))
            pen.setJoinStyle(JOINS.get(
                layer.value('layout', 'line-join', zoom, 'miter'),
                Qt.MiterJoin))
            dashes = layer.value('paint', 'line-dasharray', zoom)
            if isinstance(dashes, list) and dashes:
                # a dash pattern is in line widths, which is what Qt takes
                pen.setDashPattern([max(0.1, float(d)) for d in dashes])
            return {'pen': pen,
                    'opacity': layer.value('paint', 'line-opacity',
                                           zoom, 1.0)}

        text = color(layer.value('paint', 'text-color', zoom, '#000'))
        size = layer.value('layout', 'text-size', zoom, 12.0)
        if text is None or not size or 'text-field' not in layer.layout:
            return None
        fonts = layer.value('layout', 'text-font', zoom) or []
        name = fonts[0] if fonts else ''
        font = self._font(family, float(size), bool(BOLD.search(name)),
                          bool(ITALIC.search(name)))
        halo = color(layer.value('paint', 'text-halo-color', zoom))
        return {
            'icon': (layer.layout.get('icon-image')
                     if self.sprite is not None else None),
            'icon-size': layer.value('layout', 'icon-size', zoom, 1.0),
            # text-allow-overlap and not icon-allow-overlap: what is being
            # decided is whether this label may sit on another, and a
            # style that lets its icons overlap still wants its words
            # kept apart
            'overlap': bool(layer.value('layout', 'text-allow-overlap',
                                        zoom, False)),
            'field': layer.layout['text-field'],
            'font': font[0], 'metrics': font[1],
            'color': text,
            'halo': halo,
            'halo-width': layer.value('paint', 'text-halo-width', zoom, 0.0),
            'opacity': layer.value('paint', 'text-opacity', zoom, 1.0),
            'transform': layer.value('layout', 'text-transform', zoom, 'none'),
            'anchor': layer.value('layout', 'text-anchor', zoom, 'center'),
            'offset': layer.value('layout', 'text-offset', zoom, [0, 0]),
            'max-width': layer.value('layout', 'text-max-width', zoom, 10.0),
            'padding': layer.value('layout', 'text-padding', zoom, 2.0),
            'size': float(size),
        }

    def _font(self, family, size, bold, italic):
        """a font and its metrics, kept - measuring is most of a label.

        QFontMetricsF was 0.156s of a 0.53s render for 282 labels, and
        building the font is most of that, so both are held against the
        four things that name one.
        """
        key = (family, round(size, 1), bold, italic)
        found = self.fonts.get(key)
        if found is None:
            font = QFont(family) if family else QFont()
            font.setPixelSize(max(1, int(round(size))))
            font.setBold(bold)
            font.setItalic(italic)
            found = (font, QFontMetricsF(font))
            self.fonts[key] = found
        return found

    # ------------------------------------------------------------- shapes

    def _fills(self, painter, zoom, features, style, test, constantly,
               ox, oy, rect):
        painter.setRenderHint(QPainter.Antialiasing,
                              bool(style['antialias']))
        painter.setOpacity(style['opacity'])
        painter.setBrush(style['brush'])
        painter.setPen(style['outline'] or Qt.NoPen)
        for feature in features:
            if feature.type != POLYGON:
                continue
            if not self._passes(test, constantly, zoom, feature):
                continue
            if not self._onScreen(feature, ox, oy, rect):
                continue
            path = QPainterPath()
            # odd-even rather than classifying rings: a hole is inside its
            # exterior, so the rule punches it out without a signed area
            # per ring, and two exteriors that overlap are not a thing
            # these schemas emit
            path.setFillRule(Qt.OddEvenFill)
            for ring in feature.rings:
                path.addPolygon(ring)
            painter.drawPath(path)
            yield

    def _lines(self, painter, zoom, features, style, test, constantly,
               ox, oy, rect):
        painter.setOpacity(style['opacity'])
        painter.setPen(style['pen'])
        painter.setBrush(Qt.NoBrush)
        for feature in features:
            if feature.type == POINT:
                continue
            if not self._passes(test, constantly, zoom, feature):
                continue
            if not self._onScreen(feature, ox, oy, rect):
                continue
            for ring in feature.rings:
                painter.drawPolyline(ring)
            yield

    def _symbols(self, painter, layer, zoom, features, ox, oy, style,
                 labels, test, constantly, rect):
        """point-placed text, with the collision test that makes it read.

        Style layers are drawn in the order the style wrote them, which
        is roughly most important first, so the first label to claim a
        patch of screen keeps it.  Without this a city, its suburb and
        three roads all write over each other and none of them reads.
        """
        metrics = style['metrics']
        pad = float(style['padding'])
        for feature in features:
            if not self._passes(test, constantly, zoom, feature):
                continue
            shape = SHAPES.get(feature.type, '')
            text = style['field'].fn(zoom, feature.tags, shape)
            if not text:
                continue
            text = str(text).strip()
            if not text:
                continue
            if style['transform'] == 'uppercase':
                text = text.upper()
            elif style['transform'] == 'lowercase':
                text = text.lower()

            at = self._anchor(feature, ox, oy)
            if at is None or not rect.contains(at):
                continue

            plate = self._icon(style, zoom, feature.tags, shape, at)
            if plate is not None:
                # a route number is drawn on its shield, and the ref the
                # data carries can be several joined with a semicolon -
                # 'C4;468' in Tokyo - which is two numbers on a plate cut
                # for one.  The first is the one the sign shows.
                text = text.split(';')[0].strip() or text

            lines = self._wrap(text, metrics,
                               float(style['max-width']) * style['size'])
            box = self._box(at, lines, metrics, style)
            if plate is not None:
                # a line box is taller than its glyphs by the descent, so
                # text centered by box sits low on a plate.  Lift it half
                # of that and the number is in the middle of the shield,
                # which is where a sign puts it.
                box.translate(0, -metrics.descent() / 2.0)
            # what is drawn and what claims the space are not the same
            # once there is a plate: the plate is the bigger of the two
            hit = box if plate is None else box.united(plate[0])
            if not rect.intersects(hit):
                continue
            grown = hit.adjusted(-pad, -pad, pad, pad)
            if not style['overlap'] and any(grown.intersects(other)
                                            for other in labels):
                continue
            labels.append(grown)
            if plate is not None:
                painter.setOpacity(style['opacity'])
                painter.drawImage(plate[0], self.atlas, plate[1])
            self._label(painter, lines, box, metrics, style)
            yield

    def _icon(self, style, zoom, tags, shape, at):
        """where a sprite goes and what part of the sheet it is.

        Answers (where on the map, where in the atlas) or None - for a
        layer with no icon, a sheet without that name in it, or no sheet
        at all.  A route shield is the case this exists for: the number
        is small and a plate behind it is what lets it read over rain.
        """
        if style['icon'] is None:
            return None
        name = style['icon'].fn(zoom, tags, shape)
        found = self.sprite.get(name) if name else None
        if not found:
            return None
        ratio = float(found.get('pixelRatio') or 1)
        size = float(style['icon-size'] or 1)
        wide = found['width'] / ratio * size
        high = found['height'] / ratio * size
        return (QRectF(at.x() - wide / 2.0, at.y() - high / 2.0, wide, high),
                QRectF(found['x'], found['y'],
                       found['width'], found['height']))

    @staticmethod
    def _anchor(feature, ox, oy):
        """where a label goes: a point, or the middle of a line.

        The middle vertex rather than along the line - symbol-placement:
        line is the one thing here that is not implemented, and a name at
        the middle of its road is what stands in for it.
        """
        rings = feature.rings
        if not rings:
            return None
        if feature.type == POINT:
            return QPointF(rings[0].x() + ox, rings[0].y() + oy)
        ring = max(rings, key=lambda r: r.count())
        if ring.count() < 1:
            return None
        middle = ring.at(ring.count() // 2)
        return QPointF(middle.x() + ox, middle.y() + oy)

    @staticmethod
    def _wrap(text, metrics, width):
        """text-max-width, in ems, as lines"""
        if width <= 0 or metrics.horizontalAdvance(text) <= width:
            return [text]
        lines, line = [], ''
        for word in text.split():
            trial = (line + ' ' + word) if line else word
            if line and metrics.horizontalAdvance(trial) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines or [text]

    @staticmethod
    def _box(at, lines, metrics, style):
        """where the text sits, from its anchor and its offset"""
        height = metrics.height() * len(lines)
        width = max(metrics.horizontalAdvance(line) for line in lines)
        offset = style['offset'] or [0, 0]
        try:
            dx = float(offset[0]) * style['size']
            dy = float(offset[1]) * style['size']
        except (TypeError, ValueError, IndexError):
            dx = dy = 0.0
        anchor = style['anchor']
        left = at.x() - width / 2.0
        if 'left' in anchor:
            left = at.x()
        elif 'right' in anchor:
            left = at.x() - width
        top = at.y() - height / 2.0
        if 'top' in anchor:
            top = at.y()
        elif 'bottom' in anchor:
            top = at.y() - height
        return QRectF(left + dx, top + dy, width, height)

    @staticmethod
    def _label(painter, lines, box, metrics, style):
        halo, width = style['halo'], float(style['halo-width'] or 0)
        painter.setOpacity(style['opacity'])
        baseline = box.top() + metrics.ascent()
        for line in lines:
            wide = metrics.horizontalAdvance(line)
            x = box.left() + (box.width() - wide) / 2.0
            if halo is not None and width > 0:
                # stroke then fill: the stroke is centered on the outline,
                # so filling first would let it eat into the glyph
                path = QPainterPath()
                path.addText(x, baseline, style['font'], line)
                painter.setPen(QPen(halo, width * 2.0, Qt.SolidLine,
                                    Qt.RoundCap, Qt.RoundJoin))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(style['color']))
                painter.drawPath(path)
            else:
                painter.setPen(QPen(style['color']))
                painter.setFont(style['font'])
                painter.drawText(QPointF(x, baseline), line)
            baseline += metrics.height()


def placedTiles(grid, tiles, size):
    """(x, y, thing, size) for each tile of a grid, in view coordinates.

    The offsets are the same arithmetic the raster tiler crops with, so a
    vector layer and a radar frame line up because they came from one
    grid rather than two.
    """
    origin = grid['origin']
    ox = (int(origin['X']) - origin['X']) * size
    oy = (int(origin['Y']) - origin['Y']) * size
    out = []
    for row, y in enumerate(grid['y']):
        for column, x in enumerate(grid['x']):
            found = tiles.get((x, y))
            if found is not None:
                out.append((ox + column * size, oy + row * size, found, size))
    return out
