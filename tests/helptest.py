"""Does every shipped type, setting and field say what it is?

    python3 tests/helptest.py

help: is what an editor shows beside a setting, so every schema the
repo ships gives one to everything it declares, and each is whole
sentences: a capital first, a period last.  A help that stops short of
its period is also how a colon or a # in the middle of one shows up,
since yaml ends the text there without a word.

Needs yaml and nothing else, the same as checktest.py.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.Check import readYaml, unexplained  # noqa: E402

CORE = ('core-types.yaml', 'config-schema.yaml', 'layout-schema.yaml',
        'theme-schema.yaml', 'widget-schema.yaml')


def schemas():
    """every schema the repo ships, as paths"""
    found = [os.path.join('PiClock3', name) for name in CORE]
    found += sorted(glob.glob(os.path.join('PiClock3', '*', 'schema.yaml')))
    return found


def helps(schema):
    """(where, text) for every help: in a schema"""
    out = []

    def walk(where, spec):
        if not isinstance(spec, dict):
            return
        if 'help' in spec:
            out.append((where, spec['help']))
        fields = spec.get('of')
        if isinstance(fields, dict):
            for name, field in fields.items():
                walk('%s.%s' % (where, name), field)

    for section in ('types', 'settings'):
        for name, spec in (schema.get(section) or {}).items():
            walk(name, spec)
    return out


def sentence(text):
    """what is wrong with a help as written, or None"""
    if not isinstance(text, str):
        return 'is not text'
    if not (text[0].isupper() or text[0].isdigit()):
        return 'starts lowercase'
    if not text.endswith('.'):
        return 'has no period at the end'
    # yaml folds a line break into one space, so a sentence that ended a
    # line loses the second space the rest of the repo puts after one
    if re.search(r'\. \S', text):
        return 'has one space after a period'
    return None


def main():
    failed = checked = 0
    for path in schemas():
        schema = readYaml(path) or {}
        where = path.replace(os.sep, '/')
        for name in unexplained(schema):
            failed += 1
            print('FAIL %s: %s has no help:' % (where, name))
        for name, text in helps(schema):
            checked += 1
            wrong = sentence(text)
            if wrong:
                failed += 1
                print('FAIL %s: %s %s: %r' % (where, name, wrong, text))
    print('%d helps in %d schemas, %d failed'
          % (checked, len(schemas()), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
