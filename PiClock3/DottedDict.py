import logging
import string

logger = logging.getLogger(__name__)


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
        # a number or a list has nothing in it to expand, and callers pass
        # whatever the config held
        if not isinstance(s, str):
            return s
        try:
            return EXPANDER.vformat(s, (), self)
        except (ValueError, TypeError) as e:
            logger.warning("cannot expand %r: %s", s, e)
            return s


class Missing():
    """what a format string gets for something that is not there.

    Empty whatever is asked of it, so {plugin-data.sunrise:%H:%M} comes back
    as nothing rather than as a complaint about the format specifier.
    """

    def __format__(self, spec):
        return ''

    def __str__(self):
        return ''


class Expander(string.Formatter):
    """format(), leaving out what it cannot find rather than leaving it in.

    A name that is absent used to come back with its own braces still around
    it.  A stylesheet ignores that, which is why it went unnoticed; a label
    prints it.

    Words are not handled here: {language.x} reaches an object that answers
    every name, so a missing one is that object's business rather than this
    one's.
    """

    def get_field(self, name, args, kwargs):
        try:
            return super().get_field(name, args, kwargs)
        except (KeyError, IndexError, AttributeError, TypeError):
            logger.debug('nothing to expand for %s', name)
            return Missing(), name


EXPANDER = Expander()
