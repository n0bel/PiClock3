# PiClock3

> **August 23, 2026 - the configuration format changed and older configs will
> not load.**  Pages now name a layout and a theme instead of including a tree
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

- **There is no forecast plugin yet.**  The `classic` layout reserves a
  nine-cell column down the right hand side for it, so on that layout you
  get nine empty framed boxes.  Everything else on the page works.
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
cp Config-Example.yaml Config.yaml
cp ApiKeys-Example.yaml ApiKeys.yaml
python3 PyQtPiClock3.py
```

PyQt5 comes from apt on purpose.  Installing it with pip builds Qt from
source, which takes hours on a Pi and usually runs out of memory first.

**Python 3.9 is the floor**, which is Raspberry Pi OS Bullseye.  Bullseye is
what this is developed and tested on - Python 3.9.2 with PyQt 5.15.2.  Newer
Raspberry Pi OS should be fine and `requirements.txt` already resolves the
right package versions for it by itself, but it has had less use, so say so
if something breaks.

Then set your own latitude and longitude, and your nearest METAR station, in
`Config.yaml`.  Everything else in it already works.

A key is only needed for the base map under a radar - Mapbox or Google, one
is enough - and `ApiKeys-Example.yaml` says where to get one.  The radar
itself is free either way: neither RainViewer nor LibreWXR wants a key, and
neither does the METAR.

### The example configurations

`Config-Example.yaml` is the one to start from.  Most of the rest are the
same clock wearing a different theme, so you can see what a theme changes
without editing anything - run one directly rather than copying it:

```
python3 PyQtPiClock3.py Config-Example-Meadow.yaml
```

| | |
|---|---|
| `Config-Example.yaml` | two pages, two themes - `circuit` for the clock, `stag` for the maps |
| `Config-Example-Circuit.yaml` | orange circuitry on black, light-blue clock |
| `Config-Example-Stag.yaml` | a stag at sunset |
| `Config-Example-Archer.yaml` | an archer against an orange sky |
| `Config-Example-Meadow.yaml` | butterflies over a bright meadow, dark-blue clock |
| `Config-Example-Hairline.yaml` | the stag background with thin, hard-edged frames |
| `Config-Example-London.yaml` | the Thames at night - and the same clock somewhere else: London, metric, its own timezone |

A theme is one line of a page: `maps-page: {order: 1, layout: bigmaps, theme:
stag}`.  Writing your own is
[PiClock3/themes/FRAME-ART.md](PiClock3/themes/FRAME-ART.md).

Any config of your own is ignored by git, so it stays yours - only
`Config-Example*.yaml` is tracked.

### Plugins that ship and work

A widget draws in a region a layout named.  A provider supplies data to
widgets and occupies no region of its own.

| widget | |
|---|---|
| `AnalogClock`, `DigitalClock` | the clock face, and any ticking line of text |
| `Date` | the date across the top |
| `Astral` | sunrise, sunset and moon phase |
| `Metar` | current conditions, from a METAR station |
| `MapLoop` | an animated radar over a base map |

| provider | |
|---|---|
| `Mapbox`, `GoogleMaps` | the base map under a radar - each needs a key |
| `RainViewer`, `LibreWXR` | radar frames.  Neither needs a key |
| `WeatherCommon` | units, day/night and icon selection |

RainViewer stopped serving tiles above zoom 7 and returns a "Zoom Level Not
Supported" image instead of an error, so a close radar wants `librewxr`.

### Not written yet

* **A forecast plugin.**  This is the big one - `classic` reserves nine cells
  for it and they stand empty until it exists.  Open-Meteo, OpenWeatherMap.
* A current-conditions plugin that is not METAR - the same sources.


I'll welcome any contributions.


