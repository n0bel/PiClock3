"""Run one plugin on its own, in a region made for it.

    python3 tools/plugintest.py <plugin> [options]

    python3 tools/plugintest.py PiClock3.MapLoop
    python3 tools/plugintest.py PiClock3.Forecast --repeat 9 --region 0.25x1.0
    python3 tools/plugintest.py Aurora --base /home/me/clockwork --check

A plugin author has nowhere to try a widget except a whole config: a page,
a layout with a region the right shape, a theme, and every provider it
names.  This writes that config and runs it, so what is being looked at is
the plugin.

Nothing is written into the PiClock3 folder.  The config and the layout
go in one folder in the system temp directory, which the config names with
named-paths:, and the clock writes no log - the terminal you started this
in is the log, and a file would roll the one the real clock keeps.

What it reads from your schema.yaml, so it does not have to be told:

  provides:                  this is a provider, not a widget
  {is: provider, provides:}  a setting that names one, and what it must
                             answer - the tester finds the providers on
                             disk that answer it.  One, and it is used;
                             several, and it lists them and stops, since
                             which one is the author's call

What it cannot know, because only you do: how big the region should be,
and whether the widget expects a repeated one.  --region and --repeat.

Options:
  --region WxH     fractions of the window (default 1.0x1.0, all of it)
  --aspect N       force the region's shape, 1.0 for a square
  --repeat N       a repeated region of N cells, as a forecast column is
  --across         repeat across rather than down
  --set k=v        a setting on the plugin under test, repeatable.
                   With a provider setting in front of it, a setting on
                   that provider instead:
                   --set frame-provider.palette=4
                   --set conditions-provider.METAR=KMSP
  --provider s=P   the plugin to use for provider setting s, which is
                   what a run stops and asks for when several would do:
                   --provider frame-provider=PiClock3.LibreWXRSatellite
  --base FOLDER    a folder of yours holding plugins/, layouts/ and the
                   rest, for a plugin kept outside the PiClock3 folder.
                   One there is named by itself: Aurora, not
                   plugins.Aurora.  Repeatable
  --window N       the window, as a fraction of this desktop (0.5)
  --geometry WxH   the window in pixels instead, 1280x720
  --check          check the config and print it, draw nothing
  --keep           leave the config behind and say where it is
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the clock finds layouts, themes and keys by relative path, so it has
# to start in the PiClock3 folder, and so does whatever reads them here
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3 import Folders                                 # noqa: E402
from PiClock3.ResolvedConfig import pluginFolder             # noqa: E402

# the shipped widget that draws each role, for testing a provider: a
# provider draws nothing, so something has to draw what it supplies
CONSUMER = {
    'map': ('PiClock3.MapLoop', 'base-provider'),
    'frames': ('PiClock3.MapLoop', 'frame-provider'),
    'conditions': ('PiClock3.CurrentConditions', 'conditions-provider'),
    'hourly': ('PiClock3.Forecast', 'forecast-provider'),
    'daily': ('PiClock3.Forecast', 'forecast-provider'),
    'text': ('PiClock3.Text', 'text-provider'),
}


def schemaOf(plugin):
    """the plugin's own schema.yaml, by the name a config would write"""
    folder = pluginFolder(plugin)
    path = os.path.join(folder, 'schema.yaml') if folder else None
    if path is None or not os.path.isfile(path):
        raise SystemExit(
            '\n%s has no schema.yaml%s\n'
            'A schema is required - see docs/WRITING-A-SCHEMA.md.\n'
            'A plugin outside the PiClock3 folder needs --base, and is\n'
            'named by itself: --base /home/me/clockwork, then Aurora.\n'
            % (plugin, '' if path is None else ' at %s' % path))
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}


def wanted(schema, required=True):
    """the provider settings a widget declares, as {setting: [roles]}.

    Required ones only, by default: an optional provider left unnamed is
    the widget as it usually runs.  MapLoop's overlay-provider draws a
    second map over the radar, and naming it for you would be testing
    something nobody asked to see.
    """
    out = {}
    for name, spec in (schema.get('settings') or {}).items():
        if not isinstance(spec, dict) or spec.get('is') != 'provider':
            continue
        if required and not spec.get('required'):
            continue
        out[name] = list(spec.get('provides') or [])
    return out


def installed():
    """every plugin on disk, as {the name a config writes: its folder}.

    Scanned rather than listed, so one you installed, one you are
    writing, or one in a folder --base named is offered beside the
    shipped ones.  A plugin outside the PiClock3 folder is named by
    itself, the way a config has to name it.
    """
    found = {}
    for folder in ('PiClock3', 'plugins'):
        for path in sorted(glob.glob(os.path.join(folder, '*'))):
            found['%s.%s' % (folder, os.path.basename(path))] = path
    for folder in Folders.named('plugins'):
        for path in sorted(glob.glob(os.path.join(folder, '*'))):
            found[os.path.basename(path)] = path
    return found


def providers():
    """the installed plugins that are providers, as {module: schema}"""
    found = {}
    for module, folder in installed().items():
        path = os.path.join(folder, 'schema.yaml')
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as fh:
            schema = yaml.safe_load(fh) or {}
        if schema.get('provides'):
            found[module] = schema
    return found


def needs(schema, setting):
    """what a provider wants before it will answer, as one short note.

    Said in the list of candidates, because the difference between them
    is often only that one of them asks you for something.
    """
    note = []
    for name, spec in (schema.get('settings') or {}).items():
        if not isinstance(spec, dict) or not spec.get('required'):
            continue
        if spec.get('is') == 'apikey':
            note.append('a key in ApiKeys.yaml')
        else:
            note.append('--set %s.%s=' % (setting, name))
    return ', '.join(note)


def choose(setting, roles, found):
    """the provider for one setting: the only one, or ask which.

    One answer is no choice at all, so it is taken.  Several is the
    author's call and not the tester's - a radar under Mapbox and a
    radar under OpenFreeMap are different pictures, and picking one
    quietly is how an author ends up testing against something they did
    not mean.
    """
    able = {module: schema for module, schema in found.items()
            if set(schema['provides']) & set(roles)}
    if not able:
        raise SystemExit(
            '\n%s wants a provider of %s, and nothing here provides it.\n'
            'Name yours: --provider %s=plugins.YourPlugin\n'
            % (setting, ' or '.join(roles), setting))
    if len(able) == 1:
        return list(able)[0]

    width = max(len(m) for m in able)
    lines = []
    for module in sorted(able):
        line = '  --provider %s=%-*s' % (setting, width, module)
        lines.append((line + '  ' + needs(able[module], setting)).rstrip())
    raise SystemExit(
        '\n%s wants a provider of %s, and %d here provide it.\n'
        'Say which:\n\n%s\n'
        % (setting, ' or '.join(roles), len(able), '\n'.join(lines)))


def value(raw):
    """a --set value, read as yaml so 9 is a number and #fff is a color"""
    try:
        got = yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw
    return raw if got is None and raw not in ('', 'null', '~') else got


def desktop(fraction):
    """a window that size against this screen, as WIDTHxHEIGHT.

    Asked of Qt rather than guessed: the point of the fraction is that
    half a screen is half of the screen in front of you.
    """
    from PyQt5.QtGui import QGuiApplication
    app = QGuiApplication([])
    size = QGuiApplication.primaryScreen().size()
    app.quit()
    return '%dx%d' % (int(size.width() * fraction),
                      int(size.height() * fraction))


def region(args):
    """one region, the shape the author asked for.

    The whole window by default: what is being looked at is the plugin,
    so nothing else should be on the screen with it.
    """
    width, height = args.region.lower().split('x')
    if args.aspect:
        # aspect takes the size it is not given: from a height, it works
        # out the width.  Driven from the height on purpose - a window is
        # wider than it is tall, so a square worked out from the width
        # would be taller than the window and get cut off.
        spec = {'height': float(height), 'aspect': float(args.aspect),
                'horizontal-center': 0.0, 'vertical-center': 0.0}
    else:
        spec = {'left': 0.0, 'top': 0.0,
                'width': float(width), 'height': float(height)}
    if args.repeat:
        spec['border'] = True
        spec['repeat'] = {'count': int(args.repeat),
                          'direction': 'across' if args.across else 'down'}
    return spec


def build(args):
    """the whole config: a page, a region, the providers, the plugin"""
    schema = schemaOf(args.plugin)
    entries, widgets = {}, {}
    asked = dict(p.split('=', 1) for p in args.provider)
    found = providers()

    def fill(entry, want, roles):
        """name a provider for one setting, and make its entry.

        Named after the module's last part, so the printout and the
        config read like something somebody wrote.
        """
        module = asked.get(want) or choose(want, roles, found)
        chosen = module.rsplit('.', 1)[-1].lower()
        entries[chosen] = {'plugin': module}
        entry[want] = chosen

    if schema.get('provides'):
        # a provider: name it, and give it the widget that draws its role
        entries['under-test'] = {'plugin': args.plugin}
        roles = list(schema['provides'])
        role = roles[0]
        if role not in CONSUMER:
            raise SystemExit('\nnothing here draws %r\n' % role)
        consumer, setting = CONSUMER[role]
        entry = {'plugin': consumer, 'region': 'test',
                 setting: 'under-test'}
        # that consumer may want providers of its own - a frame source
        # needs a base map under it
        for want, wantRoles in wanted(schemaOf(consumer)).items():
            if want != setting:
                fill(entry, want, wantRoles)
        widgets['drawn-by'] = entry
        subject = ('provider', 'under-test', entries['under-test'])
    else:
        entry = {'plugin': args.plugin, 'region': 'test'}
        for want, roles in wanted(schema).items():
            fill(entry, want, roles)
        widgets['under-test'] = entry
        subject = ('widget', 'under-test', entry)

    for setting in args.set:
        key, raw = setting.split('=', 1)
        if '.' in key:
            # a setting on one of the providers, named by the setting
            # that points at it: frame-provider.palette=4
            where, key = key.split('.', 1)
            named = widgets[list(widgets)[0]].get(where)
            if named is None:
                raise SystemExit(
                    '\n%s names no provider, so %s reaches nothing.\n'
                    'The provider settings here are: %s\n'
                    % (where, key,
                       ', '.join(sorted(wanted(schema, required=False)))
                       or 'none'))
            entries[named][key] = value(raw)
        else:
            subject[2][key] = value(raw)

    config = {
        'pages': {'test-page': {'order': 0, 'layout': 'plugintest',
                                'theme': 'circuit'}},
        'location': {'latitude': 44.98, 'longitude': -93.26},
        'layout': {'regions': {'test': region(args)}},
        # the scratch folder holds the layout, and whatever --base named
        # holds the plugin under test
        'named-paths': {'base': [SCRATCH] + list(args.base)},
        'providers': entries,
        'widgets': widgets,
        'logging-level': 'info',
        # the terminal you started this in is the log: a short run wants
        # no file, and writing one would roll the log of the clock this
        # folder really runs
        'logging-to': 'none',
    }
    return config, subject


# everything this writes, out of the PiClock3 folder: it is not the
# author's work and has no business in their git status.  One fixed
# folder, so a run that is killed before its own cleanup leaves
# something the next run overwrites rather than a trail of directories.
SCRATCH = os.path.join(tempfile.gettempdir(), 'piclock3-plugintest')
CONFIG = os.path.join(SCRATCH, 'Config.yaml')
LAYOUT = os.path.join(SCRATCH, 'layouts', 'plugintest.yaml')


def written(config):
    """the config and the layout it names, in a folder of their own.

    The layout can live out here because the config says so: a folder
    named-paths: names is looked in before the PiClock3 folder's own,
    so the page finds `plugintest` without a file being put in layouts/.
    """
    os.makedirs(os.path.dirname(LAYOUT), exist_ok=True)
    with open(LAYOUT, 'w', encoding='utf-8', newline='\n') as fh:
        yaml.safe_dump({'name': 'Plugin test',
                        'description': 'one region, made by plugintest.py',
                        'regions': config['layout']['regions']},
                       fh, sort_keys=False)
    del config['layout']

    with open(CONFIG, 'w', encoding='utf-8', newline='\n') as fh:
        yaml.safe_dump(config, fh, sort_keys=False)
        # relative, and so read from the PiClock3 folder the clock runs
        # in rather than from beside the config
        fh.write('\napikeys: !include ApiKeys.yaml\n')
    return CONFIG, LAYOUT


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('plugin')
    parser.add_argument('--region', default='1.0x1.0')
    parser.add_argument('--aspect')
    parser.add_argument('--repeat', type=int)
    parser.add_argument('--across', action='store_true')
    parser.add_argument('--set', action='append', default=[])
    parser.add_argument('--provider', action='append', default=[])
    parser.add_argument('--base', action='append', default=[])
    parser.add_argument('--window', type=float, default=0.5)
    parser.add_argument('--geometry')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--keep', action='store_true')
    args = parser.parse_args()

    # before anything is looked for, so a plugin under --base is found
    # here the way the clock will find it
    Folders.setFrom({'named-paths': {'base': list(args.base)}})

    config, (kind, name, entry) = build(args)
    path, layout = written(config)

    print('%s %s, in a %s region' % (kind, args.plugin, args.region))
    for key in sorted(entry):
        if key != 'plugin':
            print('  %-20s %s' % (key, entry[key]))
    if config['providers']:
        print('  providers:')
        for provider in sorted(config['providers']):
            print('    %-18s %s'
                  % (provider, config['providers'][provider]['plugin']))

    # the python running this rather than a name to look up on PATH, so
    # the clock runs under whatever started the tester.  sys.executable
    # is empty only where python is embedded in something else.  A list
    # and not a string: there is no shell here to quote anything for
    command = [sys.executable or 'python3', 'PyQtPiClock3.py', path]
    if args.check:
        command += ['--check']
    else:
        command += ['--geometry', args.geometry or desktop(args.window)]
    print('  %s\n' % ' '.join(command))
    try:
        # from the PiClock3 folder: layouts, themes, languages and
        # ApiKeys.yaml are all found relative to where the clock is run
        return subprocess.call(command, cwd=ROOT)
    finally:
        if args.keep:
            print('\nkept: %s\n      %s' % (path, layout))
        else:
            shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
