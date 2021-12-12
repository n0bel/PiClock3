import os
import yaml
import pprint
from yamlinclude import YamlIncludeConstructor
from .DottedDict import DottedDict

# DottedDict that reads yaml config files
# allows !include
# allows overrides with keys ending in --


class Config(DottedDict):
    def __init__(self):
        DottedDict.__init__(self)
        YamlIncludeConstructor.add_to_loader_class(
            loader_class=yaml.FullLoader)  # , base_dir='/your/conf/dir')

    def load(self, name):
        if os.path.isfile(name):
            v2 = yaml.load(
                open(name, "r"), Loader=yaml.FullLoader
            )
            self._merge(v2, self)

        self._overrides(self)

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
