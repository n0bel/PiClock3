import logging
import os
import yaml
from yamlinclude import YamlIncludeConstructor
from .DottedDict import DottedDict

logger = logging.getLogger(__name__)


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


class Include(YamlIncludeConstructor):
    """!include, resolving {this-folder} against the file being included.

    The tag is handled while the parser runs, so once a config is a
    dictionary nothing records which file a value came from.  Each included
    file is substituted as it is read, which is the only moment that knows.
    """

    def _read_file(self, path, loader, encoding, *args, **kwargs):
        part = super()._read_file(path, loader, encoding, *args, **kwargs)
        return thisFolder(part, os.path.dirname(path))

# DottedDict that reads yaml config files
# allows !include
# allows overrides with keys ending in --


class Config(DottedDict):
    def __init__(self):
        DottedDict.__init__(self)
        Include.add_to_loader_class(
            loader_class=yaml.FullLoader)  # , base_dir='/your/conf/dir')

    def load(self, name):
        """the config, or a sentence saying it is not there.

        Failing here rather than carrying on empty: everything downstream
        assumes a config has pages and widgets, so a name that is not there
        surfaces much later as an attribute missing for no apparent reason.
        """
        if not os.path.isfile(name):
            raise SystemExit("config file not found: %s\n" % name)

        v2 = yaml.load(
            open(name, "r"), Loader=yaml.FullLoader
        )
        # the included files were substituted as they were read; this is
        # the outermost one, which nothing else has seen
        v2 = thisFolder(v2, os.path.dirname(name))
        self._merge(v2, self)

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
                        self._merge(d[key], d[okey])
                        del d[key]
                else:
                    self._overrides(value)

    def _merge(self, source, destination):
        for key, value in source.items():
            if isinstance(value, dict):
                node = destination.setdefault(key, DottedDict())
                self._merge(value, node)
            else:
                destination[key] = value
        return destination
