"""Where each kind is looked for, and what named-paths: adds.

    python3 tests/folderstest.py

Six kinds are found on disk rather than imported, and they do not use
their folder lists the same way: a layout is the first file found, while
languages and units are every file found, merged, the last one winning.
So the order is load bearing in two directions, and this is where that is
written down.

The first half is what the folders were before `Folders` existed, with a
bundle in each of the three holder folders to make the order visible.  A
refactor that quietly reorders them is what it is for.

It writes fixture folders under plugins/, themes/ and layouts/, and
removes them again.  It refuses to run over anything already there.

Needs nothing but yaml - no Qt, no config, no network.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3 import Folders                                 # noqa: E402

# one cloned repository in each holder, each bringing every kind it can
BUNDLES = [os.path.join(holder, 'zz-fixture')
           for holder in ('plugins', 'themes', 'layouts')]


class Made():
    """the fixture folders, while a case needs them"""

    def __enter__(self):
        for bundle in BUNDLES:
            if os.path.exists(bundle):
                raise SystemExit('%s is in the way - remove it and run again'
                                 % bundle)
            for kind in ('languages', 'units', 'layouts', 'themes'):
                os.makedirs(os.path.join(bundle, kind))
        return self

    def __exit__(self, *exc):
        for bundle in BUNDLES:
            shutil.rmtree(bundle, ignore_errors=True)


def p(*parts):
    """a path written the way this platform writes one"""
    return os.path.join(*parts)


def fixture(holder, kind):
    return p(holder, 'zz-fixture', kind)


# (name, what to ask, what should come back).  Written out rather than
# built from the same rule the code uses, since a test that shares the
# rule cannot catch the rule being wrong.
def cases():
    out = []

    # a layout or a theme: the first file found wins, so most specific
    # first, and a bundle can only add a name - never replace one
    for kind in ('layouts', 'themes'):
        out.append((
            '%s, most specific first' % kind,
            Folders.roots(kind),
            [kind, p('PiClock3', kind),
             fixture('plugins', kind), fixture('themes', kind),
             fixture('layouts', kind)]))

    # languages and units: every file is read and merged, so the list is
    # least specific first and yours is read last
    for kind in ('languages', 'units'):
        out.append((
            '%s, least specific first' % kind,
            Folders.merging(kind),
            [p('PiClock3', kind),
             fixture('plugins', kind), fixture('themes', kind),
             fixture('layouts', kind), kind]))

    out.append(('icons, and no bundle brings one',
                Folders.roots('icons'),
                ['icons', p('PiClock3', 'icons')]))
    out.append(('plugins: the checkout itself, then plugins/',
                Folders.roots('plugins'), ['', 'plugins']))
    return out


def named():
    """what named-paths: adds, and where it lands in the order"""
    out = []
    Folders.setFrom({'named-paths': {'layouts': '/mine/layouts'}})
    out.append(('a named folder comes first',
                Folders.roots('layouts')[0], '/mine/layouts'))

    Folders.setFrom({'named-paths': {'base': '/work'}})
    out.append(('base is the kind under it',
                Folders.roots('themes')[0], p('/work', 'themes')))
    out.append(('base reaches every kind',
                [Folders.roots(k)[0] for k in ('units', 'icons')],
                [p('/work', 'units'), p('/work', 'icons')]))

    Folders.setFrom({'named-paths': {'base': '/work',
                                     'layouts': '/mine/layouts'}})
    out.append(('the kind is more specific than base',
                Folders.roots('layouts')[:2],
                ['/mine/layouts', p('/work', 'layouts')]))

    Folders.setFrom({'named-paths': {'units': ['/a', '/b']}})
    out.append(('a list, in the order written',
                Folders.roots('units')[:2], ['/a', '/b']))
    out.append(('and last of all when they are merged',
                Folders.merging('units')[-2:], ['/a', '/b'][::-1]))

    Folders.setFrom({'named-paths': {'layouts': ''}})
    out.append(('an empty string names nothing',
                Folders.roots('layouts')[0], 'layouts'))

    Folders.setFrom({})
    out.append(('no block at all is the checkout alone',
                Folders.roots('layouts')[0], 'layouts'))

    # a folder that is not there is the clock's business to ignore and
    # --check's to mention
    Folders.setFrom({'named-paths': {'themes': '/nosuch',
                                     'base': ROOT}})
    out.append(('missing names the path and where it was written',
                Folders.missing(), [('named-paths.themes', '/nosuch')]))
    Folders.setFrom({})
    return out


def main():
    failed = 0
    with Made():
        asked = cases()
    asked += named()
    for name, got, want in asked:
        if got == want:
            print('  ok    %s' % name)
        else:
            failed += 1
            print('  FAIL  %s\n          wanted %r\n          got    %r'
                  % (name, want, got))
    print('\n  %d cases, %d failed' % (len(asked), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
