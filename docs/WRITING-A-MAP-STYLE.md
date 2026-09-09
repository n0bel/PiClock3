# Writing a map style

A base map that arrives as a picture - Mapbox, Google - is somebody
else's cartography and there is nothing to write.  `OpenFreeMap` sends
the data instead and the map is drawn here, so what the roads look like,
which of them appear at all, and what sits underneath them are yours.

That is what a **style** is: a name in a config, or a block written where
any other setting goes.

```yaml
widgets:
  radar1:
    base-provider: openfreemap
    style: terrain
```

## What this applies to

**Only `OpenFreeMap`.**  Every base map takes a `style:`, and for the
other two it means something else entirely: a Mapbox style id like
`mapbox/satellite-streets-v10`, or one of Google's four maptypes.  Those
are names for a picture somebody else draws, and nothing in this document
reaches them - not `layers:`, not `palette:`, not `background:`.  A
config that changes `base-provider:` and leaves `style:` alone is naming
something the new provider has never heard of.

**Trimming follows the schema, recoloring follows Liberty.**  The two
halves of a block reach different distances, and it is worth knowing
which is which before naming somebody else's style.

`layers:` is said in [OpenMapTiles](https://openmaptiles.org/schema/)
terms - source layers and classes, the words the tiles themselves are
written in.  A group is a probe rather than a list: `motorways` means
"the `transportation` layers whose own filter accepts a feature of class
`motorway`", and a style layer joins by answering yes.  So the twenty
group names reach every style built on that schema, theirs and anybody
else's, and go on reaching one that has been re-cut under new layer
names.  All five of theirs answer: 20 groups fill on `bright`, 19 on
`positron`, 18 on `dark` and `fiord`.

`palette:` still names Liberty's layers outright, because the thing it
sorts by is not in the schema.  A road and its casing are the same class
on the same source layer, filtered identically - two layers differing
only in width and color - so no amount of schema knowledge tells them
apart.  Recoloring one of their other four is the one thing a block
cannot do, and it says so in the log rather than quietly doing nothing.

A `layers:` list that matches almost nothing also says so.  That is what
a style on a *different schema* looks like - Shortbread, Protomaps - and
the answer there is to drop `layers:` and take the style whole.

## The shipped names

Seven ship, and any of OpenFreeMap's own five may be named as well:

| | |
|---|---|
| `liberty` | their whole cartography, their colors.  The most to draw |
| `terrain` | the classes that still read under weather, on shaded relief |
| `roads` | the same trim with nothing under it, to lay over a satellite |
| `light` | a printed-map ground, the way radar.weather.gov draws one |
| `daylight` | a bright green map in the shape of Mapbox Streets |
| `midnight` | near-black ground and water, and nothing else |
| `midnight-roads` | the other half of it: roads and names on nothing |
| `bright` `positron` `dark` `fiord` | theirs, trimmable but not recolorable |

All seven are cut from Liberty, so all seven can be trimmed *and*
recolored.  `liberty` is the one to look at first; `terrain` is the one
to run.

**Two of them are a pair.**  `midnight` under the weather and
`midnight-roads` over it, which puts the roads and the place names above
a storm instead of beneath it:

```yaml
    base-provider: openfreemap
    overlay-provider: openfreemap
    style: midnight
    overlay-style: midnight-roads
```

They are shaped after the two Mapbox styles `examples/arctic.yaml` uses -
SerBrynden's own - measured over the same view rather than guessed at:
87% of their base is black with water the only other thing in it, and
83% of their overlay is transparent with thin dark lines and dark labels
in the rest.  The difference is that these two need no key.

## A block instead of a name

```yaml
    style:
      from: liberty
      background: relief
      layers: [water, boundaries, motorways, highways, places]
      palette:
        from: dark
        road: '#f2e9d2'
        label: '#ffffff'
```

Four keys, and every one of them is optional.  Nothing here writes a
layer: a block says which of the source style's layers to keep and what
color they end up, so every zoom-width curve, every filter and all of the
shield logic stays theirs to maintain rather than ours to copy.

**A block merges and a string replaces.**  `Config._merge` recurses into
dicts and assigns anything else outright, so a theme can recolor a map
without restating its layer list:

```yaml
# themes/mine/theme.yaml
kind-settings:
  radar:
    style: {palette: {road: '#8fb4d8', label: '#dfe9f4'}}
```

Laid over a config that wrote a block, that keeps the block's layers and
changes two colors.  Laid over a config that wrote `style: terrain` as a
string, it *replaces* the string outright - which is the merge behaving
as it does everywhere else, and the reason to write a block when what you
mean is to adjust one.

### `from:`

Which cartography to take.  A shipped name, one of theirs, or a file of
your own; `liberty` unless you say.

### `layers:`

Which groups to keep.  Groups rather than the source style's layer ids -
Liberty has 111 of them - because `road_trunk_primary_casing` is not a
thing a config should have to know:

| group | what it draws |
|---|---|
| `land` | landcover and landuse fills |
| `parks` | park and reserve fills |
| `water` | lakes, rivers and the coastline |
| `water-names` | lake and river names |
| `boundaries` | country and state lines |
| `motorways` | motorway, with its casing |
| `highways` | trunk and primary |
| `roads` | secondary and tertiary |
| `streets` | minor, service and track |
| `paths` | footpaths and bike paths |
| `rail` | railways, with the transit ones |
| `bridges` | the bridge and tunnel variants of whatever roads are drawn |
| `shields` | route numbers |
| `street-names` | road names |
| `places` | city, town and village names |
| `regions` | state and country names - big, and a radar rarely wants them |
| `localities` | islands, neighborhoods, suburbs and hamlets |
| `places-of-interest` | shops, stations and the rest |
| `buildings` | building footprints |
| `airports` | runways, taxiways and aerodrome names |

**A group is a set, not an order.**  Layers draw in the source style's own
order whatever order they are named in, because that order is load
bearing: Liberty draws every road casing before any road inner, so a list
that put `motorways` after `roads` and was obeyed would put dark casings
over light road surfaces.  Writing the list chooses what is in, never
what is on top.

Left out, every group the source has.  A misspelling is a `--check`
problem rather than a road class that quietly never appears.

What each group means is `PiClock3/OpenFreeMap/groups.yaml`, and it is
written in the schema's words rather than one style's, so re-cutting a
style does not touch it.  A group is a list of **probes**, and a probe is
a source layer and a feature:

```yaml
  motorways:
    - {layer: transportation, type: line, shape: line,
       class: motorway, ramp: [0, 1]}
```

A style layer joins the group when its own filter accepts that feature -
which is the style answering the question rather than us guessing at its
naming.  Any attribute may be a list and the probe stands for every
combination, so `bridges` is one probe with two `brunnel` values and
fifteen classes where the id list it replaced ran to forty names.

There is deliberately no escape hatch for one raw layer id: the escape
hatch is a style file of your own, which is the honest place for that
much detail.

### `background:`

| value | what |
|---|---|
| `none` | transparent, which is what makes a style an overlay |
| `relief` | Natural Earth shaded relief, recolored to the palette |
| any color | flat - `black`, `white`, `'#f3efe2'` |

`relief` is one more fetch from the same service under the same
attribution.  Their own styles carry it as a second source beside the
vector one, so using it follows the style spec rather than bolting on a
second service.

It is used as **shape rather than color**.  Their tile is pale green,
which is the worst possible hue under a radar whose palette runs green to
red, so the tile becomes the palette's `land-high` showing through its
own brightness and is drawn over `land`: the hills are theirs and the hue
is yours.  Their maxzoom is 6, so it is real terrain under a zoom-7 radar
and a soft wash under a zoom-11 one - and the wash is worth having,
because a ground that is not flat reads as land.

### `palette:`

Roles rather than layer ids, so a recolor need not know the cartography
either:

    land  land-high  water  park  boundary
    road  road-casing  street  street-casing
    label  label-halo  shield  shield-text

`from:` names one of two shipped sets, `dark` or `light`, and anything
beside it overrides.  Which set a block starts from, when it does not
say, comes from the background's own luminance - so `background: white`
gets dark roads on a light ground without anyone writing that down.

**A palette reaches Liberty and what is cut from it, and no further.**
Unlike `layers:`, a role names layers outright, because the thing it
sorts by is not in the schema: a road and its casing are the same class
on the same source layer with the same filter, and only the id tells
them apart.  So a `palette:` on one of their other four colors nothing,
and says so in the log.

**The default ground is a desaturated gray-green.**  Tested against light
rain rather than against a storm, since drizzle is the weakest thing a
map under weather has to keep visible: what separates it from the ground
is the saturation rather than the hue, which is why the ground must stay
desaturated and why a saturated green would fail where this one does not.

## A style file of your own

A style is a file in a folder, found by name:

```yaml
# maps/winter.yaml
description: >
  Roads and nothing else, over white.
from: liberty
background: white
layers: [motorways, highways, roads, places]
palette:
  from: light
```

```yaml
providers:
  openfreemap:
    plugin: PiClock3.OpenFreeMap
    style-folders: ['{this-folder}/maps']
    style: winter
```

The plugin's own `styles/` is looked in last, so a folder of yours adds
names and can shadow a shipped one.

## What is not drawn

`MapStyle` reads the MapLibre Style Specification, which is a standard
rather than one service's format - a style from anywhere else has a fair
chance of drawing.  Four things in it do not:

- **`symbol-placement: line`.**  Road names sit at the middle vertex of
  their road rather than following it, which looks wrong on a long curve.
  This is the largest visible gap.
- **`icon-image` where there is no text with it** - a one-way arrow, a
  station marker.  An icon *behind* text does draw, which is what a route
  shield is.
- **`fill-extrusion`.**  Liberty's one 3D layer does not appear.
- **`line-blur` and `text-halo-blur`.**  Edges are hard rather than soft.

### Route shields, and how far they travel

The numbers come out on their plates, from the sprite sheet the style
names - one small fetch, held for the run.  How well that reads outside
the United States is a question about the data rather than the drawing.
Counting the `network` attribute over a tile in six countries:

| | |
|---|---|
| United States | `us-interstate`, `us-highway`, `us-state` |
| United Kingdom | `gb-trunk`, `gb-motorway` |
| Germany, Switzerland, Japan, Australia | `road` |

OpenMapTiles classifies US and GB networks and calls everything else
`road`, so Liberty gives the US its real shields and everywhere else a
plain plate sized to the number - `A 3` in Germany, `E17` in Japan, `M5`
in Australia.  That is Liberty's own arrangement rather than something
added here, and the plate is worth having whichever country it is in: a
route number is small, and a background is what lets it read over rain.

One data quirk is handled.  OSM joins several refs with a semicolon -
Tokyo has roads reading `C4;468` - which is two numbers on a plate cut
for one, so what is drawn is the first.

A paint property this does not know is ignored rather than fatal.  A
style is data from somewhere else, and refusing to draw a map over one
unknown key would be the wrong trade.

## What it costs, and the machine that decides

Drawing a map is real work, and all of it is Python: through PyQt on an
ARMv6 core a single `QPointF` costs about 135 microseconds where a tuple
costs 3, and a view has tens of thousands of vertices.  Measured at zoom
7 on the two radar sizes a 1080p clock actually has - the classic page's
370x352 and the bigmaps page's 754x850:

| | `terrain` 370x352 | `liberty` 370x352 | `terrain` 754x850 |
|---|---|---|---|
| a desktop | 56 ms | 110 ms | 153 ms |
| Pi 4, Bullseye, arm64 | 380 ms | 690 ms | 1.1 s |
| Pi Zero W, ARMv6 | 7.7 s | 14.2 s | **22.7 s** |

Decode and draw only, with the tiles already in hand.

Cutting the style is separate and is paid **once per style for the run**,
not per map: on a Zero, 0.5 seconds for a `layers:` list of seven groups
and 0.7 for one naming all twenty, against 15 seconds to draw untrimmed
Liberty at the smaller of those two sizes.  Two radars sharing a style
pay it once between them.

**So the drawing is done in slices**, forty milliseconds at a time, and
the event loop is handed back between them.  Measured on a Zero, with a
timer ticking five times a second beside the drawing:

| Pi Zero, 370x352 | drawn in | ticks that fired | worst stall |
|---|---|---|---|
| all at once | 9.0 s | **1** | 9.0 s |
| in slices | 7.7 s | **24** | 0.5 s |

The map appears when it is finished - a fraction of a second on a Pi 4,
several seconds on a Zero - and until then the region holds whatever was
there, the same as any map that has not arrived yet.  What the slicing
buys is that the clock keeps running meanwhile instead of stopping dead.

**A stall is one feature.**  A slice can only be as short as the last
thing it started, and a lake with hundreds of vertices cannot be
interrupted partway through: half a second on the classic radar, and
**2.2 seconds** on the bigmaps one at 1080p, where the same lake covers
five times the pixels.  A Pi Zero driving a 1080p bigmaps page is the
corner where this is worst - 23 seconds to draw, and while it draws the
clock ticks 81 times where 117 were due, so it runs at about two-thirds
speed rather than stopping.  The fix is the one above: fewer groups in
`layers:`, or a smaller screen.

That is also the order to reach for when a map is too slow: fewer groups
in `layers:` before anything else.  `water` is the expensive one on a
lake-covered map and `land` is the expensive one everywhere, which is why
neither `terrain` nor `roads` draws `land` at all.
