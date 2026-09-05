"""Reading a config against the schemas, before anything is drawn.

A clock has no console.  A misspelled setting is dropped in the merge, a
provider name that does not exist is a KeyError somewhere later, and a region
nobody declares is a widget that draws nowhere - all of them silent, or loud
in a place that says nothing about the config that caused them.

This walks the config once and collects everything it finds:

    problem   it cannot work.  A provider that is not there, a region that
              is not there, a value outside the set or the range its
              setting allows, a plugin whose schema does not describe it
    warning   it runs, but not as written.  A setting nobody declares, a
              block of settings that reaches nothing, a missing api key

Data rather than classes: nothing here imports a plugin or builds a widget,
so a config can be read on a machine with no display and no api keys.  A
plugin is found on disk the way units files are found, and has to ship a
schema, since without one there is nothing to read its settings against.

What a config comes to is ResolvedConfig's answer rather than one worked out
again here.  A checker with its own idea of the merge agrees with the loader
only by coincidence, and fails the worst way: calling a setting unset when
the clock will find it, and going quiet about one the clock will drop.
"""
import glob
import logging
import os
import re

import yaml

from .ResolvedConfig import ResolvedConfig

logger = logging.getLogger(__name__)

PROBLEM, WARNING = 'problem', 'warning'

HERE = os.path.dirname(os.path.abspath(__file__))

# a key given as the name of an apikeys: entry rather than in place
APIKEY = re.compile(r'^\{apikeys\.([A-Za-z0-9_-]+)\}$')

# what examples/ApiKeys.yaml writes where a key goes.  A substring, so the
# service can be named after it
PLACEHOLDER = 'YOUR API KEY'

# no service issues one this short
MINKEY = 5


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

    def __init__(self, config, resolved=None):
        self.config = config
        # the clock resolves a config once and hands it here, so a normal
        # start checks what it is about to build rather than a second copy
        self.resolved = resolved or ResolvedConfig(config).build()
        self.found = []
        self.types = {}
        self.used = set()          # providers a widget actually names

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
        """every region any page's layout declares, cells included, or None
        where a page names a layout that is not there"""
        if self.resolved.anyLayoutMissing():
            return None
        return self.resolved.regions()

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
            self.problem(where, '%r is not one of the allowed values: %s'
                         % (value, ', '.join(str(a) for a in allowed)))
            return

        kind = spec.get('names')
        if kind:
            self.checkName(where, value, kind)
        if kind == 'providers' and spec.get('provides'):
            self.checkProvides(where, value, spec['provides'])

        span = spec.get('range')
        if span and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            if value < span[0] or value > span[1]:
                self.problem(where, '%s is not in the allowed range of'
                                    ' %s to %s' % (value, span[0], span[1]))

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

    def checkProvides(self, where, name, wanted):
        """the provider a setting names has to answer the right question.

        A base map returns one picture and a frame source a stamped series
        of them, so a radar's two cannot be swapped - though the config
        that swaps them reads perfectly well.
        """
        entry = (self.config.get('providers') or {}).get(name)
        if not isinstance(entry, dict):
            return                  # checkName has already said so
        module = entry.get('plugin') or ''
        schema = self.pluginSchema(module)
        if schema is None:
            return                  # checkPlugin has already said so
        has = schema.get('provides')
        if not has:
            return                  # checkPlugin has already said so
        if not set(has) & set(wanted):
            self.problem(where, '%r provides %s, and this wants %s'
                         % (name, ', '.join(sorted(has)),
                            ' or '.join(sorted(wanted))))

    @staticmethod
    def blank(entry, name):
        """set to nothing, or not set at all.

        Not falsiness: order: 0 is the first page and precision: 0 is whole
        degrees, and a required setting holding either of those is answered.
        """
        return name not in entry or entry[name] is None or entry[name] == ''

    def checkEntry(self, where, entry, settings, declared, merged=None,
                   quiet=False):
        """one block of settings against what declares them.

        Two questions, two subjects.  `required` is asked of `merged`,
        everything the clock will hand the plugin, because a setting any of
        the eight tiers fills in is set.  Whether anything declares a
        setting is asked of the entry, the only place it can be misspelled.
        """
        if not isinstance(entry, dict):
            return
        merged = entry if merged is None else merged
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

        self.checkKinds()
        # last, because it only asks about providers a widget named, and
        # that is not known until every widget has been read
        self.checkKeys()
        return self.found

    def checkKinds(self):
        """a kind-settings: block aimed at a kind nothing here wears.

        The quietest way to write a setting that does nothing: a kind
        nobody wears merges into nothing at all.

        This config's own only.  A shipped theme styles kinds a config need
        not have, and those are not the config's mistake.
        """
        worn = set()
        for section in ('providers', 'widgets'):
            for entry in (self.config.get(section) or {}).values():
                folder = pluginFolder((entry or {}).get('plugin') or '')
                if folder is None:
                    continue
                kind = (readYaml(os.path.join(folder, 'config.yaml'))
                        or {}).get('kind')
                if kind:
                    worn.add(kind)
        for kind in sorted(self.config.get('kind-settings') or {}):
            if kind not in worn:
                self.warning('kind-settings.%s' % kind,
                             'nothing in this config is a %s, so this block'
                             ' reaches nothing.  There is %s'
                             % (kind, ', '.join(sorted(worn)) or 'nothing'))

    def checkKeys(self):
        """every setting declared an apikey, on a provider something uses.

        Reachable rather than declared: a config may list six providers and
        point at four, so the two nothing draws with are not asked for a
        key.
        """
        for name in sorted(self.used):
            entry = (self.config.get('providers') or {}).get(name)
            if not isinstance(entry, dict) or not entry.get('plugin'):
                continue
            folder = pluginFolder(entry['plugin'])
            if folder is None:
                continue            # checkPlugin has already said so
            settings = (readYaml(os.path.join(folder, 'schema.yaml'))
                        or {}).get('settings') or {}
            merged, _ = self.resolved.pluginConfig(folder, entry, False)
            for setting, value in merged.items():
                spec = self.resolve(settings.get(setting) or {})
                if spec.get('is') == 'apikey':
                    self.checkKey('providers.%s.%s' % (name, setting), value)

    def checkKey(self, where, value):
        """one key, as far as anything short of the service can tell.

        Whether a key is accepted is the service's answer, so this only
        catches what is plainly not a key at all.  A value naming an
        apikeys: entry is followed there first; one written in place is
        taken as the key itself.
        """
        named = APIKEY.match(str(value or '').strip())
        if named:
            keys = self.config.get('apikeys') or {}
            wanted = named.group(1)
            if wanted not in keys:
                self.problem(where, 'wants apikeys.%s and the config has no'
                                    ' such key' % wanted)
                return
            where, value = '%s (apikeys.%s)' % (where, wanted), keys[wanted]

        value = str(value or '').strip()
        if not value:
            self.problem(where, 'is empty - put your key there')
        elif len(value) < MINKEY:
            self.problem(where, 'is %r, too short to be a key' % value)
        elif PLACEHOLDER in value.upper():
            self.problem(where, 'is still %r - put your own key there'
                         % value)

    def checkPlugin(self, where, entry, isWidget):
        """one provider or widget entry, against its plugin's schema"""
        if not isinstance(entry, dict) or not entry.get('plugin'):
            self.problem(where, 'does not say which plugin it is.'
                                '  Add plugin: <module>')
            return
        module = entry['plugin']
        part = module.replace('.', '/')
        # two faults behind one None, wanting different sentences: the
        # plugin is not on disk, or it is and has no schema
        folder = pluginFolder(module)
        if folder is None:
            self.problem(where, 'no plugin %s.  Looked for %s/ and'
                                ' plugins/%s/' % (module, part, part))
            return
        schema = readYaml(os.path.join(folder, 'schema.yaml'))
        if schema is None:
            self.problem(where, '%s has no schema.yaml, which is required'
                         % module)
            return

        # asked of the provider rather than of whoever names it, so it is
        # said once and reaches one nothing points at yet
        if not isWidget and not schema.get('provides'):
            self.problem(where, '%s has no provides:, so it answers nothing.'
                                '  A provider names what it can be asked:'
                                ' map, frames, conditions, hourly, daily'
                         % module)

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
        # the frame provider's palette: on itself.  A name that resolves to
        # nothing leaves us unable to say what is legal here, so the entry
        # keeps its one real complaint rather than one per setting.
        passed, unresolved = set(), False
        for name, value in entry.items():
            spec = self.resolve(settings.get(name) or {})
            if spec.get('names') != 'providers' or isTemplate(value):
                continue
            if isWidget:
                self.used.add(value)
            named = (self.config.get('providers') or {}).get(value) or {}
            theirs = self.pluginSchema(named.get('plugin') or '')
            if theirs is None:
                unresolved = True
            else:
                passed |= set(theirs.get('settings') or {})

        # what the clock will hand this plugin, all eight tiers of it
        merged, _ = self.resolved.pluginConfig(pluginFolder(module), entry,
                                               isWidget)
        self.checkEntry(where, entry, settings, passed, merged,
                        quiet=unresolved)
