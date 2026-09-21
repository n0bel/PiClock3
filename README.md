# PiClock3

PiClock3 is a full-screen clock for a Raspberry Pi, on a wall or on a desk.
It draws the time on an analog or a digital face, the date, the current
conditions from a nearby airfield or a weather service, a forecast several
days out, sunrise and sunset and the phase of the moon, and animated weather
radar over a base map.  It steps through as many pages as you give it, and
what is on them, where each thing sits and how it looks are configuration
rather than code.

It is a complete rewrite of PiClock (https://github.com/n0bel/PiClock), in
Python 3 and PyQt5, and much more modular and less monolithic.

![PiClock3 running examples/default.yaml](https://raw.githubusercontent.com/n0bel/PiClock3/main/Pictures/2026-09-05_default.jpg)

That is `examples/default.yaml` as it ships, on the `classic` layout and the
`circuit` theme - and on a Pi Zero W, which is the least hardware that will
run it.

## Installing

[docs/INSTALL.md](docs/INSTALL.md) takes a fresh Raspberry Pi to a clock
that starts itself at boot.  It runs on Raspberry Pi OS Bullseye, Bookworm
and Trixie, 32-bit or 64-bit, from a Pi Zero W up.

## Status

PiClock3 runs every day on real hardware, and the shipped examples run as
they are.  It is still growing, so plugin, layout and theme formats can
change.

Bugs, requests and plans are in the issues:
https://github.com/n0bel/PiClock3/issues.  If you want to build
something, the ones marked
[help wanted](https://github.com/n0bel/PiClock3/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
are asking for exactly that.  The original PiClock is at
https://github.com/n0bel/PiClock, and SerBrynden keeps a fork of it at
https://github.com/SerBrynden/PiClock.

## The example configurations

Everything under `examples/` is there to be read and copied, never loaded
by itself.  `examples/default.yaml` is the one to start from; most of the
rest are the same clock wearing a different theme, or showing one feature,
so you can see what changes without editing anything - run one directly
rather than copying it:

```
python3 PyQtPiClock3.py examples/meadow.yaml
```

| | |
|---|---|
| `examples/default.yaml` | two pages, two themes - `circuit` for the clock, `stag` for the maps |
| `examples/circuit.yaml` | orange circuitry on black, light-blue clock |
| `examples/stag.yaml` | a stag at sunset |
| `examples/archer.yaml` | an archer against an orange sky |
| `examples/meadow.yaml` | butterflies over a bright meadow, dark-blue clock |
| `examples/hairline.yaml` | the stag background with thin, hard-edged frames |
| `examples/london.yaml` | the Thames at night - and the same clock somewhere else: London, British English, its own timezone |
| `examples/berlin.yaml` | the same clock in German - `language: de`, metric, Berlin's timezone |
| `examples/digital.yaml` | a digital face instead of hands, and what a theme reaches without being asked |
| `examples/gallery.yaml` | the clock page works through six shipped backgrounds in turn; the maps page holds one |
| `examples/australia.yaml` | Sydney - the southern hemisphere, where December is midsummer |
| `examples/arctic.yaml` | Tromso, above the Arctic Circle: months with no sunrise to print |
| `examples/mcmurdo.yaml` | McMurdo, as far the other way, under a theme whose art is generated rather than photographed |
| `examples/clockwall.yaml` | six faces and six city names, the wall behind a hotel desk |
| `examples/openfreemap.yaml` | the same clock with no `apikeys:` line at all - the base map is drawn here rather than fetched as a picture |
| `examples/bluemarble.yaml` | NASA's Blue Marble under the radar, at Flagstaff where forest meets desert |
| `examples/clouds.yaml` | radar beside the clouds - LibreWXR's satellite frames, on maps of their own |
| `examples/mapstyles.yaml` | four radars, four ways of writing a map style |
| `examples/captions.yaml` | four radars, four ways of captioning one |
| `examples/minimal.yaml` | the smallest clock that works, and a place to start from |
| `examples/everything.yaml` | the other end: every provider and every setting each plugin takes, written out with what each one does.  For reading rather than copying |
| `examples/ApiKeys.yaml` | the keys file to copy, with links to where to get one |

`Config.yaml` and `ApiKeys.yaml` are ignored by git, so what you write
stays yours.  A plugin can ship an `examples/` folder of its own, along with
`themes/`, `layouts/`, `units/` and `languages/`, so it arrives complete
rather than as code with a list of things to fetch separately.

## Trying something without editing anything

### Any setting, from the command line

Any setting in a config can be given on the command line, which is how to
answer "what would it look like if" without editing a file and putting it
back:

```
python3 PyQtPiClock3.py examples/london.yaml --set units=default
python3 PyQtPiClock3.py Config.yaml --set location.timezone=Europe/Oslo
```

The key is dotted for anything nested, and the value is read as yaml - `4` is
a number, `true` is a boolean, and a word starting with `#` is a color rather
than a comment.

`theme:` and `layout:` are blocks of their own, laid over whichever theme or
layout each page names, so either can be tried without touching it:

```
--set theme.default.color=#ff8800
--set theme.borders.default.width=0.03
--set layout.regions.clock.width=0.4
```

A plugin is reached the same way a theme reaches one, through its kind:

```
--set kind-settings.radar-frames.palette=4
--set kind-settings.digital-clock.font-weight=300
```

### Another time

`--at` starts the clock at another time and lets it run on from there, which
is the only way to see a polar night in August:

```
python3 PyQtPiClock3.py examples/mcmurdo.yaml --at 2026-06-21
python3 PyQtPiClock3.py examples/arctic.yaml  --at "2026-12-21 13:45"
```

It is an offset rather than a fixed moment, so the seconds still run.  Only
the clock moves: the radar still shows what the frame server has, because
that is all it has.  `start-at:` in a config does the same permanently.

`--help` prints all of it, and
[docs/COMMAND-LINE-OPTIONS.md](docs/COMMAND-LINE-OPTIONS.md) explains why
they are there.

## Where a setting comes from

### The order of precedence

A widget's settings are assembled from several places, each having the last
word over the one before:

1. the plugin's own `config.yaml`, beside its code
2. the theme's `default:`, for the five names Qt owns - `color`,
   `background-color`, `font-family`, `font-style` and `font-weight`
3. the theme's `kind-settings:`, then its `plugin-settings:`
4. the config's `kind-settings:`, then its `plugin-settings:`
5. the widget's own entry under `widgets:`

So a theme colors everything by saying `color:` once, a config overrules the
theme without editing it, and one widget overrules both by naming a value
itself.  `--set` writes into the config, which is why it beats a theme.

### Colors and fonts

Those five Qt names then travel two roads, neither needing the plugin's
help.  The theme's `default:` goes on the page, and Qt hands its colors and
fonts down to everything drawn there.  Whatever resolved for one widget goes
on that widget's region, and reaches whatever it draws.  Nearer wins, so a
`kind-settings` color beats the page's - and a widget that names one itself
beats both.  `background-color` takes the first road only: CSS does not
inherit it, so a region background belongs in a theme's `styles:`.

`effect:` - a glow or a drop shadow - is an ordinary setting on the same
tiers, applied by core to a widget's regions.  See
[docs/WRITING-A-THEME.md](docs/WRITING-A-THEME.md).

## What ships

A widget draws in a region a layout named.  A provider supplies data to
widgets and occupies no region of its own.

### Widgets

| widget | |
|---|---|
| `AnalogClock`, `DigitalClock` | the clock face, and any ticking line of text |
| `Date` | the date across the top |
| `Astral` | sunrise, sunset and moon phase |
| `CurrentConditions` | what the weather is doing now |
| `Forecast` | the next few hours, then the next few days |
| `MapLoop` | an animated radar over a base map |
| `Text` | words in a region - a city name over a clock face, a note under a map |

### Providers

| provider | |
|---|---|
| `Metar` | an observation from an airfield.  No key, no forecast |
| `OpenMeteo` | conditions and forecast from a model.  No key |
| `OpenWeatherMap`, `TomorrowIO` | the same three answers, for people who already have one of those keys.  Both free plans |
| `Mapbox`, `GoogleMaps` | the base map under a radar - each needs a key |
| `OpenFreeMap` | the base map, or the roads over one.  **No key**: it sends vector tiles and the cartography is drawn here, so the colors are the theme's - and what sits under them can be NASA's Blue Marble, also keyless.  See [WRITING-A-MAP-STYLE.md](docs/WRITING-A-MAP-STYLE.md) |
| `RainViewer`, `LibreWXR` | radar frames.  Neither needs a key |
| `LibreWXRSatellite` | infrared satellite frames - the clouds.  No key |

### Units

Units are core rather than a weather feature.  `units: metric` in a config
picks a set, and the table behind it lives in `PiClock3/units/` - what ships
is in `sets.yaml` there - found the way themes and layouts are found, so a
`units/` folder of your own or a plugin's merges over it.

### Languages

Languages are core in the same way.  `language: de` picks one, and a
language is one file in `PiClock3/languages/` - what ships is what is in that
folder - found on the same search path, so a `languages/` folder of your own
or a plugin's merges over it.  A file holds the codes it answers to (`code:
[de, deu, ger]`), the words, and a table of weather conditions.

Without `language:` the clock speaks the machine's language - `LANG` and
its relatives on a Pi, the user's language on Windows - and `language:
system` says the same thing outright.  A language no file answers to is
English, and the log says which it tried.  A regional code like `de-AT` uses
its own file when there is one and `de` when there is not; a regional file
writes only what differs and takes the rest from its base language.

Day and month names come from the system rather than from that table, and the
language file lists the locales that mean it, so a config needs nothing
further.  On a Pi the locale has to exist first - `sudo dpkg-reconfigure
locales` - and if none of them is installed the names stay in English and the
log says so.  Setting `locale:` in a config overrides all of them.

### Weather sources

`CurrentConditions` and `Forecast` do not care which source they are given.
A weather provider answers three questions - what it is doing now, the next
hours, the next days - and answers empty for what it cannot know: a station
has no forecast, so pointing `Forecast` at one draws nothing.  Point them at
different sources if you like: a real observation from the field down the
road, beside a model's forecast.

Open-Meteo needs no key, but its data is CC-BY, so `Forecast` prints its
name at the bottom of the column.  A station's credit is the station id, which
is what the conditions block shows beside the observation time.

RainViewer stopped serving tiles above zoom 7 and returns a "Zoom Level Not
Supported" image instead of an error, so a close radar needs `librewxr`.

## Extending it

### Guides

A guide for each question:

| | |
|---|---|
| [docs/WRITING-A-CONFIG.md](docs/WRITING-A-CONFIG.md) | your own `Config.yaml` - pages, location, providers, widgets, settings |
| [docs/WRITING-A-THEME.md](docs/WRITING-A-THEME.md) | what a page looks like - colors, fonts, frames, backgrounds, which art the widgets use |
| [docs/WRITING-A-LAYOUT.md](docs/WRITING-A-LAYOUT.md) | where things go - regions, fractions, repeats |
| [docs/WRITING-A-PLUGIN.md](docs/WRITING-A-PLUGIN.md) | a widget that draws or a provider that fetches, and what a theme can reach in it |
| [docs/WRITING-A-SCHEMA.md](docs/WRITING-A-SCHEMA.md) | describing what a plugin accepts, so something other than a reader can act on it |
| [docs/WRITING-A-LANGUAGE.md](docs/WRITING-A-LANGUAGE.md) | a translation - one yaml file, no code |
| [docs/WRITING-UNITS.md](docs/WRITING-UNITS.md) | the conversion table and the named sets that pick from it |
| [docs/FRAME-ART.md](docs/FRAME-ART.md) | drawing the nine-slice sheets a frame is made of |
| [docs/MARKER-ART.md](docs/MARKER-ART.md) | drawing the pins a radar puts on a map |
| [docs/COMMAND-LINE-OPTIONS.md](docs/COMMAND-LINE-OPTIONS.md) | `--set` and `--at`, and why a clock needs them |

### Themes, layouts and plugins

A theme, a layout and a plugin are separate on purpose: any theme works with
any layout, and neither knows what the other is called.

Each is a git repository cloned into its own folder, and each may carry some
of the others along with it:

| a published ... | may also hold |
|---|---|
| plugin, in `plugins/` | a layout, a theme, language files, units, its art, examples |
| theme, in `themes/` | a layout, another theme, language files, units, its art, examples |
| layout, in `layouts/` | a theme, another layout, language files, units, examples |

Carrying is not depending: a page still names its layout and its theme
separately.  And **a bundled part can add a name, never replace one** - a
cloned repository cannot quietly become the `classic` your config already
names, and `--check` says so when two folders hold one name.

One thing stays where it is: nothing carries a plugin but a plugin, since
`plugin:` names a module path.

A language file is worth knowing about here even if you speak the one the
clock ships: a plugin uses one to name what it draws, and a theme can use
one to rename what the clock already draws.

### Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) is about contributing to this repository
rather than building on it.

The issues marked
[help wanted](https://github.com/n0bel/PiClock3/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
are the ones where somebody else's hardware or a spare evening would move
things: a weather station on a network I do not own, an ambilight, buttons
and a remote.  Several are a plugin of their own, which is the easiest
place to start - [docs/WRITING-A-PLUGIN.md](docs/WRITING-A-PLUGIN.md)
covers it.

I'll welcome any contributions.


