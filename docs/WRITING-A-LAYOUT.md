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

  date:     {left: 0.0,  top: 0.0,    width: 1.0, height: 0.1, style: date}
  bottom:   {left: 0.0,  bottom: 0.0, width: 1.0, height: 0.1, style: bottom}
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

## Everything is a fraction

`left`, `right`, `top`, `bottom`, `width` and `height` are fractions of the
page, never pixels.  That is what lets one layout serve an 800x600 panel and
a 1080p monitor without a second copy.

Give an edge and a size: `left` with `width`, `top` or `bottom` with
`height`.  `right: 0.0` means flush to the right edge, not zero width.

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
    font-size: 0.75            # a fraction of the region's height
    qproperty-alignment: AlignCenter
  bottom:
    font-size: 0.36
    qproperty-alignment: AlignCenter
```

Carry the sizing here, because how big text has to be to fit a region is the
layout's business - it is what lets a layout look right under a theme that
has never heard of it.  A theme overrides whichever properties it cares to
and leaves the rest.

A `font-size` written as a bare number is a fraction of the **region's**
height.  One with units, `20px`, is used as written.

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
