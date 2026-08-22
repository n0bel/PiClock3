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

## Python and OS

Python 3.9 is the floor, which means Raspberry Pi OS Bullseye.  Older Pis that
can't run that should stay on [PiClock 1](https://github.com/n0bel/PiClock),
which is kept alive for exactly that reason.

So no `match` statements and no `int | str` annotations.  Develop on whatever
you like, but don't reach past 3.9 without saying so.

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
