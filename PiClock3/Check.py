"""Reading a config against the schemas, before anything is drawn.

A clock has no console.  A misspelled setting is dropped in the merge, a
provider name that does not exist is a KeyError somewhere later, and a region
nobody declares is a widget that draws nowhere - all of them silent, or loud
in a place that says nothing about the config that caused them.

Every value is read against what its schema declares, and every name
against the things that exist to be named - regions, themes, layouts,
providers, languages, unit sets, plugin kinds.  Both go as deep as the
config does, and it collects everything rather than stopping at the first:

    problem   it cannot work
    warning   it runs, but not as written

Data rather than classes: nothing here imports a plugin or builds a widget,
so a config can be read on a machine with no display and no api keys.  A
plugin is found on disk the way units files are found, and has to ship a
schema, since without one there is nothing to read its settings against.

What a config comes to is ResolvedConfig's answer rather than one worked out
again here.  A checker with its own idea of the merge agrees with the loader
only by coincidence, and fails the worst way: calling a setting unset when
the clock will find it, and going quiet about one the clock will drop.
"""
import collections
import contextlib
import difflib
import glob
import logging
import os
import re
import zoneinfo

from .Config import ConfigError, GEOMETRY, Lines, readYaml as read
from .ResolvedConfig import (partHolders, partPaths, partRoots,
                             pluginFolder, ResolvedConfig)
from .Units import MEASURE, Units

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

# what a pattern: names, and the shape to say when a value is not one.
# Named rather than written into a schema, so the clock and this read a
# value with one expression
PATTERNS = {'geometry': (GEOMETRY, 'WIDTHxHEIGHT, or WIDTHxHEIGHT+X+Y')}

PRIMITIVES = {'number': (int, float), 'string': str, 'boolean': bool}

# who declares a setting, for the times that is not the entry's own plugin.
# A widget hands its config to the providers it names, so everything here is
# theirs rather than the entry's: a spec is unreadable without the types the
# schema that wrote it invented, and a `names:` pointing into a folder is
# unreadable without the settings that say where that folder is.
Declared = collections.namedtuple('Declared',
                                  'spec types module merged folder')

# what to call the shape of a value, in a sentence.  In order and read
# with isinstance rather than keyed on the exact class: a bool is an int,
# and every block a config holds is a DottedDict rather than a dict - so
# an exact lookup answers a reader with the name of one of our classes.
SHAPES = ((bool, 'true'), (int, 'a number'), (float, 'a number'),
          (str, 'a word'), (list, 'a list'), (dict, 'a block'),
          (type(None), 'nothing'))


def describe(value):
    """what this value is, to say in a sentence about what was wanted"""
    for kind, word in SHAPES:
        if isinstance(value, kind):
            return word
    return 'a %s' % type(value).__name__


def isTemplate(value):
    """{location.latitude} is a string until something expands it.

    Any setting may hold one, so a value with braces in it is not checked
    against a type, a range or a set - what it will be is not known yet.
    """
    return isinstance(value, str) and '{' in value and '}' in value


def mapping(value):
    """a block of settings, or nothing where something else was written.

    Every walk here reads config somebody typed, so a scalar can turn up
    anywhere a block belongs.  checkShape reports it once; the walks past
    that point want it not to be there rather than to raise.
    """
    return value if isinstance(value, dict) else {}


def suggest(known, value):
    """what to say after naming something that is not there.

    The whole list where somebody could read it, and the near misses where
    they could not: there are six hundred timezones.
    """
    if len(known) <= 12:
        return 'There is %s' % (', '.join(sorted(known)) or 'none')
    close = difflib.get_close_matches(str(value), sorted(known), 3)
    if close:
        return 'Did you mean %s' % ', '.join(close)
    return 'There are %d to choose from' % len(known)


def readYaml(path):
    """a yaml file, or None where there is none.

    A file that is there and will not read raises, so a caller with
    somewhere to put a finding can say which file and which line rather
    than treating it as one that was never written.
    """
    if not os.path.isfile(path):
        return None
    return read(path)


class Check():

    def __init__(self, config, resolved=None, source=None, overridden=()):
        self.config = config
        # the file the config was read from, and the dotted paths --set
        # wrote over it, so a finding can say where a value came from.  A
        # caller with neither - a config built in memory - gets findings
        # with no such note, which is the whole of what it costs
        self.source = source
        self.overridden = tuple(overridden)
        self.lines = Lines()
        # the clock resolves a config once and hands it here, so a normal
        # start checks what it is about to build rather than a second copy
        self.resolved = resolved or ResolvedConfig(config).build()
        self.found = []
        self.types = {}
        self.described = set()     # plugins read against their own schema
        self.folders = None        # every plugin installed, found once
        self.redefined = set()     # plugins redefining a core type
        self.units = None          # the units table, read once
        # every timezone, read once and only if a config names one
        self.zones = None
        # the plugin whose settings are being read, as (merged, folder) -
        # what a names: pointing into a folder that plugin declares needs.
        # On self rather than an argument because it has to survive
        # checkValue -> checkBlock -> checkEntry -> checkValue, which is the
        # path an image: inside a markers: list takes.
        self.declaring = ({}, None)

    # ------------------------------------------------------------ saying

    def say(self, severity, where, message):
        self.found.append((severity, self.placed(where), message))

    def placed(self, where):
        """a finding's path, and where that value was written.

        Every finding comes through here, so this is the only place that
        has to know.  A path nothing can be found for is left as it is:
        naming a line that is not the cause is worse than naming none,
        and most of what has no line is a setting that is simply absent.
        """
        if ' ' in where or where.endswith(')'):
            # a plugin's own file, or a path that already says where it
            # came from
            return where
        steps = where.split('.')
        if any(steps[:len(o)] == o for o in self.overridden):
            return '%s (--set)' % where
        if steps[0] in ('layouts', 'themes') and len(steps) > 2:
            path = self.resolved.partFiles.get((steps[0], steps[1]))
            steps = steps[2:]
        else:
            path = self.source
        if not path:
            return where
        line = self.lines.at(path, steps)
        return where if line is None else '%s (%s line %d)' % (
            where, path.replace(os.sep, '/'), line)

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

    def reading(self, path):
        """a yaml file, or None with a finding saying why not.

        Unreadable is collected rather than raised, because a check exists
        to say everything that is wrong at once and one third-party plugin
        with a tab in its schema should not end the run.
        """
        try:
            return readYaml(path)
        except ConfigError as e:
            self.problem(e.where, e.message)
            return None

    def load(self):
        """the shapes, before anything is looked at against them"""
        core = self.reading(os.path.join(HERE, 'core-types.yaml')) or {}
        self.types.update(core.get('types') or {})
        self.configSchema = self.reading(
            os.path.join(HERE, 'config-schema.yaml')) or {}
        self.types.update(self.configSchema.get('types') or {})
        self.widgetSchema = self.reading(
            os.path.join(HERE, 'widget-schema.yaml')) or {}
        self.layoutSchema = self.reading(
            os.path.join(HERE, 'layout-schema.yaml')) or {}
        self.types.update(self.layoutSchema.get('types') or {})
        self.themeSchema = self.reading(
            os.path.join(HERE, 'theme-schema.yaml')) or {}
        self.types.update(self.themeSchema.get('types') or {})
        # what a plugin may not redefine
        self.coreTypes = set(self.types)

    @contextlib.contextmanager
    def typesOf(self, schema, module):
        """a plugin's own types, for as long as its own settings are read.

        Two plugins may both invent a `part`, and they mean different
        shapes, so the names cannot share one table.  A core name is
        another matter: redefining one changes what every other schema
        meant by it, and that is reported rather than allowed.
        """
        mine = schema.get('types') or {}
        for name in sorted(set(mine) & self.coreTypes):
            if module not in self.redefined:
                self.redefined.add(module)
                self.problem('%s schema.yaml' % module,
                             '%s is a core type and this redefines it'
                             % name)
        saved = self.types
        self.types = dict(saved, **mine)
        try:
            yield
        finally:
            self.types = saved

    @contextlib.contextmanager
    def settingsOf(self, merged, folder):
        """whose settings these are, while they are being read"""
        saved = self.declaring
        self.declaring = (merged or {}, folder)
        try:
            yield
        finally:
            self.declaring = saved

    @contextlib.contextmanager
    def readingAs(self, candidate):
        """one candidate's whole world, for as long as its spec is read.

        Its types, because a spec naming one its schema invented is
        otherwise unreadable, and its settings, because a `names:` pointing
        into a folder is answered by where that plugin says the folder is.
        """
        with self.typesOf({'types': candidate.types}, candidate.module):
            with self.settingsOf(candidate.merged, candidate.folder):
                yield

    @contextlib.contextmanager
    def aside(self):
        """findings collected rather than kept, and handed to the caller.

        For a value that has to satisfy only one of several specs: it is
        checked against each, and whichever complaints come of the ones it
        failed are the caller's to keep or to drop.
        """
        saved, mine = self.found, []
        self.found = mine
        try:
            yield mine
        finally:
            self.found = saved

    def pluginSchema(self, module):
        """a plugin's own schema, and the types it invents, or None"""
        folder = pluginFolder(module)
        if folder is None:
            return None
        return self.reading(os.path.join(folder, 'schema.yaml'))

    def named(self, kind):
        """what a names: target can legally be, as a set of names.

        None where the answer depends on somewhere else in the config -
        regions belong to a page's layout rather than to the config, so the
        caller resolves those itself.
        """
        if kind == 'providers':
            return set(self.config.get('providers') or {})
        if kind in ('layouts', 'themes'):
            # a name only counts if loadPart would find something under it,
            # asked with the paths loadPart itself walks - otherwise art
            # sitting loose in themes/ is offered as a theme.  The folders
            # are partRoots' answer rather than a second copy of it: a name
            # the clock loads and this does not know about is the worst
            # thing either of them can say
            found = []
            for root in partRoots(kind):
                found += glob.glob(os.path.join(root, '*'))
            names = {os.path.splitext(os.path.basename(f))[0] for f in found}
            return {n for n in names
                    if any(os.path.isfile(p) for p, _ in partPaths(kind, n))}
        if kind == 'languages':
            # the same folders Languages searches, so a language a plugin
            # ships counts as one
            found = glob.glob(os.path.join('PiClock3', 'languages', '*.yaml'))
            for base in ('PiClock3', 'plugins'):
                found += glob.glob(os.path.join(base, '*', kind, '*.yaml'))
            found += glob.glob(os.path.join(kind, '*.yaml'))
            return {os.path.splitext(os.path.basename(f))[0] for f in found}
        if kind == 'unit-sets':
            return set(self.unitsTable().sets)
        if kind == 'timezones':
            # read once: six hundred names off a Pi's disk is not something
            # to do again for the second clock on a wall of them.  None
            # where there is no table, since a machine with none still runs
            # a clock on its own zone
            if self.zones is None:
                self.zones = zoneinfo.available_timezones() or set()
            return self.zones or None
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
        """`of: [a, b]` as the specs those names stand for.

        A list only.  A block's of: is a mapping of its fields, and a field
        sharing a name with a type would otherwise stand in for the block.
        """
        of = spec.get('of')
        return [self.resolve(self.types[name])
                for name in (of if isinstance(of, list) else [])
                if isinstance(name, str) and name in self.types]

    def accepts(self, spec, seen=None):
        """the primitives a scalar setting may hold, or an empty set where
        it says nothing"""
        seen = seen or set()
        if spec.get('is') in PRIMITIVES:
            return {spec['is']}
        out = set()
        of = spec.get('of')
        # one alternative may be written as the bare name rather than a
        # list of one, and a schema doing that should still be checked
        if isinstance(of, str) and spec.get('is') != 'list':
            of = [of]
        for name in (of if isinstance(of, list) else []):
            if name in PRIMITIVES:
                out.add(name)
            elif name in self.types and name not in seen:
                seen.add(name)
                out |= self.accepts(self.resolve(self.types[name]), seen)
        return out

    def checkShape(self, where, value, spec):
        """a block, a table or a list has to be written as one.

        Known by its fields as well as by the word, since a setting saying
        `is: location` keeps its own `is` through resolve.
        """
        want = spec.get('is')
        if want == 'list':
            shape, ok = 'a list', isinstance(value, list)
        elif want in ('block', 'table') or self.fields(spec):
            shape, ok = 'a block of settings', isinstance(value, dict)
        else:
            return True
        if not ok:
            self.problem(where, 'must be %s, and this is %s'
                         % (shape, describe(value)))
        return ok

    def unitsTable(self):
        """the units table, loaded the way the clock loads it.

        Units wants only a config, and Check has one, so the same reader
        answers here rather than a second one written to agree with it.
        """
        if self.units is None:
            self.units = Units(self)
            self.units.load()
        return self.units

    def checkMeasure(self, where, value, spec):
        """a number written with a unit, against the units its quantity
        names.

        quantity: is what says which are legal - a measure with none is
        Qt's to read, and this leaves it alone.
        """
        quantity = spec.get('quantity')
        if not quantity or not isinstance(value, str):
            return
        table = self.unitsTable().quantities.get(quantity)
        if table is None:
            return              # the schema's fault, and it says so itself
        found = MEASURE.match(value.strip())
        if found is None:
            self.problem(where, '%r is not a number, with or without a unit'
                         % value)
            return
        unit, known = found.group(2).strip(), table.get('units') or {}
        if unit and unit not in known:
            self.problem(where, '%r is not a unit of %s.  There is %s'
                         % (unit, quantity, ', '.join(sorted(known))))

    def checkPattern(self, where, value, spec):
        """a string the clock will read with an expression rather than
        take as it stands"""
        found = PATTERNS.get(spec.get('pattern'))
        if found is None or not isinstance(value, str):
            return
        if not found[0].match(value):
            self.problem(where, '%r is not %s' % (value, found[1]))

    def checkType(self, where, value, spec):
        """a scalar against the primitives its setting takes.

        A boolean is not a number, whatever Python thinks: yaml reads true
        and 1 differently and so does everything downstream.
        """
        allowed = self.accepts(spec)
        if not allowed:
            return
        for name in allowed:
            if isinstance(value, PRIMITIVES[name]) and (
                    name == 'boolean' or not isinstance(value, bool)):
                return
        self.problem(where, '%r is %s, and this takes %s'
                     % (value, describe(value),
                        ' or '.join(sorted(allowed))))

    def fields(self, spec):
        """what a block declares, the with: chain included"""
        out = {}
        base = spec.get('with')
        if isinstance(base, str) and base in self.types:
            out.update(self.fields(self.resolve(self.types[base])))
        of = spec.get('of')
        if isinstance(of, dict):
            out.update(of)
        return out

    def checkBlock(self, where, value, spec):
        """a mapping against what declares its keys.

        A block names its keys and a table invents them, so one is checked
        against fields and the other against the one type its values are.
        """
        for entry in self.alternatives(spec) or [spec]:
            fields = self.fields(entry)
            if fields:
                self.checkEntry(where, value, fields, {}, value)
                return
            if entry.get('is') == 'table':
                of = entry.get('of')
                for name, item in (value.items() if of in self.types else ()):
                    self.checkValue('%s.%s' % (where, name), item,
                                    self.types[of])
                return
            if entry.get('is') == 'block':
                return      # declares no fields, so read somewhere else
        self.problem(where, 'is a block of settings and this setting takes'
                            ' a value')

    def checkList(self, where, value, spec):
        """a list against the one type its items are"""
        for entry in self.alternatives(spec) or [spec]:
            if entry.get('is') == 'list':
                of = entry.get('of')
                for n, item in (enumerate(value) if of in self.types else ()):
                    self.checkValue('%s.%d' % (where, n), item,
                                    self.types[of])
                return
        self.problem(where, 'is a list and this setting does not take one')

    def checkValue(self, where, value, spec):
        """one value against one setting's declaration"""
        if isTemplate(value):
            return
        if value is None or value == '':
            return              # blank is unset, and required: says so
        spec = self.resolve(spec)
        if not self.checkShape(where, value, spec):
            return

        if isinstance(value, dict):
            self.checkBlock(where, value, spec)
            return

        if isinstance(value, list):
            self.checkList(where, value, spec)
            return

        # before one alternative is picked below: a region's border: takes
        # true or a name, and narrowing to the name would reject true
        self.checkType(where, value, spec)
        self.checkMeasure(where, value, spec)
        self.checkPattern(where, value, spec)

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
        if isinstance(kind, dict):
            # a folder the plugin itself declares, rather than one of the
            # things this file knows how to enumerate
            if kind.get('files'):
                self.checkFiles(where, value, kind['files'])
            kind = None
        elif kind:
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
            self.problem(where, 'no %s named %r.  %s'
                         % (kind.rstrip('s'), value, suggest(known, value)))

    def checkFiles(self, where, value, patterns):
        """a name that has to be one of the files a folder holds.

        The folder is one the plugin points at with settings of its own, so
        a pattern names those settings rather than a path:

            names: {files: '{marker-images-folder}/*.png'}

        Several patterns are the several folders a plugin looks in, and the
        answer is what they hold between them, so write the same ones the
        code searches and no others.  Where a theme has pointed a plugin at
        a set of its own, what ships is not among them - the clock does not
        fall through to it, so neither does this.

        A value with a separator in it is a path rather than a name, the
        way `markerPath` reads one.
        """
        if not isinstance(value, str) or not value:
            return
        settings, folder = self.declaring
        if '/' in value.replace(os.sep, '/'):
            if not os.path.isfile(value):
                self.problem(where, 'no file at %r' % value)
            return

        known, looked = set(), []
        if isinstance(patterns, str):
            patterns = [patterns]
        for pattern in patterns:
            found = self.pattern(pattern, settings, folder)
            if found is None or found in looked:
                continue
            looked.append(found)
            known |= {os.path.splitext(os.path.basename(f))[0]
                      for f in glob.glob(found)}
        # nothing to spell against is not a finding: a folder that is not
        # there is the folder's problem, and saying so per value would say
        # it once per marker
        if not known:
            return
        if value not in known:
            self.problem(where, 'no file called %r in %s.  %s'
                         % (value, ' or '.join(
                             os.path.dirname(p).replace(os.sep, '/')
                             for p in looked), suggest(known, value)))

    def pattern(self, text, settings, folder):
        """a names: pattern with the names in it put in.

        A name is one of the plugin's own settings, or a dotted one in the
        config - MapLoop looks in `folders: marker:` before its own set, so
        its patterns have to be able to say so.  Twice around, because a
        setting's value can name another.

        {plugin-folder} is put in from here rather than looked up: the
        clock expands it at the moment a plugin asks, from the module doing
        the asking, so what a config.yaml holds is the word itself.
        {this-folder} is already a path by now, ResolvedConfig having
        replaced it when the file was read.

        None where a name is left over.  The folder is then not known, and
        guessing at it would report every value in it as missing.
        """
        for _ in range(2):
            for name in sorted(set(re.findall(r'{([^{}]+)}', text))):
                if name == 'plugin-folder':
                    found = folder and folder.replace(os.sep, '/')
                else:
                    found = (settings or {}).get(name)
                    if not isinstance(found, str):
                        found = self.dotted(name)
                if isinstance(found, str):
                    text = text.replace('{%s}' % name, found)
        return None if '{' in text else text

    def dotted(self, name):
        """a dotted name against the config itself, or None"""
        found = self.config
        for part in name.split('.'):
            if not isinstance(found, dict):
                return None
            found = found.get(part)
        return found if isinstance(found, str) else None

    def checkProvides(self, where, name, wanted):
        """the provider a setting names has to answer the right question.

        A base map returns one picture and a frame source a stamped series
        of them, so a radar's two cannot be swapped - though the config
        that swaps them reads perfectly well.
        """
        entry = mapping(self.config.get('providers')).get(name)
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
        An empty list is nothing, though - a widget whose region: is []
        draws nowhere - and only required settings ask, so MapLoop's
        captions: [] goes on meaning what it means.
        """
        return name not in entry or any(entry[name] is v or entry[name] == v
                                        for v in (None, '', [], {}))

    def checkEntry(self, where, entry, settings, declared, merged=None,
                   quiet=False, required=True, module=None, owns=False):
        """one block of settings against what declares them.

        Two questions, two subjects.  `required` is asked of `merged`,
        everything the clock will hand the plugin, because a setting any of
        the eight tiers fills in is set.  Whether anything declares a
        setting is asked of the entry, the only place it can be misspelled.

        A kind-settings: block is only part of what a plugin will get, so
        it answers the second question and not the first.

        `declared` is what somebody other than this entry's own plugin
        declares - the providers it names - as name to the specs that
        declare it.  A setting in there used to be skipped, which said its
        name was legal and never looked at its value.
        """
        if not isinstance(entry, dict):
            return
        merged = entry if merged is None else merged
        for name, spec in (settings or {}).items() if required else ():
            if spec.get('required') and self.blank(merged, name):
                self.problem('%s.%s' % (where, name), 'must be set')
        for name, value in entry.items():
            candidates = list((declared or {}).get(name) or ())
            if name in (settings or {}):
                # this entry's own plugin first, and with no types of its
                # own to install: typesOf has already installed them
                candidates.insert(0, Declared(settings[name], None, module,
                                              self.declaring[0],
                                              self.declaring[1]))
            if candidates:
                self.checkDeclared('%s.%s' % (where, name), value, candidates,
                                   owns and name in (settings or {}))
            elif not quiet:
                self.warning('%s.%s' % (where, name),
                             'nothing declares this setting, so it is'
                             ' dropped')
        self.checkNarrowed(where, entry, settings, declared, merged, owns)

    def checkNarrowed(self, where, entry, settings, declared, merged, owns):
        """a narrowed setting the entry does not write for itself.

        The loop above asks about what an entry says, which is where a
        misspelling can be.  A narrowing has to be asked of what the
        plugin will actually get instead, because `zoom: 11` reaches a
        radar from kind-settings: as readily as from the widget and a
        frame service that stops at 7 minds either way.

        The block cannot answer it - a kind block reaches every radar and
        which frame provider each names is not knowable there, so a block
        saying 11 is right for a clock whose radars all use LibreWXR.
        Here is where both halves are known.

        Only names the entry's own plugin declares and a named provider
        also declares, so a setting nobody narrowed is asked nothing new.
        """
        if not owns or not merged:
            return
        for name, candidates in (declared or {}).items():
            if name in entry or name not in (settings or {}):
                continue
            if self.blank(merged, name):
                continue
            for candidate in candidates:
                with self.readingAs(candidate):
                    self.checkValue('%s.%s' % (where, name),
                                    merged[name], candidate.spec)

    def checkDeclared(self, where, value, candidates, owned=False):
        """one value against every spec that declares its name.

        Usually there is one.  Several is a widget naming two providers
        that both declare `style:`, or a kind block reaching every plugin
        wearing the kind - and they rarely agree, since `style:` is a
        Mapbox style id to one and one of Google's four maptypes to the
        other.  So a value any of them takes is taken here: the config
        names which plugin actually reads it, and that one is entitled to
        its own vocabulary.

        `owned` is the case that is not that.  When the entry's own
        plugin declares the name, the setting is the widget's and a
        provider declaring it too is *narrowing* it rather than offering
        another word for it - MapLoop owns `zoom:` and hands a view to
        whoever it names, so a frame service that stops at zoom 7 is
        saying so about MapLoop's zoom rather than about one of its own.
        Every spec has to take the value there, where any of them will do
        above.  Nothing else tells the two apart: `style:` is only ever
        declared by the providers, never by MapLoop.
        """
        if owned:
            for candidate in candidates:
                with self.readingAs(candidate):
                    self.checkValue(where, value, candidate.spec)
            return
        if len(candidates) == 1:
            with self.readingAs(candidates[0]):
                self.checkValue(where, value, candidates[0].spec)
            return
        blamed = []
        for candidate in candidates:
            with self.readingAs(candidate):
                with self.aside() as found:
                    self.checkValue(where, value, candidate.spec)
            if not found:
                return
            blamed.append(candidate.module)
        # one line rather than one per candidate, which is what checking a
        # value against each of them gives and is several ways of saying
        # the same thing about the same line.
        #
        # A kind-settings: block belongs to no one plugin, so its own spec
        # has no name to give - and where none of them has, the sentence
        # ends without a list rather than with an empty one.
        named = sorted(set(m for m in blamed if m))
        self.problem(where, '%r suits nothing that declares it%s'
                     % (value, ': %s' % ', '.join(named) if named else ''))

    # ----------------------------------------------------------- walking

    def run(self):
        """every finding there is, as (severity, where, message)"""
        self.load()

        # a layout or theme that is there and will not read, first: every
        # region it would have declared is about to be missing, and none
        # of what follows from that is the mistake anybody made
        for where, _, error in self.resolved.unreadable:
            self.problem('%s (%s)' % (where, error.where), error.message)

        settings = self.configSchema.get('settings') or {}
        tables = ('pages', 'providers', 'widgets')

        for name, spec in settings.items():
            if spec.get('required') and self.blank(self.config, name):
                self.problem(name, 'must be set')
        for name, value in self.config.items():
            if name not in settings:
                self.warning(name, 'nothing declares this setting, so it is'
                                   ' dropped')
            elif name not in tables:
                self.checkValue(name, value, settings[name])
            else:
                # walked below, so only their shape is asked here
                self.checkShape(name, value, self.resolve(settings[name]))

        page = self.types.get('page') or {}
        for name, entry in mapping(self.config.get('pages')).items():
            if self.checkShape('pages.' + name, entry, self.resolve(page)):
                self.checkEntry('pages.' + name, entry, page.get('of'), {})

        for kind in ('providers', 'widgets'):
            for name, entry in mapping(self.config.get(kind)).items():
                self.checkPlugin('%s.%s' % (kind, name), entry,
                                 kind == 'widgets')

        for where, region, key, name in self.resolved.unnamed:
            self.warning('%s.%s.%s' % (where, region, key),
                         "no %s named %r, so this region takes the theme's"
                         ' default' % (key, name))

        self.checkParts()
        self.checkClashes()
        self.checkKinds()
        self.checkSettings('', self.config)
        # last, because it only asks about providers a widget named, and
        # that is not known until every widget has been read
        self.checkKeys()
        return self.found

    def checkParts(self):
        """each layout and theme a page named, against its own schema.

        Read once however many pages share it, and as ResolvedConfig
        settled it, so the config's layout: and theme: blocks are checked
        where they land rather than where they were written.
        """
        for kind, schema in (('layouts', self.layoutSchema),
                             ('themes', self.themeSchema)):
            seen = set()
            for pageName, page in mapping(self.config.get('pages')).items():
                name = mapping(page).get(kind[:-1])
                part = self.resolved.pages.get(pageName)
                if not isinstance(name, str) or name in seen or part is None:
                    continue
                seen.add(name)
                part = part[0 if kind == 'layouts' else 1]
                self.checkEntry('%s.%s' % (kind, name), part,
                                schema.get('settings') or {}, {})
                if kind == 'themes':
                    self.checkSettings('%s.%s.' % (kind, name), part)

    def checkClashes(self):
        """a layout or theme name that more than one folder answers to.

        loadPart takes the first that exists and says nothing, which was
        fine while there were two folders and one of them was yours.  A
        repository may now bring a part along with it, so two installed
        themes can each carry a layout called `tall` and the one that wins
        is whichever sorted first.

        Every name, not only the ones a page uses: somebody who installs
        two themes should hear about it before they switch pages and
        wonder.
        """
        for kind in ('layouts', 'themes'):
            for name in sorted(self.named(kind) or ()):
                paths = [p.replace(os.sep, '/')
                         for p in partHolders(kind, name)]
                if len(paths) < 2:
                    continue
                self.warning(
                    '%s.%s' % (kind, name),
                    '%d folders hold a %s called %r.  %s is used; %s %s not'
                    % (len(paths), kind[:-1], name, paths[0],
                       ' and '.join(paths[1:]),
                       'is' if len(paths) == 2 else 'are'))

    def installed(self):
        """every plugin folder on this machine, whether a config uses it.

        No schema is nothing to spell a setting against, and naming such a
        plugin is a problem in its own right.  Somebody else's may sit a
        level down, the way a clone leaves it.
        """
        if self.folders is None:
            self.folders = [
                f for f in (glob.glob(os.path.join('PiClock3', '*'))
                            + glob.glob(os.path.join('plugins', '*'))
                            + glob.glob(os.path.join('plugins', '*', '*')))
                if os.path.isfile(os.path.join(f, 'schema.yaml'))]
        return self.folders

    def declaredFor(self, block, key):
        """what a settings block's target declares, from disk.

        Whether a block reaches anything changes when a provider is
        swapped, so it is not asked.  Whether a setting exists at all is
        spelling, and that is what is asked here.
        """
        if block == 'plugin-settings':
            # named exactly, so found the way the loader finds it
            folder = pluginFolder(key)
            folders = [f for f in [folder] if f and os.path.isfile(
                os.path.join(f, 'schema.yaml'))]
        else:
            folders = [f for f in self.installed()
                       if (self.reading(os.path.join(f, 'config.yaml'))
                           or {}).get('kind') == key]
        settings, types = {}, {}
        for folder in folders:
            schema = self.reading(os.path.join(folder, 'schema.yaml')) or {}
            settings.update(schema.get('settings') or {})
            types.update(schema.get('types') or {})
            if not schema.get('provides'):
                settings.update(self.widgetSchema.get('settings') or {})
        return settings, types

    def checkSettings(self, where, holder):
        """the two settings blocks of a config or of a theme.

        A widget hands its own config to the providers it names, so a
        setting one of those declares belongs here too.
        """
        for block in ('kind-settings', 'plugin-settings'):
            for key, values in mapping(holder.get(block)).items():
                at = '%s%s.%s' % (where, block, key)
                if not isinstance(values, dict):
                    self.problem(at, 'must be a block of settings')
                    continue
                settings, types = self.declaredFor(block, key)
                if not settings:
                    continue    # nothing installed to spell it against
                with self.typesOf({'types': types}, key):
                    self.checkEntry(at, values, settings,
                                    self.passedAnywhere(), required=False)

    def passedAnywhere(self):
        """every setting any provider in this config declares.

        A widget passes its own config down, so naming one of these in a
        settings block is how a radar sets its frame provider's palette.
        Which provider is not knowable here - a block reaches whatever a
        widget happens to name - so every one of them is a candidate and
        the value has only to suit one.
        """
        passed = {}
        for entry in (self.config.get('providers') or {}).values():
            module = mapping(entry).get('plugin') or ''
            self.addDeclared(passed, self.pluginSchema(module), module)
        return passed

    def addDeclared(self, passed, schema, module):
        """what one schema declares, into a name-to-candidates mapping.

        The declaring plugin's own settings travel with each of them: a
        `names:` pointing into a folder is answered by where *that* plugin
        says its folder is, not where the entry writing the value does.
        """
        folder = pluginFolder(module or '')
        merged = {}
        if folder:
            merged, _ = self.resolved.pluginConfig(folder, {}, False)
        for name, spec in ((schema or {}).get('settings') or {}).items():
            passed.setdefault(name, []).append(
                Declared(spec, schema.get('types') or {}, module,
                         merged, folder))

    def checkKinds(self):
        """a kind two plugins wear and disagree about.

        A widget and a provider take different settings, so a block aimed
        at a kind they both wear has no single meaning.  Only where a
        block aims at it, and only this config's own.
        """
        worn = {}
        for section in ('providers', 'widgets'):
            for entry in mapping(self.config.get(section)).values():
                module = mapping(entry).get('plugin') or ''
                folder = pluginFolder(module)
                if folder is None:
                    continue
                kind = (self.reading(os.path.join(folder, 'config.yaml'))
                        or {}).get('kind')
                if not kind:
                    continue
                schema = self.reading(
                    os.path.join(folder, 'schema.yaml')) or {}
                role = 'provider' if schema.get('provides') else 'widget'
                worn.setdefault(kind, {}).setdefault(role, set()).add(module)

        for kind in sorted(mapping(self.config.get('kind-settings'))):
            roles = worn.get(kind) or {}
            if len(roles) > 1:
                self.warning('kind-settings.%s' % kind,
                             'reaches %s, which do not take the same'
                             ' settings' % ', and '.join(
                                 '%s %s' % (role, ', '.join(sorted(
                                     roles[role]))) for role in sorted(roles)))

    def checkKeys(self):
        """every setting declared an apikey, on a provider something uses.

        Reachable rather than declared: a config may list six providers and
        point at four, so the two nothing draws with are not asked for a
        key.  Which four is the merge's answer, since a config may point
        at one from kind-settings: rather than from the widget itself.
        """
        for name in sorted(self.resolved.usedProviders()):
            entry = mapping(self.config.get('providers')).get(name)
            if not isinstance(entry, dict) or not entry.get('plugin'):
                continue
            folder = pluginFolder(entry['plugin'])
            if folder is None:
                continue            # checkPlugin has already said so
            settings = (self.reading(os.path.join(folder, 'schema.yaml'))
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
            keys = mapping(self.config.get('apikeys'))
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
        schema = self.reading(os.path.join(folder, 'schema.yaml'))
        if schema is None:
            self.problem(where, '%s has no schema.yaml, which is required'
                         % module)
            return

        # provides: is what a provider has and a widget has not, so it
        # answers both halves of "is this in the right section" without
        # importing the class the way the loader does.  Asked here rather
        # than of whoever names it, so it is said once and reaches a
        # provider nothing points at yet.
        if isWidget and schema.get('provides'):
            self.problem(where, '%s answers %s, so it is a provider.  Move'
                                ' it to providers:'
                         % (module, ', '.join(sorted(schema['provides']))))
        elif not isWidget and not schema.get('provides'):
            self.problem(where, '%s has no provides:, so it answers nothing.'
                                '  A provider names what it can be asked:'
                                ' map, frames, conditions, hourly, daily.'
                                '  A widget belongs in widgets:' % module)

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
        passed, unresolved = {}, False
        with self.typesOf(schema, module):
            for name, value in entry.items():
                spec = self.resolve(settings.get(name) or {})
                if (spec.get('names') != 'providers' or isTemplate(value)
                        or not isinstance(value, str)):
                    continue    # checkValue says what a non-name is
                named = mapping(self.config.get('providers')).get(value) or {}
                theirs = self.pluginSchema(named.get('plugin') or '')
                if theirs is None:
                    unresolved = True
                else:
                    self.addDeclared(passed, theirs, named.get('plugin'))

            # a plugin's defaults against its own schema, once however
            # many instances there are: the two describe one thing
            if module not in self.described:
                self.described.add(module)
                defaults = self.reading(
                    os.path.join(folder, 'config.yaml')) or {}
                for name in sorted(set(defaults) - set(settings) - {'kind'}):
                    self.problem('%s config.yaml' % module,
                                 '%s is a default and no schema declares it'
                                 % name)

            # what the clock will hand this plugin, all eight tiers of it
            merged, _ = self.resolved.pluginConfig(pluginFolder(module),
                                                   entry, isWidget)
            with self.settingsOf(merged, folder):
                self.checkEntry(where, entry, settings, passed, merged,
                                quiet=unresolved, module=module, owns=True)
