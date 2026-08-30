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

So say a thing once where it applies to everything of a kind:

```yaml
kind-settings:
  radar:
    base-provider: mapbox
    frame-provider: librewxr
```

and the four radars below need not repeat it.  `plugin-settings:` does the
same keyed by plugin rather than kind.  A widget's own entry still wins, which
is how one radar differs from the rest.

**This is also the answer to "I edited a shipped file and an update
overwrote it".**  Anything a plugin, theme or layout carries can be reached
from the config instead, in a file `git pull` will not touch.

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

## `folders:`

```yaml
folders:
  marker: PiClock3/markers
```

Named paths that a setting can expand.  `MapLoop` builds a marker's file
name against `{folders.marker}`, so pointing that at a folder of your own is
how a radar gets a pin you drew without editing anything inside `PiClock3/`.

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
