"""The words, and which language's words to use.

A language is one file: what to call it, and a table of strings.  Files are
found the way themes, layouts and units are found, and every file claiming
the same language is merged, so a plugin ships its own words without editing
the shipped table and you can change a word without editing a plugin.

    PiClock3/languages/     shipped
    PiClock3/*/languages/   a core plugin's own words
    plugins/*/languages/    a third-party plugin's
    themes/*/languages/     what a theme brought with it
    layouts/*/languages/    what a layout brought with it
    languages/              yours

A file lists the codes it answers to, the everyday one first:

    code: [de, deu, ger]

A config's language: is matched against all of them, and a regional tag
falls back to the language it is a region of, so de, deu and de-AT all
arrive at the same file.  Nothing requires a standard code - a language
that has none can claim any name nothing else is using, or be known by the
name of its file.
"""
import copy
import glob
import logging
import os
import re
import sys

from .Config import readYaml
from .ResolvedConfig import HOLDERS

logger = logging.getLogger(__name__)

# the word a config writes to ask for the machine's own language, and what
# an unset language: means
SYSTEM = 'system'

# LC_ALL=C and its like are a request for no language rather than for a
# language called C
NOLANGUAGE = ('c', 'posix')

# de_AT.UTF-8@euro -> de-at: the encoding and the modifier say nothing
# about which words to draw
LOCALE = re.compile(r'^([a-z]{2,8})(?:[_-]([a-z0-9]{2,8}))?', re.I)


class Languages():

    # the keys merge() shapes itself.  every other key in a language file is
    # carried through untouched for setting() to find.
    STRUCTURED = ('code', 'codes', 'name', 'locale', 'strings', 'conditions')

    def __init__(self, piclock):
        self.piclock = piclock
        # canonical name -> {'codes', 'name', 'strings'}
        self.languages = {}
        self.requested = None

    @staticmethod
    def _merge(source, destination):
        for key, value in source.items():
            if isinstance(value, dict):
                Languages._merge(value, destination.setdefault(key, {}))
            else:
                destination[key] = value
        return destination

    def folders(self):
        """every place a language file can be, least specific first.

        A cloned repository may bring words of its own whatever it was
        cloned for: a plugin naming what it draws, a theme renaming what
        the clock calls things.  So every folder one is cloned into is
        looked in, not only plugins/.
        """
        found = [os.path.join('PiClock3', 'languages')]
        for holder in ('PiClock3',) + HOLDERS:
            found += sorted(glob.glob(
                os.path.join(holder, '*', 'languages')))
        found.append('languages')
        return [f for i, f in enumerate(found) if f not in found[:i]]

    def load(self):
        for folder in self.folders():
            self.merge(folder)
        self.inherit()
        # after the files, so the machine's answer can be checked against
        # the codes the files claim
        self.requested = self.chosen()
        logger.info('languages: %s; using %s',
                    ', '.join('%s (%s)' % (v['name'], k)
                              for k, v in sorted(self.languages.items())),
                    self.chosen())

    def inherit(self):
        """a regional language takes what it does not say from its base.

        So en-GB writes only what Britain does differently, rather than a
        second copy of English that drifts from the first.  `from:` names
        the base where the code does not.
        """
        for key, entry in sorted(self.languages.items()):
            named = entry.get('from') or (key.split('-')[0]
                                          if '-' in key else '')
            base = self.byCode(str(named).lower()) if named else None
            if base is None or base is entry:
                continue
            for table in ('strings', 'conditions'):
                entry[table] = self._merge(entry[table],
                                           copy.deepcopy(base[table]))
            if not entry['locale']:
                entry['locale'] = list(base['locale'])
            for name, value in base.items():
                if name not in self.STRUCTURED and name not in entry:
                    entry[name] = copy.deepcopy(value)
            logger.debug('language %s inherits from %s', key, base['name'])

    def byCode(self, code):
        """the entry answering to `code`, or None"""
        for entry in self.languages.values():
            if code in entry['codes']:
                return entry
        return None

    def fromSystem(self):
        """the code this machine is set to, or None.

        Read in the order glibc reads them, then from the file Debian keeps
        it in, since a clock started by systemd may have none of them set.
        Windows sets none of the four and is asked outright.
        """
        asked = []
        for name in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            # LANGUAGE is a preference list: fr_CA:fr:en
            asked += (os.environ.get(name) or '').split(':')
        asked += [self.fromFile(), self.fromWindows()]
        codes = [c for c in (self.asCode(a) for a in asked) if c]
        for code in codes:
            if self.byCode(code) or self.byCode(code.split('-')[0]):
                return code
        # none of them has a file: the first is what to name in the log
        return codes[0] if codes else None

    @staticmethod
    def fromFile():
        """LANG or LC_ALL in Debian's /etc/default/locale, or None"""
        try:
            with open(os.path.join(os.sep, 'etc', 'default', 'locale'),
                      encoding='utf-8') as fh:
                for line in fh:
                    name, _, value = line.partition('=')
                    if name.strip() in ('LANG', 'LC_ALL'):
                        return value.strip().strip('"\'')
        except OSError:
            pass
        return None

    @staticmethod
    def fromWindows():
        """the user's language on Windows, which sets no LANG"""
        if not sys.platform.startswith('win'):
            return None
        try:
            import ctypes
            size = 85                   # LOCALE_NAME_MAX_LENGTH
            buf = ctypes.create_unicode_buffer(size)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, size):
                return buf.value
        except Exception as e:
            logger.debug('no language from Windows: %s', e)
        return None

    @staticmethod
    def asCode(text):
        """de_AT.UTF-8@euro as de-at, or None for nothing and for C"""
        found = LOCALE.match((text or '').strip())
        if not found or found.group(1).lower() in NOLANGUAGE:
            return None
        language, region = found.group(1).lower(), found.group(2)
        return '%s-%s' % (language, region.lower()) if region else language

    INTENSITIES = ('-', '+', 'VC')
    DESCRIPTORS = ('MI', 'BC', 'PR', 'DR', 'BL', 'SH', 'TS', 'FZ')

    def condition(self, notation):
        """words for a WMO 4678 notation, in the language this clock uses.

        Falls back from the exact notation to less specific ones, so a
        language that has translated a dozen entries still reads sensibly:

            -SHRA  ->  SHRA  ->  RA  ->  the notation itself
        """
        if not notation:
            return ''
        table = self.conditions()
        for key in self.wider(notation):
            if key in table:
                return table[key]
        logger.debug('no wording for condition %s', notation)
        return notation

    @classmethod
    def wider(cls, notation):
        """a notation, then the same thing said less precisely.

        Detail is given up in the order it is least missed: how hard it is
        coming down, then the second and later phenomena, then the shape of
        it.  An untranslated -SHRABR reaches Light Rain Showers this way.
        """
        intensity, descriptor, group = cls.split(notation)
        tried = []
        for d in (descriptor, ''):
            for g in (group, group[:2]):
                for i in (intensity, ''):
                    tried.append(i + d + g)
        return [n for j, n in enumerate(tried) if n and n not in tried[:j]]

    @classmethod
    def split(cls, notation):
        """a notation into intensity, descriptor and phenomenon group"""
        rest, intensity = notation, ''
        for p in cls.INTENSITIES:
            if rest.startswith(p):
                intensity, rest = p, rest[len(p):]
                break
        descriptor = ''
        for p in cls.DESCRIPTORS:
            if rest.startswith(p) and len(rest) > 2:
                descriptor, rest = p, rest[len(p):]
                break
        return intensity, descriptor, rest

    def entry(self):
        """the file this clock's language: arrived at, or None.

        de-AT before de: a regional table wins if there is one, and falls
        back to the language it is a region of when there is not.
        """
        want = self.chosen()
        for code in (want, want.split('-')[0]):
            for entry in self.languages.values():
                if code in entry['codes']:
                    return entry
        return None

    def locales(self):
        """LC_TIME names this language answers to, best first.

        Day and month names come from the C library rather than from the
        table here, so a language says which locales mean it.  The spelling
        is not the same on every platform, hence a list.
        """
        found = self.entry()
        return list(found.get('locale') or []) if found else []

    def setting(self, name, default=None):
        """a top-level key from this clock's language, or English's.

        Falling through to English is what strings() does, so a translation
        that leaves date-format out gets a working date rather than none.
        """
        for entry in (self.entry(), self.languages.get('en')):
            if entry and name in entry:
                return entry[name]
        return default

    def conditions(self):
        found = self.entry() or self.languages.get('en')
        return (found.get('conditions') or {}) if found else {}

    def merge(self, folder):
        if not os.path.isdir(folder):
            return
        for path in sorted(glob.glob(os.path.join(folder, '*.yaml'))):
            part = readYaml(path)
            key = self.key(part, path)
            entry = self.languages.setdefault(
                key, {'codes': [], 'name': key, 'strings': {},
                      'conditions': {}, 'locale': []})
            # in the order the file wrote them, its everyday code first
            for code in list(self.codes(part)) + [key]:
                code = code.lower()
                if code not in entry['codes']:
                    entry['codes'].append(code)
            if part.get('name'):
                entry['name'] = part['name']
            if part.get('locale'):
                entry['locale'] = part['locale']
            self._merge(part.get('strings') or {}, entry['strings'])
            self._merge(part.get('conditions') or {},
                        entry.setdefault('conditions', {}))
            # anything else the file declares - date-format, date-ordinal -
            # is carried as it is, so a new one needs no code here and
            # setting() can find it
            for name, value in part.items():
                if name not in self.STRUCTURED:
                    entry[name] = value
            logger.debug('language %s from %s', key, path)

    @staticmethod
    def codes(part):
        """the codes a file answers to - one name or a list of them"""
        code = part.get('code')
        if not code:
            return []
        return [str(code)] if isinstance(code, str) else [str(c) for c in code]

    @classmethod
    def key(cls, part, path):
        """what to file this under - its first code, else its file name.

        A plugin adding words to a language it did not write only has to get
        one of the codes right, or name the file the same.
        """
        for code in cls.codes(part):
            return code.lower()
        return os.path.splitext(os.path.basename(path))[0].lower()

    def chosen(self):
        """the code this clock speaks.

        The config's language:, or the machine's own where it says nothing
        or says system.  English where the machine names a language no file
        answers to.

        Read once and remembered, because config['language'] is replaced
        after loading by the file itself, so that a format string can reach
        {language.strings.sunrise} and {language.date-format}.
        """
        if self.requested:
            return self.requested
        want = self.piclock.config.get('language')
        want = str(want).lower() if want else SYSTEM
        if want != SYSTEM:
            return want
        code = self.fromSystem()
        if code and (self.byCode(code)
                     or self.byCode(code.split('-')[0])):
            logger.info('language: the machine says %s', code)
            return code
        if code:
            logger.warning('this machine says %s, and no language file'
                           ' answers to it; using English', code)
        return 'en'

    def strings(self):
        """the table for the language this clock is set to.

        An unknown language falls back to English rather than to nothing,
        because a missing word shows as the key and a whole missing table
        would show as a page of them.
        """
        found = self.entry()
        if found:
            return found['strings']
        want = self.chosen()
        if want != 'en':
            logger.warning('no language %r; known: %s', want,
                           ', '.join(sorted(
                               c for e in self.languages.values()
                               for c in e['codes'])))
        english = self.languages.get('en')
        return english['strings'] if english else {}
