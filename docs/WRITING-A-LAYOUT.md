# Writing a layout

A layout says where things go.  It names regions; a config puts widgets in
them; a theme says what they look like.  The three are separate on purpose,
so any theme works with any layout and a layout can be swapped without
rewriting the widgets.

```yaml
name: Classic
description: Conditions and two radars left, clock center, forecast right

provides: [current, maps, clock, date, bottom, forecast]

regions:

  current:  {left: 0.0,  top: 0.0,    width: 0.2, height: 0.3333}

  maps:     {left: 0.0,  top: 0.3333, width: 0.2, height: 0.6667,
             border: radar, repeat: {count: 2, direction: down}}

  forecast: {right: 0.0, top: 0.0,    width: 0.2, height: 1.0,
             border: true, repeat: {count: 9, direction: down}}

  clock:    {width: 0.5, aspect: 1.0,
             horizontal-center: 0.0, vertical-center: 0.0}

  date:     {left: 0.2, right: 0.2, top: 0.0,    height: 0.1, style: date}
  bottom:   {left: 0.2, right: 0.2, bottom: 0.0, height: 0.1, style: bottom}
```

## Where a layout goes

There is a `layouts` folder beside `Config.yaml`, at the top of the checkout,
and that one is yours.  It is searched before `PiClock3/layouts`, so a layout
of your own named `classic` is used instead of the shipped one without
touching what ships.  It is in `.gitignore`, so `git pull` never has anything
of yours to conflict with.

    PiClock3/layouts/       shipped with the project
    layouts/                yours, and searched first

Somebody else's is a git repository, cloned straight in, and named in a page:

```
git clone https://github.com/someone/piclock3-layout-tall layouts/tall
```

```yaml
pages:
  clock-page: {order: 0, layout: tall, theme: circuit}
```

A layout is usually one file, `layouts/tall.yaml`, because a layout has no
art - it is geometry.  A folder works too, `layouts/tall/layout.yaml` or
`layouts/tall/tall.yaml`, which is what a repository named after itself looks
like when it is cloned.

**If you mean to contribute the layout to PiClock3 itself**, put it in
`PiClock3/layouts/` and open a pull request - being inside the package is
what makes it ship for everybody.  See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Say which themes it was drawn against

A layout and a theme are separate, but they are not indifferent to each
other: a layout that leaves the middle of the page empty needs a background
with something in the middle, and one that stands nine forecast cells in a
column needs frames narrow enough to hold them.  Both ways round, the pairing
is a real constraint.

So name the themes you drew it against in the `description`, and if you
publish it, in the README.  It saves the next person discovering the pairing
by looking at something that overlaps.

## Say which screen it was designed for

Fractions carry a layout across resolutions, but not across shapes.  A width
is a fraction of the screen's width and a height a fraction of its height, so
on a screen of a different shape every region comes out a different shape
too.  A radar drawn nearly square at 16:9 is a tall narrow slot at 4:3, and
text sized from a region's height no longer fits across its width - the date
runs under the forecast column and the conditions block spills off the side.

Nothing can be done about that unless the layout says what it was drawn on:

```yaml
designed-for: '16:9'
```

With that, core corrects each region's width in proportion to how far the
screen departs from it - wider on a narrower screen, narrower on a wider one
- so a region keeps the shape it was designed with, and the layout renders as
close to its intent as the screen allows.  Text follows, because a region's
text is measured against the shape the region actually came out: one that
kept its shape keeps its text size, one that could not gets it smaller.

Heights are never touched.  A wider screen has no spare height to give, and a
region grown downward would cover the one beneath it.

A region is corrected only if the correction still fits from wherever it is
anchored.  Half-correcting one that cannot fit leaves it the wrong shape
anyway and takes the margin off one side doing it.

Quote it.  Yaml reads a bare `16:9` as sexagesimal - 16x60+9 - and a layout
designed for a screen 969 times wider than tall draws nothing you can read.  A
plain number needs no quoting if you prefer: `designed-for: 1.7778`.

Leave it out and nothing is corrected, which is how every layout behaved
before this existed.  Nothing is assumed on your behalf: guessing 16:9
for a layout drawn on a 4:3 panel would shrink its text on the one screen it
was drawn for.  Every layout that ships here says '16:9', except `panel`.

## Everything is a fraction

`left`, `right`, `top`, `bottom`, `width` and `height` are fractions of the
page, never pixels.  That is what lets one layout serve a 1280x720 panel and
a 1080p monitor without a second copy.  A screen of a different *shape* needs
one thing more - see [the screen it was designed
for](#say-which-screen-it-was-designed-for).

Give an edge and a size: `left` with `width`, `top` or `bottom` with
`height`.  `right: 0.0` means flush to the right edge, not zero width.

### Both edges and no size

Give `left` and `right` and no `width`, and the region is whatever lies
between them.  That is what a strip wants when it has to stay clear of the
columns beside it:

```yaml
current:  {left: 0.0, top: 0.0, width: 0.2, height: 0.3333}
forecast: {right: 0.0, top: 0.0, width: 0.2, height: 1.0, ...}

date:     {left: 0.2, right: 0.2, top: 0.0, height: 0.1, style: date}
```

The strip's edges are the columns' own fractions, and they are corrected the
same way the columns' widths are - so the strip is the gap between them on any
shape of screen.  Work the width out by hand instead and it only holds at the
shape you worked it out for: a narrower screen widens the columns inward while
a fixed width widens outward, and the two close on each other until the text
is sitting over a column.

`aspect: 1.0` makes the region square, measured off its **width** - so on a
16:9 screen `width: 0.3` with `aspect: 1.0` is already about half the height.
That catches people out.

`horizontal-center` and `vertical-center` place a region relative to the
middle of the page, offset by the fraction given.  `0.0` is dead center;
`-0.11` sits it a little high.

## Repeats

A region that repeats becomes several, named `forecast.1`, `forecast.2` and
so on.  A widget can take the whole set - the forecast fills one cell per
hour or day - or a config can name a single cell.

```yaml
forecast: {left: 0.0, bottom: 0.07, width: 1.0, height: 0.20,
           border: true, repeat: {count: 6, direction: across, gap: 0.01}}
```

`direction` is `down` or `across`.  `gap` is a fraction of the span, left
between the cells.

## Borders

`border: true` asks the theme for its `default` frame; `border: radar` asks
for one by name.  A theme that has no such name falls back to `default`, so a
layout never has to know which themes exist.

## Styles

`style: date` asks for a named set of Qt stylesheet properties.  Both files
have a say in what that name means, and the theme has the last word:

```yaml
layout-style-settings:
  date:
    font-size: 0               # as large as fits
    qproperty-alignment: AlignCenter
  bottom:
    font-size: 0
    qproperty-alignment: AlignCenter
```

Carry the sizing here, because how big text has to be to fit a region is the
layout's business - it is what lets a layout look right under a theme that
has never heard of it.  A theme overrides whichever properties it cares to
and leaves the rest.

### How big the text is

A `font-size` written as a bare number is a fraction of the **region's**
height.  One with units, `20px`, is used as written.

**`font-size: 0` means as large as fits.**  Core measures the text against the
region and takes the size down until it fits across, starting from eight
tenths of the region's height.  Use it where the region is the only thing
that constrains the text - a date in a strip that already stops at the columns
either side of it.  A size only ever comes down and never goes back up, so a
clock started on a short date does not clip on a long one.

**`fit: true` alongside a size** is the same measurement used as a limit
rather than a target.  The text is the size you asked for, and shrinks only if
that will not fit.  Use it where the size is a design decision rather than
whatever the box allows - a line that should stay quiet next to a heading, say
- and you want it rescued rather than clipped on a screen you did not draw
for.

The difference matters most where a region is wider than the text needs.  A
`0` fills it; a size with `fit` keeps the proportion you chose.

If a layout names a style and nothing defines it, the region simply gets no
extra styling, and the log says so.

## `provides`

`provides:` lists the region names a config can use.  It is documentation
rather than enforcement, but keep it truthful - it is the first thing
somebody reads when working out what to put where.

## Overriding one while trying things

A `layout:` block in a config is laid over whichever layout a page names,
which is how to try a different geometry without editing the file:

```
python3 PyQtPiClock3.py Config.yaml --set layout.regions.clock.width=0.4
```
