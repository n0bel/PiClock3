"""Where the clock looks for the things a config names.

Six kinds are found by looking on disk rather than by being imported:
layouts, themes, plugins, languages, units and icons.  Each folder list
used to be written out where it was needed, in the same shape four times
over - the name itself, `PiClock3/<name>`, and whatever a cloned
repository brought with it.  They are here instead, so a folder added to
one of them is added everywhere that kind is looked for, and so the
clock and `--check` cannot come to different answers about where
something is.

`named-paths:` adds folders of your own to any of them:

    named-paths:
      base:    /home/me/clockwork      # holds layouts/ themes/ ...
      layouts: /home/me/radar-layouts

Everything in it is optional, a string or a list, and what it names is
looked in before the checkout's own folders.

Two orders come out of here, because the kinds use their answers
differently.  A layout or a theme is one file, so the first one found
wins and the list is most specific first.  Languages and units are
merged, every file that exists being read, so the last one read wins and
they ask for `merging()` instead - the same list backwards.
"""
import glob
import os
import sys

# the three folders a published repository is cloned into, and so the
# three that may carry something else along with them - a layout, a
# theme, words, units.  Not a plugin: `plugin:` names a module path, so
# one inside a theme would have to be called themes.frost.plugins.tides.
HOLDERS = ('plugins', 'themes', 'layouts')

# what named-paths: may name, which is the folder each kind lives in
KINDS = ('layouts', 'themes', 'plugins', 'languages', 'units', 'icons')

# what named-paths: said, and what of it went onto sys.path.  Module
# state, because every folder below is already relative to the directory
# the clock was started in - the search path is one per process, and
# threading it through five call sites would not make it less so.
_named = {}
_added = []


def setFrom(config):
    """read named-paths:, for every search path here to answer from.

    Replaced rather than added to, so a process that reads twenty
    configs - a test suite - starts each one from what it says itself.
    """
    global _named
    _named = dict(config.get('named-paths') or {}) if config else {}
    onPath()


def listed(value):
    """one folder or several: a config may write either"""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if isinstance(v, str)]


def named(kind):
    """the folders named-paths: adds for this kind, most specific first.

    The kind's own key first and base: after it, since naming a folder
    for layouts is the more specific thing to have said.
    """
    out = list(listed(_named.get(kind)))
    out += [os.path.join(base, kind) for base in listed(_named.get('base'))]
    return out


def missing():
    """every named path that is not there, as (where, path).

    A folder that is not there is not an error - the clock reads the
    ones that are - but it is almost always a typo, which is what
    --check is for.
    """
    out = []
    for key in ('base',) + KINDS:
        for path in listed(_named.get(key)):
            if not os.path.isdir(path):
                out.append(('named-paths.%s' % key, path))
    return out


def bundles(kind, holders):
    """what repositories cloned into those folders brought, sorted"""
    out = []
    for holder in holders:
        out += sorted(glob.glob(os.path.join(holder, '*', kind)))
    return out


def shipped(kind):
    """the checkout's own folders for this kind, most specific first.

    Not one rule for all six: a core plugin ships words and units and
    cannot ship a layout, and an icon set is looked for in two folders
    and no bundle.  Written as the four lists they have always been.
    """
    if kind in ('layouts', 'themes'):
        return ([kind, os.path.join('PiClock3', kind)]
                + bundles(kind, HOLDERS))
    if kind in ('languages', 'units'):
        # backwards, because these are read least specific first and
        # merged - see merging().  The last file read wins, so what is
        # yours has to be read after what a bundle brought, and a
        # bundle's after PiClock3's own.
        return ([kind]
                + list(reversed(bundles(kind, ('PiClock3',) + HOLDERS)))
                + [os.path.join('PiClock3', kind)])
    if kind == 'icons':
        return ['icons', os.path.join('PiClock3', 'icons')]
    # plugins: '' is the checkout itself, where PiClock3.MapLoop is
    return ['', 'plugins']


def roots(kind):
    """every folder of this kind, most specific first"""
    return named(kind) + shipped(kind)


def merging(kind):
    """every folder of this kind, least specific first and each once.

    For the kinds that read every file rather than the first: the same
    folders backwards, so what is more specific is read last and wins
    the merge.  Duplicates are dropped here rather than in roots(),
    because which copy of a repeated folder is dropped decides what
    beats what, and only this end of the list has to care.
    """
    out = list(reversed(roots(kind)))
    return [f for i, f in enumerate(out) if f not in out[:i]]


def onPath():
    """the named plugin folders, importable.

    A plugin of yours is named by itself - `plugin: Aurora` - since
    `plugins.Aurora` has to go on meaning the checkout's own, two
    packages not being able to share a name.  What a previous config
    added comes off first, so one process reading two configs does not
    keep the first one's folders.
    """
    for folder in _added:
        while folder in sys.path:
            sys.path.remove(folder)
    del _added[:]
    for folder in named('plugins'):
        where = os.path.abspath(folder)
        sys.path.insert(0, where)
        _added.append(where)
