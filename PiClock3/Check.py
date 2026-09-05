"""Reading a config against the schemas, before anything is drawn.

A clock has no console.  A misspelled setting is dropped in the merge, a
provider name that does not exist is a KeyError somewhere later, and a region
nobody declares is a widget that draws nowhere - all of them silent, or loud
in a place that says nothing about the config that caused them.

This walks the config once and collects everything it finds:

    problem   it cannot work.  A provider that is not there, a region that
              is not there, a value outside the set its setting allows
    warning   it runs, but not as written.  A setting nobody declares, a
              number outside a range a schema guessed at

Data rather than classes: nothing here imports a plugin or builds a widget,
so a config can be read on a machine with no display and no api keys.  A
plugin is found on disk the way units files are found, and one that ships no
schema contributes nothing rather than a page of complaints about settings
this cannot know.
"""
import glob
import logging
import os

import yaml

logger = logging.getLogger(__name__)

PROBLEM, WARNING = 'problem', 'warning'

HERE = os.path.dirname(os.path.abspath(__file__))


def isTemplate(value):
    """{location.latitude} is a string until something expands it.

    Any setting may hold one, so a value with braces in it is not checked
    against a type, a range or a set - what it will be is not known yet.
    """
    return isinstance(value, str) and '{' in value and '}' in value


def pluginFolder(module):
    """where a plugin's files are, without importing it"""
    part = module.replace('.', os.sep)
    for folder in (part, os.path.join('plugins', part)):
        if os.path.isdir(folder):
            return folder
    return None


def readYaml(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}


class Check():

    def __init__(self, config):
        self.config = config
        self.found = []
        self.types = {}
        self.regions = {}          # layout name -> the regions it declares

    # ------------------------------------------------------------ saying

    def say(self, severity, where, message):
        self.found.append((severity, where, message))

    def problem(self, where, message):
        self.say(PROBLEM, where, message)

    def warning(self, where, message):
        self.say(WARNING, where, message)

    def problems(self):
        return [f for f in self.found if f[0] == PROBLEM]

    def warnings(self):
        return [f for f in self.found if f[0] == WARNING]

    def report(self):
        """every finding, worst first, as lines somebody can read"""
        return ['%-8s %s: %s' % (severity, where, message)
                for severity, where, message
                in self.problems() + self.warnings()]

    # ----------------------------------------------------------- loading

    def load(self):
        """the shapes, before anything is looked at against them"""
        core = readYaml(os.path.join(HERE, 'core-types.yaml')) or {}
        self.types.update(core.get('types') or {})
        self.configSchema = readYaml(
            os.path.join(HERE, 'config-schema.yaml')) or {}
        self.types.update(self.configSchema.get('types') or {})
        self.widgetSchema = readYaml(
            os.path.join(HERE, 'widget-schema.yaml')) or {}

    def pluginSchema(self, module):
        """a plugin's own schema, and the types it invents, or None"""
        folder = pluginFolder(module)
        if folder is None:
            return None
        return readYaml(os.path.join(folder, 'schema.yaml'))

    def layoutRegions(self, name):
        """every region a layout declares, its repeats' cells included.

        The same search PiClock3._loadPart does, because a check that looked
        somewhere else would pass a config the clock then refuses.
        """
        if name in self.regions:
            return self.regions[name]
        part = None
        for base in ('layouts', os.path.join('PiClock3', 'layouts')):
            for path in (os.path.join(base, name + '.yaml'),
                         os.path.join(base, name, 'layout.yaml'),
                         os.path.join(base, name, name + '.yaml')):
                part = part or readYaml(path)
        if part is None:
            self.regions[name] = None
            return None
        names = set()
        for region, spec in (part.get('regions') or {}).items():
            names.add(region)
            repeat = spec.get('repeat') if isinstance(spec, dict) else None
            for cell in range(1, int((repeat or {}).get('count', 0)) + 1):
                names.add('%s.%d' % (region, cell))
        self.regions[name] = names
        return names

    def named(self, kind):
        """what a names: target can legally be, as a set of names.

        None where the answer depends on somewhere else in the config -
        regions belong to a page's layout rather than to the config, so the
        caller resolves those itself.
        """
        if kind == 'providers':
            return set(self.config.get('providers') or {})
        if kind in ('layouts', 'themes'):
            found = glob.glob(os.path.join(kind, '*')) + \
                glob.glob(os.path.join('PiClock3', kind, '*'))
            return {os.path.splitext(os.path.basename(f))[0] for f in found}
        if kind == 'unit-sets':
            sets = (readYaml(os.path.join(HERE, 'units', 'sets.yaml'))
                    or {}).get('sets') or {}
            return set(sets) | set(self.config.get('unit-sets') or {})
        return None

    def everyRegion(self):
        """every region any page's layout declares, cells included.

        None where a page names a layout that is not there, because then
        the answer is not known - and saying every widget sits in a region
        that does not exist would bury the one line that is actually wrong
        under one complaint per widget.
        """
        names = set()
        for page in (self.config.get('pages') or {}).values():
            found = self.layoutRegions((page or {}).get('layout') or '')
            if found is None:
                return None
            names |= found
        return names

    # ---------------------------------------------------------- checking

    def resolve(self, spec, seen=None):
        """a setting's own words, over those of the type it says it is.

        `{is: provider}` carries nothing itself; `provider` carries
        `names: providers`.  A setting saying both keeps its own.
        """
        if not isinstance(spec, dict):
            return {}
        seen = seen or set()
        name = spec.get('is')
        if not isinstance(name, str) or name in seen or name not in self.types:
            return dict(spec)
        seen.add(name)
        merged = self.resolve(self.types[name], seen)
        merged.update(spec)
        return merged

    def alternatives(self, spec):
        """`of: [a, b]` as the specs those names stand for"""
        found = []
        for name in spec.get('of') or []:
            if isinstance(name, str) and name in self.types:
                found.append(self.resolve(self.types[name]))
        return found

    def checkValue(self, where, value, spec):
        """one value against one setting's declaration"""
        if isTemplate(value):
            return
        spec = self.resolve(spec)

        if isinstance(value, list):
            for entry in self.alternatives(spec):
                if entry.get('is') == 'list':
                    inner = entry.get('of')
                    if isinstance(inner, str) and inner in self.types:
                        for n, item in enumerate(value):
                            self.checkValue('%s.%d' % (where, n), item,
                                            self.types[inner])
                    return
            return

        for entry in self.alternatives(spec) or [spec]:
            if entry.get('names') or entry.get('one-of') or entry.get('range'):
                spec = entry if entry.get('names') else spec
                break

        allowed = spec.get('one-of')
        if allowed and value not in allowed:
            self.problem(where, '%r is not one of %s'
                         % (value, ', '.join(str(a) for a in allowed)))
            return

        kind = spec.get('names')
        if kind:
            self.checkName(where, value, kind)

        span = spec.get('range')
        if span and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            if value < span[0] or value > span[1]:
                self.warning(where, '%s is outside %s to %s'
                             % (value, span[0], span[1]))

    def checkName(self, where, value, kind):
        """a string that has to name something that exists"""
        if not isinstance(value, str):
            return
        if kind == 'regions':
            known = self.everyRegion()
            if known is not None and value not in known:
                self.problem(where, 'no region %r - no page\'s layout'
                                    ' declares one' % value)
            return
        known = self.named(kind)
        if known is None:
            return
        if value not in known:
            self.problem(where, 'no %s named %r.  There is %s'
                         % (kind.rstrip('s'), value,
                            ', '.join(sorted(known)) or 'none'))

    @staticmethod
    def blank(entry, name):
        """set to nothing, or not set at all.

        Not falsiness: order: 0 is the first page and precision: 0 is whole
        degrees, and a required setting holding either of those is answered.
        """
        return name not in entry or entry[name] is None or entry[name] == ''

    def checkEntry(self, where, entry, settings, declared, defaults=None,
                   quiet=False):
        """one block of settings against what declares them.

        `defaults` is what the plugin's own config.yaml brings, because that
        is what the clock will merge under this entry - a setting answered
        there is answered, and asking for it again would be asking somebody
        to write out a default that already works.
        """
        if not isinstance(entry, dict):
            return
        merged = dict(defaults or {})
        merged.update(entry)
        for name, spec in (settings or {}).items():
            if spec.get('required') and self.blank(merged, name):
                self.problem('%s.%s' % (where, name), 'must be set')
        for name, value in entry.items():
            if name in declared:
                continue
            if name in (settings or {}):
                self.checkValue('%s.%s' % (where, name), value, settings[name])
            elif not quiet:
                self.warning('%s.%s' % (where, name),
                             'nothing declares this setting, so it is'
                             ' dropped')

    # ----------------------------------------------------------- walking

    def run(self):
        """every finding there is, as (severity, where, message)"""
        self.load()
        settings = self.configSchema.get('settings') or {}
        tables = ('pages', 'providers', 'widgets')

        for name, spec in settings.items():
            if spec.get('required') and self.blank(self.config, name):
                self.problem(name, 'must be set')
        for name, value in self.config.items():
            if name in settings and name not in tables:
                self.checkValue(name, value, settings[name])

        for name, page in (self.config.get('pages') or {}).items():
            self.checkEntry('pages.' + name, page,
                            (self.types.get('page') or {}).get('of'), ())

        for kind in ('providers', 'widgets'):
            for name, entry in (self.config.get(kind) or {}).items():
                self.checkPlugin('%s.%s' % (kind, name), entry,
                                 kind == 'widgets')
        return self.found

    def checkPlugin(self, where, entry, isWidget):
        """one provider or widget entry, against its plugin's schema"""
        if not isinstance(entry, dict) or not entry.get('plugin'):
            self.problem(where, 'does not say which plugin it is.'
                                '  Add plugin: <module>')
            return
        module = entry['plugin']
        schema = self.pluginSchema(module)
        if schema is None:
            self.warning(where, 'no schema for %s, so nothing here is'
                                ' checked' % module)
            return

        self.types.update(schema.get('types') or {})
        settings = dict(schema.get('settings') or {})
        if isWidget:
            settings.update(self.widgetSchema.get('settings') or {})
            settings.update((self.types.get('widget-entry') or {}).get('of')
                            or {})
        else:
            settings.update((self.types.get('provider-entry') or {}).get('of')
                            or {})

        # a widget may also carry the settings of a provider it names -
        # MapLoop hands its own config to its providers, and a radar sets
        # the frame provider's palette: on itself
        # a widget may also carry the settings of a provider it names -
        # MapLoop hands its own config to its providers, and a radar sets
        # the frame provider's palette: on itself.  A name that resolves to
        # nothing leaves us unable to say what is legal here, so the entry
        # keeps its one real complaint rather than one per setting.
        passed, unresolved = set(), False
        for name, value in entry.items():
            spec = self.resolve(settings.get(name) or {})
            if spec.get('names') != 'providers' or isTemplate(value):
                continue
            named = (self.config.get('providers') or {}).get(value) or {}
            theirs = self.pluginSchema(named.get('plugin') or '')
            if theirs is None:
                unresolved = True
            else:
                passed |= set(theirs.get('settings') or {})

        folder = pluginFolder(module)
        defaults = readYaml(os.path.join(folder, 'config.yaml')) or {}
        self.checkEntry(where, entry, settings, passed, defaults,
                        quiet=unresolved)
