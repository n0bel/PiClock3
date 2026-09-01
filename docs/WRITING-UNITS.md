# Units

A provider hands a widget a number and says what unit it is in.  The widget
does not convert it or decide how to print it - it asks:

```python
self.units('temperature', 'C', 12.0)    # '53.6°F', '12.0°C' or '285.1K'
```

What comes back depends on the **set** the clock is using, and nothing in the
widget knows which one that is.  That is the whole design: a provider reports
in whatever it reports in, a widget draws whatever it is given, and the
choice lives in one place a reader controls.

Two files hold it, in `PiClock3/units`:

    quantities.yaml     what a unit is, and how to convert it
    sets.yaml           which unit to show for each quantity

Both are extended rather than edited - see **Adding your own** below.

## `units:` picks a set

```yaml
units: metric
```

Four ship: `default`, `metric`, `SI` and `nautical`.  An unknown name falls
back to `default` rather than failing, so a typo costs you the set you meant
and not the clock.

A widget can name its own, which is how one panel reads in knots while the
rest of the clock is metric:

```yaml
  wind:
    plugin: PiClock3.CurrentConditions
    units: nautical
```

**Named sets rather than a metric/imperial switch**, because real preference
is not two-valued.  `nautical` wants knots and nautical miles but Celsius; a
US reader often wants Fahrenheit and inches but km/h for wind.  Two flags
cannot say that and four named sets can.

## A quantity, and why there are ten of them

```yaml
temperature:
  base: C
  units:
    C: {factor: 1,   offset: 0,      suffix: '°C', precision: 1}
    F: {factor: 1.8, offset: 32,     suffix: '°F', precision: 1}
    K: {factor: 1,   offset: 273.15, suffix: 'K',  precision: 1}
```

Each quantity names a **base**, and every unit is a factor and an offset
relative to it:

    value_in_base   = (value - offset) / factor
    value_in_target = value_in_base * factor + offset

So a conversion is two steps through the base rather than a rule for every
pair.  Adding a unit is one line and it converts to and from everything else
for free.

| | |
|---|---|
| `factor` `offset` | the arithmetic above.  `offset` may be left out and means 0 |
| `prefix` `suffix` | belong to the unit, because a currency wants its symbol in front and a temperature wants it behind |
| `precision` | decimals, unless something asks otherwise |
| `via` | a lookup instead of arithmetic - see below |

**Quantities are named for what wants a different unit, not for dimension.**
`depth`, `distance`, `altitude` and `height` are all length and none of them
want the same one: rain in millimeters, a range in kilometers, a cloud base
in feet.  The ten are `altimeter`, `altitude`, `depth`, `direction`,
`distance`, `height`, `pressure`, `rate`, `speed` and `temperature`.

`pressure` and `altimeter` are the same dimension on purpose and are still
two quantities - an altimeter setting is corrected to sea level, and mixing
the two silently is how a reading comes out 38mb wrong.

## `via:` for what arithmetic cannot do

```yaml
direction:
  base: deg
  units:
    deg: {factor: 1,          suffix: '°',   precision: 0}
    dir: {via: compass}
```

Some conversions are lookups.  `via:` names a function in the `VIA` registry
in `Units.py`, which is handed the value already converted to the quantity's
base:

```python
def compass(value, unit):
    """degrees as a point of the compass - a lookup, not arithmetic"""
    return Compass.findHeading(value, 3).abbr


VIA = {'compass': compass}
```

A `via:` naming something unregistered stops the clock and says so, rather
than printing a number in the wrong unit.  Registering one means editing
`Units.py`, so it is the one part of this a yaml file cannot add.

## A set says only what it wants

```yaml
sets:
  nautical:
    temperature: C
    altimeter: inHg
    speed: kt
    distance: nmi
    altitude: ft
```

`nautical` never mentions `depth` or `rate`, so those fall back to the
quantity's own `base`.  That fallback is what lets a set survive a plugin
adding a quantity it has never heard of - a tide plugin's new `tide` shows in
its base unit under all four sets, and each set adds a line for it or does
not.

## `precision:` where the table is wrong for the space

The table's precision suits the unit.  A widget may want something else,
and says so per quantity:

```yaml
  current-conditions:
    plugin: PiClock3.CurrentConditions
    precision:
      temperature: 0        # whole degrees in a narrow column
```

A quantity the block does not name keeps the table's answer.  This changes
one widget and nothing else - the table is still what every other widget
reads.

## Adding your own

**Do not edit the shipped files.**  Units load from every folder on a search
path, merged, least specific first:

    PiClock3/units/           what ships
    PiClock3/*/units/         a bundled plugin's
    plugins/*/units/          an installed plugin's
    units/                    yours, beside Config.yaml

So a `units/quantities.yaml` of your own holding just

```yaml
temperature:
  units:
    Ré: {factor: 0.8, offset: 0, suffix: '°Ré', precision: 1}
```

adds a unit to a quantity that already exists without restating it, and
survives `git pull`.  Dicts merge and anything else replaces, the same rule
`Config` follows.  Plugins are found by scanning disk rather than by import,
because the table has to exist before the first widget draws.

A config can also define a set inline, without a folder:

```yaml
unit-sets:
  mine:
    temperature: C
    speed: mph
units: mine
```

`unit-sets:` merges over whatever the files loaded, so it can add a set or
change one line of a shipped one.  Editing the conversion table itself
belongs in a `units/` folder - that is what the search path is for.

## Checking your work

`logging-level: info` prints what loaded:

    units: 10 quantities, 4 sets, using metric

A quantity or set you added and do not see there was not found - check the
folder name is exactly `units` and the file ends `.yaml`.  A unit that
converts wrongly is almost always a `factor` measured against the wrong
base; convert one known value by hand through the two steps above.
