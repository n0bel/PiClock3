# Command line options

```
python3 PyQtPiClock3.py [config.yaml] [--set key=value ...] [--at when]
                        [--geometry WIDTHxHEIGHT]
```

There are four, and `--help` prints them.  This page is mostly about why they
exist, because that is what tells you when to reach for one.

## Why there are any

A clock is a thing you look at.  There is no console in it, no inspector, no
way to poke a running one and ask what color it thinks the digital face is -
it draws, full screen, and that is the whole interface.  So the only way to
find out whether a change is right is to run it and look.

That makes the loop *edit, run, look, edit back* - and the file being edited
is `Config.yaml`, which is not a scratch file.  It is gitignored because it
is **your actual clock**, the one on the wall with your location and your
keys in it.  Trying a theme by editing that file means breaking the working
clock to find out whether the theme is any good, and remembering to put it
back afterwards.

`--set` is that loop without the editing, `--at` reaches the states you
cannot reach by waiting, and `--geometry` reaches the screens you do not
have.  None is needed to run a clock.  They exist for the person changing
one.

## `config.yaml` - which config to run

The one positional argument.  Defaults to `Config.yaml` in the current
folder, which is why the everyday case is just:

```
python3 PyQtPiClock3.py
```

Anything not starting with `-` is taken as the config name, and the last one
wins if you give more than one.  Nothing stops you keeping several - the
shipped `examples/` are exactly that, ordinary configs kept under their own
names.

## `--set key=value` - one setting, from outside the file

```
python3 PyQtPiClock3.py examples/berlin.yaml --set units=default
```

The key is dotted for anything nested, and may be repeated:

```
--set location.timezone=Europe/Oslo
--set widgets.clock.plugin=PiClock3.DigitalClock
```

It is applied **after** the file is read, so the command line has the last
word over everything in it - including anything an `!include` brought in.

A key that does not exist yet is created rather than refused.  That is
deliberate: it is what lets you add a setting a config never mentioned, and
it is also why a typo is silent.  If a `--set` seems to do nothing, suspect
the spelling of the path before suspecting the mechanism.

### Values are read as yaml

`4` is a number, `true` is a boolean, `[a, b]` is a list, and anything else
is the string it looks like - the same reading it would get in the file it
is standing in for.

One special case worth knowing, because it will bite otherwise: **yaml reads
a leading `#` as a comment**, so `--set …color=#ff8800` would read as
nothing at all.  A color is the likeliest thing anybody overrides, so an
empty reading of a non-empty word is taken as the word, and `#ff8800`
arrives as the string it obviously is.

Two characters mean something different to yaml than they do here, and both
are read the way this program means them rather than the way yaml would:

    --set theme.default.color=#ff8800                   a color, not a comment
    --set kind-settings.clock.art={this-folder}/hands   a template, not a mapping

`{` opens a mapping in yaml and a template here, and `#` opens a comment in
yaml and a color everywhere else.  A value beginning with either arrives as
the text you typed.  Nothing is given up by that: a mapping is set one leaf
at a time from a command line anyway, which is what the dotted path is for.

Quoting is still your shell's business - a value with spaces or a `#` your
shell would eat needs quoting by its rules, not ours:

```
--set 'kind-settings.digital-clock.format={plugin-data.now:%H:%M}'
```

### Reaching a theme or a layout

`theme:` and `layout:` are blocks of their own, laid over whichever theme or
layout each page names.  So either can be tried without editing it, and
without the theme having to be yours:

```
--set theme.default.color=#ff8800
--set theme.borders.default.width=0.03
--set layout.regions.clock.width=0.5
```

This is the shortest way to answer "would this theme be better in orange" -
and to find out that the shipped one you were about to fork only needed one
value changed.

### Reaching into a plugin

**Name the instance.**  Not the plugin and not its kind - the name the config
gave that particular widget or provider:

```
--set providers.metar.METAR=NZWD
--set widgets.radar1.zoom=9
--set widgets.clock.region=bottom
```

The names are the keys under `providers:` and `widgets:` in the config you
are running, so the config is also the list of what you can say.

This is the answer rather than one of three answers, and the reason is
precedence.  An instance's own entry is the **last** thing merged, after the
plugin's defaults, after the theme, and after both `-settings` blocks.  So
for any value an instance names in the file, the instance path is the only
door that reaches it - the others are outranked before they are read.

That is not a corner case.  Instances name exactly the interesting values:

```yaml
providers:
  metar: {plugin: PiClock3.Metar, METAR: EDDB}
widgets:
  radar1: {plugin: PiClock3.MapLoop, region: maps.1, zoom: 7}
```

`METAR` and `zoom` are both written on the instance, so

```
--set kind-settings.weather-source.METAR=NZWD
```

is read, applied, and then quietly beaten by the `EDDB` in the file.  The
clock still shows Berlin, and nothing says why.  Reach for the instance and
it works:

```
--set providers.metar.METAR=NZWD
```

### The other two, and when they help

`kind-settings:` still works from the command line, for a value **no instance
names** - a default nobody overrode:

```
--set kind-settings.radar-frames.palette=4
--set kind-settings.digital-clock.font-weight=300
--set 'kind-settings.digital-clock.effect=glow 0.25'
--set kind-settings.analog-clock.effect=none
```

`effect:` is worth knowing for trying things: it is a glow or a drop shadow,
a setting like any other, and every widget takes one whether or not it ships
with one.  The blur is a fraction of the region's height.

Being by kind, it reaches every plugin of that sort at once, which is its
point: both radar maps, or both digital clocks, without naming either.

`plugin-settings:` cannot be reached by `--set` at all.  It is keyed by the
plugin's name - the literal string `PiClock3.Metar`, dots and all - while
`--set` reads a dot as a step down into the config, so
`--set plugin-settings.PiClock3.Metar.METAR=NZWD` builds four nested levels
and matches nothing.

Little is lost by that.  Between the instance path, which is narrower, and
`kind-settings`, which is broader, what `plugin-settings` uniquely offers is
*one plugin but not the others sharing its kind* - and only two kinds here
have more than one plugin, `radar-frames` and `basemap`.  For that, edit the
config.

The order all of these resolve in is in the
[README](../README.md#where-a-setting-comes-from), and which to use when you
are writing a file rather than a command line is in
[WRITING-A-THEME.md](WRITING-A-THEME.md).

## `--at when` - start the clock somewhere else in time

```
python3 PyQtPiClock3.py examples/mcmurdo.yaml --at 2026-06-21
python3 PyQtPiClock3.py examples/arctic.yaml  --at "2026-12-21 13:45"
```

Written as `2026-06-21` or `2026-06-21 13:45`; anything `fromisoformat`
accepts will do.  It is the same as `start-at:` in a config, which is the
permanent version.

**It is an offset, not a fixed moment.**  The clock is put that far from now
and then runs on normally, so the seconds still tick and a slideshow still
advances.  A frozen clock would not show you much.

The reason it exists is that a good half of what this program computes is a
function of the date, and you cannot get at any of it by waiting a few
minutes.  A polar night cannot be seen in August, a sun that rises at 02:56
only does so around midsummer, and the moon is whatever phase it is today.
Every one of those is a place bugs live - which is what
`examples/arctic.yaml` and `examples/mcmurdo.yaml` are for, and neither is
worth much without this flag.

**Only the clock moves.**  The radar still shows what the frame server has,
because that is all it has, and the weather is still today's - a station
does not keep the past and a model does not forecast backwards.  So a clock
set to midwinter shows midwinter's sun over this afternoon's rain.  That is
a limit of where the data comes from rather than a decision, and it is the
one thing to remember before reading anything into a screenshot taken this
way.

## `--geometry WIDTHxHEIGHT` - a screen you do not have

```
python3 PyQtPiClock3.py --geometry 800x600
python3 PyQtPiClock3.py examples/london.yaml --geometry 1920x1080+100+100
```

Runs in a window of that size instead of filling the screen.  `+X+Y` places
it; without one it lands wherever the window manager puts it.  `geometry:` in
a config is the permanent version, though a config is an odd place for it.

**It is not a scaled picture of another screen.**  Every size in a layout or
a theme is a fraction of the screen, and a layout is corrected for the shape
it finds against the shape it says it was `designed-for`, so the clock lays
itself out for the size given and what comes out is what that screen would
show.  Text is sized and fitted against the regions that result, not shrunk
afterwards.

Which makes it the way to see whether a layout survives a shape it was not
drawn for - `classic` says `16:9`, so `--geometry 1024x768` shows what the
correction does with it, and `--set pages.clock-page.layout=panel` beside it
shows a layout drawn for 4:3 instead.

The one thing it cannot tell you is how the clock behaves on a machine that
is not this one.  Fonts, Qt version and how fast the maps composite are all
still this machine's.

## `--help`, `-h`

Prints the usage and exits.  Asking is not an error, so it goes to standard
output and exits `0` - which matters if you are calling this from a script.

## When something is wrong with the command line

Every one of these fails at startup with a sentence rather than a traceback,
because the person reading it is usually not the person who wrote the code:

```
$ python3 PyQtPiClock3.py --bogus
no such option '--bogus'

$ python3 PyQtPiClock3.py --set
--set wants key=value

$ python3 PyQtPiClock3.py Config.yaml --set 'x="unclosed'
cannot read '"unclosed' as a value: while scanning a quoted scalar

$ python3 PyQtPiClock3.py Config.yaml --at "next tuesday"
start-at: 'next tuesday' is not a date and time.  Write it as
2026-06-21 or 2026-06-21 13:45.
```

All of them exit `1`.  A problem in the config itself also puts up a dialog,
since a clock that starts on a Pi at boot has nobody watching a terminal.

## Seeing what it did

There is no `--verbose`; the level is a config key, which `--set` reaches
like any other:

```
python3 PyQtPiClock3.py examples/digital.yaml --set logging-level=info
```

`debug`, `info` or `warning`, the last being the default.

Each `--set` says what it did as it does it, which is the way to confirm a
path was spelled right:

    set units = 'metric'
    set kind-settings.digital-clock.font-weight = 300

Those appear at `info`, and the level has to be `info` or `debug` **in the
config file** to see them - a `--set` cannot raise the level in time to
report itself, since it has to be applied before anything can read it.  Most
of the shipped examples already carry `logging-level: debug`.

`debug` adds the whole resolved config and the stylesheet each widget was
built with - which is how to find out where a color actually came from,
rather than reasoning about which tier should have won.

Output goes to `PyQtPiClock3.log` beside the program, and to stderr.  The
log is rolled at every start and seven are kept, so the run before last is
still there when you realize you needed it.

## While it is running

Not command line options, but the other half of driving a clock you cannot
type at:

| | |
|---|---|
| `Space` | next page |
| `F4` | quit |
| `F6` / `F7` | previous / next slideshow image |
| `F8` | hold the slideshow, or let it run |

F6, F7 and F8 are the keys PiClock v1 used for these, and act on the
slideshow of the page being looked at.
