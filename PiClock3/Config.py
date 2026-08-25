import logging
import os
import yaml
import pprint
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
        if os.path.isfile(name):
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

        The value is read as yaml, so 7 is a number, true is a boolean and
        anything else is the string it looks like - the same reading it would
        get in the file it is standing in for.
        """
        if '=' not in setting:
            raise SystemExit("\n--set wants key=value, not %r\n" % setting)
        path, raw = setting.split('=', 1)
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            raise SystemExit("\ncannot read %r as a value: %s\n" % (raw, e))
        # yaml reads a leading # as a comment, so '#bef' arrives as nothing.
        # A color is the likeliest thing anyone overrides, so an empty
        # reading of a non-empty word is taken as the word.
        if value is None and raw.strip() not in ('', 'null', '~'):
            value = raw.strip()
        here = self
        parts = path.strip().split('.')
        for part in parts[:-1]:
            if not isinstance(here.get(part), dict):
                here[part] = DottedDict()
            here = here[part]
        here[parts[-1]] = value
        logger.info('set %s = %r', path, value)

    def dump(self):
        pprint.pformat(self)

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
