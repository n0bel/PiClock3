# PiClock3

> **August 23 and 24, 2026 - the configuration format changed and older
> configs will not load.**  Pages now name a layout and a theme instead of including a tree
> of blocks, and block names changed with it.  PiClock3 will tell you if it
> sees an older config.  This only affects configurations written before that
> date - see
> [BREAKING-CONFIGURATION-CHANGE-2026-08-23.md](BREAKING-CONFIGURATION-CHANGE-2026-08-23.md).

> Drawing frame art, or writing a theme?  See
> [PiClock3/themes/FRAME-ART.md](PiClock3/themes/FRAME-ART.md).

PiClock3 is a complete rewrite of PiClock (https://github.com/n0bel/PiClock).
It is based on Python3 and PyQt5.  It is also much more modular and less monolithic.

## Work in progress

**This is being published to show the shape of the thing, not because it is
finished.  It does work** - it has been running on real clocks throughout,
and the shipped example configurations run as they are.  But it is not done,
and it is worth knowing what you are getting:

- **There will be bugs.**  Whole areas have had little use outside the
  handful of clocks they were written on.
- **Things will keep moving.**  Plugin, layout and theme formats are settling
  but are not frozen, and a change that breaks configurations is still
  possible - the one on August 23, 2026 was such a change.

If you want a clock to simply rely on today, use the original PiClock
(https://github.com/n0bel/PiClock) or this fork of it
(https://github.com/SerBrynden/PiClock), which is still being updated.  Come
here to see where PiClock is going, to run it, and to say what is wrong with
it.

Ongoing updates to this will be https://github.com/n0bel/PiClock/issues/230

I'll be committing many partially complete commits here as an easy means to
distribute code to my PiClocks for testing.

There is no manual.  What follows is enough to get it running.

Log into your Pi, on the screen or over ssh, as an ordinary user - **not**
as root.  The home directory you land in is where this should go.

```
git clone https://github.com/n0bel/PiClock3.git
cd PiClock3
sudo apt update
sudo apt install python3-pyqt5 python3-yaml
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
cp examples/default.yaml Config.yaml
cp examples/ApiKeys.yaml ApiKeys.yaml
```

**Now edit `ApiKeys.yaml`**, because what you just copied holds the word
`'MAPBOXAPIKEY'` rather than a key.  The base map under a radar is the only
thing that needs one, and either of these will do:

  - Mapbox - https://account.mapbox.com - goes in `mbapi`
  - Google Static Maps - https://console.cloud.google.com - goes in `googleapi`

The example points its radars at Mapbox; if you got a Google key instead,
change `base-provider: mapbox` to `base-provider: googlemaps` in
`Config.yaml`.  Skip this and everything still runs - the radar simply
animates over bare background with no map beneath it.

Nothing else wants a key.  Radar frames are free from both RainViewer and
LibreWXR, and so is the METAR.

Then:

```
python3 PyQtPiClock3.py
```

PyQt5 comes from apt on purpose.  Installing it with pip builds Qt from
source, which takes hours on a Pi and usually runs out of memory first.

**Python 3.9 is the floor**, which is Raspberry Pi OS Bullseye.  Bullseye is
what this is developed and tested on - Python 3.9.2 with PyQt 5.15.2.  Newer
Raspberry Pi OS should be fine and `requirements.txt` already resolves the
right package versions for it by itself, but it has had less use, so say so
if something breaks.

The clock, the date, the almanac, the current conditions, the forecast and
the radar all work at this point - but it thinks it is somewhere else.  The example sits at
45, -93 with KLVN for its METAR, because it has to say something.  Set your
own latitude and longitude and your nearest METAR station in `Config.yaml`.

### The example configurations

Everything under `examples/` is there to be read and copied, never loaded
by itself.  `examples/default.yaml` is the one to start from; most of the
rest are the same clock wearing a different theme, so you can see what a
theme changes without editing anything - run one directly rather than
copying it:

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
| `examples/london.yaml` | the Thames at night - and the same clock somewhere else: London, metric, its own timezone |
| `examples/berlin.yaml` | the same clock in German - `language: de`, metric, Berlin's timezone |
| `examples/ApiKeys.yaml` | the keys file to copy, with links to where to get one |

A theme is one line of a page: `maps-page: {order: 1, layout: bigmaps, theme:
stag}`.  Writing your own is
[PiClock3/themes/FRAME-ART.md](PiClock3/themes/FRAME-ART.md).

`Config.yaml` and `ApiKeys.yaml` are ignored by git, so what you write
stays yours.  A plugin can ship an `examples/` folder of its own, along with
`themes/`, `layouts/`, `units/` and `languages/`, so it arrives complete
rather than as code with a list of things to fetch separately.

### Plugins that ship and work

A widget draws in a region a layout named.  A provider supplies data to
widgets and occupies no region of its own.

| widget | |
|---|---|
| `AnalogClock`, `DigitalClock` | the clock face, and any ticking line of text |
| `Date` | the date across the top |
| `Astral` | sunrise, sunset and moon phase |
| `CurrentConditions` | what the weather is doing now |
| `Forecast` | the next few hours, then the next few days |
| `MapLoop` | an animated radar over a base map |

| provider | |
|---|---|
| `Metar` | an observation from an airfield.  No key, no forecast |
| `OpenMeteo` | conditions and forecast from a model.  No key |
| `Mapbox`, `GoogleMaps` | the base map under a radar - each needs a key |
| `RainViewer`, `LibreWXR` | radar frames.  Neither needs a key |

Units are core rather than a weather feature.  `units: metric` in a config
picks a set - `default`, `metric`, `SI` or `nautical` ship - and the table
behind it lives in `PiClock3/units/`, found the way themes and layouts are
found, so a `units/` folder of your own or a plugin's merges over it.

Languages are core in the same way.  `language: de` picks one - `en` and `de`
ship - and a language is one file in `PiClock3/languages/`, found on the same
search path, so a `languages/` folder of your own or a plugin's merges over
it.  A file holds the codes it answers to (`code: [de, deu, ger]`), the words,
and a table of weather conditions.

Day and month names come from the system rather than from that table, and the
language file lists the locales that mean it, so a config needs nothing
further.  On a Pi the locale has to exist first - `sudo dpkg-reconfigure
locales` - and if none of them is installed the names stay in English and the
log says so.  Setting `locale:` in a config overrides the lot.

`CurrentConditions` and `Forecast` do not care which source they are given.
A weather provider answers three questions - what it is doing now, the next
hours, the next days - and answers empty for what it cannot know: a station
has no forecast, so pointing `Forecast` at one draws nothing.  Point them at
different sources if you like: a real observation from the field down the
road, beside a model's forecast.

Open-Meteo needs no key, but its data is CC-BY, so `Forecast` prints its
name at the foot of the column.  A station's credit is the station id, which
is what the conditions block shows beside the observation time.

RainViewer stopped serving tiles above zoom 7 and returns a "Zoom Level Not
Supported" image instead of an error, so a close radar wants `librewxr`.

### Not written yet

* An OpenWeatherMap provider.  The widgets are ready for one - it only has to
  answer the same three questions `OpenMeteo` does, and say what the sky is
  doing in the same notation.  See CONTRIBUTING.md.
* Wind and humidity in the forecast column; the provider already carries
  them.


I'll welcome any contributions.


