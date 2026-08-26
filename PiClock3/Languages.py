"""The words, and which language's words to use.

A language is one file: what to call it, and a table of strings.  Files are
found the way themes, layouts and units are found, and every file claiming
the same language is merged, so a plugin ships its own words without editing
the shipped table and you can change a word without editing a plugin.

    PiClock3/languages/     shipped
    PiClock3/*/languages/   a core plugin's own words
    plugins/*/languages/    a third-party plugin's
    languages/              yours

A file lists the codes it answers to, the everyday one first:

    code: [de, deu, ger]

A config's language: is matched against all of them, and a regional tag
falls back to the language it is a region of, so de, deu and de-AT all
arrive at the same file.  Nothing requires a standard code - a language
that has none can claim any name nothing else is using, or be known by the
name of its file.
"""
import glob
import logging
import os

import yaml

logger = logging.getLogger(__name__)


class Languages():

    # the keys merge() shapes itself.  every other key in a language file is
    # carried through untouched for setting() to find.
    STRUCTURED = ('code', 'codes', 'name', 'locale', 'strings', 'conditions')

    def __init__(self, piclock):
        self.piclock = piclock
        self.languages = {}          # canonical name -> {'codes', 'name', 'strings'}
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
        found = [os.path.join('PiClock3', 'languages')]
        for base in (os.path.join('PiClock3', '*'), os.path.join('plugins', '*')):
            found += sorted(glob.glob(os.path.join(base, 'languages')))
        found.append('languages')
        return [f for i, f in enumerate(found) if f not in found[:i]]

    def load(self):
        self.requested = self.chosen()
        for folder in self.folders():
            self.merge(folder)
        logger.info('languages: %s; using %s',
                    ', '.join('%s (%s)' % (v['name'], k)
                              for k, v in sorted(self.languages.items())),
                    self.chosen())

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
            with open(path, encoding='utf-8') as fh:
                part = yaml.safe_load(fh) or {}
            key = self.key(part, path)
            entry = self.languages.setdefault(
                key, {'codes': set(), 'name': key, 'strings': {},
                      'conditions': {}, 'locale': []})
            entry['codes'].update(c.lower() for c in self.codes(part))
            entry['codes'].add(key)
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
        """the code the config asked for.

        Read once and remembered, because config['language'] is replaced by
        the table itself after loading - so that {language.sunrise} in a
        format string means the word, which is what it reads like.
        """
        if self.requested:
            return self.requested
        want = self.piclock.config.get('language')
        return str(want).lower() if want else 'en'

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
                               c for e in self.languages.values() for c in e['codes'])))
        english = self.languages.get('en')
        return english['strings'] if english else {}
