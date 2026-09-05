# Writing a schema

A plugin's `config.yaml` declares its settings and their defaults, and a
comment beside each says what it does.  That is enough for a person reading
the file.  It is not enough for a program: nothing outside the plugin can
tell that `marker-size: 0.2` is a fraction of the map rather than a count of
pixels, that `size:` also takes `small`, `mid` or `tiny` and nothing else,
or that `forecast-provider:` has to name something the config's own
`providers:` block defines.

A `schema.yaml` beside the `config.yaml` says the **shape** of what the
plugin accepts.  The defaults stay where they are.

```yaml
description: >
  A METAR station report - what the sky is actually doing at one airfield,
  rather than what a model expects.  Hourly, and no forecast of any kind.

provides: [conditions]

settings:

  METAR:   {is: string, required: true}
  refresh: {is: number, unit: minutes}
  # a station reports about hourly, so asking oftener re-reads one line
```

That is a whole schema.  Most are this size.

## Where a schema goes

Beside the code it describes, so a plugin cloned into `plugins/` brings its
own:

    PiClock3/<Plugin>/schema.yaml   what that plugin accepts
    plugins/<yours>/schema.yaml     the same, for one of yours

Five more describe the files that are not plugins:

    PiClock3/core-types.yaml        the shapes more than one plugin needs
    PiClock3/config-schema.yaml     your Config.yaml
    PiClock3/layout-schema.yaml     a file in layouts/
    PiClock3/theme-schema.yaml      a theme's theme.yaml
    PiClock3/widget-schema.yaml     what any widget takes, being a widget

## Required, and what it decides

**A schema is required.**  A plugin without one does not load.  `Date` ships
one line of config and its module has no docstring, so nothing in the
project said what Date is - which is exactly the plugin that would never get
an optional schema, and exactly the one an editor cannot list.
`description:` is the field every schema has; `settings:` is the part that
may be left out.

**Not a second place to write defaults.**  `config.yaml` holds the value and
the schema describes it.  Two files that can disagree about a default would
be worse than having no schema at all.  The other half of that rule: every
setting a plugin reads has a default in its `config.yaml`, so a schema
declaring one that is not there is describing a setting nobody can find.

**A problem stops the clock; a warning does not.**  A setting misspelled, or
a `provider` naming something the config does not define, is a problem: it
cannot work, so the clock says so and exits rather than drawing the wrong
thing quietly.  A value outside a range the schema guessed at is a warning -
it runs, and the log says what it did.  The split belongs to #24, which is
where all of this is enforced.

## The document

| | |
|---|---|
| `description:` | what the plugin is, in a sentence or three.  Required, and the reason a schema is |
| `provides:` | for a `Weather` provider, which of `conditions`, `hourly` and `daily` it actually answers |
| `types:` | shapes this schema invents, if it needs any |
| `settings:` | the settings themselves |

`provides:` is how a config can tell that pointing `forecast-provider:` at a
station is a mistake.  A `Weather` subclass inherits all three whether it
implements them or not - `conditions()` answering `None`, `hourly()` and
`daily()` an empty list - so having the method proves nothing, and only the
plugin can say which it means.

## Four kinds

Every type is one of four, and the kind is what a reader has to know before
anything else:

    scalar   a string, a number, a boolean
    block    an object whose keys are known    marker {location, color}
    table    an object whose keys you invent   widgets {radar1, radar2}
    list     an array

`block` and `table` are both objects and the difference is who names the
keys.  A `marker` has a `location` and a `color` because the plugin says so;
`widgets:` has `radar1` and `radar2` because you said so.

## What a setting says

One of these three:

    is: <type>          exactly this
    of: [<type>, ...]   any one of these types
    with: <type>        that type's fields sit beside these, not under

`of:` is always type names and `one-of:` is always values, so neither has to
be read in context.

`with:` is for a shape that extends another.  `geometry` is `placement` and
three more fields, and a region written in a layout has `left:` and `width:`
at the same level - not `width:` inside a `placement:` block:

```yaml
  geometry:
    is: block
    with: placement
    of:
      width:  {is: number}
      height: {is: number}
      aspect: {is: number}
```

## And whatever else is true of it

| | |
|---|---|
| `one-of: [v, ...]` | these values, and nothing else |
| `required: true` | must be set; blank is a problem |
| `inherits: <where>` | blank takes it from there - `page`, `clock` |
| `range: [low, high]` | inclusive |
| `unit: <what>` | what a bare number counts, where the units table has nothing to say - `minutes`, `milliseconds`.  No suffix is accepted |
| `quantity: <what>` | an entry in `units/quantities.yaml` - see [WRITING-UNITS.md](WRITING-UNITS.md).  A bare number is that quantity's base, and any unit it lists may be written instead: `altitude` takes `1600` and `'5280ft'` alike |
| `names: <what>` | must name something that exists.  See below |
| `portable: true` | a `strftime` format written the glibc way and turned round for Windows |

**Silence means optional, and blank means none.**  Those three states -
required, optional, inherited - are what a blank default cannot tell you by
itself, and saying which is most of what a schema adds.

## `names:` is the one worth reaching for

Five kinds of string are not free text at all.  They have to name something
that exists somewhere else:

    providers   an entry of the config's own providers:
    regions     one a page's layout declares, cells included
    layouts     a file in layouts/
    themes      a folder in themes/
    unit-sets   a set in units/sets.yaml, or one added to it

```yaml
  forecast-provider: {is: provider, required: true}
  region:            {of: [region-name, region-names], required: true}
```

A misspelled provider name is a `KeyError` at startup and a misspelled
region is a widget that draws nowhere, and both are a list somebody could
have picked from.  Say `names:` wherever a setting is a reference, because a
string the schema cannot place is the one failure a reader cannot see
coming.

## Types you already have

`core-types.yaml` holds the shapes more than one plugin needs.  Use them by
name; a name there may not be redefined.

| | |
|---|---|
| `measure` | a number carrying its own unit, `'20px'` or `'5280ft'` |
| `size` `font-size` | a fraction of what holds it, or a measure.  `font-size` takes 0 besides, meaning as large as fits |
| `color` | anything Qt reads - a name, `#rgb`, `#rrggbb`, `rgba()` |
| `strftime` | a time format, written the glibc way |
| `template` | a line with `{names}` in it, looked up when it is drawn |
| `provider` | one of the config's own `providers:` |
| `effect` `effects` | a glow or a drop shadow, and the three names |
| `location` | latitude, longitude, timezone, elevation |
| `placement` | where a box sits inside the box holding it |
| `geometry` | placement, and how big |

## What a widget gets for free

`widget-schema.yaml` describes what a plugin accepts by being a widget
rather than by being itself, and `widget-config.yaml` beside it holds those
defaults:

    color  background-color  font-family  font-style  font-weight
    effect  icons-folder  units  precision

Do not declare these.  A widget takes them whether or not its author ever
heard of them, and they merge under whatever its own `config.yaml` says - so
naming one in your schema is giving yourself a different default, not
claiming the setting.  A provider takes none of them, having no region for a
theme to reach.  [WRITING-A-PLUGIN.md](WRITING-A-PLUGIN.md) says what each
of them does and which four Qt carries into whatever you draw.

## Inventing a type

When a setting is a list of things with their own rules, name the thing:

```yaml
types:

  marker:
    is: block
    of:
      location: {is: location, required: true}
      image:    {is: string}
      color:    {is: color}
      size:     {of: [number, measure, marker-sizes]}

  marker-sizes:
    is: scalar
    one-of: [small, mid, tiny]

settings:

  markers:     {is: list, of: marker}
  marker-size: {of: [number, measure, marker-sizes]}
```

A type invented here belongs to this plugin.  Put it in `core-types.yaml`
only when a second plugin needs the same shape, and then it belongs to
everybody.

## Checking your work

The schema is data, so the first check is that it is data - this says
nothing on success and names the line on failure:

```bash
python3 -c "import yaml; yaml.safe_load(open('PiClock3/Metar/schema.yaml'))"
```

Then point `--check` at a config that uses your plugin - see
[COMMAND-LINE-OPTIONS.md](COMMAND-LINE-OPTIONS.md).  It reads the config
against every schema it can find, so a setting you declared wrongly shows up
as a complaint about the config rather than as a clock that draws the wrong
thing:

```bash
python3 PyQtPiClock3.py examples/default.yaml --check
```

A setting your `config.yaml` has and your schema does not is reported there.
The two it cannot see are still yours to read for:

- every setting the schema declares has a default in `config.yaml`, unless
  it is `required:`
- nothing is declared that the `.py` never reads

A schema that disagrees with its `config.yaml` is wrong in the direction
that matters most, because the whole point is that a program can trust it.
And a plugin with no schema is still loaded today - the rule is written,
not enforced.
