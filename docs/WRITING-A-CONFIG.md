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
| `location:` | latitude, longitude, timezone, elevation |
| `language:` | which language file the words come from |
| `units:` | which set of units - `default`, `metric`, `SI` or `nautical`, and see [WRITING-UNITS.md](WRITING-UNITS.md) |
| `providers:` | plugins that fetch data and draw nothing |
| `widgets:` | plugins that draw, each in a region its page's layout named |
| `kind-settings:` / `plugin-settings:` | settings for every widget of a kind, or of a plugin |
| `folders:` | named paths a setting can expand |
| `logging-level:` | `debug`, `info`, `warning` |
| `logging-rotate:` / `logging-max-size:` / `logging-keep:` | when the log is rolled, and how many are kept |
| `geometry:` | run in a window of a given size rather than filling the screen |
| `apikeys:` | pulled in from `ApiKeys.yaml` with `!include` |
| `locale:` | overrides the locale the language file asks for |
| `start-at:` | start the clock at another moment and let it run on |
| `theme:` / `layout:` | a block laid over whichever theme or layout a page names |
| `styles:` | named Qt properties, the config's own |

**Write a key once.**  yaml lets the second one win without a word, so a
config saying `location:` twice would quietly draw the weather for the
wrong place.  A key written twice is a problem instead, naming both lines,
and the clock will not start on it.  It catches the commonest way of
making one: commenting a setting out to try another, and leaving both.

## `pages:`

```yaml
pages:
  clock-page: {order: 0, layout: classic, theme: circuit}
  maps-page:  {order: 1, layout: bigmaps, theme: circuit}
```

Each page names a **layout**, which says where the regions are, and a
**theme**, which says what they look like.  `order` is the sequence they
rotate in; the space bar steps through them, and so does a click or a tap.

The names on the left are yours.  What matters is that the names under a
layout's `regions:` are the ones your widgets ask for - `classic` has
`current`, `maps`, `clock`, `date`, `bottom` and `forecast`, so those are
where a widget on that page can sit.  One that repeats offers its cells as
well, `maps.1` and `maps.2`, which is what a single radar names.

## `location:`

```yaml
location:
  latitude: 45
  longitude: -93
  timezone:
  elevation:
```

Only the two coordinates are needed; the other two can be left blank or left
out.

A blank `timezone:` means the machine's own, which is right when the clock
sits where it is pointed.  Name a zone - `Europe/London`, `Pacific/Auckland` -
when it does not.

A clock face takes a `timezone:` of its own as well, which is how six faces
on one page show six cities - `examples/clockwall.yaml` is that wall.  It
defaults to the location's, so a page that says nothing keeps the one zone
it always had.

A blank `elevation:` lets a weather service work it out from the
coordinates, which it does better than a guess - give one only where that is
wrong, as it is on a peak.  A bare number is meters however `units:` is set,
because a set converts what is shown and never what you type; write `5280ft`
to say otherwise, or any other unit `altitude` defines in
[WRITING-UNITS.md](WRITING-UNITS.md).

Widgets reach these with `{location.latitude}`, so a radar centered on the
clock's own position does not repeat the numbers.

## `providers:` and `widgets:`

A **provider** fetches and draws nothing.  A **widget** draws in a region.
Which section an entry is written in is what says which it is, and `--check`
says when one is in the wrong one.

```yaml
providers:
  openmeteo: {plugin: PiClock3.OpenMeteo}
  metar:     {plugin: PiClock3.Metar, METAR: KMSP}
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

  forecast:
    plugin: PiClock3.Forecast
    region: forecast
    forecast-provider: openmeteo      # the same idea, its own key
```

Which is how one clock shows a real observation from the field down the road
beside a model's forecast: point two widgets at different providers.

A provider nothing points at is not loaded at all, and the log says which
were left out.  Loading one starts it - some fetch the moment they start,
and some go on asking every few minutes - so listing an alternative you
are not using, the way the shipped examples list both radar sources,
costs nothing.

Each widget that needs a provider has its own key for it, so the two above
can name different ones.  A radar names two, `base-provider:` for the map
underneath and `frame-provider:` for the weather over it.  A name that is
not in `providers:` stops the clock at startup with a `KeyError` holding
the name it could not find - spelling is worth checking there first.

The two are not interchangeable, and swapping them reads perfectly well:
a base map answers with one picture and a frame source with a stamped
series of them.  `--check` catches that before the clock does.

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
| `current-conditions`, `forecast`, `date`, `almanac`, `text` | the rest of the widgets |
| `basemap`, `radar-frames`, `weather-source`, `forecast-source` | the providers |

So a kind is what a thing *is*, and several plugins can share one - Mapbox and
GoogleMaps are both `basemap`, so a setting under that reaches whichever you
use.  `plugin-settings:` is the same idea keyed by the plugin instead, for
when you mean one implementation and not the other.

A widget's own entry still wins over both, which is how one radar differs from
the rest while the other three take the shared block.

A block for a kind nothing here wears merges into nothing and is left
alone, since a config shared between clocks keeps blocks for the other
one's plugins.  A misspelled kind looks the same, so check it against the
table above when a block seems to do nothing.

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

**`center:` and `zoom:` point the map.**  Unset, as above, a map sits on the
clock's own `location:` at zoom 7.  Between the two sits the frame provider:
a service covering one country knows its extent better than a config does,
so if it declares a `center:` or a `zoom:` of its own, a map that says
nothing takes it.  Say either on the widget and yours wins.

**`style:` is the base map itself**, named in whatever vocabulary the
provider uses: a Mapbox style id like `mapbox/satellite-streets-v10`, one
of Google's four maptypes - `roadmap`, `satellite`, `terrain` or `hybrid` -
or, for `OpenFreeMap`, one of `terrain`, `liberty`, `roads`, `light`,
`daylight`, `midnight` and `midnight-roads`, or a whole block describing
one.  That last provider draws the map here rather than fetching a
picture of it, so its styles are the only ones a config or a theme can
recolor; the block is
[WRITING-A-MAP-STYLE.md](WRITING-A-MAP-STYLE.md).
The two do not translate, so a config that changes `base-provider:` and
leaves `style:` alone is naming something the new provider has never heard
of.  Mapbox has no such style and no map arrives - the plain gray described
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

**If the base map cannot be had, the radar is drawn on plain gray** and the
map keeps asking for it - quickly at first, then backing off to hourly.
Nothing is credited on the gray, because it is nobody's imagery.  A map that
has no radar yet still draws everything else, so the markers and the labels
do not wait on the weather.

## `markers:` - pins on a radar

A list of places to draw a picture.  Only `location:` is required; a marker
with nothing else drawn is a gray teardrop.

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

**`color:`** tints the picture.  The shipped markers are gray so that
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

Say nothing and you get the line every map carries - the frame's time and
who supplied it, `14:20 LibreWXR`, top left and outlined - plus the map's
`label:` top right if it has one.  Only the frame provider is named there:
radar tiles carry nothing of their own, while a base map arrives with its
own logo and credit already drawn into it.

**`caption-time-format:` is the time on that line**, `'%H:%M'` unless you
say otherwise, and `'%-I:%M %p'` for a twelve-hour clock.  Write it the
glibc way and it is turned round for Windows.  It reaches only the built-in
line; a `captions:` list of your own carries its formats inside its braces.

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

## What the widgets take

Everything a plugin accepts is declared in its own `config.yaml` beside its
code, with a default for each - **that file is the list**.  These are the
ones worth saying out loud.  Any of them goes where any other setting goes:
on the widget, in `kind-settings:`, or in a theme.

**Read it, do not edit it.**  It is the plugin's declaration of what it
takes and what it ships, which is what a configuration editor will read to
know your options.  Change one to suit your clock and the change is invisible
to anyone reading your config, and gone the next time you update.  Your own
config has the last word over it, which is the whole point of the order
above.

**Any widget that shows a measurement** takes `precision:`, a block keyed by
quantity, for when the unit table's own answer is wrong for the space:

```yaml
  current-conditions:
    plugin: PiClock3.CurrentConditions
    region: current
    precision:
      temperature: 0        # whole degrees in a narrow column
      pressure: 2
```

The quantities are `altimeter`, `altitude`, `depth`, `direction`,
`distance`, `height`, `pressure`, `rate`, `speed` and `temperature`.  Each
unit in `PiClock3/units/quantities.yaml` carries a precision of its own -
one decimal for °C and °F - and this overrides it for one widget without
touching the table everything else reads.  A quantity the block does not
name keeps the table's answer.  The table, and how to add to it, is
[WRITING-UNITS.md](WRITING-UNITS.md).

**`PiClock3.Forecast`** draws one cell of its region per period.

| | |
|---|---|
| `hourly` `daily` | how many cells of each - 3 and 6.  Asking for more than the region has warns and draws what fits |
| `hourly-step` | hours between the hourly cells, 3, so three of them reach nine hours out |
| `hour-format` `day-format` | strftime for the corner of a cell, `%A %-I:%M%p` and `%A` |

**`PiClock3.CurrentConditions`**

| | |
|---|---|
| `observed-format` | strftime for when the reading was taken, `%H:%M`, followed by whatever the source calls itself |

**`PiClock3.Astral`**

| | |
|---|---|
| `polar-format` | drawn instead of `format:` on a day the sun neither rises nor sets, where the usual line has no time to put in and would print its own braces.  It is why `arctic.yaml` and `mcmurdo.yaml` read correctly for the months either place has no sunrise |

**`PiClock3.DigitalClock`**

| | |
|---|---|
| `extra-font-attributes` | anything Qt understands that has no setting of its own, put into the stylesheet as written |

**`PiClock3.Date`**

| | |
|---|---|
| `format` | strftime for the date line.  The default is `{language.date-format}` - the language's own line, which knows where the day belongs in the sentence.  Beside strftime's codes it understands `{day}`, the day with no leading zero, and `{sup}`, the ordinal after it: `en` writes `%A %B {day}<sup>{sup}</sup> %Y` and gets *Thursday September 3rd 2026* |

**`PiClock3.Text`** draws words in a region - a caption, a name over a clock
face, a line travelling past.

| | |
|---|---|
| `text` | what to draw.  It is expanded, so `{location.city}` and anything else the clock knows can be written into it.  Blank draws nothing |
| `text-provider` | a plugin supplying the words instead, and saying when they change.  Nothing ships with one; writing one is [WRITING-A-PLUGIN.md](WRITING-A-PLUGIN.md) |
| `overflow` | what to do with a line too wide for its region: `fit` shrinks it, `marquee` travels it past right to left, `clip` lets the edge cut it.  `fit` unless you say |
| `marquee-speed` | how far a marquee travels in a second, in widths of the region, 0.25 |
| `font-size` | a fraction of the region's height, 0.3.  `20px` is used as written, and 0 is as large as fits |

**`PiClock3.AnalogClock`**, **`PiClock3.DigitalClock`**, **`PiClock3.Date`**

| | |
|---|---|
| `timezone` | the zone this face shows.  It defaults to `{location.timezone}`, so a page that says nothing keeps the clock's own zone.  Naming one per face is what makes a wall of them |

**`PiClock3.MapLoop`**, beyond the radar and caption settings above

| | |
|---|---|
| `dwell` | milliseconds a frame is on screen, 200 |
| `hold` | milliseconds to rest on the newest frame before the loop starts again, 1200 |
| `font-family` | the face the captions and the label are drawn in.  Empty, the default, takes the page's |

**Providers**

| | |
|---|---|
| `refresh` | minutes between asks - 10 for `Metar`, whose stations report about hourly, and 30 for the three forecast sources, whose free plans are generous rather than unlimited.  `TomorrowIO` is the one with a ceiling worth knowing: 25 requests an hour, and it spends two each time round |
| `METAR` | the airfield `Metar` reads, by ICAO id - `KMSP` unless you say, and the nearest field to you is almost certainly better.  It is also what the reading is credited as, which is why the conditions block ends in a station id rather than a service name |
| `forecast-days` | how many days a forecast source is asked for.  9 for `OpenMeteo`, which will give up to 16, and 6 for the two keyed ones - six being what the forecast widget asks for.  `OpenWeatherMap` reaches it by rolling up 120 hours of three-hour steps, and `TomorrowIO` sends six days outright.  A source that comes up short says so in the log, and the fix is `hourly: 4` with `daily: 5` |
| `apikey` | the key `OpenWeatherMap` and `TomorrowIO` need, as `{apikeys.owmapi}` and `{apikeys.tmapi}` - the names v1 used, so keys carry across unrenamed |

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
digital clock's `now`, for instance.  `{this-folder}` is the folder of the
file that said it, so art travels with whatever ships it.

**`{language.*}` follows the language file's own shape.** A word is in the
`strings:` table and reaches as `{language.strings.sunrise}`; a setting
beside the tables reaches by its own name, `{language.date-format}`:

```yaml
format: '{language.date-format}'          # PiClock3/Date/config.yaml
```

The two miss differently, on purpose.  A word nobody has translated yet
comes back spaced and capitalized, so a plugin naming one still reads.  A
setting nobody has comes back empty - a format string is not a word, and one
that answered with its own name would draw `Date-Format` across the clock
and look deliberate.

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

## `logging-level:` and the log file

`debug`, `info` or `warning`, and **`info` when you say nothing**.  Output
goes to `PyQtPiClock3.log` beside the program and to stderr.

`debug` is what the examples ship with; it logs every region's geometry,
every web request with its timing, and what each layout and theme resolved
to.  A start costs about 30 KB of log at `debug` and 5 KB at `info`.

`warning` is quiet to the point of writing nothing at all on a clock that is
working - which is worth knowing before choosing it, since
[reporting a problem](../CONTRIBUTING.md) asks for the log and an empty one
says nothing about what the clock was doing.

```yaml
logging-level: info
logging-rotate: per-run   # per-run or daily
logging-max-size: 10      # MB; 0 for no limit
logging-keep: 7
```

`per-run` rolls the log at every start, so `PyQtPiClock3.log.1` is the run
before this one - which is what makes trying a config four times leave four
logs to compare.  It rolls again at `logging-max-size`, so a clock left up
for months cannot fill the card.

`daily` rolls at midnight instead and **not** on a restart, so several runs
of one day share a file, named `PyQtPiClock3.log.2026-09-07`.  Choose it to
compare one day with another rather than one run with the run before.
`logging-max-size` means nothing under it.

`logging-keep` is how many older logs to hold - runs under `per-run`, days
under `daily`.  All three are read before the log is opened, so a change
takes effect on the run that asks for it rather than the next one.

## `apikeys:`

```yaml
apikeys: !include ApiKeys.yaml
```

`!include` reads another file in where the tag sits, so keys live in one place
and a config can be published without them.  A setting reaches a key by name -
`{apikeys.mbapi}` - which is how a provider gets one without the config
repeating it.

**The name is read from where you started the clock, not from beside the
config.**  That is why every example says `!include ApiKeys.yaml` and they
all get the one file at the top of the checkout, wherever the example
itself lives.  A file that is not there says so, and says where it looked.

Only Mapbox and Google need a key.  Radar frames from RainViewer and
LibreWXR are free, so is the METAR, and so is `OpenFreeMap` - which is
why `examples/openfreemap.yaml` has no `apikeys:` line at all.

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
