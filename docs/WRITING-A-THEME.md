# Writing a theme

A theme is what a page looks like: the picture behind it, the frames round
its boxes, the colors and the fonts, and which art the widgets use.  A page
names one and a layout says where things sit - the two are separate on
purpose, so any theme works with any layout.

    PiClock3/themes/meadow/theme.yaml
    PiClock3/themes/meadow/background.png
    PiClock3/themes/meadow/frame.png

Drawing the frames themselves is [FRAME-ART.md](FRAME-ART.md).

## Where a theme goes

There is a `themes` folder beside `Config.yaml`, at the top of the checkout,
and that one is yours.  It is searched before `PiClock3/themes`, so a theme
of your own named `circuit` is used instead of the shipped one without
touching what ships - and `git pull` never has anything of yours to conflict
with.  It is in `.gitignore` for the same reason.

    PiClock3/themes/        shipped with the project
    themes/                 yours, and searched first

Somebody else's theme is a git repository, cloned straight in:

```
cd PiClock3
git clone https://github.com/someone/piclock3-theme-nightshift themes/nightshift
```

Then name it, in any page of your config:

```yaml
pages:
  clock-page: {order: 0, layout: classic, theme: nightshift}
```

Nothing is registered and nothing is installed - the folder being there is
the whole of it.  To stop using one, name a different theme; to be rid of it,
delete the folder.

**If you mean to contribute the theme to PiClock3 itself**, that is the other
folder: put it in `PiClock3/themes/yours/` and open a pull request.  Being
inside the package is what makes it ship for everybody, and it is why the two
folders exist rather than one.  See
[CONTRIBUTING.md](../CONTRIBUTING.md).

That cuts both ways, and it is the one trap here: **anything a shipped
example names has to live under `PiClock3/`.**  An example pointing at a
theme in the top-level `themes/` works perfectly on the machine it was
written on and arrives at everybody else's clone with its theme missing,
because that folder is not committed.

### A file or a folder, and what a repository should be called

A theme with no art of its own can be a single file, `themes/mine.yaml`.  One
that ships pictures wants a folder, so the pictures travel with it.  Inside a
folder either name works:

    themes/nightshift/theme.yaml        the plain name
    themes/nightshift/nightshift.yaml   the repository named after itself

The second exists because a repository called `piclock3-theme-nightshift`
usually holds a file called `nightshift.yaml`, and cloning it should simply
work.  If you are publishing one, prefer `theme.yaml` - it survives somebody
cloning into a folder they named something else.

Inside a folder, a plain relative path is relative to **that folder**, so a
published theme never has to know where it was installed:

```yaml
background: background.png      # themes/nightshift/background.png
```

`{this-folder}/background.png` says the same thing explicitly, and is what to
write in a file that might be `!include`d from somewhere else.

### Publishing one

A theme repository needs nothing but the yaml and the art.  Worth adding: a
README with a screenshot, a line saying which layouts it was drawn against
(see [WRITING-A-LAYOUT.md](WRITING-A-LAYOUT.md)), and a license for the
images - a theme is mostly pictures, and the license on those is the part
somebody actually has to check.

## The file

A theme is a folder with a `theme.yaml` and whatever art it uses:

```yaml
name: Meadow
description: The meadow background

background: 'background.png'

default:                     # cascades to everything on the page
  font-size: 0.02            # a fraction of the screen height
  font-family: Arial
  background-color: transparent
  color: '#042299'

borders:
  default:
    art: 'frame.png'
    width: 0.012             # frame weight, a fraction of screen height
    inset: 0.5               # where content lands, a fraction of width
  radar:
    art: 'frame.png'
    width: 0.012
    inset: 0.5

kind-settings:               # what the plugins should use
  analog-clock:       {clock-images-folder: darkblue}
  current-conditions: {icons-folder: icons-darkblue}
  forecast:           {icons-folder: icons-darkblue}
```

`default:` sets the page-wide cascade, so pick `color:` against your
background - a pale blue reads well on the dark ones and is close to
invisible on a bright one.

Five of its names are Qt's and mean what Qt means by them: **`color`,
`background-color`, `font-family`, `font-style` and `font-weight`**.  Setting
`color:` once colors the digital clock, the conditions and the forecast, and
a plugin must not use one of those names for anything else.

They arrive by two roads, and neither needs the plugin's cooperation.  The
`default:` block is put on the page itself, and Qt hands its colors and fonts
down to everything drawn on it.  Anything that resolved for one widget - from
`kind-settings:`, from `plugin-settings:`, from the widget's own entry - is
put on that widget's **region**, and reaches whatever the plugin draws there.
Nearer wins, so a `kind-settings` color beats the page's, and a widget that
names a color itself beats both.

`background-color` travels the first road only.  CSS does not inherit it, so
putting it on a region would paint a box behind every child - including the
analog clock's face, which is a picture that expects to see through.  To give
one region a background, use a `styles:` entry, below.

`font-size` is deliberately not among the five.  It is a fraction of whatever
it sits in, and a page is not the same height as a region - the page's `0.02`
would draw a clock face four pixels tall.

`kind-settings:` is how a theme reaches anything else a plugin takes.  The
key is the plugin's **kind** - `analog-clock`, `forecast`, `radar` - and what
follows is merged into the settings of every plugin wearing it.  A kind means
"interchangeable with", so a setting under one means the same thing to all of
them.  `plugin-settings:` does the same for one plugin named exactly, as
`PiClock3.AnalogClock`, for when a kind is too broad.

An instance keeps the last word: a widget that names a value in the config
holds it, whatever the theme says.

### Glows and shadows

`effect:` is an ordinary setting, so a theme reaches it the same way:

```yaml
kind-settings:
  digital-clock: {effect: glow 0.125}
  analog-clock:  {effect: glow 0.04}
  forecast:      {effect: none}
```

`glow <blur> <lighten>`.  The blur is a fraction of the region's height, so
the halo is the same size on an 800x600 panel and on 4K - a fixed pixel count
is a quarter the relative size on one that it is on the other.  `lighten`
brightens the widget's own color for the glow and defaults to 150: a pale
color has clipped to white by then, while a dark one merely brightens, so a
dark-on-light theme does not get a white halo behind dark text.  `none` or
`glow 0` turns it off.

The long form names a color outright, or offsets it into a drop shadow:

```yaml
effect: {type: glow, blur: 0.125, color: '#ffffff', offset: 0}
```

A color cannot go in the short form - yaml reads a space then `#` as the
start of a comment, so it would vanish without a word.

Two things worth knowing.  The effect goes on the **region**, so it covers
everything the widget draws there - for the analog clock that is the dial,
all three hands and the lettering together.  And a widget gets exactly one
effect, so `effect:` is a slot rather than a list.

Only the digital clock ships with one.  Every other widget will take one and
has none by default.

`borders:` are named frames.  A layout asks for `border: true` to get
`default`, or `border: radar` for a named one, and an unknown name falls back
to `default` so any theme works with any layout.

`art` is the PNG.  `width` is the frame's weight as a fraction of screen
height, so it stays the same weight on a small panel as on a big monitor -
0.012 is about 13px at 1080p and 7px at 800x600.  `inset` is where content
lands inside the frame, as a fraction of that width: a frame that glows
inward wants about 0.5, so content sits in the middle of the fade, while a
solid rule with a hard edge wants 1.0, so content sits right against it
instead of being pulled back into a fade that is not there.

Drawing the sheet itself - the 3x3 grid, what gets stretched, and how to
check it - is [FRAME-ART.md](FRAME-ART.md).

`styles:` are named sets of raw Qt stylesheet properties, which a layout
region asks for by name with `style: date`.  This is where a region's own
background belongs, since that is the one Qt name a theme cannot push
through `kind-settings:`.  Both files have a say in them,
and the theme has the last one:

- a layout carries its own under `layout-style-settings:`, because how big
  the text has to be to fit a region is the layout's business.  That is what
  lets a layout look right under a theme that has never heard of it.
- a theme's `styles:` are merged over those, one property at a time.  Setting
  `date: {font-size: 0.4}` changes the size and leaves the alignment the
  layout asked for.

So a theme need only say what it wants to differ.  `meridian` is the one that
does: its date rides above the sun diagram, so the theme sets `date:
{font-size: 0.5}` where its layout asks for 0.62.  The rest leave the layouts'
sizes alone.

A name nothing defines is simply not applied, and says so in the log.

## A background that changes

`background:` takes a folder instead of a picture, and works through it:

```yaml
background:
  folder: 'slides'           # inside the theme, or any path you like
  interval: 305              # seconds on each picture
  fit: contain               # or cover
  color: '#000'              # behind contain, where the picture does not reach
  order: shuffle             # or sorted
```

Only `folder:` is needed; the rest are the defaults above.

`files:` takes its place when the pictures are named one by one rather than
gathered in a folder:

```yaml
background:
  files:
    - '../stag/background.png'
    - '../meadow/background.png'
  interval: 20
  fit: cover
```

A folder is listed again whenever something is put in it; a named set is
fixed.  `examples/gallery.yaml` uses the second form to work through every
background the shipped themes have, which cannot be a folder because each one
lives in its own theme and they all answer to `background.png`.

A relative path, in either form, is inside the theme, the same as any other
art - so a theme can ship its pictures, and `../` reaches a neighboring
theme's.  An absolute path is left alone, which is what your own photographs
want: they are not theme art and do not belong in the theme folder.

`contain` fits the whole picture in and fills what is left with `color:`.
`cover` fills the screen and crops what overhangs, taking the middle rather
than a corner.  Photographs of mixed shapes look better under `cover` on a
small screen, where letterbox bars cost real space.

`shuffle` is a running order dealt once, not a fresh pick each turn, so
stepping back goes to the picture you actually just saw.

Which pages run one follows from which theme they name: give the clock page a
theme with a folder and the maps page one with a picture, and only the clock
changes.  A page nobody is looking at stops until it is showing again.

**F6** steps back, **F7** forward, and **F8** holds on the picture showing.
Pictures are read when they are shown rather than all at once, and the folder
is listed again only when something in it changes - so a photograph dropped in
appears without restarting the clock.
