# Writing a plugin

A plugin is a folder holding a module and a `config.yaml` beside it.  Drop it
into `plugins` and a config can name it; nothing has to be registered.  Start
from [piclock3-plugin-template](https://github.com/n0bel/piclock3-plugin-template).

They come in two sorts.  A **widget** draws in a region a layout named.  A
**provider** supplies data to widgets and occupies no region of its own -
which is why no theme reaches a provider, and why anything a theme should be
able to say belongs on a widget.

Each sort is a class to subclass, and a provider picks the one that says
what it supplies:

```python
from PiClock3.Widget import Widget      # draws in a region
from PiClock3.BaseMap import BaseMap    # the map under the frames
from PiClock3.Frames import Frames      # timestamped tiles, animated
from PiClock3.Weather import Weather    # what the sky is doing, or will be
```

What each one asks of you is written beside it in that file.  Leave out
something the role cannot answer on your behalf and you get an error naming
your plugin, rather than a failure in the middle of a redraw.

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

The loader imports that name and finds your class inside by inspection, so
it can be called whatever suits.  It takes the class your module *defines*
rather than the role class your module imports: both are `Plugin`
subclasses, and only one of them is yours.  `plugins` itself needs no
`__init__.py`.

Nothing is registered anywhere.  The `config.yaml` next to your code is found
from the imported module rather than from a path anybody writes down - which
is what makes a clone work the moment it lands.

**Declare every setting you read there, and give each one a default.**  That
file is the list of what your plugin accepts - a default that exists only
inside your `.py` is one nobody can find, and a theme cannot set what it
cannot see.  A value the user has to supply still declares: empty, or the
`{apikeys.mbapi}` sort of name that reaches their config.

It is read by more than a person.  A setting missing from it is one no
editor can offer and no check can validate, so `self.config.get('format')`
against a `config.yaml` that never mentions `format` is a setting that does
not exist as far as anything outside your code can tell.

Comment the ones whose *value* means something a reader cannot infer -
`font-family: ''  # empty takes the page's`.  Not what the setting is for;
its name does that, and how to choose a value belongs in a document rather
than beside a default.

**A default can be a name rather than a value.**  Anything in braces is
looked up when the setting is used, so a plugin declares where its answer
comes from instead of copying it:

```yaml
apikey:   '{apikeys.mbapi}'          # the user's key
latitude: '{location.latitude}'      # where the clock is pointed
format:   '{language.date-format}'   # the language's own date line
```

That last one is why `Date` has no fallback in its code.  `{language.*}`
follows the language file's shape - `{language.strings.sunrise}` for a word,
a setting beside the tables by its own name - so a translation supplies the
answer and the plugin declares only that it wants it.  Details are in
[WRITING-A-LANGUAGE.md](WRITING-A-LANGUAGE.md).

A plugin brings its own `languages/` and `units/` folders with it if it has
them, and both are merged rather than first-wins, so a plugin adds words and
quantities without editing the shipped tables:

    plugins/tides/languages/en.yaml      merged over the shipped English
    plugins/tides/units/quantities.yaml  merged over the shipped quantities

What goes in that quantities file, and why a set that has never heard of your
quantity still works, is [WRITING-UNITS.md](WRITING-UNITS.md).

**If you mean to contribute the plugin to PiClock3 itself**, that is the
other folder: put it in `PiClock3/Tides/` alongside the core plugins, name it
`PiClock3.Tides.Tides` in the config, and open a pull request.  Being inside
the package is what makes it ship for everybody, and it is why the two
locations exist rather than one.  See [CONTRIBUTING.md](../CONTRIBUTING.md).

### What a plugin repository holds

    __init__.py         from .Tides import *
    Tides.py            the module, holding your Widget or Provider subclass
    config.yaml         its defaults, and the list of what a theme may set
    README.md           what it does, and any key it needs
    languages/en.yaml   optional, words of its own
    units/*.yaml        optional, quantities of its own

Ship a `README` that says which service it talks to and whether that needs an
account.  A key belongs in the user's `ApiKeys.yaml`, never in your
`config.yaml` - see [Two rules](#two-rules-worth-reading-before-you-publish).

## Weather providers say what the sky is doing, not what to call it

A weather provider answers `conditions()`, `hourly(count, step)` and
`daily(count)`.  Implement the ones your source can answer and leave the
rest: `Weather` answers them with nothing - `None` for conditions, an empty
list for the other two - so a station says it has no forecast by not
writing one.  Each entry carries its condition as **WMO code table 4678
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

`self.variant()` swaps a `-day` name for its `-night` one - it comes with
the `Weather` class, along with `self.humidity()` and `self.feelsLike()`.
Which one applies is `Sun.daytime()`, from `PiClock3.Sun`, which answers
from the sun rather than from the hour.

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
props = self.scaleFont({'font-size': self.config['font-size']},
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

### If you format a time

Resolve the format once in `start()`, through `strftimePortableFormat()`,
and keep what it gives you:

```python
def start(self):
    self.hourFormat = self.strftimePortableFormat(self.config['hour-format'])
```

Two reasons, and only one of them is portability.

`%-d` drops a leading zero on glibc and raises on Windows; `%#d` does it on
Windows and silently pads on glibc.  A config travels between the two, so it
is written the glibc way and turned round for you.  Any `%-x` is handled,
not only the day.

And a widget that draws a time redraws every second, so resolving in the
tick would run the substitution forever for an answer that cannot change.

That is the whole contract - use the saved string however you were going to,
whether that is `when.strftime(self.hourFormat)` or handing it to `expand()`
for a `{plugin-data.now:%-I}` template.

Do not strip the zero yourself afterwards.  Both shipped plugins used to,
and both got it wrong: one tested the first character of the whole rendered
string, so `'%S %I'` ate the seconds' zero and `'%A %I:%M'` missed the
hour's; the other could not fire at all for either format it shipped.
`%-I` is a field, and knows which one it is.

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

### `{this-folder}` and `{plugin-folder}`

Any path in any yaml can be written `{this-folder}/art/x.png`, meaning the
folder that file was read from — your plugin's directory in your
`config.yaml`, a theme's directory in its `theme.yaml`.  It is how art
travels with whatever ships it, without anything knowing where it was
installed.

`{plugin-folder}` is the other one, and it means the folder of whatever
code is asking.  The difference is when each is resolved: `{this-folder}`
is substituted as a file is read, so it is fixed to the file that wrote it,
while `{plugin-folder}` is worked out at the moment your code calls
`expand()` and so follows your plugin rather than the yaml.

That makes it the one to use for a default a theme is expected to move.
`AnalogClock` ships `clock-images-base-folder: '{plugin-folder}'` beside
`clock-images-folder: lightblue`, so the art is found in the plugin until a
theme points the base folder at `{this-folder}` and the set at its own -
which then resolves against the theme, because the theme's yaml is where
that line was read.  `MapLoop` does the same for markers.

`from-theme:` used to declare a mapping from theme names to your own.  It is
gone; the Qt names arrive by themselves and everything else comes
through `kind-settings`.

## Say what your service must be credited as

Every provider carries a name, and the default is nothing:

```python
class LibreWXR(Frames):
    attribution = 'LibreWXR'
```

A widget reads it straight, and a caption reaches it as
`{plugin-data.frame-attribution}` or `{plugin-data.base-attribution}`.  A
provider that needs no credit says nothing and appears nowhere.  One whose
credit is only known at run time - a station reporting its own id - sets
`self.attribution` in `__init__` instead.

**A frame provider hands over a time and a name, never a caption.**  The
slot comes back through the callback, and whatever draws the frames turns it
into a line - `MapLoop` writes the time in its own `caption-time-format:`
and puts your `attribution` after it.  The format is the clock's to choose,
the same way words for a weather condition are, so a provider that formats a
time has made itself as untranslatable as one that hands over English.

This is the only credit a radar gets, because radar tiles carry no mark of
their own.

### If your images arrive with a mark already on them

A base map from a static-image API usually has the provider's logo and credit
drawn into the picture, and a radar painted over it would bury them - which
both Mapbox and Google forbid in as many words.  So send a mask with the
pixmap saying where your marks are, and core lifts exactly those pixels back
over everything drawn on top:

```python
callback(p, self.bottomBandMask(p, rsize, 20))
```

`bottomBandMask` covers the common case, a full-width band across the bottom.
The mask is an alpha `QImage` the size of the pixmap you are handing over, so
a mark somewhere else, or one with a soft edge, is yours to paint.

Two rules if you paint your own:

- **Feather only edges that are inside the picture.**  An edge lying on the
  pixmap's own boundary has nothing to fade into, and softening it lets the
  radar bleed in at the very edge.
- **Grow outward from your mark, never inward.**  Softening the inside of the
  area your logo occupies makes the logo itself part-transparent, which is
  the thing this exists to prevent.

Measure rather than guess where your marks land, at several requested sizes:
they are usually a fixed number of pixels anchored to an edge, so what
fraction of the image they occupy changes with the size while the pixels do
not.  Send the mask through the callback rather than storing it on yourself -
one provider instance serves every map on the clock, so anything kept on
`self` belongs to whichever request finished last.

## Two rules worth reading before you publish

Keys travel in URLs, so anything logging a URL logs the key - see
[Never log an API key](../CONTRIBUTING.md#never-log-an-api-key).

Dependencies are pinned deliberately and Python 3.9 is the floor, because a
clock runs unattended on hardware nobody touches for years.  Both are
explained in [CONTRIBUTING.md](../CONTRIBUTING.md).
