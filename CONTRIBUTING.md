# Contributing to PiClock3

Bug reports, fixes and plugins are all welcome.  A few things worth knowing
first.

## Plugins

PiClock3 ships a small set of built-in plugins — enough for a useful clock out
of the box, plus the providers that other plugins depend on.  It is meant to
stay small.

Anything more specific is better as your own repo: a camera, a regional data
source, whatever you have wired up.  Nobody needs permission for that and it
does not wait on us.  Start from
[piclock3-plugin-template](https://github.com/n0bel/piclock3-plugin-template)
and tag your repo `piclock3-plugin` so people can find it.  Themes and layouts
work the same way.

If you think something really does belong in the built-in set, open an issue
before writing it, so we can talk about it first.

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
service uses.  It is deliberately not normalised — it exists so that anything
a provider does not translate is still reachable by someone who wants it.
Shipped widgets never read it, and anything that does is knowingly tied to
one provider.

## Never log an API key

Keys travel as part of a URL, so anything that logs a URL logs the key:

```python
logger.info("map url %s", mapUrl)     # leaks the key
```

Log the pieces you actually need — host, zoom, size — or strip the query
string first.  This applies at every level **including debug**, because the
debug log is exactly what people attach to an issue.

If you add a provider, log what it asked for, not what it sent.

## Dependencies

Dependencies are pinned on purpose and updated by hand, after someone has
looked at what changed.  Please do not add dependabot or anything like it —
automatic version-bump pull requests will be closed.

A clock runs unattended on hardware people rarely touch, often for years.  A
dependency that updates itself is one that can break a clock nobody is
watching.  If you find a version worth moving to, open an issue or a pull
request and say what it fixes.

Security advisories are a different thing and we do watch those.  They tell us
something and leave the decision with us, which is the point.

## Style

PEP8, and flake8-clean.

Please don't reformat code you aren't changing.  Optimize-imports and
reformat-on-save turn a ten line fix into a two hundred line diff, and the ten
lines get lost in it.

## The floor

**Python 3.9, which means Raspberry Pi OS Bullseye.**  Older Pis that can't
run that should stay on [PiClock 1](https://github.com/n0bel/PiClock), which
is kept alive for exactly that reason.

A floor only means something if it is honored.  Ours has been broken twice
without anyone deciding to break it, so it is worth being concrete.

### The code

No `match` statements, no `int | str` annotations.  Neither is needed here and
both are 3.10.

### Dependencies count too

A version bump can raise the floor as effectively as a language feature, and
it does it silently — the code still looks fine and still runs on your machine.
Three pins in this repo did exactly that, all merged without being run:

* `tzlocal~=5.4` and `metar~=2.0.1` both require Python 3.10.  The code needs
  `get_localzone_name` (tzlocal 3.0) and `strict=` (metar 1.8).
* `pyyaml-include~=2.2.0` renamed its module from `yamlinclude` to
  `yaml_include`, so `Config.py` could not import it at all.

**But do not reach for an upper cap.**  That was our first fix and it was
wrong.  pip already reads `requires_python`, so a release needing 3.10 is
never offered to a 3.9 box.  With no cap, pip resolves:

```
python 3.9    metar-1.11.0  tzlocal-5.3.1
python 3.11   metar-2.0.1   tzlocal-5.4.4
```

Capping those would have done nothing on Bullseye and held Bookworm and
Trixie on old packages.  **Floor-only specs let every system take the newest
it can actually run.**

So when a dependency worries you, work out which kind of break it is:

* **Needs a newer Python** — no cap.  `requires_python` handles it, and
  capping only hurts newer systems.
* **Changed its API** — cap it, because no metadata expresses that.
  `pyyaml-include>=1.3,<2` is capped for this reason and stays capped.

Either way, if you genuinely need something the floor cannot run, say out loud
that you are moving the floor rather than letting a pin do it quietly.

### Testing against it

Developing on 3.12 and assuming is not testing.  Nothing about a newer
interpreter will tell you what a 3.9 one does.

At minimum, gate the syntax:

```
python -c "import ast,sys;[ast.parse(open(f,encoding='utf-8').read(),f,feature_version=(3,9)) for f in sys.argv[1:]]" $(git ls-files '*.py')
```

That catches `match` and nothing else, so it is a floor on the floor rather
than a substitute for running it.

Better, and what actually counts: run it on Python 3.9, or on a Bullseye Pi.
`pip install --dry-run --python-version 3.9 --only-binary=:all: -r
requirements.txt` will at least tell you whether the dependencies resolve
there before you find out the hard way.

### Moving the floor

Sometimes it should move.  When it does, that is a decision with its own
commit and its own reason — not a side effect of a version bump nobody read.
Update this file and the README when it happens.

## AI assisted contributions

Allowed, and encouraged.  Use whatever helps you get it done.

You are responsible for what you send, though — not your agent.  That means
you have read it, you understand it, and you have run it.  "The AI wrote it"
isn't an answer to a review comment, and an agent can't run your change on a
real clock overnight for you.

## Test on real hardware

A clock runs for months without anyone touching it, so the interesting bugs
are the ones a short run on a desktop never sees — midnight rollover, daylight
saving, a timer that drifts after a day, a service that stops answering at
3am.

Run your change on an actual clock overnight before sending it.

## Reporting a problem

Attach `PyQtPiClock3.log`, but read it first and take out anything that looks
like a key or a token.  Say which Pi, which OS and which Python.

A screenshot helps more than a description for anything that looks wrong on
screen.

## Expect slow replies

One person, spare time.  Pull requests here have sat for a long time before
being looked at.  That isn't disinterest, and a nudge on an old one is fine.
