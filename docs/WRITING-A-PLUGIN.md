# Writing a plugin

A plugin is a folder holding a module, a `config.yaml` of its settings and
their defaults, and a `schema.yaml` saying what those settings are.  Drop it
into `plugins` and a config can name it; nothing has to be registered.

## Decide where it is going, before you write much

There are two destinations, and they start differently:

1. **Your own repository.**  Almost every plugin belongs here.  You
   publish it, you maintain it, and it is yours alone.
2. **Into PiClock3 itself.**  It becomes part of the core, and this
   project's maintainers carry it from then on - so it is rare, and worth
   asking about before you write much.

**1. Your own repository.**  A camera, a data source for one country, a
chart of something nobody else draws.  It lives in `plugins/`.  Start from
the template - it is a GitHub template repository, so clicking *Use this
template* gives you a repository of your own, which you clone into the
clock:

```
cd PiClock3
git clone https://github.com/you/piclock3-aurora plugins/Aurora
```

That way your plugin has a history of its own from the first minute.
[Publishing one](#publishing-one) is the rest of it.

**2. Into PiClock3 itself.**  The built-in set is meant to stay small -
enough for a useful clock, plus the providers other plugins depend on - so
open an issue before writing much.  If the answer is yes, the folder is
`PiClock3/<Name>/` in a fork of this project and it arrives by pull
request.  See [CONTRIBUTING.md](../CONTRIBUTING.md).

**Without a GitHub account, or when it is going into PiClock3:** take the
template's files rather than its history.

```
git clone https://github.com/n0bel/piclock3-plugin-template plugins/Aurora
rm -rf plugins/Aurora/.git     # its history is the template's, not yours
```

Downloading the template as a zip does the same thing without git.

## Widgets and providers

A plugin is one of two kinds.  A **widget** draws in a region a layout
named.  A **provider** supplies data to widgets and occupies no region of
its own - which is why no theme reaches a provider, and why anything a
theme should be able to say belongs on a widget.

Each kind is a class to subclass, and a provider picks the one that says
what it supplies:

```python
from PiClock3.Widget import Widget      # draws in a region
from PiClock3.BaseMap import BaseMap    # the map under the frames
from PiClock3.Frames import Frames      # timestamped tiles, animated
from PiClock3.Weather import Weather    # what the sky is doing, or will be
from PiClock3.TextSource import TextSource   # words that change on their own
```

What each one asks of you is written beside it in that file.  Leave out
something the role cannot answer on your behalf and you get an error naming
your plugin, rather than a failure in the middle of a redraw.

**A provider must say which of its role's questions it answers**, in its
`schema.yaml`, because inheriting a method proves nothing:

```yaml
provides: [frames]        # BaseMap: [map].  Weather: any of
                          # conditions, hourly, daily.  TextSource: [text]
```

Required, not optional: a provider exists to be asked something, and this
is what lets a config be told it has named a base map where a frame source
belongs.

## Where a plugin goes

A plugin is a folder, and which folder depends on the decision above.

    plugins/Aurora/       yours, or one you cloned
    PiClock3/MapLoop/     one that ships with PiClock3

A third place, for one you are writing and keep somewhere else:
`named-paths: plugins:` in a config names a folder that holds plugin
folders, the way `plugins/` does, and a plugin found there is named by
itself - `plugin: Aurora` rather than `plugin: plugins.Aurora`, since two
folders cannot both be the `plugins` package.  See
[WRITING-A-CONFIG.md](WRITING-A-CONFIG.md).

**Your own repository** - it lives in `plugins/`, beside `Config.yaml` at
the top of the checkout.  PiClock3 does not track that folder, so
`git pull` never overwrites what you put there.

**Into PiClock3 itself** - it lives in `PiClock3/<Name>/`, inside your fork
of this project.  That folder *is* tracked, which is what allows you to
make a pull request, to contribute to the core of the project, and it is
why the two places exist.

To install somebody else's plugin, put their folder in `plugins/` - or let
git fetch it for you:

```
cd PiClock3
git clone https://github.com/someone/piclock3-aurora plugins/Aurora
```

Then name it in a config, and give the instance a region to draw in:

```yaml
widgets:
  aurora:
    plugin: plugins.Aurora
    region: bottom
```

`plugin:` names the **folder**, not the file - the same shape as the core
plugins, which are named `PiClock3.Astral` rather than
`PiClock3.Astral.Astral`.  So the folder needs an `__init__.py` that lifts
the class into it:

```python
from .Aurora import *  # noqa: F401,F403
```

The loader imports that name and finds your class inside by inspection, so
it can be called whatever suits.  It takes the class your module *defines*
rather than the role class your module imports: both are `Plugin`
subclasses, and only one of them is yours.  `plugins` itself needs no
`__init__.py`.

### Why that line carries a `noqa`

flake8 complains twice about it, and both complaints are right about what
they see and wrong about what it is for:

* **F403**, that a star import hides which names a file defines.  True, and
  the point: naming the class here would mean writing it twice, and the
  loader is deliberately built so you never tell us what your class is
  called.
* **F401**, that nothing in `__init__.py` uses what the import brought in.
  Also true.  The file exists to put a name where the loader will look for
  it, not to use it.

Both fall out of the same decision - that a plugin is a folder you drop in
and a config names by folder.  `importlib.import_module` imports the
package, and `pluginClass` reads that package with `inspect.getmembers`, so
the class has to be an attribute of it.  One line does that, and it is the
only line of glue a plugin needs.

The `noqa` sits on the line rather than in a config of ours, because your
repository is not ours: a setting in PiClock3's flake8 configuration would
not reach a plugin you keep somewhere else.  On the line, the reason travels
with the idiom, and anything else you add to that file is still checked.

Nothing is registered anywhere.  The `config.yaml` next to your code is found
from the imported module rather than from a path anybody writes down - which
is what makes a clone work the moment it lands.

**Declare every setting you read there, and give each one a default.**  That
file is the list of what your plugin accepts - a default that exists only
inside your `.py` is one nobody can find, and a theme cannot set what it
cannot see.  A value the user has to supply still declares: empty, or the
`{apikeys.mbapi}` kind of name that reaches their config.

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

    plugins/Aurora/languages/en.yaml      merged over the shipped English
    plugins/Aurora/units/quantities.yaml  merged over the shipped quantities

What goes in that quantities file, and why a set that has never heard of your
quantity still works, is [WRITING-UNITS.md](WRITING-UNITS.md).

**If you mean to contribute the plugin to PiClock3 itself**, that is the
other folder: put it in `PiClock3/Aurora/` alongside the core plugins, name
it `PiClock3.Aurora` in a config the way every shipped plugin is named, and
open a pull request.  Being inside the package is what makes it ship for
everybody, and it is why the two locations exist rather than one.  Ask
first, as [Decide where it is going](#decide-where-it-is-going-before-you-write-much)
says, and read [CONTRIBUTING.md](../CONTRIBUTING.md).

### What a plugin repository holds

    __init__.py          required, from .Aurora import *  # noqa: F401,F403
    Aurora.py            required, your Widget or Provider subclass
    config.yaml          required, its defaults and what a theme may set
    schema.yaml          required, the shape of those settings
    README.md            what it does, and any key it needs
    languages/en.yaml    optional, words of its own
    units/*.yaml         optional, quantities of its own
    layouts/tall.yaml    optional, a layout with a region for what it draws
    themes/nightsky/     optional, a theme
    examples/aurora.yaml optional, run by naming it

A widget that draws something new usually needs somewhere to draw it, and
no shipped layout declares a region for a thing that did not exist.  So a
`layouts/` folder in your repository is searched - see
[WRITING-A-LAYOUT.md](WRITING-A-LAYOUT.md) for where it sits in the order.
One rule: **a layout you bring can add a name, never replace one.**  Calling
it `classic` gets you a `--check` warning and the shipped `classic`.

An example is run by naming it, from the clock's own directory:

    python3 PyQtPiClock3.py plugins/Aurora/examples/aurora.yaml

`{this-folder}` is the folder of the file that said it, so art beside the
example is found wherever the repository was cloned.  `apikeys: !include
ApiKeys.yaml` is read relative to the directory the clock was **started**
in, so write the same line the shipped examples write and it finds the
user's own keys.

A `schema.yaml` is required.  Without one, `--check` says
`plugins.Aurora has no schema.yaml, which is required` and counts it a
problem rather than a warning.  Inside it, `description:` is the only part
that is required in turn - see [WRITING-A-SCHEMA.md](WRITING-A-SCHEMA.md).

### Publishing one

If you started from the template, the plugin is already a repository:
commit and push, and you are published.

If you started in a plain folder instead, it has no history yet - PiClock3
ignores `plugins/`, so none of your commits here are about it, and if the
folder is lost so is the work.  Three commands, run where it already sits:

```
cd plugins/Aurora
git init                      # this folder is now a project of its own
git add .                     # everything in it
git commit -m "what it does"  # the first version, saved
```

Give the repository a name that says what it is.  `piclock3-aurora` tells
somebody what they are getting; calling it `PiClock3` gives you two
projects with one name and nobody able to tell them apart.  Whoever
installs it chooses the folder it lands in:

```
cd PiClock3
git clone https://github.com/someone/piclock3-aurora plugins/Aurora
```

**Everything it needs travels with it** - the theme it wants, the layout
that declares its region, its examples, its words, its units and its art.
The search path looks inside a plugin's own folder for all of them, so
they belong in your repository rather than loose in somebody's checkout.
[What a plugin repository holds](#what-a-plugin-repository-holds), above,
is the list.

**What does not go in the shipped tree.**  `PiClock3/` is this project's:
`PiClock3/themes/`, `PiClock3/layouts/` and `PiClock3/<Name>/` are tracked
here, so anything of yours put there is what `git pull` conflicts with, and
what a fresh clone does not have.  Your own parts go in `themes/`,
`layouts/` and `plugins/` at the top of the checkout, which are ignored for
exactly that reason - or inside the plugin repository you are publishing.

One rule for the parts you bring: **a bundled part can add a name, never
replace one.**  A layout of yours called `classic` draws a `--check`
warning and the shipped `classic` is used.

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
of them in the stylesheet it builds.**  `DigitalClock` declares none, and
the whole of its styling is:

```python
props = self.scaleFont({'font-size': self.config['font-size']},
                       self.clockrect.height())
self.clockface.setStyleSheet(self.styleRule(
    'clockface', props, self.config['extra-font-attributes']))
```

`styleRule(name, props, extra)` builds the rule for one label you drew, by
the object name you gave it.  The third argument is an
`extra-font-attributes` setting if your plugin offers one — a user writes
that line by hand, so whatever it says about semicolons is settled there
rather than in every plugin separately.  Leave it off if you have no such
setting.

Set one of the five on your own widget only when you want it to differ from
what the region says — an id selector outranks the region's rule, so yours
wins.

`font-size` is not among the five: it is a fraction of whatever it sits in,
and your region is not the same height as a label inside it.

### Several boxes in one region

A widget drawing more than one thing — a picture with figures under it, say
— should not work out where they go in code.  Declare a `layout:` block of
your own, one entry per box, and say `{is: part}` against each in your
schema:

```yaml
# config.yaml
layout:
  icon:   {left: 0.0, top: 0.0, width: 0.32, height: 1.0}
  wx:     {left: 0.32, top: 0.02, width: 0.68, height: 0.74,
           font-size: 0.20, align: left-top, wrap: true}
  day:    {left: 0.32, bottom: 0.02, width: 0.68, height: 0.26,
           font-size: 0.17, align: right-bottom}
```

```yaml
# schema.yaml
settings:
  layout:
    is: block
    of:
      icon: {is: part}
      wx:   {is: part}
      day:  {is: part}
```

`part` is a core type: you do not declare it, and you may not redefine it.
It takes the geometry keys **a page layout uses for a region**, read as
fractions of your region rather than of the page, plus `font-size`,
`align` — `left-top`, `center-top`, `right-bottom`, `center` — and `wrap`.

`self.part('wx')` then builds it: a `QLabel`, named, transparent, sized,
aligned, and placed.  Where a layout repeated your region, name the cell:
`self.part('wx', region)`.  A part that says no `align` keeps Qt's own,
left and centered down the height; pass `align=` for a plugin-wide default
that a part's own `align:` still beats.

**The names are the only part of this the code fixes.**  A theme or a
config can move any of them without touching your plugin, the same way it
moves a region.

### Graphics effects happen without you

A glow or a drop shadow is not a stylesheet property, so none of the above
would carry it.  Core applies `effect:` to your regions before `start()`
runs, and a Qt effect covers a widget's whole subtree and picks up children
made afterward — so it reaches everything you draw, and **there is nothing
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
    self.hourFormat = self.strftimePortableFormat(
        self.piclock.expand(self.config['hour-format']))
```

Expand first when the default reaches into the language, as
`'%A {language.time-format}%p'` does, so strftime sees a format rather
than braces.

Two reasons, and only one of them is portability.

`%-d` drops a leading zero on glibc and raises on Windows; `%#d` does it on
Windows and silently pads on glibc.  A config travels between the two, so it
is written the glibc way and converted for you.  Any `%-x` is handled,
not only the day.

And a widget that draws a time redraws every second, so resolving in the
tick would run the substitution forever for an answer that cannot change.

That is the whole contract - use the saved string however you were going to,
whether that is `when.strftime(self.hourFormat)` or handing it to `expand()`
for a `{plugin-data.now:%-I}` template.

Do not strip the zero yourself afterward.  Both shipped plugins used to,
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

**Say which tiles did not arrive.**  The callback also takes
`failed=`, the squares of the pixmap whose tiles are missing, and
`tiles=`, how many were asked for.  `MapLoop` hatches the missing squares,
drops a frame where nothing arrived, and asks again next interval, so an
outage is not drawn as clear sky.  Hand the callback to `TileFetcher` and
both are filled in for you; a provider that draws its frames some other way
passes them itself, or calls back with the pixmap alone and is taken as
complete.

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

**A provider that draws its own map knows more than a band.**
`OpenFreeMap` gets vector tiles and paints the credit itself, so its mask
is the `QPainterPath` the text came from, grown by the halo - the radar
keeps the space between the letters instead of losing a strip.  Send
`None` when there is nothing baked in and nothing to protect.

### A service that wants a header

Qt sends no `User-Agent` at all, and a host behind Cloudflare answers 403
to a request without one.  `WebGet` takes them, which is the only way a
provider can send one:

```python
WebGet(url, self.gotTile, params,
       headers={'User-Agent': 'PiClock3 (+https://github.com/...)'})
```

Name your plugin and give a link.  A tile service with no key has no other
way to tell one busy client from a hundred, and being identifiable is most
of what keeps a free service free.

## Two rules worth reading before you publish

Keys travel in URLs, so anything logging a URL logs the key - see
[Never log an API key](../CONTRIBUTING.md#never-log-an-api-key).

Dependencies are pinned deliberately and Python 3.9 is the floor, because a
clock runs unattended on hardware nobody touches for years.  Both are
explained in [CONTRIBUTING.md](../CONTRIBUTING.md).
