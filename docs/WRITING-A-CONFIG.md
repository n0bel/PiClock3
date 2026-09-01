# Writing a config

`Config.yaml` is the one file that is yours.  It says where the clock is,
which pages it has, and which widgets sit in them.  Everything else - themes,
layouts, plugins, languages - is something the config *names*.

    Config.yaml            yours, beside PyQtPiClock3.py
    ApiKeys.yaml           your keys, kept separate so a config can be shared

Both are in `.gitignore`, so `git pull` never has anything of yours to
conflict with.  Start by copying one:

```
cp examples/default.yaml Config.yaml
cp examples/ApiKeys.yaml ApiKeys.yaml
```

Everything under `examples/` is meant to be read.  A config there can also be
run directly without copying, which is the quickest way to see what a change
does:

```
python3 PyQtPiClock3.py examples/london.yaml
```

## The shape of it

Only `pages` and `widgets` are needed to draw anything.  The rest have
defaults, or do nothing until you want them.

| | |
|---|---|
| `pages:` | which pages exist, and the layout and theme each one wears |
| `location:` | latitude, longitude, timezone |
| `language:` | which language file the words come from |
| `units:` | which unit table - `default`, `metric`, `SI` or `nautical` |
| `providers:` | plugins that fetch data and draw nothing |
| `widgets:` | plugins that draw, each in a region its page's layout named |
| `kind-settings:` / `plugin-settings:` | settings for every widget of a kind, or of a plugin |
| `folders:` | named paths a setting can expand |
| `logging-level:` | `debug`, `info`, `warning` |
| `geometry:` | run in a window of a given size rather than filling the screen |
| `apikeys:` | pulled in from `ApiKeys.yaml` with `!include` |
| `locale:` | overrides the locale the language file asks for |
| `start-at:` | start the clock at another moment and let it run on |
| `theme:` / `layout:` | a block laid over whichever theme or layout a page names |
| `styles:` | named Qt properties, the config's own |

## `pages:`

```yaml
pages:
  clock-page: {order: 0, layout: classic, theme: circuit}
  maps-page:  {order: 1, layout: bigmaps, theme: circuit}
```

Each page names a **layout**, which says where the regions are, and a
**theme**, which says what they look like.  `order` is the sequence they
rotate in; the space bar steps through them.

The names on the left are yours.  What matters is that the regions a layout
`provides:` are the names your widgets ask for - `classic` provides `current`,
`maps`, `clock`, `date`, `bottom` and `forecast`, so those are the regions a
widget on that page can sit in.

## `location:`

```yaml
location:
  latitude: 45
  longitude: -93
  timezone:
```

A blank `timezone:` means the machine's own, which is right when the clock
sits where it is pointed.  Name a zone - `Europe/London`, `Pacific/Auckland` -
when it does not.

Widgets reach these with `{location.latitude}`, so a radar centred on the
clock's own position does not repeat the numbers.

## `providers:` and `widgets:`

A **provider** fetches and draws nothing.  A **widget** draws in a region.

```yaml
providers:
  openmeteo: {plugin: PiClock3.OpenMeteo}
  metar:     {plugin: PiClock3.Metar, METAR: KLVN}
  mapbox:    {plugin: PiClock3.Mapbox}
  librewxr:  {plugin: PiClock3.LibreWXR}

widgets:
  clock: {plugin: PiClock3.AnalogClock, region: clock}
  date:  {plugin: PiClock3.Date, region: date}
```

Providers are loaded first, because a widget names the providers it draws
with and they have to exist by then.  The names on the left are yours again,
and they are what a widget refers to:

```yaml
  current-conditions:
    plugin: PiClock3.CurrentConditions
    region: current
    conditions-provider: metar        # the name from providers:
```

Which is how one clock shows a real observation from the field down the road
beside a model's forecast: point two widgets at different providers.

A repeat gives a layout several regions from one entry, named `maps.1`,
`maps.2` and so on.  A widget takes one cell, or the whole set - `Forecast`
fills one cell per hour or day.

## Settings, and which one wins

A widget's settings are assembled from several places, each having the last
word over the one before:

1. the plugin's own `config.yaml`, beside its code
2. the theme's `default:`, for the five names Qt owns
3. the theme's `kind-settings:`, then its `plugin-settings:`
4. the config's `kind-settings:`, then its `plugin-settings:`
5. the widget's own entry under `widgets:`

### `kind-settings:` belongs to themes.  A config may borrow it

These two blocks were made for themes, and a theme has no alternative to
them.  It cannot name your widgets, because you chose those names - one
person's radar is `radar1` and another's is `north`.  So a theme names what a
thing *is* instead:

```yaml
# PiClock3/themes/circuit/theme.yaml
kind-settings:
  analog-clock:       {clock-images-folder: lightblue}
  current-conditions: {icons-folder: icons-lightblue}
  forecast:           {icons-folder: icons-lightblue}
```

Every shipped theme has a block like that, and it is the only way one can say
which hands a clock draws or which icons a forecast uses.

**The same two blocks work in a config**, where they are a convenience rather
than a necessity: you *can* name your widgets, so anything written in one
could have been written on the widget itself.  What they save is repetition -
four radars on two pages is what most clocks have, and that is the difference
between saying `frame-provider` once or four times.

**The shipped examples do not use them.**  Every setting sits on the thing it
affects, so a radar's entry shows everything about that radar in one place and
can be edited without knowing this section exists.  Reach for `kind-settings:`
in a config when the repeating annoys you, which is a fine reason and a later
one.

**`radar` is not the plugin's name.**  It is the plugin's *kind*, declared in
its own `config.yaml`:

| kind | plugin |
|---|---|
| `radar` | `MapLoop` |
| `analog-clock`, `digital-clock` | the two clock faces |
| `current-conditions`, `forecast`, `date`, `almanac` | the rest of the widgets |
| `basemap`, `radar-frames`, `weather-source`, `forecast-source` | the providers |

So a kind is what a thing *is*, and several plugins can share one - Mapbox and
GoogleMaps are both `basemap`, so a setting under that reaches whichever you
use.  `plugin-settings:` is the same idea keyed by the plugin instead, for
when you mean one implementation and not the other.

A widget's own entry still wins over both, which is how one radar differs from
the rest while the other three take the shared block.

**This is also the answer to "I edited a shipped file and an update
overwrote it".**  Anything a plugin, theme or layout carries can be reached
from the config instead, in a file `git pull` will not touch.

## What a radar draws

A `MapLoop` is several things stacked and flattened into one picture per
frame, bottom to top: the base map, the radar, an overlay if you asked for
one, your markers, the base map's own logo and credit, and the captions.

```yaml
widgets:
  radar1:
    plugin: PiClock3.MapLoop
    region: maps.1
    base-provider: mapbox
    frame-provider: librewxr
    style:           serbrynden/cmtb05qoy000401sk73c24q61
    overlay-style:   serbrynden/cmtb066o1000l01snc11ne90m
    overlay-opacity: 1.0
    frame-opacity:   1.0
```

**`style:` is the base map itself**, named in whatever vocabulary the
provider uses: a Mapbox style id like `mapbox/satellite-streets-v10`, or one
of Google's four maptypes - `roadmap`, `satellite`, `terrain` or `hybrid`.
The two do not translate, so a config that changes `base-provider:` and
leaves `style:` alone is naming something the new provider has never heard
of.  Mapbox has no such style and no map arrives - the plain grey described
below.  Google answers 200 and quietly draws a roadmap instead, so
`GoogleMaps` checks the name against the four first and says in the log what
it did.

**Say nothing and the provider uses its own** - satellite streets for
Mapbox, hybrid for Google, each declared in the plugin's `config.yaml` and
reachable from your config like anything else a plugin carries.  Most of the
shipped examples say nothing, which is what lets them run on either
provider: name a style and the config belongs to the one that understands
it.

**`overlay-style:` is a second base map drawn *over* the radar**, so the
boundaries, roads and place names a storm would otherwise bury stay readable.
It is a style whose ground and water are transparent, leaving only the lines
and labels.  Name none and no such layer is built at all.
`overlay-provider:` takes it from a different provider than the base map;
unset, it uses the same one.

**`frame-opacity:` fades the radar instead**, for a base map worth seeing
through.  It is the other way to solve the same problem, and it costs you
some of the weather: below about 0.45 the light returns start to disappear.

Both composite once as the picture arrives rather than on every repaint, so
neither costs anything while the loop runs.

**A base map's own logo and credit are lifted back over the radar**, because
the radar would otherwise cover them and both Mapbox and Google say in as
many words that their attribution must not be obscured.  That happens
whatever your captions say.  `ignore-attribution-mask: true` turns it off,
and the provider's terms are the thing to read before you do.

**If the base map cannot be had, the radar is drawn on plain grey** and the
map keeps asking for it - quickly at first, then backing off to hourly.
Nothing is credited on the grey, because it is nobody's imagery.  A map that
has no radar yet still draws everything else, so the markers and the labels
do not wait on the weather.

## `markers:` - pins on a radar

A list of places to draw a picture.  Only `location:` is required; a marker
with nothing else drawn is a grey teardrop.

```yaml
widgets:
  radar1:
    plugin: PiClock3.MapLoop
    region: maps.1
    markers:
      - location:
          latitude: '{location.latitude}'
          longitude: '{location.longitude}'
        image: teardrop-home
        color: red
      - location: {latitude: 44.88, longitude: -93.22}
        image: teardrop-work
        color: '#8cf'
        size: mid
```

A marker outside what the map covers is simply not drawn, which is what lets
one list serve a zoomed-out radar and a zoomed-in one.

**`image:`** names the picture.  A bare name comes from the set the radar
draws from, so `teardrop-home` finds the shipped one and a theme that ships
a file of that name stands in for it.  A name with a path in it is read from
where it says, and `.png` is added if you leave the extension off.  Six
ship: `teardrop`, `teardrop-dot`, `teardrop-home`, `teardrop-work`,
`teardrop-school` and `teardrop-family`.

**`size:`** is how tall the picture is drawn.  A bare number is a fraction of
the map's height and one with units is used as written, the same rule a
caption's size follows.  `small`, `mid` and `tiny` are names for three
proportions of the default.  A fraction rather than a count of pixels
because a clock's radars are not one size: the classic page's is about a
third the height of the bigmaps one, and a pin should take the same share of
each.  `marker-size:` on the radar is what a marker that says nothing gets,
so a map full of pins is sized once rather than pin by pin; it defaults
to 0.2.

**`color:`** tints the picture.  The shipped markers are grey so that
multiplying them by your color keeps their shading, and the symbol inside
each is black, which no color changes - that is why the house stays black on
a red pin.  A picture already colored can only be darkened by this.

**`visible:`** drawn unless it is set to something other than 1, so
`visible: false` puts a marker away without deleting it.

The middle of the picture is what lands on the location.  Drawing your own,
and what that rule means for how you draw it, is
[MARKER-ART.md](MARKER-ART.md).

## `captions:` - text over a radar

A `MapLoop` draws its own text, composited into each frame rather than laid
over it, so nothing that happens to the radar can fade it or cover it.

Say nothing and you get the line every map carries - the frame provider's own
stamp, `14:20 LibreWXR`, top left and outlined - plus the map's `label:` top
right if it has one.  Only the frame provider is named there: radar tiles
carry nothing of their own, while a base map arrives with its own logo and
credit already drawn into it.

**`label:` is a name for the map**, for a clock showing more than one and no
other reason - unset, nothing is drawn.  Three settings dress it:

```yaml
widgets:
  radar2:
    plugin: PiClock3.MapLoop
    region: maps.2
    label: 'Close in'
    label-size:    0.10     # a fraction of the map's height
    label-color:   '#bef'
    label-outline: true     # black or white, taken from label-color
```

`label-outline:` is off unless asked for, and a color there names one
outright instead of deriving it.  It is worth asking for over a base map
light enough to swallow the text: the pale default suits satellite imagery
and disappears on snow, which is why `examples/mcmurdo.yaml` turns it on.
The line above it is outlined already, because that one has to survive
whatever the radar puts underneath.

Writing a list replaces that one rather than adding to it:

```yaml
widgets:
  radar1:
    plugin: PiClock3.MapLoop
    region: maps.1
    captions:
      - text: '{plugin-data.frame-time:%H:%M} {plugin-data.frame-attribution}'
        left: 0.02
        top: 0.02
        size: 18px
        outline: true
      - text: 'Regional'
        right: 0.02
        top: 0.02
        size: 0.05
        color: '#bef'
      - '{location.latitude}, {location.longitude}'
```

**A caption is placed the way a layout places a region**, against the map
instead of against the page: `left`, `right`, `top`, `bottom`,
`horizontal-center` and `vertical-center`, all fractions, and a side that
would run off an edge is held at it.  It needs no `width` or `height` - the
text's own size is what gets placed.

| | |
|---|---|
| `text` | the only one needed.  Expanded when it is drawn, so `{...}` reaches anything |
| `left` `right` `top` `bottom` | fractions of the map, as in a layout |
| `horizontal-center` `vertical-center` | offset from the middle, as in a layout |
| `size` | a bare number is a fraction of the map's height, one with units is used as written |
| `color` | anything Qt reads as a color |
| `outline` | `true` for one derived from the text's own color, or name one.  Absent means none |

A bare string, as the third entry above, is an entry with everything else left
to the defaults - top left, `caption-size` and `caption-color`, which are also
the fallback for any entry that omits them.  Only one caption can be the one
that says nothing; give the others a place.

**`size` is a fraction of the map**, the same way a theme's `font-size` is a
fraction of the region it lands in, so a caption keeps its share of a small
radar and a large one.  A clock's radars are not all one size - the classic
layout stacks two and gives each a third of the screen's height, where
bigmaps sets two side by side and gives each four fifths - and a caption that
is a fixed count of pixels is loud on the small one or lost on the large.
The default, `caption-size: 0.06`, is about 12px on a classic radar at
800x600 and 21px at 1080p.

`label-size` means the same thing and always has, which is why it needs no
conversion.  Every size a radar takes is a fraction of the map.

**Nothing moves out of the way of anything.**  The bottom of a map is where a
base map's own logo and credit sit, so a caption put there lands on top of
them.  That is the trade for `bottom: 0.0` meaning the bottom of the map and
nothing else - the alternative was captions shifting by an amount that depends
on which provider drew the map and how big the region is, which no config
could predict.

`text` reaches the whole namespace, and the map publishes into it:
`{plugin-data.frame-time}` is the moment the frame showing was taken and takes
a format, `{plugin-data.frame-caption}` is what the frame provider calls it,
and `{plugin-data.frame-attribution}`, `{plugin-data.base-attribution}` and
`{plugin-data.overlay-attribution}` are what each service is called.

**A list replaces, and cannot be adjusted in part.**  The merge that assembles
settings recurses into blocks but assigns a list outright, so one written on a
widget replaces one written in `kind-settings:` entirely - restate the whole
list rather than expecting to change one entry of it.  `label:` and its three
settings are ignored once a list is given, and the log says so.

**Attribution is the one thing to be careful about.**  A base map's own logo
and credit are lifted back over the radar whatever the captions say, so no
list can lose those; `ignore-attribution-mask: true` turns that off, and the
provider's terms are the thing to read first.  The frame provider is not
protected that way, because radar tiles carry no mark of their own - a list
that never names it leaves RainViewer or LibreWXR uncredited, and the log
warns when one does not.

`examples/captions.yaml` is a clock with all of this on it, one treatment per
radar.

## `locale:`

A language file lists the locales it answers to, and the first one the
machine actually has is used - so a config normally needs nothing here.  Name
one when the machine has a locale the file does not list, or when you want
English words with another language's day names:

```yaml
locale: en_GB.UTF-8
```

On a Pi the locale has to have been generated first, with `sudo
dpkg-reconfigure locales`.  If none of them takes, day and month names stay
in the system default and the log says so.

## `start-at:`

```yaml
start-at: 2026-12-21 13:45
```

Starts the clock at another moment and lets it run on from there, which is
the only way to see a polar night in August.  It is an offset rather than a
fixed time, so the seconds still tick.  Only the clock moves: a radar still
shows what the frame server has.

`--at` does the same for one run.

## `theme:` and `layout:`

A `theme:` or `layout:` block in a config is laid over whichever one each page
names, so either can be adjusted without editing the file it belongs to - or
without owning it at all:

```yaml
layout:
  regions:
    clock: {width: 0.4}

theme:
  default: {color: '#ff8800'}
```

That is what makes somebody else's theme usable when it is nearly right.  It
applies to every page, since every page's theme and layout are merged with
the same block.

## `styles:`

Named sets of raw Qt stylesheet properties, the same idea a theme's `styles:`
carries and reachable the same way by a layout's `style:`.  A theme is the
better home for them - this exists so a config can have the last word.

## Where a value can come from

Anything in braces is looked up when the setting is used, not when the file is
read:

```yaml
center:
  latitude: '{location.latitude}'      # the clock's own position
apikey: '{apikeys.mbapi}'              # what Mapbox/config.yaml says
format: '{plugin-data.now:%H:%M:%S}'   # what the widget published
```

`{location.*}` and `{apikeys.*}` reach the config's own blocks.
`{plugin-data.*}` reaches whatever the widget itself has published - the
digital clock's `now`, for instance.  `{language.*}` reaches the words of the
current language, and `{this-folder}` is the folder of the file that said it,
so art travels with whatever ships it.

A name that is not there comes back empty rather than complaining, so
`{plugin-data.sunrise:%H:%M}` draws nothing on a day the sun does not rise
instead of failing on the format specifier.  That cuts both ways: a brace you
meant literally is eaten too.

## `folders:` - deprecated

```yaml
folders:
  marker: mymarkers
```

**Do not write this in anything new.**  It still works, and no shipped
config uses it any more.

Named paths that a setting can expand.  One thing ever read one: a marker's
`image:` is looked for in `{folders.marker}` before the set its radar draws
from, which is how a config supplied pins of its own before marker sets
existed.  A config that still names it keeps working, and still wins over a
theme's set - having said where its markers come from, it should.

The two ways that replace it: a **set**, which is a folder of pins a theme
names and which restyles every radar at once, or a **path** in a marker's
own `image:`, which is read from where it says.  Both are in
[MARKER-ART.md](MARKER-ART.md).  Left out entirely - the ordinary case - a
marker comes from `PiClock3/MapLoop/markers`.

This is not the same as the search path that finds layouts, themes, units and
languages - those are found by looking in your folder before the shipped one,
and need no entry here.

## `logging-level:`

`debug`, `info` or `warning`.  Output goes to `PyQtPiClock3.log` beside the
program and to stderr.  `debug` is what the examples ship with; it logs every
region's geometry, every web request with its timing, and what each layout
and theme resolved to.

## `apikeys:`

```yaml
apikeys: !include ApiKeys.yaml
```

`!include` reads another file in where the tag sits, so keys live in one place
and a config can be published without them.  A setting reaches a key by name -
`{apikeys.mbapi}` - which is how a provider gets one without the config
repeating it.

Only the base map under a radar needs a key.  Radar frames from RainViewer and
LibreWXR are free, and so is the METAR.

## Trying something before you write it down

Any setting can be given on the command line, which answers "what would it
look like if" without editing a file and putting it back:

```
python3 PyQtPiClock3.py --set location.timezone=Europe/Oslo
python3 PyQtPiClock3.py --set kind-settings.radar.frame-opacity=0.5
```

The key is dotted for anything nested.  See
[COMMAND-LINE-OPTIONS.md](COMMAND-LINE-OPTIONS.md).

## Where to go next

| | |
|---|---|
| [WRITING-A-THEME.md](WRITING-A-THEME.md) | what a page looks like |
| [WRITING-A-LAYOUT.md](WRITING-A-LAYOUT.md) | where things go |
| [WRITING-A-PLUGIN.md](WRITING-A-PLUGIN.md) | a widget or a provider of your own |
| [WRITING-A-LANGUAGE.md](WRITING-A-LANGUAGE.md) | a translation |
