

class DottedDict(dict):
    def __init__(self):
        super().__init__(self)
        self.__dict__ = self

    # also allow x['some.deeper.path']
    def __getitem__(self, key):
        if '.' not in key:
            return super().__getitem__(key)
        value = self
        for subkey in key.split('.'):
            value = value[subkey]
        return value

    # expand string based on dictionary even allowing dots
    # x = dd.expand("{something}/test")
    # if dd['something'] = y result is "y/test"
    # also allows dots
    # actually using format to make it happen
    def expand(self, s):
        return s.format(**self)
