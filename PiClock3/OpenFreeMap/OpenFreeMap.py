"""OpenFreeMap, as a base map and as an overlay.

The point of it is the thing missing from every other base map here: no
key, no account, no card.  They serve vector tiles rather than finished
pictures, which is why this is more code than Mapbox - and is also why it
can do three things a static image cannot.  The colors are ours, so roads
can be drawn to read over green, yellow and red rather than hoping a
photograph shows through.  The credit is text we draw, so the mask that
protects it can be the letters instead of a band across the weather.  And
city names come out in the clock's own language, because the tile carries
a name per feature in about eighty of them.

    tiles     vector, .pbf, maxzoom 14
    limits    none.  Their README: no registration, no user database, no
              API keys, no cookies, and no limit on views or requests
    terms     MIT, no SLA, attribution required.  Heavy users are meant
              to self-host, which they publish scripts for
    path      /planet/<dated>/{z}/{x}/{y}.pbf, from the TileJSON

Nothing about the service is written down here except its style URLs and
what its terms require.  Where the tiles are comes from the style, per
source, the way the spec says: theirs names a TileJSON for the vector
tiles and an inline array for the Natural Earth relief, two ways of
saying it rather than one, and both are read where they are declared -
so a style putting them on different hosts costs nothing.  Everything
their own five name is on this one host and keyless, the sprite sheet
and the relief included; upstream Liberty spreads the same four across
MapTiler, GitHub Pages and a key, and rehosting that is much of what
OpenFreeMap is.  The dated path in the TileJSON is not guessable - it
read 20260830_080001_pt one week and 20260906_080001_pt the next.

What sits under the layers is a `background:`, and a name there is a
**ground** - a raster source substituted for the style's own, listed in
grounds.yaml.  Two ship: their Natural Earth relief, used as the shape
of the land, and NASA's Blue Marble, drawn as the picture it is.  A
ground brings its own credit, which is drawn beside ours.

One provider serves both of MapLoop's roles.  An overlay style has no
background layer, so its pixmap is transparent where nothing is drawn,
and that is the whole difference between the two.
"""
import json
import logging
import itertools
import math
import os
import time

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtNetwork import QNetworkReply

from ..BaseMap import BaseMap
from ..Config import readYaml
from ..MapStyle import MapStyle, color, compile, placedTiles
from ..Projection import tileGrid
from ..VectorTile import VectorTile
from ..WebGet import WebGet

logger = logging.getLogger(__name__)

# facts about the service rather than settings anybody should change
THEIRS = ('liberty', 'bright', 'positron', 'dark', 'fiord')
STYLE_URL = 'https://tiles.openfreemap.org/styles/%s'

# their vector tiles are 512 pixels of ground, and the radar's are 256, so
# a grid of theirs matches the radar's one zoom shallower
TILESIZE = 512
TILEPX = 256

WHITE, BLACK = QColor(255, 255, 255), QColor(0, 0, 0)

# what a probe's shape: is worth, in the words geometry-type answers in
SHAPES = {'point': 'Point', 'line': 'LineString', 'polygon': 'Polygon'}

# the zoom a group's probes are asked at.  A filter may hold a zoom test
# as well as an attribute one, and this is a zoom every road class is
# drawn at - a group is which layers draw a thing, not at what scale.
PROBE_ZOOM = 12

# "asked for and not here yet", which a request has to be able to tell
# from "there is no such thing" - one is worth waiting for and the other
# would wait for ever
WAITING = object()

# Cloudflare answers 403 to a request that sends no User-Agent, and
# WebGet sends none of its own
AGENT = 'PiClock3 (+https://github.com/n0bel/PiClock3)'

# what their terms require, word for word from their README - which also
# says the OpenFreeMap part is "optional but appreciated", and that is
# the only reason a short form is allowed to exist at all: a 200 pixel
# classic radar cannot fit the long one at a legible size.
CREDIT = 'OpenFreeMap © OpenMapTiles  Data from OpenStreetMap'
SHORT_CREDIT = '© OpenMapTiles  OpenStreetMap'

# The credit's height: a fraction of the map, floored and capped.  A bare
# fraction cannot serve one clock whose radars run 200 pixels tall on
# classic and 850 on bigmaps - the one that reads at 200 is a banner at
# 850 - which is the same reason a caption's default size is in pixels.
CREDIT_SIZE, CREDIT_FLOOR, CREDIT_CEILING = 0.035, 7, 14

# how much of the relief shows through, where a style asks for it as the
# ground.  Soft light over the land color, so this is how hilly it looks
# rather than how gray.
RELIEF_OPACITY = 0.55

# how long the drawing may hold the event loop before giving it back.
# A radar animates five times a second, so a slice has to be a good deal
# shorter than a tick or the clock stutters while a map is built.
SLICE = 0.04

# and how long to wait before taking it again.  Not zero: Qt runs a zero
# timer ahead of the ordinary ones, so a slice that reschedules itself
# at zero starves the very timers this exists to protect.  Measured on a
# Pi Zero, a millisecond is the difference between the clock ticking 24
# times while a map is drawn and ticking once.
BREATH = 1

# which palette a background implies, when the style does not say
LIGHT_GROUND = 0.5

# the paint key a role sets, when it does not name one: whichever is the
# layer kind's own principal color
PRINCIPAL = {'fill': 'fill-color', 'line': 'line-color',
             'symbol': 'text-color', 'background': 'background-color',
             'fill-extrusion': 'fill-extrusion-color'}

# what a probe says about itself rather than about a feature
SAID = ('layer', 'type', 'shape', 'icon')


def features(probe):
    """the features one probe stands for.

    Any attribute may be written as a list, and what the probe means is
    every combination of them - `class: [rail, transit]` beside
    `brunnel: [bridge, tunnel]` is four features, and a layer joining on
    any one of them joins.  Writing the cross product out by hand is how
    a road group ends up forty lines long, which is the thing this
    replaces.

    A probe naming no shape stands for all three, since a filter that
    tests geometry-type would otherwise have to be guessed at.
    """
    shapes = ([SHAPES[probe['shape']]] if probe.get('shape')
              else list(SHAPES.values()))
    tags = {k: v for k, v in probe.items() if k not in SAID}
    names = sorted(tags)
    spread = [tags[n] if isinstance(tags[n], list) else [tags[n]]
              for n in names]
    for combination in (itertools.product(*spread) if names else [()]):
        yield dict(zip(names, combination)), shapes


class OpenFreeMap(BaseMap):

    attribution = 'OpenFreeMap'

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.metas = {}            # tilejson url -> what it said
        self.waiting = []          # requests waiting on something to land
        self.styles = {}           # name -> MapStyle, built once
        self.sources = {}          # style name -> what its tiles come from
        self.sheets = {}           # sprite url -> (index, atlas)
        self.parts = {}            # sprite url -> the halves, as they land
        self.tiles = {}            # tile key -> VectorTile or QImage
        self.inflight = {}         # tile key -> the jobs waiting on it
        self.reliefs = {}          # id(MapStyle) -> the ground it draws
        self.groups = {}
        self.roles = {}
        self.palettes = {}
        self.grounds = {}

    def start(self):
        here = os.path.dirname(os.path.abspath(__file__))
        found = readYaml(os.path.join(here, 'groups.yaml')) or {}
        self.groups = found.get('groups') or {}
        self.roles = found.get('roles') or {}
        self.palettes = readYaml(os.path.join(here, 'palettes.yaml')) or {}
        found = readYaml(os.path.join(here, 'grounds.yaml')) or {}
        self.grounds = found.get('grounds') or {}
        logger.debug('%s %d groups, %d roles, %d palettes, %d grounds',
                     self.name, len(self.groups), len(self.roles),
                     len(self.palettes), len(self.grounds))

    def pageChange(self):
        return

    # ------------------------------------------------------------ fetching

    def fetch(self, url, done, params=None):
        """a WebGet carrying the User-Agent this service requires"""
        WebGet(url, done, params, headers={'User-Agent': AGENT})

    def drain(self):
        """whatever was waiting on something that has now landed"""
        waiting, self.waiting = self.waiting, []
        for view, layerConfig, callback in waiting:
            self.build(view, layerConfig, callback)

    def getMapPixmap(self, view, layerConfig, callback):
        self.build(view, layerConfig, callback)

    # -------------------------------------------------------------- styles

    def wanted(self, layerConfig):
        """the style this request asks for, as a name or a block.

        A widget's own overlay-style: outranks its style:, which outranks
        the provider's own default - the ordinary tier order, except that
        MapLoop passes the overlay's name down rather than merging it.
        """
        found = layerConfig.get('style')
        if found is None:
            found = self.config.get('style')
        return found or 'liberty'

    def styleFor(self, wanted):
        """a MapStyle for a name or a block, built at most once.

        Keyed on what was asked for rather than on a name, because two
        radars may write two different blocks and a block has no name.

        Three answers, and telling the last two apart is what keeps a
        request from waiting for a style that is never coming: a
        MapStyle, WAITING while the source style is still in flight, or
        None for one that does not exist.
        """
        key = json.dumps(wanted, sort_keys=True, default=str)
        if key in self.styles:
            return self.styles[key]
        spec = wanted if isinstance(wanted, dict) else self.read(wanted)
        if spec is None:
            self.styles[key] = None
            return None
        built, high = self.assemble(spec)
        if built is WAITING or built is None:
            return built
        self.styles[key] = built
        self.reliefs[id(built)] = high
        return built

    def read(self, name):
        """a style file by name, from the folders this looks in.

        A name is a file in one of style-folders: - the plugin's own last,
        so a folder of yours can add names and shadow one of these.
        """
        for folder in self.folders():
            path = os.path.join(folder, '%s.yaml' % name)
            if os.path.isfile(path):
                logger.debug('%s style %s from %s', self.name, name, path)
                return readYaml(path) or {}
        if name in THEIRS:
            # one of their five, taken whole and unrecolored
            return {'from': name}
        logger.warning('%s: no style called %r, and it is not one of'
                       ' theirs (%s)', self.name, name, ', '.join(THEIRS))
        return None

    def folders(self):
        """where a style name is looked for, nearest first"""
        here = os.path.dirname(os.path.abspath(__file__))
        out = []
        for folder in (self.config.get('style-folders') or []):
            found = self.piclock.expand(folder)
            if found:
                out.append(found)
        out.append(os.path.join(here, 'styles'))
        return out

    def assemble(self, spec):
        """a style block as a MapStyle: their cartography, filtered and
        recolored.

        Answers the style and, where its ground is the relief, the color
        its hills lift to - which colors the tiles rather than the style.

        Nothing here writes a layer.  A block says which of the source
        style's layers to keep and what color they should end up, so
        every zoom-width curve, every filter and all of the shield logic
        stays theirs to maintain rather than ours to copy.
        """
        source = self.source(spec.get('from') or 'liberty')
        if source is WAITING or source is None:
            return source, None
        sheet = self.sprite(source.get('sprite'))
        if sheet is WAITING:
            return WAITING, None
        style = json.loads(json.dumps(source))     # theirs stays untouched

        groups = spec.get('layers')
        if groups:
            keep = set()
            asked = []
            for group in groups:
                found = self.groups.get(group)
                if found is None:
                    logger.warning('%s: no layer group called %r', self.name,
                                   group)
                    continue
                asked.append(found)
            probed = self.probed(style['layers'],
                                 {probe.get('layer') for probes in asked
                                  for probe in probes})
            for probes in asked:
                keep.update(self.matching(probes, probed))
            # what is under the layers is background:'s to decide, so a
            # group list never drops the background or the relief - those
            # two are in no group exactly so that this is possible
            style['layers'] = [
                layer for layer in style['layers']
                if layer.get('id') in keep
                or layer.get('type') in ('background', 'raster')]
            self.shaped(spec, keep, len(asked))

        ground = spec.get('background')
        palette = self.palette(spec.get('palette'), ground)
        self.ground(style, ground, palette)
        self.recolor(style, palette)
        self.weigh(style, spec.get('weight'))
        logger.debug('%s style from %r: %d layers', self.name,
                     spec.get('from'), len(style['layers']))
        # what a raster tile becomes as it lands: a ground used as shape
        # says the color its hills lift to, one drawn raw says nothing
        found = self.grounds.get(ground) or {}
        high = (found, color(palette.get('land-high'))) if found else None
        return MapStyle(style, sheet), high

    def probed(self, layers, wanted=None):
        """each style layer with its filter compiled, under its source
        layer.

        Compiled once for the whole style rather than once per probe: a
        group asks with several features and there are twenty groups, so
        the same filter would otherwise be put the same question many
        times over.  Kept under the source layer because a probe names
        one, and walking the sixty transportation layers to answer a
        question about `place` is most of the work if it is not.

        `wanted` is the source layers the groups being asked for name,
        and compiling anything else is work for an answer nobody wants.
        """
        out = {}
        for spec in layers:
            where = spec.get('source-layer')
            if not where or (wanted is not None and where not in wanted):
                continue
            found = spec.get('filter')
            out.setdefault(where, []).append(
                (spec, compile(found) if found else None))
        return out

    def matching(self, probes, probed, zoom=PROBE_ZOOM):
        """which of a style's layers a group's probes accept.

        A probe is a source layer and a feature, and a style layer joins
        the group when its own filter accepts that feature - so nothing
        here reads a layer id and the same word works on any style built
        on the schema.  A layer with no filter at all draws everything
        its source layer holds, so its source layer alone decides.
        """
        out = set()
        for probe in probes:
            kind = probe.get('type')
            icon = probe.get('icon')
            asking = None
            for spec, test in probed.get(probe.get('layer')) or ():
                if spec.get('id') in out:
                    continue
                if kind is not None and spec.get('type') != kind:
                    continue
                if icon is not None:
                    layout = spec.get('layout') or {}
                    if bool(layout.get('icon-image')) != icon:
                        continue
                if test is None:
                    # no filter at all, so the layer draws whatever its
                    # source layer holds and the source layer is answer
                    # enough
                    out.add(spec['id'])
                    continue
                if asking is None:
                    asking = list(features(probe))
                for tags, shapes in asking:
                    if any(test(zoom, tags, shape) for shape in shapes):
                        out.add(spec['id'])
                        break
        return out

    def shaped(self, spec, keep, asked):
        """say so when a layers: list found almost nothing to keep.

        The groups are OpenMapTiles schema terms, which every style on
        that schema answers to - but a style on another one answers to
        none of them, and would draw an empty map that looks like a
        broken provider rather than a style asking for what is not
        there.  Measured rather than keyed on a name, so a style of
        somebody else's is judged the same way as one of theirs.
        """
        if not asked or len(keep) >= 2 * asked:
            return
        logger.warning(
            '%s: layers: named %d groups and they matched %d of this'
            ' style\'s layers, so the map will be nearly empty.  The'
            ' groups are OpenMapTiles schema terms - source layers and'
            ' classes - and %r does not appear to be built on that'
            ' schema.  Drop layers: to take the style whole.',
            self.name, asked, len(keep), spec.get('from') or 'liberty')

    def source(self, name):
        """one of their styles, fetched once and kept for the run"""
        if name not in self.sources:
            self.sources[name] = WAITING
            self.fetch(STYLE_URL % name, self.gotStyle, {'name': name})
        return self.sources[name]

    def sprite(self, url):
        """the icon sheet a style names, as (index, atlas).

        Two files - a json index and one png holding every icon - so the
        pair is only ready when both have landed.  A style with no sprite
        at all, or a sheet that will not come, answers None and its
        symbol layers draw their text alone.
        """
        if not url:
            return None
        if url not in self.sheets:
            self.sheets[url] = WAITING
            self.parts[url] = {}
            self.fetch(url + '.json', self.gotSprite,
                       {'url': url, 'part': 'index'})
            self.fetch(url + '.png', self.gotSprite,
                       {'url': url, 'part': 'atlas'})
        return self.sheets[url]

    def gotSprite(self, error, data, params):
        url, part = params['url'], params['part']
        held = self.parts.setdefault(url, {})
        if error != QNetworkReply.NoError:
            logger.warning('%s: no sprite %s (%s) - route shields will'
                           ' draw as bare numbers', self.name, part, error)
            held[part] = None
        elif part == 'index':
            try:
                held['index'] = json.loads(bytes(data).decode('utf-8'))
            except ValueError:
                logger.warning('%s: the sprite index is not json', self.name)
                held['index'] = None
        else:
            image = QImage()
            image.loadFromData(data)
            held['atlas'] = None if image.isNull() else image

        if 'index' in held and 'atlas' in held:
            if held['index'] and held['atlas'] is not None:
                self.sheets[url] = (held['index'], held['atlas'])
                logger.info('%s sprite %s: %d icons', self.name,
                            url.rsplit('/', 1)[-1], len(held['index']))
            else:
                self.sheets[url] = None
            self.drain()

    def gotStyle(self, error, data, params):
        name = params['name']
        self.sources[name] = None
        if error != QNetworkReply.NoError:
            logger.warning('%s: style %s did not answer (%s) - a map from'
                           ' it cannot be drawn', self.name, name, error)
        else:
            try:
                self.sources[name] = json.loads(bytes(data).decode('utf-8'))
            except ValueError:
                logger.warning('%s: style %s is not json', self.name, name)
        self.drain()

    def palette(self, spec, ground):
        """the colors a role gets, from a named set and what is beside it.

        Which set to start from is the background's own luminance when
        nobody says, so background: white gets dark roads on a light
        ground without anyone having written that down.
        """
        spec = dict(spec or {})
        named = spec.pop('from', None)
        if named is None:
            named = 'light' if self.pale(ground) else 'dark'
        out = dict(self.palettes.get(named) or {})
        if named not in self.palettes:
            logger.warning('%s: no palette called %r', self.name, named)
        out.update(spec)
        return out

    @staticmethod
    def pale(ground):
        """whether what is under the map is light enough to darken it for"""
        if ground in (None, 'none', 'relief'):
            return False
        found = color(ground)
        return found is not None and found.lightnessF() > LIGHT_GROUND

    def ground(self, style, wanted, palette):
        """what sits under the layers: a named ground, a color, or
        nothing.

        A ground is a raster source and naming one substitutes it for
        the style's own, so everything below here - which tiles cover
        the view, fetching them, drawing them - reads the style's
        sources: block exactly as it did and needs to know nothing about
        where a ground comes from.  grounds.yaml is the whole list.

        A color replaces the background layer outright and drops the
        raster, and `none` removes both, which is what makes a style an
        overlay.
        """
        if wanted is None:
            return
        ground = self.grounds.get(wanted) or {}
        style['layers'] = [layer for layer in style['layers']
                           if layer.get('type') != 'background'
                           and (ground or layer.get('type') != 'raster')]
        if wanted == 'none':
            return
        # --check cannot catch this: background: takes a color as well as
        # a ground, and a color is any string Qt will read, so a union of
        # the two rejects nothing.  Here is where a typo is found.
        if not ground and color(wanted) is None:
            logger.warning(
                '%s: background: %r is neither a color nor a ground, so'
                ' this map has nothing under it.  A ground is one of %s,'
                ' and a color is anything Qt reads - white, #f3efe2.',
                self.name, wanted, ', '.join(sorted(self.grounds)))
            return
        # under a picture the ground color only shows where the tiles
        # have not arrived; under the relief it is half of what is drawn
        style['layers'].insert(0, {
            'id': 'piclock-background', 'type': 'background',
            'paint': {'background-color':
                      palette.get('land') if ground else wanted}})
        if not ground:
            return
        # Their raster layer is written for world zooms - it stops at 7
        # and has faded to a tenth by 6 - because under their own
        # cartography that is all it is for.  As the ground it draws at
        # every zoom, at full strength when it is a picture and blended
        # when it is being used as the shape of the land.
        raw = ground.get('color') == 'raw'
        for layer in style['layers']:
            if layer.get('type') == 'raster':
                layer.pop('maxzoom', None)
                layer.pop('minzoom', None)
                layer['paint'] = {
                    'raster-opacity': 1.0 if raw else RELIEF_OPACITY,
                    'raster-resampling':
                        'nearest' if ground.get('magnify') == 'nearest'
                        else 'linear'}
                self.sourced(style, layer.get('source'), ground)

    @staticmethod
    def sourced(style, name, ground):
        """point a style's raster source at the ground's own tiles.

        `from: style` means the ground is the one the style already
        declares - Natural Earth, which Liberty carries as its second
        source - so there is nothing to substitute.  Anything else
        replaces the tiles, the zoom it stops at and the size of one,
        which is all `tilesFor` reads.
        """
        if not name or ground.get('from') == 'style':
            return
        tiles = ground.get('tiles')
        if not tiles:
            return
        spec = (style.get('sources') or {}).get(name)
        if spec is None:
            return
        spec.pop('url', None)              # a TileJSON would win over these
        spec['tiles'] = list(tiles)
        spec['maxzoom'] = ground.get('maxzoom', 8)
        spec['tileSize'] = ground.get('tilesize', TILEPX)

    @staticmethod
    def weigh(style, weight):
        """every line width, scaled.

        A style's widths are zoom curves that took somebody real work, so
        this multiplies them rather than replacing them - a road still
        thickens as it is zoomed into, just less of it.  What it is for
        is that Liberty draws heavier than Mapbox Streets does at the
        same scale, and under a radar the thinner cartography is easier
        to see weather through.
        """
        if not weight or weight == 1:
            return
        for layer in style['layers']:
            if layer.get('type') != 'line':
                continue
            paint = layer.setdefault('paint', {})
            for key in ('line-width', 'line-gap-width'):
                if key in paint:
                    paint[key] = ['*', paint[key], float(weight)]

    def recolor(self, style, palette):
        """a palette's roles onto the layers that should agree about color.

        Which paint key is the layer's own kind - fill-color on a fill,
        line-color on a line - so a role names layers rather than knowing
        what a color is called.  A role replaces whatever expression was
        there, zoom-varying or not, which is what recoloring means.
        """
        wanted = {}
        for role, spec in self.roles.items():
            paint = (spec or {}).get('paint')
            for layer in (spec or {}).get('layers') or []:
                if palette.get(role):
                    wanted.setdefault(layer, []).append(
                        (paint, palette[role]))
        painted, drawn = set(), 0
        for layer in style['layers']:
            if layer.get('type') in PRINCIPAL:
                drawn += 1
            for paint, value in wanted.get(layer.get('id')) or ():
                key = paint or PRINCIPAL.get(layer.get('type'))
                if key:
                    layer.setdefault('paint', {})[key] = value
                    painted.add(layer.get('id'))
        # A role names Liberty's layers outright, because what it sorts
        # by is not in the schema: a road and its casing are the same
        # class on the same source layer, filtered identically, so
        # nothing but the id tells them apart.  A style that uses other
        # ids therefore recolors to almost nothing, which is worth a
        # line - unlike layers:, this cannot be measured against the
        # schema.  A share rather than none at all, since their other
        # four do carry a handful of Liberty's names by coincidence.
        if wanted and drawn and len(painted) * 4 < drawn:
            logger.warning(
                '%s: palette: reached %d of this style\'s %d drawn'
                ' layers, so most of it keeps its own colors.  A palette'
                ' names Liberty\'s layers, and a road casing is not'
                ' something the schema can pick out - so only a style'
                ' cut from liberty recolors.', self.name, len(painted),
                drawn)

    # --------------------------------------------------------------- tiles

    def build(self, view, layerConfig, callback):
        """everything one map needs, then draw it when it has arrived"""
        style = self.styleFor(self.wanted(layerConfig))
        if style is WAITING:
            # the source style is still on its way, and build() runs
            # again from drain() when it lands
            self.waiting.append((view, layerConfig, callback))
            return
        if style is None:
            callback(QPixmap(), None)
            return

        # a style whose ground is the relief says what its hills lift to,
        # and that colors the tile once as it lands rather than blending
        # it on every draw
        high = self.reliefs.get(id(style))
        sources = style.style.get('sources') or {}
        wanted = []
        for kind in ('vector', 'raster'):
            for source in style.wanted(kind):
                found = self.tilesFor(sources.get(source) or {})
                if found is WAITING:
                    # a TileJSON on its way: build() runs again from
                    # drain() when it lands
                    self.waiting.append((view, layerConfig, callback))
                    return
                if found:
                    wanted.append((kind, source, found))

        job = {'view': view, 'style': style, 'callback': callback,
               'placed': {}, 'pending': 0, 'urls': {},
               # a ground from another service is named in the credit
               # beside ours, since drawing somebody's picture without
               # saying whose is the one thing none of these allow
               'also': (high[0].get('credit') if high else '') or ''}
        for kind, source, (template, size, maxzoom) in wanted:
            make, tag = self.asTile, ''
            if kind == 'raster':
                make = self.asImage
                if high is not None and high[0].get('color') != 'raw':
                    tint = high[1]
                    tag = tint.name()

                    def make(data, scale, tint=tint):     # noqa: F811
                        return self.asRelief(data, tint)
            self.want(job, source, template, size, maxzoom, make, tag)
        if not job['pending']:
            self.finish(job)

    def tilesFor(self, spec):
        """where one source's tiles come from: (template, size, maxzoom).

        A style says this per source and in one of two ways - a `tiles:`
        array outright, or a `url:` naming a TileJSON to read it from.
        Both are answered here rather than assuming one service's, which
        is what lets a style draw layers from more than one place: their
        own put the vector tiles behind a TileJSON and the Natural Earth
        relief in an inline array, at different hosts.

        WAITING while a TileJSON is in flight, None for a source that
        says neither.
        """
        vector = spec.get('type') == 'vector'
        size = spec.get('tileSize') or (TILESIZE if vector else TILEPX)
        if spec.get('tiles'):
            return (spec['tiles'][0], size,
                    spec.get('maxzoom', 14 if vector else 6))
        if not spec.get('url'):
            return None
        meta = self.tilejson(spec['url'])
        if meta is WAITING or meta is None:
            return meta
        return ((meta.get('tiles') or [''])[0],
                meta.get('tileSize') or size, meta.get('maxzoom', 14))

    def tilejson(self, url):
        """a source's TileJSON, fetched once and kept for the run.

        Theirs carries a dated path - it read 20260830_080001_pt one week
        and 20260906_080001_pt the next - so it is not guessable and not
        remembered between runs: a stale one is a 404 per tile rather
        than an error anybody can read.
        """
        if url not in self.metas:
            self.metas[url] = WAITING
            self.fetch(url, self.gotTileJson, {'url': url})
        return self.metas[url]

    def gotTileJson(self, error, data, params):
        url = params['url']
        self.metas[url] = None
        if error != QNetworkReply.NoError:
            logger.warning('%s: no tilejson at %s (%s) - nothing from that'
                           ' source can be drawn', self.name, url, error)
        else:
            try:
                meta = json.loads(bytes(data).decode('utf-8'))
                self.metas[url] = meta
                found = (meta.get('tiles') or [''])[0]
                logger.info('%s tiles %s, zoom %s-%s', self.name,
                            found.rsplit('/', 4)[1] if found else '?',
                            meta.get('minzoom'), meta.get('maxzoom'))
            except ValueError:
                logger.warning('%s: the tilejson at %s is not json',
                               self.name, url)
        self.drain()

    def want(self, job, source, template, size, maxzoom, make, tag=''):
        """the tiles one source needs for a view, asked for at once.

        The world is `size * 2**zoom` pixels wide whatever the tiles are,
        and the radar's is `256 * 2**view.zoom`, so the zoom that covers
        the same ground is `view.zoom + log2(256/size)` - one less for
        their 512 pixel vector tiles, and three more for a 256 pixel
        relief tile whose zoom stops at 6.

        Where that runs past the service's maxzoom the deepest tile it
        has is fetched and drawn larger, which is what over-zoom is.  The
        style is still evaluated at the view's zoom, so widths and label
        thresholds stay those of the zoom asked for.
        """
        view = job['view']
        matching = view.zoom + math.log(float(TILEPX) / size, 2)
        zoom = int(min(matching, maxzoom))
        scale = size * (2.0 ** (matching - zoom))
        grid = tileGrid(view.center, zoom, view.rect.width(),
                        view.rect.height(), scale)
        job.setdefault('grids', {})[source] = (grid, scale, make)
        n = 2 ** zoom
        for y in grid['y']:
            if not 0 <= y < n:
                continue
            for x in grid['x']:
                url = (template.replace('{z}', str(zoom))
                       .replace('{x}', str(x % n)).replace('{y}', str(y)))
                # keyed by the url and by what the tile was made into,
                # so two radars at one zoom share a fetch and two
                # palettes do not share a colored relief
                key = (url, tag)
                job['urls'][(source, x, y)] = key
                if key in self.tiles:
                    continue
                # a tile somebody else asked for first is still not here.
                # Two radars share a zoom and a center in the shipped
                # example, and treating an in-flight tile as arrived is
                # how the second one draws an empty map.
                job['pending'] += 1
                if key in self.inflight:
                    self.inflight[key].append(job)
                    continue
                self.inflight[key] = [job]
                self.fetch(url, self.gotTile,
                           {'key': key, 'make': make, 'scale': scale})
        logger.debug('%s %s: %dx%d tiles at zoom %d, %.0fpx', self.name,
                     source, len(grid['x']), len(grid['y']), zoom, scale)

    def gotTile(self, error, data, params):
        key = params['key']
        if error != QNetworkReply.NoError:
            logger.debug('%s tile failed (%s): %s', self.name, error, key[0])
        else:
            self.tiles[key] = params['make'](data, params['scale'])
        for job in self.inflight.pop(key, ()):
            job['pending'] -= 1
            if job['pending'] < 1:
                self.finish(job)

    @staticmethod
    def asTile(data, scale):
        return VectorTile(data, scale)

    @staticmethod
    def asImage(data, scale=None):
        """a raster tile at its own size.

        Not scaled to how large it will be drawn: an over-zoomed relief
        tile reaches 8192 square under a zoom 11 radar, which is 256MB
        for a wash.  MapStyle draws it into a rect instead.
        """
        image = QImage()
        image.loadFromData(data)
        return image

    @classmethod
    def asRelief(cls, data, high):
        """a shaded relief tile as shape rather than as picture.

        Their tile is pale green, which is the worst possible hue under a
        radar whose own palette runs green to red.  What is wanted from
        it is the hills, so it comes out as the palette's land-high
        showing through the tile's own brightness - drawn over the land
        color, that is land lifted where the ground rises, and their
        green never appears at all.

        Grayscale8 and Alpha8 are both one byte a pixel with the same
        layout, so the brightness becomes the transparency by reading the
        same bytes the other way - no pixel loop, just two Qt conversions
        and a composite, once as the tile lands rather than on every
        draw.  convertToFormat cannot do this: asked for Alpha8 it
        answers fully opaque, having no idea the gray was meant as cover.

        The bytes are copied rather than pointed at.  A QImage built on
        constBits() borrows the buffer and does not own it, and the
        segfault when the original is collected is not worth the 64KB a
        tile that copying costs.
        """
        image = cls.asImage(data)
        if image.isNull():
            return image
        gray = image.convertToFormat(QImage.Format_Grayscale8)
        raw = gray.constBits().asstring(gray.sizeInBytes())
        shape = QImage(raw, gray.width(), gray.height(),
                       gray.bytesPerLine(), QImage.Format_Alpha8)
        out = QImage(gray.size(), QImage.Format_ARGB32_Premultiplied)
        out.fill(high)
        painter = QPainter()
        painter.begin(out)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, shape)
        painter.end()
        return out

    def finish(self, job):
        """every tile is in: start drawing, a slice at a time"""
        view, style = job['view'], job['style']
        size = view.rect.size()
        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        placed = {}
        for source, (grid, scale, _) in (job.get('grids') or {}).items():
            found = {}
            for (which, x, y), key in job['urls'].items():
                if which == source and self.tiles.get(key) is not None:
                    found[(x, y)] = self.tiles[key]
            placed[source] = placedTiles(grid, found, scale)

        painter = QPainter()
        painter.begin(image)
        job['image'] = image
        job['painter'] = painter
        job['size'] = size
        job['started'] = time.monotonic()
        job['slices'] = 0
        job['steps'] = style.steps(
            painter, float(view.zoom), placed,
            QRectF(0, 0, size.width(), size.height()),
            self.config.get('font-family') or None)
        self.slice(job)

    def slice(self, job):
        """draw for a while, then let the clock have the loop back.

        The whole reason this is not one call: a Pi Zero spends seconds
        drawing a view, and a second of blocked event loop is a second in
        which the second hand does not move and a radar frame does not
        change.  A slice is short enough to sit inside one animation
        tick, so the clock runs at its own speed while the map builds.

        Nothing is handed over half drawn.  The map appears when it is
        finished, later on a slow machine than a fast one, and until then
        the region holds whatever was there - which for a first draw is
        nothing, the same as any map that has not arrived yet.
        """
        deadline = time.monotonic() + SLICE
        job['slices'] += 1
        for _ in job['steps']:
            if time.monotonic() >= deadline:
                QTimer.singleShot(BREATH, lambda: self.slice(job))
                return

        painter, size = job['painter'], job['size']
        mask = self.credit(painter, size, job.get('also') or '')
        painter.end()
        logger.debug('%s drew a %dx%d map in %d slices, %.0f ms', self.name,
                     size.width(), size.height(), job['slices'],
                     (time.monotonic() - job['started']) * 1000.0)
        job['callback'](QPixmap.fromImage(job['image']), mask)

    # --------------------------------------------------------------- credit

    def credit(self, painter, size, also=''):
        """their credit, drawn in, and a mask that is the letters.

        Every other base map arrives with a mark baked into it and can say
        no more than "somewhere along the bottom", so its mask is a band
        and the band hides weather.  This one draws the mark, so the mask
        can be the same path the text came from, grown by the halo: the
        radar keeps the space between the letters.

        Grown rather than eroded, for the reason a band is: covering a
        little extra hides a little weather, covering too little hides
        attribution.
        """
        height = int(round(min(CREDIT_CEILING,
                               max(CREDIT_FLOOR,
                                   size.height() * CREDIT_SIZE))))
        style = self._creditStyle(height)
        text, path = self._creditPath(style, size, height, also)
        if path is None:
            return None

        halo = max(1.0, height / 6.0)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(1.0)
        painter.setPen(QPen(style['halo'], halo * 2.0, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(style['ink'])
        painter.drawPath(path)

        mask = QImage(size, QImage.Format_Alpha8)
        mask.fill(0)
        stamp = QPainter()
        stamp.begin(mask)
        stamp.setRenderHint(QPainter.Antialiasing, True)
        stamp.setPen(QPen(QColor(255, 255, 255, 255), halo * 3.0,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        stamp.setBrush(QColor(255, 255, 255, 255))
        stamp.drawPath(path)
        stamp.end()
        logger.debug('%s credit %r at %dpx in %dx%d', self.name, text,
                     height, size.width(), size.height())
        return mask

    def _creditStyle(self, height):
        family = self.config.get('font-family')
        font = QFont(family) if family else QFont()
        font.setPixelSize(height)
        return {'font': font,
                'ink': color(self.config.get('credit-color')) or WHITE,
                'halo': color(self.config.get('credit-halo')) or BLACK}

    @staticmethod
    def _creditPath(style, size, height, also=''):
        """the long credit, or the short one where the long will not fit.

        A ground brought in from somewhere else is named alongside, and
        ours is shortened before theirs is dropped: a 200 pixel radar
        fits neither long form, and naming nobody for the picture the
        map is drawn on would be worse than abbreviating the credit for
        the roads.  Theirs goes last, when even the short pair will not
        fit, because OpenMapTiles requires its credit where NASA asks
        for one.
        """
        metrics = QFontMetricsF(style['font'])
        margin = max(2.0, height * 0.4)
        lines = [CREDIT, SHORT_CREDIT]
        if also:
            lines = [CREDIT + '  ' + also, SHORT_CREDIT + '  ' + also] + lines
        for text in lines:
            wide = metrics.horizontalAdvance(text)
            if wide <= size.width() - 2 * margin or text is SHORT_CREDIT:
                if wide > size.width() - 2 * margin:
                    return text, None      # even the short one will not fit
                path = QPainterPath()
                path.addText(QPointF(size.width() - margin - wide,
                                     size.height() - margin
                                     - metrics.descent()),
                             style['font'], text)
                return text, path
        return None, None
