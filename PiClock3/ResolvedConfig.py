"""Everything a config decides before anything is drawn.

Which layout and theme each page is built from, which regions those layouts
declare and which theme each region belongs to, and what every plugin's
settings come out as once the eight tiers have been merged over each other.

None of it needs a screen, a network or a plugin's code, so it is the half
of startup --check can run.  The clock builds its widgets from what comes
out of here and Check reads the same answers, which is what stops the two
disagreeing about a config.

Finding a plugin is the one thing this leaves to its caller: the clock has
the imported module and takes the folder from that, Check finds one on
disk.  So the folder arrives as an argument.
"""
import logging
import os

from .Config import ConfigError, merge, readYaml, thisFolder
from .DottedDict import DottedDict


logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))

# Qt's own property names, which mean here what they mean in Qt.  A widget
# declaring one is asking for the page's answer to it.
CASCADE = ('color', 'background-color', 'font-family', 'font-style',
           'font-weight')


def mapping(value):
    """a block of settings, or nothing where something else was written.

    This reads config somebody typed, so a scalar can turn up where a block
    belongs.  Check reports that; here it only has to not raise.
    """
    return value if isinstance(value, dict) else {}


def localPath(value, home):
    """one relative path, made relative to the folder it came in"""
    if (isinstance(value, str) and '{' not in value
            and not os.path.isabs(value)):
        return (home + '/' + value).replace(os.sep, '/')
    return value


def localArt(part, home):
    """point a folder's own art at that folder.

    a theme that ships its own images should not have to know where it was
    installed, so inside a folder a plain relative path is relative to the
    folder.  a path with a {placeholder} is left alone: that is how the
    shipped themes reach the common image directory.
    """
    keys = ('art', 'background', 'folder', 'files', 'image')
    if isinstance(part, list):
        for v in part:
            localArt(v, home)
    elif isinstance(part, dict):
        for k, v in part.items():
            if k in keys and isinstance(v, list):
                part[k] = [localPath(x, home) for x in v]
            elif isinstance(v, (dict, list)):
                localArt(v, home)
            elif k in keys:
                part[k] = localPath(v, home)
    return part


def pluginFolder(module):
    """where a plugin's files are, without importing it"""
    part = module.replace('.', os.sep)
    for folder in (part, os.path.join('plugins', part)):
        if os.path.isdir(folder):
            return folder
    return None


def partPaths(kind, name):
    """where a layout or a theme of this name could be, in the order tried.

    Either a file or a folder will do.  A folder is what a git checkout of
    somebody else's theme looks like, so themes/mine.yaml and
    themes/mine/theme.yaml both work, and so does the repository naming its
    file after itself.
    """
    stem = 'theme' if kind == 'themes' else 'layout'
    for base in (kind, os.path.join('PiClock3', kind)):
        folder = os.path.join(base, name)
        yield os.path.join(base, name + '.yaml'), None
        yield os.path.join(folder, stem + '.yaml'), folder
        yield os.path.join(folder, name + '.yaml'), folder


def loadPart(kind, name):
    """a layout or a theme - the user's own first, then the shipped one.

    None where there is none, so a caller with somewhere to put the news
    can say so its own way instead of ending the program.
    """
    stem = 'theme' if kind == 'themes' else 'layout'
    for path, home in partPaths(kind, name):
        if not os.path.isfile(path):
            continue
        part = readYaml(path)
        logger.debug('%s %s from %s', stem, name, path)
        # localArt leaves a {placeholder} alone, so it has to run before
        # the placeholder becomes a path
        part = localArt(part, home) if home else part
        return thisFolder(part, os.path.dirname(path)), path
    return None, None


def noSuchPart(kind, name):
    """what to say about a layout or theme that is not there"""
    stem = 'theme' if kind == 'themes' else 'layout'
    return ("no %s named '%s'.  looked for %s.yaml, %s/%s.yaml and "
            "%s/%s.yaml, in %s/ and in PiClock3/%s/\n"
            % (stem, name, name, name, stem, name, name, kind, kind))


def cellNames(name, spec):
    """the regions one layout entry actually declares.

    A repeat registers its cells and never the bare name, so a widget
    naming the repeat is naming all of them and a widget naming a cell is
    naming one.
    """
    repeat = spec.get('repeat') if isinstance(spec, dict) else None
    count = int((repeat or {}).get('count', 0)) if repeat else 0
    if not count:
        return [name]
    return ['%s.%d' % (name, i) for i in range(1, count + 1)]


class ResolvedConfig():
    """what the config comes to, page by page, before any of it is drawn."""

    def __init__(self, config):
        self.config = config
        # page name -> its layout and theme, in the config's own order,
        # since the later page wins a name two layouts both declare
        self.pages = {}
        # region name -> the theme of the page it sits on
        self.regionTheme = {}
        # each repeat's name, which is not a region itself but is what a
        # widget writes to mean all of its cells
        self.repeats = set()
        # (where, kind, name) for a layout or theme a page named and is
        # not there.  The kind matters: no layout, no regions.
        self.missing = []
        # (where, kind, ConfigError) for one that is there and will not read
        self.unreadable = []
        # (kind, name) -> the file it was actually read from
        self.partFiles = {}
        # (page, region, style or border, name) a layout asks its page's
        # theme for and the theme does not have
        self.unnamed = []

    def build(self):
        """every page's layout and theme, and the regions they declare.

        A part that is not there is recorded rather than raised, so a
        caller collecting everything wrong with a config gets the rest of
        it too, and its page is skipped.
        """
        for pageName, page in mapping(self.config.get('pages')).items():
            page = mapping(page)
            layout = self.part('pages.%s.layout' % pageName,
                               'layouts', page.get('layout'))
            theme = self.part('pages.%s.theme' % pageName,
                              'themes', page.get('theme'))
            if layout is None or theme is None:
                continue
            # theme: and layout: blocks in the config have the last word
            # over the files they name, which is what makes either testable
            # from the command line without editing it.  Named for what
            # they change rather than -settings: they are not keyed by a
            # target the way kind-settings and plugin-settings are.
            merge(mapping(self.config.get('layout')), layout)
            merge(mapping(self.config.get('theme')), theme)
            theme['styles'] = self.regionStyles(layout, theme)
            self.namesNobodyDefines(pageName, layout, theme)
            self.pages[pageName] = (layout, theme)
            for name, spec in mapping(layout.get('regions')).items():
                cells = cellNames(name, spec)
                if cells != [name]:
                    self.repeats.add(name)
                for cell in cells:
                    self.regionTheme[cell] = theme
        return self

    def usedProviders(self):
        """the providers something in this config actually points at.

        Asked of the merge rather than of what a widget entry says, because
        a provider may be named a tier away:

            kind-settings:
              radar: {base-provider: mapbox, frame-provider: librewxr}

        which is the documented way to point four radars at one map, and
        names mapbox nowhere under widgets:.  Reading the entry alone would
        call that provider unused and leave the radar with no base map.

        Nothing here imports a plugin - a folder is found from the module
        name - so it can be asked before anything is loaded.

        Any merged value that is a provider's name counts, rather than
        only the settings a schema calls providers.  That over-counts on
        purpose.  Counting one too many costs a request nobody wanted;
        missing one costs the clock a provider it needs, so the loose
        answer is the safe one.
        """
        names = set(mapping(self.config.get('providers')))
        if not names:
            return set()
        used, entries = set(), mapping(self.config.get('widgets'))
        for name, entry in list(entries.items()) + list(
                mapping(self.config.get('providers')).items()):
            entry = mapping(entry)
            module = entry.get('plugin')
            folder = pluginFolder(module) if isinstance(module, str) else None
            if folder is None:
                # what this points at cannot be known, and --check
                # reports the missing plugin itself.  Everything loads
                # rather than skipping one that was needed
                return names
            try:
                merged, _ = self.pluginConfig(folder, entry,
                                              name in entries)
            except ConfigError:
                return names        # a schema that will not read, likewise
            for value in merged.values():
                if not isinstance(value, str):
                    continue
                if value in names:
                    used.add(value)
                elif '{' in value:
                    # frame-provider: '{something}' is a name once it is
                    # expanded, and the merge holds it before that
                    expand = getattr(self.config, 'expand', None)
                    grown = expand(value) if expand else value
                    if grown in names:
                        used.add(grown)
        return used

    def part(self, where, kind, name):
        """one layout or theme a page named, or None with the news kept.

        A file that is there and will not read is kept apart from one that
        is not there: they need different sentences, and reporting the
        second for the first is how an empty theme used to surface as a
        widget drawing nowhere.
        """
        try:
            part, path = loadPart(kind, name) if name else (None, None)
        except ConfigError as e:
            self.unreadable.append((where, kind, e))
            return None
        if part is None:
            self.missing.append((where, kind, name or ''))
        else:
            # which of the paths partPaths offers this one answered to,
            # so a finding about a value in it can name the file
            self.partFiles[(kind, name)] = path
        return part

    def anyLayoutMissing(self):
        """whether a page named a layout that is not there.

        Then no region is knowable, and complaining about each widget in
        turn would bury the one line that is wrong.  One that is there and
        will not read leaves exactly the same hole.
        """
        return any(kind == 'layouts'
                   for _, kind, _ in self.missing + self.unreadable)

    def regionStyles(self, layout, theme):
        """the named styles a region can ask for, layout first then theme.

        A layout knows how big its text has to be to fit; a theme knows
        what it should look like.  So a layout carries the sizing as a
        default and a theme overrides whatever it cares to, which is what
        lets a layout nobody has themed still look right.
        """
        styles = {}
        merge(layout.get('layout-style-settings') or {}, styles)
        merge(theme.get('styles') or {}, styles)
        return styles

    def namesNobodyDefines(self, pageName, layout, theme):
        """the styles and borders a layout's regions ask this page's theme
        for and it does not have.

        Only a page knows the pairing, so it is settled here rather than
        left to a checker that sees one at a time.
        """
        have = {'style': set(theme.get('styles') or {}),
                'border': set(theme.get('borders') or {})}
        for region, spec in mapping(layout.get('regions')).items():
            if not isinstance(spec, dict):
                continue
            for key in ('style', 'border'):
                name = spec.get(key)
                if isinstance(name, str) and name not in have[key]:
                    self.unnamed.append(
                        ('pages.%s' % pageName, region, key, name))

    def regions(self):
        """every name a widget's region: may legally use.

        A repeat's cells, and the repeat's own name beside them, since
        naming the repeat names all of its cells at once.
        """
        return set(self.regionTheme) | self.repeats

    # ------------------------------------------------------- the tiers

    def pluginConfig(self, folder, entry, isWidget):
        """one instance's settings, and which tier last set each of them.

        Eight tiers, each merged over the last: what the role takes, the
        plugin's own defaults, the page's theme three ways - its default:,
        its kind-settings: and its plugin-settings: - then the config's own
        two of those, and last the entry itself.

        Each tier is named as it is merged, because the merge is the last
        moment anything can tell a shipped default from an answer somebody
        wrote.
        """
        config = DottedDict()
        tiers = {}

        # what the role itself takes: a widget accepts color and effect
        # whether or not the plugin ever heard of them, and a provider
        # accepts neither, having no region for a theme to reach
        if isWidget:
            path = os.path.join(HERE, 'widget-config.yaml')
            merge(readYaml(path), config, tiers, 'role')

        defaults = {}
        path = os.path.join(folder, 'config.yaml') if folder else ''
        if path and os.path.isfile(path):
            defaults = readYaml(path)
            defaults = thisFolder(defaults, os.path.dirname(path))
            merge(defaults, config, tiers, 'plugin')

        # the theme of the page this instance draws on, if it draws at all.
        # a provider occupies no region, so no theme reaches it - which is
        # why anything a theme should be able to say belongs on a widget.
        theme = self.themeFor(entry.get('region'))
        if theme:
            self.cascade(theme, defaults, config, tiers)
            self.settingsFor(theme, defaults, entry, config, tiers, 'theme')

        # the config has the same two blocks and the last word over the theme
        self.settingsFor(self.config, defaults, entry, config, tiers, 'config')
        merge(entry, config, tiers, 'widget')
        return config, tiers

    @staticmethod
    def cascade(theme, defaults, config, tiers=None):
        """the theme's default: reaching every widget that takes the name.

        font-size is deliberately not among them.  It is a fraction of
        whatever it sits in, and a page and a region are not the same
        height - the page's 0.02 would draw a clock face at four pixels.
        """
        page = theme.get('default') or {}
        for name in CASCADE:
            if name in page and name in defaults:
                config[name] = page[name]
                if tiers is not None:
                    tiers[name] = 'theme default'

    @staticmethod
    def settingsFor(source, defaults, entry, config, tiers=None, where=''):
        """kind-settings: then plugin-settings:, from a theme or the config.

        A kind is what a plugin is interchangeable with, so a kind-setting
        means the same thing to every plugin wearing it.  plugin-settings:
        names one exactly, for the times that is too broad.
        """
        for block, key in (('kind-settings', defaults.get('kind')),
                           ('plugin-settings', entry.get('plugin'))):
            settings = source.get(block)
            if (isinstance(settings, dict)
                    and isinstance(settings.get(key), dict)):
                merge(settings[key], config, tiers,
                      ('%s %s' % (where, block)).strip())

    def themeFor(self, region):
        """the theme of the page an instance draws on.

        A list names several and they are on one page; the bare name of a
        repeat names its cells, which share one.
        """
        if isinstance(region, list):
            region = region[0] if region else None
        if not isinstance(region, str) or not region:
            return None     # Check says what a region that is not a name is
        if region in self.regionTheme:
            return self.regionTheme[region]
        head = region + '.'
        for key in self.regionTheme:
            if key.startswith(head):
                return self.regionTheme[key]
        return None
