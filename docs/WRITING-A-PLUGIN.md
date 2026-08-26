# Writing a plugin

A plugin is a folder holding a module and a `config.yaml` beside it.  Drop it
into `plugins` and a config can name it; nothing has to be registered.  Start
from [piclock3-plugin-template](https://github.com/n0bel/piclock3-plugin-template).

They come in two sorts.  A **widget** draws in a region a layout named.  A
**provider** supplies data to widgets and occupies no region of its own -
which is why no theme reaches a provider, and why anything a theme should be
able to say belongs on a widget.

## Where a plugin goes

There is a `plugins` folder beside `Config.yaml`, at the top of the checkout,
and that one is yours.  It is in `.gitignore`, so `git pull` never has
anything of yours to conflict with.

    PiClock3/<Name>/        the core plugins, shipped with the project
    plugins/<name>/         yours and everybody else's

Somebody else's is a git repository, cloned straight in:

```
cd PiClock3
git clone https://github.com/someone/piclock3-tides plugins/tides
```

Then name it in a config, and give the instance a region to draw in:

```yaml
widgets:
  tides:
    plugin: plugins.tides
    region: bottom
```

`plugin:` names the **folder**, not the file - the same shape as the core
plugins, which are named `PiClock3.Astral` rather than
`PiClock3.Astral.Astral`.  So the folder needs an `__init__.py` that lifts
the class into it:

```python
from .Tides import *
```

The loader imports that name and finds the `Plugin` subclass inside by
inspection, so the class can be called whatever suits.  `plugins` itself
needs no `__init__.py`.

Nothing is registered anywhere.  The `config.yaml` next to your code is found
from the imported module rather than from a path anybody writes down - which
is what makes a clone work the moment it lands.

A plugin brings its own `languages/` and `units/` folders with it if it has
them, and both are merged rather than first-wins, so a plugin adds words and
quantities without editing the shipped tables:

    plugins/tides/languages/en.yaml      merged over the shipped English
    plugins/tides/units/quantities.yaml  merged over the shipped quantities

**If you mean to contribute the plugin to PiClock3 itself**, that is the
other folder: put it in `PiClock3/Tides/` alongside the core plugins, name it
`PiClock3.Tides.Tides` in the config, and open a pull request.  Being inside
the package is what makes it ship for everybody, and it is why the two
locations exist rather than one.  See [CONTRIBUTING.md](../CONTRIBUTING.md).

### What a plugin repository holds

    __init__.py         from .Tides import *
    Tides.py            the module, holding a Plugin subclass
    config.yaml         its defaults, and the list of what a theme may set
    README.md           what it does, and any key it needs
    languages/en.yaml   optional, words of its own
    units/*.yaml        optional, quantities of its own

Ship a `README` that says which service it talks to and whether that needs an
account.  A key belongs in the user's `ApiKeys.yaml`, never in your
`config.yaml` - see [Two rules](#two-rules-worth-reading-before-you-publish).

## Weather providers say what the sky is doing, not what to call it

A weather provider answers `current()`, `hourly(count, step)` and
`daily(count)`, and answers empty for whatever it cannot know — a station has
no forecast.  Each entry carries its condition as **WMO code table 4678
notation**, the present-weather codes a METAR is written in, and never as
words:

```python
{'when': ..., 'condition': '-SHRA', 'icon': 'rain', 'temp': 14.0,
 'raw': ...}
```

`-SHRA` is light rain showers.  Turning that into words is the widget's job,
in whatever language the clock is set to, so a provider that hands over
English has made itself untranslatable.  Cloud amount has no 4678 notation,
so a provider with nothing falling reports the METAR sky-cover code instead —
`SKC`, `FEW`, `SCT`, `BKN`, `OVC`.

If your source speaks something else — numeric codes, or its own English —
map it to notation in a table at the top of your plugin, the way
`OpenMeteo.WMO` does.  You do not have to hit an exact 4678 entry: the lookup
gives up detail in a fixed order, so `-SHRABR` still finds "Light Rain
Showers" even though 4678 has no such code.

`icon` is one of the eleven names the shipped icon sets use:

    clear-day     clear-night    partly-cloudy-day    partly-cloudy-night
    cloudy        fog            rain                 sleet
    snow          thunderstorm   wind

`Weather.variant()` swaps a `-day` name for its `-night` one, and
`Weather.daytime()` will tell you which applies from the sun rather than from
the hour.

`raw` is the service's own record for that entry, in whatever shape the
service uses.  It is deliberately not normalized — it exists so that anything
a provider does not translate is still reachable by someone who wants it.
Shipped widgets never read it, and anything that does is knowingly tied to
one provider.

## What a theme can reach in your plugin

Your plugin ships a `config.yaml` beside its code holding its defaults.  A
theme or a config can set any key in it, and can set keys that are not in it
— `kind-settings` merges whatever it is given.  What the file really declares
is what your plugin *reads*.

Five names carry a promise.  **`color`, `background-color`, `font-family`,
`font-style` and `font-weight` are Qt's, and mean here what they mean in
Qt.**  Do not use one of them for anything else — a radar palette called
`color` would be handed a hex string meant for text.  (That is why the frame
providers call theirs `palette`.)

Four of the five — all but `background-color`, which CSS does not inherit —
are put on your region by core, as a `QWidget` rule, from whatever resolved
for your instance.  Qt carries them to everything you draw there.  **So a
widget that only draws text needs none of them in its `config.yaml` and none
of them in the stylesheet it builds.**  `DigitalClock` declares none and its
stylesheet is one line:

```python
props = self.piclock.scaleFont({'font-size': self.config['font-size']},
                               self.clockrect.height())
```

Set one on your own widget only when you want it to differ from what the
region says — an id selector outranks the region's rule, so yours wins.

`font-size` is not among the five: it is a fraction of whatever it sits in,
and your region is not the same height as a label inside it.

### Graphics effects happen without you

A glow or a drop shadow is not a stylesheet property, so none of the above
would carry it.  Core applies `effect:` to your regions before `start()`
runs, and a Qt effect covers a widget's whole subtree and picks up children
made afterwards — so it reaches everything you draw, and **there is nothing
for your plugin to do**.

```yaml
effect: glow 0.125         # blur as a fraction of the region's height
effect: none
```

Two things to know rather than to code.  A widget gets exactly one effect,
so if you ever call `applyEffect()` yourself you replace the one core set.
And the effect renders the whole subtree — for a widget that is alone in its
region that is what you want, but if you draw an icon beside your text, the
icon glows too.

Anything else a theme wants to set it reaches through your **kind**:

```yaml
kind: forecast          # in your config.yaml

kind-settings:          # in a theme, or in a config
  forecast:
    icons-folder: icons-darkblue
```

**A kind means "interchangeable with", not "similar to".**  Plugins sharing
one should take the same settings, so a config can swap them and a setting
means the same thing to each.  `Mapbox` and `GoogleMaps` are both `basemap`;
`RainViewer` and `LibreWXR` are both `radar-frames`.  If yours is not
swappable with anything, give it a kind of its own.

### Read your own config, never the theme

By the time your plugin is built, everything a theme said has been merged
into `self.config`, along with everything the config said over the theme and
everything the instance said over both.  That resolved answer is the only one
that respects what the user asked for.

`self.themeDefault(name)` reaches the page's own answer, and is right only
as a **last resort**, after `self.config` — for a value that is the theme's
rather than yours, that no key of yours declares.  Reaching it first would
skip `kind-settings`, `plugin-settings` and the widget's own entry, all of
which outrank a theme's `default:`.

`self.color()` is that chain already written: `self.config`, then the page,
then white.  It exists because a graphics effect needs a real color in
Python where a stylesheet would have inherited one.

### `{this-folder}`

Any path in any yaml can be written `{this-folder}/art/x.png`, meaning the
folder that file was read from — your plugin's directory in your
`config.yaml`, a theme's directory in its `theme.yaml`.  It is how art
travels with whatever ships it, without anything knowing where it was
installed.

`from-theme:` used to declare a mapping from theme names to your own.  It is
gone; the Qt names arrive by themselves and everything else comes
through `kind-settings`.

## Two rules worth reading before you publish

Keys travel in URLs, so anything logging a URL logs the key - see
[Never log an API key](../CONTRIBUTING.md#never-log-an-api-key).

Dependencies are pinned deliberately and Python 3.9 is the floor, because a
clock runs unattended on hardware nobody touches for years.  Both are
explained in [CONTRIBUTING.md](../CONTRIBUTING.md).
