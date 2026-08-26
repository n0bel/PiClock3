# Writing a language

A language is one yaml file.  There is no code in a translation, nothing to
compile and nothing to register - which is the point: somebody who speaks a
language and has never opened a Python file can add one.

    PiClock3/languages/en.yaml
    PiClock3/languages/de.yaml

Two ship, English and German.  A file holds the codes it answers to, the
shape of a date, the everyday words, and a table of weather conditions.

## Where a language goes

There is a `languages` folder beside `Config.yaml`, at the top of the
checkout, and that one is yours.  Create it - unlike `themes/` and
`layouts/` it is not there already.

    PiClock3/languages/     shipped with the project
    PiClock3/*/languages/   a core plugin's own words
    plugins/*/languages/    a third-party plugin's
    languages/              yours, and read last

Every file claiming the same language is **merged**, later winning, rather
than the first one found being used whole.  That is the difference from
themes and layouts, and it is what makes a translation additive: a plugin
ships the words it needs without editing the shipped table, and you change a
single word without editing either.

To change one word and nothing else, that is the whole file:

```yaml
# languages/en.yaml
code: [en, eng]
strings:
  feels_like: Feels
```

Then name it in a config, or leave it - `en` is the default:

```yaml
language: de
```

**If you mean to contribute the translation to PiClock3 itself**, put it in
`PiClock3/languages/` and open a pull request.  Translations are the most
useful thing to contribute and the easiest to review, so they are welcome.
See [CONTRIBUTING.md](../CONTRIBUTING.md).

## `code:` - what the language answers to

```yaml
code: [de, deu, ger]
name: Deutsch
```

List every name the language is known by, the everyday one first.  A config's
`language:` is matched against all of them, and a regional tag falls back to
the language it is a region of, so `de`, `deu`, `ger` and `de-AT` all arrive
at the same file.

Nothing requires a standard code.  A language that has none can claim any
name nothing else is using, or be known by the name of its file.

`name:` is what the language calls itself, and is what the log lists.

## `locale:` - day and month names

Day and month names are **not** in the table.  They come from the system,
through `strftime`, so a translation does not have to carry seven day names
and twelve month names that the C library already knows.

What the file carries is the list of locale names that mean this language,
tried in order until one is accepted:

```yaml
locale: [de_DE.UTF-8, de_DE.utf8, German_Germany.1252, de_DE]
```

The spelling differs by platform - glibc, macOS and Windows each want a
different form - which is why it is a list rather than a string.  On a Pi the
locale also has to have been generated first:

```
sudo dpkg-reconfigure locales
```

If none of them is accepted the day and month names stay in English and the
log says so, which is the usual explanation for a clock that is otherwise
translated.  `locale:` in a config overrides the list.

## `date-format:` - the shape of a date

`strftime` localizes the *names* but never the *order*: `%A %d %B %Y` gives
"Mittwoch 26 August 2026" in German, which is nearly right, and there is no
directive for a long date the way `%x` gives a short one.  So the language
says the shape:

```yaml
# en.yaml
date-format: '%A %B {day}<sup>{sup}</sup> %Y'

# de.yaml
date-format: '%A, {day}. %B %Y'
```

It is a `strftime` string with two extra tokens.  **`{day}` is the day of
the month, without a leading zero** - written that way because `%-d` means
that on glibc, `%#d` on Windows, and each raises on the other, so the
natural thing to write would break the clock on one platform.  **`{sup}`**
is the ordinal suffix, below.

Anything else the config holds can go in it too - `{location.timezone}` and
the like - because the string is expanded before `strftime` sees it.

The whole thing is a default: `format:` on the Date widget, or in
`kind-settings: {date: {format: ...}}`, outranks it.  That is what to use
for one clock in a language you otherwise want left alone.

## `date-ordinal:` - 26th, 1er, or nothing

```yaml
# en.yaml
date-ordinal: {1: st, 2: nd, 3: rd, 21: st, 22: nd, 23: rd, 31: st, default: th}

# fr.yaml - the first of the month only
date-ordinal: {1: er}
```

Keyed by day of the month, with `default:` for the rest.  A day nothing
matches and no `default:` gives an empty string, so `<sup></sup>` draws
nothing - which is why French needs one entry and no default.

Most languages do not need this key at all.  Of twenty-one locales, only English
attaches a suffix to every day; French uses one on the first; German, Danish,
Norwegian, Finnish, Czech, Icelandic and Hungarian write a plain period,
which is just a character in `date-format:`; and the rest use a bare numeral.
Leave the key out and no suffix is added.

## `strings:` - the everyday words

```yaml
strings:
  pressure: Pressure
  humidity: Humidity
  wind: Wind
  gusting: Gusting
  feels_like: Feels Like
  sunrise: Sunrise
  sunset: Sunset
  moon_phase: Moon Phase
  full_moon: Full Moon
  polar_day: Sun Up All Day
  polar_night: No Sunrise Today
```

A key is lowercase with underscores.  A widget asks for one by name, and **a
key no table has becomes itself, spaced and capitalized** - so `feels_like`
with nothing behind it draws as "Feels Like".

That fallback is why a new plugin reads sensibly in a language nobody has
translated it into yet, and why an untranslated key shows up as English-ish
words rather than as a crash or an empty box.  It also means a typo in a key
is quiet: `humdity` draws as "Humdity" rather than complaining.

## `conditions:` - what the sky is doing

The larger half of the file.  A weather provider never says "Light Rain" - it
emits a notation, and this table is where that notation becomes words.  That
split is what lets a station and a model be described in the same vocabulary,
and what lets a translation exist at all.

```yaml
conditions:
  # sky cover - a separate METAR group, not in 4678
  'SKC':    Clear
  'FEW':    Mostly Clear
  'SCT':    Partly Cloudy
  'BKN':    Mostly Cloudy
  'OVC':    Overcast

  # WMO 4678 present weather
  '-RA':    Light Rain
  'RA':     Rain
  '+RA':    Heavy Rain
  'VCBLSN': Blowing Snow Nearby
```

The codes are WMO Code Table 4678, the present-weather vocabulary a METAR
report is written in, plus the sky-cover groups - which are a separate part of
a METAR and are not in 4678 at all.  The shipped table is 235 entries: 9 of
sky cover and 226 of present weather.

**Translate the meaning, not the English.**  The shipped English is itself a
mechanical rendering of the WMO definitions, so it is a starting point rather
than a source text.  Reach for whatever your national weather service
actually says on a forecast: the German file says `Heiter`, `Wolkig` and
`Stark bewölkt` because that is what the DWD says, not because they are good
translations of "Mostly Clear", "Partly Cloudy" and "Mostly Cloudy".

A code you have no wording for can be left out.  It falls back the same way a
string does, to the code spaced and capitalized, which is ugly but honest -
better than a wrong word for weather somebody is standing in.

## Checking it

Set the language and run a clock:

```
python3 PyQtPiClock3.py examples/berlin.yaml --set language=de
```

The log lists every language it found and which one it chose:

    languages: Deutsch (de), English (en); using de

If yours is not in that list, the file is somewhere that is not being read
from, or its `code:` is not what you thought.

The date is the quickest thing to eyeball, since it is on the screen at all
times and changes shape entirely between languages:

```
python3 PyQtPiClock3.py examples/berlin.yaml --set language=de
```

If it stays English, the file is not being read or its `code:` is not what
you thought.  If the words are right but the order is not, `date-format:` is
missing and English's was used.

For the conditions, point the station at somewhere reporting something
unusual.  A station is a provider rather than a widget, so:

```
python3 PyQtPiClock3.py examples/berlin.yaml --set language=de         --set providers.metar.METAR=NZWD
```

`NZWD` is Williams Field at McMurdo, which reports blowing snow.  It only
transmits while the station is staffed, so if nothing arrives, that is why -
`examples/mcmurdo.yaml` puts a model beside it for exactly that reason.
