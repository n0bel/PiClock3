# Tests

Three programs that check the half of the clock a desktop can check: reading
a config, reporting what is wrong with it, and saying where. They are here so
you can run them against your own change, and so you have something to copy
when your change deserves a test of its own.

They are not a gate. Nothing runs them for you, there is no CI, and a pull
request is not rejected for skipping them. They are a tool.

```
python3 tests/run.py
```

That runs all three and answers with an exit code. Each is also a program in
its own right, and running one directly gives you its own output:

```
python3 tests/checktest.py
```

Run them from wherever you like — each moves to the checkout root itself,
because the clock finds plugins, layouts and themes by relative path.

## What is here

| | what it guards | needs |
|---|---|---|
| `importtest.py` | that every module still imports | PyQt5 |
| `checktest.py` | what `--check` says about a broken config | the requirements |
| `logtest.py` | the logging settings, read before the log exists | PyQt5 |
| `linetest.py` | whether a finding names the right file and line | PyQt5 |

`importtest.py` is the shallowest and the widest. The clock imports a plugin
only when a config names one, so loading `PyQtPiClock3.py` reaches eleven of
the thirty-odd modules here and none of the four biggest providers — a
syntax error or a missing import in `Mapbox.py` passes every other suite. It
asks one question of all of them and answers nothing else.

`checktest.py` imports `PiClock3.Check` and nothing else. `Check` has no
PyQt import anywhere in it, on purpose — its own docstring says a config
should be readable "on a machine with no display and no api keys" — so it
runs wherever the requirements install. The other two load or run
`PyQtPiClock3.py`, so they need Qt. Neither opens a window.

All three together take about half a minute on a desktop, most of it
`checktest.py` resolving a config from disk 129 times over.

`run.py` reports a suite that cannot run as **skip** rather than as a
failure. Not having Qt installed is a fact about your machine, not about your
change.

## Running one against your own change

The point of a regression test is the run you do *before* you are happy with
the change, and again after. Both suites print one line per case, so a diff
of two runs is a readable answer.

The cheapest useful thing, and the one most likely to catch something:

```
python3 tests/run.py
```

Two more one-liners belong beside it. Lint what you touched, by name:

```
python3 -m flake8 PiClock3/Check.py tests/
```

Named files rather than a bare `flake8`, which lints the whole tree.
[CONTRIBUTING.md](../CONTRIBUTING.md) asks you not to reformat code you are
not changing, and the tree is not clean today — running it bare buries your
three findings in a couple of hundred that were already there.

Then gate the syntax against the Python floor:

```
python3 -c "import ast,sys;[ast.parse(open(f,encoding='utf-8').read(),f,feature_version=(3,9)) for f in sys.argv[1:]]" $(git ls-files '*.py')
```

That parses every file the way Python 3.9 would, without running it, so
`match` and anything else newer than the floor is a syntax error here rather
than a crash on a Bullseye Pi. It catches syntax and only syntax: a 3.10
library call like `itertools.pairwise` parses perfectly and still fails on
3.9.

## Adding a case

### to `checktest.py`

A case is a config and the findings it must produce. `config()` gives you a
clean one and each argument does one thing to it:

```python
    dict(name='a widget in a region no layout declares',
         config=config(a=put('widgets', 'clock', 'region', 'nowhere')),
         wants=['no region'], forbids=[]),
```

`wants` is matched as a substring of `"where: message"`, so a case says what
it is looking for and nothing about the wording around it — rephrasing a
message does not break a test that was not about the phrasing.

**`forbids` is the half that matters.** A checker that complains about a
config the clock runs happily is worse than one that says nothing, because
people learn to ignore it. Most cases should forbid something:

```python
    dict(name='a page naming a layout that is not there',
         config=config(a=put('pages', 'clock-page', 'layout', 'nosuch')),
         wants=['no layout'],
         # every widget's region becomes unknowable, and saying so once per
         # widget would bury the one line that is wrong
         forbids=['no region']),
```

Two more keys: `once='...'` asserts a finding is said exactly once, for the
things that should not be repeated per widget; `xfail=True` marks something
`Check` gets wrong that nothing has fixed yet, and the runner tells you when
one starts passing so it can be un-marked.

`needs='Twin'` builds a plugin the repo does not ship — see `FIXTURES` near
the bottom of the file for the small schemas, and add one if your case needs a
plugin shaped a particular way.

### to `logtest.py`

A tuple: a name, the config text, any `--set` arguments, the setting, and
what should come out. Most of its cases are one value written every way
somebody might write it.

### to `linetest.py`

A fixture, the finding to look for, and what the parenthetical after the path
has to be. Line numbers are found by searching the fixture for a marker
rather than counted by hand, so editing a fixture cannot silently move an
assertion.

## Two habits worth more than the tests

### Prove the test can fail

A test that passes against broken code is worse than no test, and you cannot
tell the two apart by reading. Break the thing on purpose and watch the suite
go red:

```
# revert the line you just wrote, or invert its condition
python3 tests/run.py     # it must FAIL, and on the cases you expect
git checkout -- the-file
```

This is how the logging change was checked. Deleting the two lines that strip
quotes off a value fails 8 of `logtest.py`'s 26 cases — which is what proves
those 8 are about anything, and it is worth doing to see. Without those two
lines, `logging-rotate: 'daily'` quietly falls back to per-run, which is a bug
nobody would notice from a passing suite.

Do it once per behavior you add, not once per commit.

### For a restructure, dump and compare

When you are changing *how* something is computed rather than what it should
answer — a merge order, a resolution path — the useful test is not a case
list. It is: dump the whole answer to a file before, dump it again after, and
diff.

Write a throwaway script that walks every widget in every shipped example,
prints its resolved settings as sorted JSON, and run it on both sides of the
change. Byte-identical output over sixteen configs is a much stronger claim
than any set of assertions you would think to write, and it costs twenty
lines. Then throw it away — it is a proof about one change, not a test.

## What these do not cover

Everything that makes a clock a clock. Nothing here draws a pixel, advances a
timer, fetches a tile, or runs past midnight. A green run means every module
imports and a config is read and reported on correctly. It says nothing at
all about whether the thing works.

The gap worth knowing about: `importtest.py` proves a name is there when a
module loads, and nothing here proves one is there when a method runs. A
provider that reaches for something only inside a network callback is not
covered by any of this.

So [CONTRIBUTING.md](../CONTRIBUTING.md) still applies, and its rule is the
one that finds the real bugs: **run your change on an actual clock
overnight.** The interesting failures are the ones a short desktop run never
sees — a rollover, a daylight saving change, a timer that drifts after a
day, a service that stops answering at 3am.

## A note on your checkout

`checktest.py` and `linetest.py` write fixture plugins, themes and layouts
into `plugins/`, `themes/` and `layouts/`, because that is where the clock
looks for them. They are all named `_selftest`, they are deleted at the end
of the run, and a suite refuses to start if one is already there rather than
removing something you installed.

Those three folders are git-ignored, so nothing a run leaves behind can end
up in a commit.
