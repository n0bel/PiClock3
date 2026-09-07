import logging
import os
import re
import zoneinfo

import tzlocal
import yaml
from yamlinclude import YamlIncludeConstructor
from .DottedDict import DottedDict

logger = logging.getLogger(__name__)

# geometry: as the clock reads it, and as a check reads it - one pattern,
# so the two cannot come to different answers about the same word
GEOMETRY = re.compile(r'^\s*(\d+)\s*[xX,]\s*(\d+)'
                      r'(?:\s*\+\s*(\d+)\s*\+\s*(\d+))?\s*$')


class ConfigError(Exception):
    """a file that will not read, in words somebody can act on.

    It carries the two halves a finding is made of, because whoever
    catches one either stops the program or files it beside the other
    findings, and neither of those wants a traceback.
    """

    def __init__(self, where, message):
        super().__init__('%s: %s' % (where, message))
        self.where = where
        self.message = message


def sentence(problem):
    """what went wrong, in plainer words where there are any.

    yaml's own wording is accurate and mostly readable, so it is what
    comes through.  Only the few people actually hit are rewritten: a
    table with a line per message would age worse than no table.
    """
    if not problem:
        return 'it will not read as yaml'
    if r"'\t'" in problem and 'cannot start any token' in problem:
        return 'a tab, and yaml indents with spaces'
    if 'expected <block end>' in problem:
        return 'the indenting does not line up'
    if 'found unexpected end of stream' in problem:
        return 'a quote is opened and never closed'
    if 'mapping values are not allowed' in problem:
        return 'a colon inside a value, which needs quoting'
    return problem


# what yaml calls input that did not come from a file
NOTAFILE = ('<unicode string>', '<byte string>', '<string>', '<file>')


def yamlFault(path, error):
    """a yaml error as (where, what), with the offending line under it.

    The mark is the whole point: it is what lets a reader be told which
    file and which line, which is otherwise the hardest thing to find
    about a config spread over a dozen of them.

    The mark names the file itself where it can, since an error inside an
    !include belongs to the included file rather than to the one that
    named it, and saying the outer one would send somebody to a line that
    is fine.
    """
    mark = error.problem_mark or error.context_mark
    what = sentence(error.problem)
    if mark is None:
        return path, what
    named = getattr(mark, 'name', None)
    where = path if not named or named in NOTAFILE else named
    snippet = mark.get_snippet()
    return ('%s line %d' % (where, mark.line + 1),
            '%s\n%s' % (what, snippet) if snippet else what)


class NoDuplicates():
    """a loader that will not let a key be written twice.

    yaml lets the second one win without a word, so a config can say
    location: twice and quietly draw the weather for the wrong city.
    Nobody means to write a key twice, so it is said rather than settled.

    Over construct_mapping rather than as a constructor of its own: the
    one that ships yields a block before it fills it, so a document can
    refer to itself, and replacing it would drop that silently.
    """

    MERGE = 'tag:yaml.org,2002:merge'

    def construct_mapping(self, node, deep=False):
        seen = {}
        for keyNode, _ in node.value:
            if keyNode.tag == self.MERGE:
                continue
            key = self.construct_object(keyNode, deep=deep)
            if key in seen:
                raise yaml.MarkedYAMLError(
                    None, None,
                    '%s is written twice, on lines %d and %d'
                    % (key, seen[key], keyNode.start_mark.line + 1),
                    keyNode.start_mark)
            seen[key] = keyNode.start_mark.line + 1
        return super().construct_mapping(node, deep=deep)


class Safe(NoDuplicates, yaml.SafeLoader):
    """every yaml file but the config"""


class Full(NoDuplicates, yaml.FullLoader):
    """the config, which takes !include as well"""


def readYaml(path, loader=Safe):
    """one yaml file, or a ConfigError saying what is wrong with it.

    Everything the clock reads comes through here - the config, layouts,
    themes, languages, units, and a plugin's own two - so a file that
    will not parse names itself the same way wherever it was read from.

    The file has to be there.  A caller that can do without one asks
    first, because not having a theme and having one that will not read
    are different things to say.
    """
    try:
        with open(path, encoding='utf-8') as fh:
            # the text rather than the handle: yaml keeps the line it was
            # reading only for a string, and that line under a caret is
            # most of what makes the answer readable
            part = yaml.load(fh.read(), Loader=loader)
    except yaml.MarkedYAMLError as e:
        raise ConfigError(*yamlFault(path, e))
    except OSError as e:
        raise ConfigError(path, 'cannot be read: %s' % e.strerror)
    if part is None:
        raise ConfigError(path, 'is empty')
    return part


def zoneFor(name):
    """a named zone, or this machine's.

    Blank means the machine's own, which is right for a clock standing
    where it is pointed.  A name it does not know is a warning rather than
    a stop: a clock showing the wrong hour still shows the time.
    """
    name = name.strip() if isinstance(name, str) else ''
    if name:
        try:
            return zoneinfo.ZoneInfo(name)
        except Exception as e:
            logger.warning("timezone %r unknown, using this machine's: %s",
                           name, e)
    return zoneinfo.ZoneInfo(tzlocal.get_localzone_name())


def thisFolder(part, home):
    """{this-folder} is the folder of the yaml that said it.

    The same thing in every file - a config, a theme, a layout, a plugin's
    own defaults - so art travels with whatever ships it and nothing has to
    know where it was installed:

        clock:
          clock-images-base-folder: '{this-folder}/hands'
    """
    where = home.replace(os.sep, '/') or '.'
    if isinstance(part, dict):
        for key, value in part.items():
            part[key] = thisFolder(value, home)
    elif isinstance(part, list):
        return [thisFolder(value, home) for value in part]
    elif isinstance(part, str) and '{this-folder}' in part:
        return part.replace('{this-folder}', where)
    return part


def merge(source, destination, tiers=None, tier=None, path=''):
    """source over destination, recursing into dicts.

    Anything that is not a dict is assigned outright, so a list replaces a
    list rather than extending one.

    `tiers` collects which tier last wrote each dotted path, for a caller
    assembling one config out of several.  It travels as an argument
    because a DottedDict has no attributes to hang it on.

    A function rather than a method, because a theme over a layout and the
    eight tiers under a plugin both need it without holding a Config.
    """
    for key, value in source.items():
        where = path + key
        if isinstance(value, dict):
            # a block replaces whatever is not one, the way a list does.
            # effect: is written either way round, so a tier writing the
            # long form lands on a shorthand string below it
            node = destination.get(key)
            if not isinstance(node, dict):
                node = destination[key] = DottedDict()
            merge(value, node, tiers, tier, where + '.')
        else:
            destination[key] = value
            if tiers is not None:
                tiers[where] = tier
    return destination


class Include(YamlIncludeConstructor):
    """!include, resolving {this-folder} against the file being included.

    The tag is handled while the parser runs, so once a config is a
    dictionary nothing records which file a value came from.  Each included
    file is substituted as it is read, which is the only moment that knows.
    """

    def _read_file(self, path, loader, encoding, *args, **kwargs):
        try:
            part = super()._read_file(path, loader, encoding, *args, **kwargs)
        except OSError:
            # the file is named against the folder the clock was started
            # in rather than the one that said !include, so where it
            # looked is worth saying - it is rarely where you expect
            raise ConfigError(
                '!include %s' % path,
                'is not there.  looked in %s' % os.path.abspath('.'))
        return thisFolder(part, os.path.dirname(path))

# DottedDict that reads yaml config files
# allows !include
# allows overrides with keys ending in --


class Config(DottedDict):
    def __init__(self):
        DottedDict.__init__(self)
        Include.add_to_loader_class(
            loader_class=Full)  # , base_dir='/your/conf/dir')

    def load(self, name):
        """the config, or a sentence saying it is not there.

        Failing here rather than carrying on empty: everything downstream
        assumes a config has pages and widgets, so a name that is not there
        surfaces much later as an attribute missing for no apparent reason.
        """
        if not os.path.isfile(name):
            raise SystemExit("config file not found: %s\n" % name)

        v2 = readYaml(name, Full)
        # the included files were substituted as they were read; this is
        # the outermost one, which nothing else has seen
        v2 = thisFolder(v2, os.path.dirname(name))
        merge(v2, self)

        self._overrides(self)

    def override(self, setting):
        """one key=value from the command line, into a dotted path.

        The value is read the way the file would read it - see value().
        """
        if '=' not in setting:
            raise SystemExit("\n--set wants key=value, not %r\n" % setting)
        path, raw = setting.split('=', 1)
        value = self.value(raw)
        here = self
        parts = path.strip().split('.')
        for part in parts[:-1]:
            if not isinstance(here.get(part), dict):
                here[part] = DottedDict()
            here = here[part]
        here[parts[-1]] = value
        logger.info('set %s = %r', path, value)

    @staticmethod
    def value(raw):
        """one word from the command line, read the way a file would read it.

        yaml, so 7 is a number and true is a boolean - except at the two
        characters where yaml and this program disagree.

        A leading # is a comment to yaml and a color to everybody else, so
        '#bef' would arrive as nothing.  A leading { opens a mapping to yaml
        and a template to this program, so '{plugin-data.now:%H:%M}' would
        arrive as a one-key dict - and then fail somewhere else entirely,
        merging a dict onto a string - while '{this-folder}/hands' would not
        parse at all.  In each case what was meant is plainly the text, so
        the text is what it gets.

        Nothing is lost by it: a mapping is set one leaf at a time from the
        command line, which is what the dotted path is for.
        """
        raw = raw.strip()
        if raw.startswith('{'):
            return raw
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            raise SystemExit("\ncannot read %r as a value: %s\n" % (raw, e))
        if value is None and raw not in ('', 'null', '~'):
            return raw
        return value

    # finds keys ending in --, merges with key of name without --
    def _overrides(self, d):
        keys = list(d.keys())
        for key in keys:
            value = d[key]
            if isinstance(value, dict):
                if key.endswith("--"):
                    okey = key[:-2]
                    if okey in d:
                        merge(d[key], d[okey])
                        del d[key]
                else:
                    self._overrides(value)
