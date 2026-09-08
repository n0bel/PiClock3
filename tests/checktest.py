"""What --check says, for configs written to be wrong in one way each.

    python3 tests/checktest.py

A case is a config and the findings it must produce.  `wants` is matched as
a substring of "where: message", so a case says what it is looking for and
nothing about the wording around it.  `forbids` is the other half and the
one that matters most: a checker that complains about a config the clock
runs happily is worse than one that says nothing.

A case may be marked xfail, for something Check gets wrong that nothing has
fixed yet.  There are none at present.

Nothing here imports PyQt or opens a window, because Check does not: it is
the half of startup that reads a config, and it runs on a machine with no
display, no keys and no network.
"""
import copy
import os
import shutil
import sys

# Check finds plugins, layouts and themes by walking relative paths, so the
# clock's own directory is where it has to be run from.  Going there rather
# than insisting on it means this works from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PiClock3.Check import Check                    # noqa: E402


BASE = {
    'pages': {'clock-page': {'order': 0, 'layout': 'classic',
                             'theme': 'circuit'}},
    'language': 'en',
    'location': {'latitude': 44.735428, 'longitude': -93.163912},
    'providers': {
        'openmeteo': {'plugin': 'PiClock3.OpenMeteo'},
        'metar': {'plugin': 'PiClock3.Metar'},
        'mapbox': {'plugin': 'PiClock3.Mapbox'},
        'librewxr': {'plugin': 'PiClock3.LibreWXR'},
    },
    'widgets': {
        'clock': {'plugin': 'PiClock3.AnalogClock', 'region': 'clock'},
        'current-conditions': {'plugin': 'PiClock3.CurrentConditions',
                               'region': 'current',
                               'conditions-provider': 'metar'},
        'radar1': {'plugin': 'PiClock3.MapLoop', 'region': 'maps.1',
                   'base-provider': 'mapbox', 'frame-provider': 'librewxr'},
    },
    'apikeys': {'mbapi': 'a-real-looking-key'},
}


def config(**changes):
    """the base config with one thing done to it.

    Each value is a function taking the config, so a case can reach into a
    nested block rather than restating one.
    """
    out = copy.deepcopy(BASE)
    for change in changes.values():
        change(out)
    return out


def drop(*path):
    def do(cfg):
        here = cfg
        for step in path[:-1]:
            here = here[step]
        del here[path[-1]]
    return do


def put(*path):
    value = path[-1]
    path = path[:-1]

    def do(cfg):
        here = cfg
        for step in path[:-1]:
            here = here.setdefault(step, {})
        here[path[-1]] = value
    return do


def google():
    """GoogleMaps as a second base map, with a key so the cases about
    style: are not read past an apikey complaint"""
    def do(cfg):
        cfg['providers']['googlemaps'] = {'plugin': 'PiClock3.GoogleMaps'}
        cfg['apikeys']['googleapi'] = 'another-real-looking-key'
    return do


CASES = [
    # ------------------------------------------------ nothing wrong
    dict(name='the base config itself',
         config=config(),
         wants=[], forbids=['must be set', 'nothing declares', 'no region',
                            'apikeys',
                            # it names a shipped layout and a shipped theme,
                            # so a checker that cannot find those is broken
                            # in a way every other case would sail past
                            'no layout', 'no theme']),

    # ------------------------------------------------ names
    dict(name='a widget naming a provider that is not there',
         config=config(a=put('widgets', 'current-conditions',
                             'conditions-provider', 'nosuch')),
         wants=['no provider'], forbids=[]),
    dict(name='a widget in a region no layout declares',
         config=config(a=put('widgets', 'clock', 'region', 'nowhere')),
         wants=['no region'], forbids=[]),
    dict(name='a page naming a layout that is not there',
         config=config(a=put('pages', 'clock-page', 'layout', 'nosuch')),
         wants=['no layout'],
         # every widget's region becomes unknowable, and saying so once per
         # widget would bury the one line that is wrong
         forbids=['no region']),
    dict(name='a page naming a theme that is not there',
         config=config(a=put('pages', 'clock-page', 'theme', 'nosuch')),
         wants=['no theme'], forbids=[]),
    dict(name='a language that is not there',
         config=config(a=put('language', 'nosuch')),
         wants=['no language named'], forbids=[]),
    dict(name='a language that is',
         config=config(a=put('language', 'de')),
         wants=[], forbids=['no language']),
    dict(name='a timezone that is not there',
         config=config(a=put('location', 'timezone', 'Europe/Londin')),
         wants=['no timezone named', 'Did you mean Europe/London'],
         forbids=[]),
    dict(name='a timezone that is',
         config=config(a=put('location', 'timezone', 'Asia/Kolkata')),
         wants=[], forbids=['timezone']),
    dict(name='a blank timezone is this machine, not a mistake',
         config=config(a=put('location', 'timezone', None)),
         wants=[], forbids=['timezone']),
    # six hundred names is not a list anyone reads, so a long one offers
    # near misses and a short one still names them all
    dict(name='a name nothing is close to',
         config=config(a=put('location', 'timezone', 'zzzz')),
         wants=['There are', 'to choose from'], forbids=['Africa/Abidjan']),
    dict(name='a style no theme on that page defines',
         config=config(a=put('layout', 'regions',
                             {'clock': {'style': 'nosuchstyle'}})),
         wants=['clock.style', "no style named 'nosuchstyle'"], forbids=[]),
    dict(name='a border no theme on that page defines',
         config=config(a=put('layout', 'regions',
                             {'clock': {'border': 'nosuchborder'}})),
         wants=['clock.border', "no border named"], forbids=[]),

    # ------------------------------------------------ required
    dict(name='a widget that does not say which plugin it is',
         config=config(a=drop('widgets', 'clock', 'plugin')),
         wants=['does not say which plugin'], forbids=[]),
    dict(name='a widget with no region',
         config=config(a=drop('widgets', 'clock', 'region')),
         wants=['widgets.clock.region: must be set'], forbids=[]),
    dict(name='a map with no frame provider',
         config=config(a=drop('widgets', 'radar1', 'frame-provider')),
         wants=['widgets.radar1.frame-provider: must be set'], forbids=[]),
    dict(name='no location',
         config=config(a=drop('location')),
         wants=['location: must be set'], forbids=[]),

    # ------------------------------------------------ values
    dict(name='a setting nobody declares',
         config=config(a=put('widgets', 'clock', 'no-such-setting', 1)),
         wants=['nothing declares this setting'], forbids=[]),
    dict(name='a top-level key nobody declares',
         config=config(a=put('unitss', 'metric')),
         wants=['warning unitss: nothing declares'], forbids=[]),
    # the four the code reads and the schema did not name, plus the
    # deprecated one a marker's image: still expands
    dict(name='the top-level keys a config may really write',
         config=config(a=put('styles', {'big': {'font-size': '40px'}}),
                       b=put('unit-sets', {'mine': {'temperature': 'C'}}),
                       c=put('folders', {'marker': '/pins'}),
                       d=put('layout', {'regions': {'clock':
                                                    {'width': 0.4}}}),
                       e=put('theme', {'default': {'color': 'white'}})),
         wants=[], forbids=['nothing declares', 'takes a value',
                            'must be a block']),
    dict(name='a number outside the range its schema gives',
         config=config(a=put('widgets', 'radar1', 'zoom', 47)),
         wants=['problem widgets.radar1.zoom: 47 is not in the allowed'
                ' range of 0 to 20'],
         forbids=['warning widgets.radar1.zoom']),
    dict(name='a value outside the set its schema allows',
         config=config(a=put('providers', 'googlemaps',
                             {'plugin': 'PiClock3.GoogleMaps',
                              'style': 'satellite-streets-v10'})),
         wants=['problem', 'is not one of'], forbids=[]),
    # ------------------------------------------------ inside a block
    dict(name='a range inside a block',
         config=config(a=put('location', 'latitude', 200)),
         wants=['problem', 'location.latitude', 'allowed range'],
         forbids=[]),
    dict(name='a required setting inside a block',
         config=config(a=drop('location', 'latitude')),
         wants=['location.latitude', 'must be set'],
         forbids=[]),
    dict(name='an undeclared setting inside a block',
         config=config(a=put('location', 'lattitude', 44.7)),
         wants=['location.lattitude', 'nothing declares'],
         forbids=[]),
    dict(name='a block a with: brings in is still declared',
         config=config(a=put('widgets', 'radar1', 'markers',
                             [{'location': {'latitude': 44.7,
                                            'longitude': -93.1},
                               'color': 'red'}])),
         wants=[], forbids=['nothing declares']),
    dict(name='a range two blocks deep',
         config=config(a=put('widgets', 'radar1', 'markers',
                             [{'location': {'latitude': 200,
                                            'longitude': -93.1}}])),
         wants=['allowed range'], forbids=[]),

    # ------------------------------------------------ settings blocks
    dict(name='a range inside kind-settings',
         config=config(a=put('kind-settings', 'radar', {'zoom': 47})),
         wants=['kind-settings.radar.zoom', 'allowed range'],
         forbids=[]),
    dict(name='an undeclared setting inside kind-settings',
         config=config(a=put('kind-settings', 'radar', {'zooom': 7})),
         wants=['kind-settings.radar.zooom', 'nothing declares'],
         forbids=[]),
    dict(name='a range inside plugin-settings',
         config=config(a=put('plugin-settings', 'PiClock3.MapLoop',
                             {'zoom': 47})),
         wants=['plugin-settings.PiClock3.MapLoop.zoom', 'allowed range'],
         forbids=[]),
    # Two questions can be asked of a settings block.  Whether it reaches
    # anything is this config's business and changes when a provider is
    # swapped, so that one is not asked.  Whether a setting exists at all
    # is spelling, and is answered by what is installed.
    dict(name='a block for something not installed is quiet',
         config=config(a=put('plugin-settings', 'PiClock3.NotHere',
                             {'zoom': 7}),
                       b=put('kind-settings', 'nosuchkind', {'zoom': 7})),
         wants=[], forbids=['NotHere', 'nosuchkind']),
    dict(name='a block for a plugin installed but not loaded here',
         config=config(a=put('plugin-settings',
                             {'PiClock3.GoogleMaps': {'style': 'hybrid'}})),
         wants=[], forbids=['GoogleMaps']),
    dict(name='and a typo in that same block is still caught',
         config=config(a=put('plugin-settings',
                             {'PiClock3.GoogleMaps': {'styyle': 'hybrid'}})),
         wants=['plugin-settings.PiClock3.GoogleMaps.styyle',
                'nothing declares'], forbids=[]),
    dict(name='a setting only a sibling of that kind declares',
         config=config(a=put('kind-settings', 'radar-frames',
                             {'palette': 4})),
         wants=[], forbids=['palette']),
    # somebody else's plugin sits a level down, the way a cloned
    # repository leaves it, and is spelled against just the same
    dict(name='a typo aimed at a plugin a level down',
         config=config(a=put('plugin-settings',
                             {'_selftest_vendor.Thing': {'styyle': 'x'}})),
         wants=['plugin-settings._selftest_vendor.Thing.styyle',
                'nothing declares'],
         forbids=[], needs='Nested'),
    dict(name='and its own setting is left alone',
         config=config(a=put('plugin-settings',
                             {'_selftest_vendor.Thing': {'style': 'x'}})),
         wants=[], forbids=['_selftest_vendor.Thing'], needs='Nested'),
    # a plugin with no schema cannot be spelled against, and is a problem
    # in its own right wherever a config actually names it
    dict(name='a plugin with no schema, named by a config',
         config=config(a=put('providers', 'bare',
                             {'plugin': 'plugins._selftest'})),
         wants=['has no schema.yaml, which is required'],
         forbids=[], needs='NoSchema'),

    # a plugin schema that will not read is a finding, not the end of the
    # run - it says which file and which line, and the config is still read
    dict(name='a plugin schema with a tab in it',
         config=config(a=put('providers', 'bare',
                             {'plugin': 'plugins._selftest'})),
         wants=['schema.yaml line 5', 'a tab, and yaml indents with spaces'],
         forbids=['Traceback'], needs='BadSchema'),
    dict(name='a plugin schema that is empty',
         config=config(a=put('providers', 'bare',
                             {'plugin': 'plugins._selftest'})),
         wants=['schema.yaml', 'is empty'],
         forbids=['Traceback'], needs='EmptySchema'),

    # a theme's blocks are read the same way, which is how a plugin
    # renaming a setting out from under a theme is found
    dict(name='a typo in a theme kind-settings block',
         config=config(a=put('theme', 'kind-settings',
                             {'radar': {'zooom': 7}})),
         wants=['kind-settings.radar.zooom', 'nothing declares'],
         forbids=[]),
    dict(name='a theme setting that still lands is quiet',
         config=config(a=put('theme', 'kind-settings',
                             {'radar': {'zoom': 7}})),
         wants=[], forbids=['kind-settings.radar']),
    dict(name='a bad value in a theme kind-settings block',
         config=config(a=put('theme', 'kind-settings',
                             {'radar': {'zoom': 47}})),
         wants=['kind-settings.radar.zoom', 'allowed range'], forbids=[]),

    # two plugins may each invent a `part`, meaning different shapes, so
    # the names cannot share one table
    dict(name='one plugin type name does not reach another plugin',
         config=config(a=put('theme', 'kind-settings',
                             {'forecast':
                              {'layout':
                               {'attribution': {'align': 'left-top'}}}}),
                       b=put('widgets', 'forecast',
                             {'plugin': 'PiClock3.Forecast',
                              'region': 'forecast',
                              'forecast-provider': 'openmeteo'}),
                       c=put('widgets', 'current-conditions',
                             {'plugin': 'PiClock3.CurrentConditions',
                              'region': 'current',
                              'conditions-provider': 'metar'})),
         wants=[], forbids=['align']),
    dict(name='a name in a region list that is not a name',
         config=config(a=put('widgets', 'clock', 'region', ['clock', 7])),
         wants=['widgets.clock.region.1'], forbids=[]),
    dict(name='a good kind-settings block is quiet',
         config=config(a=put('kind-settings', 'radar', {'zoom': 7})),
         wants=[], forbids=['kind-settings.radar']),

    # ------------------------------------------------ layouts and themes
    dict(name='an undeclared key in a layout region',
         config=config(a=put('layout', 'regions',
                             {'clock': {'nonsense': 1}})),
         wants=['nothing declares'], forbids=[]),
    dict(name='an undeclared key in a theme border',
         config=config(a=put('theme', 'borders',
                             {'default': {'wdith': 0.02}})),
         wants=['themes.', 'borders.default.wdith', 'nothing declares'],
         forbids=[]),
    # effect: is written as a word or as a block, and the tier below is
    # widget-config.yaml's `effect: none` - so the block lands on a string
    dict(name='the long form of a setting that is also a word',
         config=config(a=put('widgets', 'clock', 'effect',
                             {'type': 'glow', 'blur': 0.125})),
         wants=[], forbids=['nothing declares', 'takes']),
    dict(name='and it is still checked once it lands',
         config=config(a=put('widgets', 'clock', 'effect',
                             {'type': 'sparkle'})),
         wants=['effect.type', 'is not one of'], forbids=[]),
    dict(name='the word form still works',
         config=config(a=put('widgets', 'clock', 'effect', 'glow 0.125')),
         wants=[], forbids=['effect']),

    # ------------------------------------------------ patterns
    # the clock reads geometry: with an expression and refuses one it
    # cannot, so a check reading it with the same expression agrees
    dict(name='a geometry the clock would refuse',
         config=config(a=put('geometry', 'nonsense')),
         wants=['geometry:', 'WIDTHxHEIGHT'], forbids=[]),
    dict(name='a geometry with no height',
         config=config(a=put('geometry', '800x')),
         wants=['WIDTHxHEIGHT'], forbids=[]),
    dict(name='the shapes a geometry may take',
         config=config(a=put('geometry', '1920x1080+100+100')),
         wants=[], forbids=['geometry']),
    dict(name='and the other spellings of it',
         config=config(a=put('geometry', '800,600')),
         wants=[], forbids=['geometry']),

    # ------------------------------------------------ units
    # quantity: is what says which units a measure may carry, and the
    # clock refuses to start on one it cannot read
    dict(name='a measure with a made-up unit',
         config=config(a=put('location', 'elevation', '900xyz')),
         wants=["'xyz' is not a unit of altitude"], forbids=[]),
    dict(name='a measure with a real unit',
         config=config(a=put('location', 'elevation', '900ft')),
         wants=[], forbids=['elevation']),
    dict(name='a measure written as a bare number',
         config=config(a=put('location', 'elevation', 1600)),
         wants=[], forbids=['elevation']),
    dict(name='a measure that is not a number at all',
         config=config(a=put('location', 'elevation', 'high')),
         wants=['is not a number, with or without a unit'], forbids=[]),
    dict(name="a widget's units: naming a set that is not there",
         config=config(a=put('widgets', 'clock', 'units', 'nosuchset')),
         wants=['no unit-set named'], forbids=[]),
    dict(name="a widget's units: naming one that is",
         config=config(a=put('widgets', 'clock', 'units', 'metric')),
         wants=[], forbids=['unit-set']),

    # ------------------------------------------------ malformed shapes
    # a checker that dies on a bad config fails where it is most needed,
    # so each of these has to come back as a finding rather than a raise
    dict(name='a scalar where a block belongs',
         config=config(a=put('location', 7)),
         wants=['location: must be a block of settings'], forbids=[]),
    dict(name='a scalar where a table belongs',
         config=config(a=put('pages', 3)),
         wants=['pages: must be a block of settings'], forbids=[]),
    dict(name='a scalar where an entry belongs',
         config=config(a=put('widgets', 'clock', 'notablock')),
         wants=['widgets.clock'], forbids=[]),
    dict(name='a scalar where a page belongs',
         config=config(a=put('pages', 'clock-page', 7)),
         wants=['pages.clock-page'], forbids=[]),
    dict(name='a block where a name belongs',
         config=config(a=put('widgets', 'clock', 'region', {'x': 1})),
         wants=['widgets.clock.region'], forbids=[]),
    dict(name='a list where a number belongs',
         config=config(a=put('location', 'latitude', [1, 2])),
         wants=['location.latitude', 'does not take one'], forbids=[]),
    dict(name='a word where a list belongs',
         config=config(a=put('widgets', 'radar1', 'markers', 'notalist')),
         wants=['markers: must be a list'], forbids=[]),
    # issue 26: the one entry under captions: is commented out and what is
    # left indents under it, so a list arrives as a block.  A config's
    # blocks are DottedDicts, so this is also what proves the shape is
    # named by what it is rather than by the class holding it
    dict(name='a block where a list belongs is called a block',
         config=config(a=put('widgets', 'radar1', 'captions',
                             {'color': 'white'})),
         wants=['captions: must be a list, and this is a block'],
         forbids=['DottedDict']),
    dict(name='an empty list where a region is required',
         config=config(a=put('widgets', 'clock', 'region', [])),
         wants=['widgets.clock.region: must be set'], forbids=[]),
    # captions: [] is MapLoop's own default and means something
    dict(name='an empty list that is not required stays meaningful',
         config=config(a=put('widgets', 'radar1', 'captions', [])),
         wants=[], forbids=['captions']),

    # ------------------------------------------------ types
    dict(name='a word where a number belongs',
         config=config(a=put('theme', 'borders',
                             {'default': {'width': 'wide'}})),
         wants=['problem', 'width', 'number'], forbids=[]),
    dict(name='a number where a word belongs',
         config=config(a=put('location', 'timezone', 7)),
         wants=['problem', 'timezone'], forbids=[]),
    dict(name='true where a number belongs',
         config=config(a=put('widgets', 'radar1', 'zoom', True)),
         wants=['problem', 'zoom'], forbids=[]),
    # a region's border: is true or the name of one, so narrowing to the
    # name would leave true looking like the wrong sort of value
    dict(name='a setting taking either a boolean or a name',
         config=config(a=put('layout', 'regions',
                             {'clock': {'border': True}})),
         wants=[], forbids=['takes']),
    dict(name='a measure is a word and a size takes either',
         config=config(a=put('widgets', 'radar1', 'caption-size', '12px'),
                       b=put('widgets', 'radar1', 'frame-opacity', 0.4)),
         wants=[], forbids=['takes']),
    dict(name='a template is still not read as a value',
         config=config(a=put('widgets', 'radar1', 'zoom',
                             '{plugin-data.z}')),
         wants=[], forbids=['takes']),
    # a key written with nothing after it means unset, and the shipped
    # examples do exactly that for timezone
    dict(name='a blank value is unset, not a wrong one',
         config=config(a=put('location', 'timezone', None),
                       b=put('widgets', 'radar1', 'overlay-style', '')),
         wants=[], forbids=['takes', 'is not one of']),
    dict(name='but a blank required setting is still caught',
         config=config(a=put('widgets', 'radar1', 'frame-provider', '')),
         wants=['frame-provider: must be set'], forbids=[]),
    dict(name='the shipped layouts and themes are quiet',
         config=config(),
         wants=[], forbids=['layouts.', 'themes.']),
    dict(name='a template is not read as a value',
         config=config(a=put('location', 'latitude', '{somewhere.else}')),
         wants=[], forbids=['outside', 'is not one of']),

    # ------------------------------------------------ api keys
    dict(name='a key the config does not have',
         config=config(a=drop('apikeys', 'mbapi')),
         wants=['problem', 'wants apikeys.mbapi'], forbids=[]),
    dict(name='a key set to nothing',
         config=config(a=put('apikeys', 'mbapi', '')),
         wants=['problem providers.mapbox.apikey (apikeys.mbapi): is empty'],
         forbids=[]),
    dict(name='a key too short to be one',
         config=config(a=put('apikeys', 'mbapi', 'abcd')),
         wants=["problem", "is 'abcd', too short to be a key"], forbids=[]),
    dict(name='five characters is allowed to be a key',
         config=config(a=put('apikeys', 'mbapi', 'abcde')),
         wants=[], forbids=['apikey']),
    dict(name='a key still holding the shipped line',
         config=config(a=put('apikeys', 'mbapi', 'YOUR API KEY FOR MAPBOX')),
         wants=['problem', 'is still'], forbids=[]),
    dict(name='the shipped line whatever service it names',
         config=config(a=put('apikeys', 'mbapi', 'your api key for anything')),
         wants=['problem', 'is still'], forbids=[]),
    # a key may be written on the provider instead of named through
    # apikeys:, and the same things are wrong with it
    dict(name='a key written in place',
         config=config(a=put('providers', 'mapbox', 'apikey', 'pk.eyJ1Ijoi')),
         wants=[], forbids=['apikey']),
    dict(name='a key written in place, empty',
         config=config(a=put('providers', 'mapbox', 'apikey', '   ')),
         wants=['problem providers.mapbox.apikey: is empty'], forbids=[]),
    dict(name='a key written in place, still the shipped line',
         config=config(a=put('providers', 'mapbox', 'apikey',
                             'YOUR API KEY FOR MAPBOX')),
         wants=['problem', 'is still'], forbids=[]),
    dict(name='a key wanted only by a provider nothing uses',
         config=config(a=drop('apikeys', 'mbapi'),
                       b=drop('widgets', 'radar1')),
         wants=[], forbids=['apikeys']),

    # ------------------------------------------------ the other six tiers
    dict(name='a required setting answered by kind-settings',
         config=config(a=drop('widgets', 'current-conditions',
                              'conditions-provider'),
                       b=put('kind-settings', 'current-conditions',
                             {'conditions-provider': 'metar'})),
         wants=[], forbids=['must be set']),
    dict(name='a required setting answered by plugin-settings',
         config=config(a=drop('widgets', 'radar1', 'frame-provider'),
                       b=put('plugin-settings', 'PiClock3.MapLoop',
                             {'frame-provider': 'librewxr'})),
         wants=[], forbids=['must be set']),
    dict(name='a required setting answered by a theme kind-settings',
         config=config(a=drop('widgets', 'current-conditions',
                              'conditions-provider'),
                       b=put('theme', 'kind-settings', 'current-conditions',
                             {'conditions-provider': 'metar'})),
         wants=[], forbids=['must be set']),

    # ------------------------------------------------ roles
    # the loader refuses both of these by importing the class; the checker
    # has to reach the same answer from provides: alone, or a config would
    # pass --check and then not start
    dict(name='a provider written under widgets:',
         config=config(a=put('widgets', 'metar',
                             {'plugin': 'PiClock3.Metar', 'region': 'date'})),
         wants=['problem widgets.metar: PiClock3.Metar answers conditions,'
                ' so it is a provider'],
         forbids=['nothing declares']),
    # WRITING-A-SCHEMA says a schema and its config.yaml describe one
    # thing, so a default nothing declares is a setting nobody can find
    dict(name='a default no schema declares',
         config=config(a=put('widgets', 'twin',
                             {'plugin': 'plugins._selftest',
                              'region': 'date'})),
         wants=['plugins._selftest config.yaml', 'extra is a default'],
         forbids=[], needs='TwinExtra'),
    # a plugin invents its own types, but redefining a core name changes
    # what every other schema meant by it
    dict(name='a plugin redefining a core type',
         config=config(a=put('providers', 'twin',
                             {'plugin': 'plugins._selftest'})),
         wants=['plugins._selftest schema.yaml', 'color is a core type'],
         forbids=[], needs='TwinCore'),
    dict(name='a widget written under providers:',
         config=config(a=put('providers', 'oddity',
                             {'plugin': 'PiClock3.Date'})),
         wants=['problem providers.oddity', 'A widget belongs in widgets:'],
         forbids=[]),
    # a kind is what a plugin is interchangeable with, so two plugins
    # wearing one kind and disagreeing about their role is a contradiction
    # nothing can act on
    dict(name='a kind-settings block reaching both roles',
         config=config(a=put('widgets', 'twin',
                             {'plugin': 'plugins._selftest',
                              'region': 'date'}),
                       b=put('kind-settings', 'basemap', {'style': 'x'})),
         wants=['warning kind-settings.basemap', 'do not take the same'],
         forbids=[], needs='Twin'),
    # two plugins picking one word does nothing on its own, so nothing is
    # said until a block aims at it
    dict(name='the same two kinds with no block aimed at them',
         config=config(a=put('widgets', 'twin',
                             {'plugin': 'plugins._selftest',
                              'region': 'date'})),
         wants=[], forbids=['basemap'], needs='Twin'),
    dict(name='kinds that agree are quiet',
         config=config(),
         wants=[], forbids=['wears']),

    # ------------------------------------------------ what a provider is for
    dict(name='a base map named as the frame provider',
         config=config(a=put('widgets', 'radar1', 'frame-provider',
                             'mapbox')),
         wants=['provides map, and this wants frames'], forbids=[]),
    dict(name='a frame source named as the base map',
         config=config(a=put('widgets', 'radar1', 'base-provider',
                             'librewxr')),
         wants=['provides frames, and this wants map'], forbids=[]),
    dict(name='a station named as the forecast provider',
         config=config(a=put('widgets', 'forecast',
                             {'plugin': 'PiClock3.Forecast',
                              'region': 'forecast',
                              'forecast-provider': 'metar'})),
         wants=['provides conditions, and this wants daily or hourly'],
         forbids=[]),
    dict(name='a model answering both questions',
         config=config(a=put('widgets', 'current-conditions',
                             'conditions-provider', 'openmeteo')),
         wants=[], forbids=['provides']),
    # PiClock3.Date is a widget, so its schema has no provides: - which is
    # also what a provider nobody has finished declaring looks like
    dict(name='a provider that answers nothing',
         config=config(a=put('providers', 'quiet',
                             {'plugin': 'PiClock3.Date'})),
         wants=['providers.quiet: PiClock3.Date has no provides:'],
         forbids=[]),
    dict(name='and it is said once, not once per widget naming it',
         config=config(a=put('providers', 'quiet',
                             {'plugin': 'PiClock3.Date'}),
                       b=put('widgets', 'current-conditions',
                             'conditions-provider', 'quiet')),
         wants=['has no provides:'], forbids=[], once='has no provides:'),
    dict(name='a widget is not asked to provide anything',
         config=config(),
         wants=[], forbids=['has no provides:']),

    dict(name='a kind-settings block something wears',
         config=config(a=put('kind-settings', 'radar', {'zoom': 7})),
         wants=[], forbids=['kind-settings.radar']),

    # --------------------------- a provider's settings, on a widget
    # A widget hands its config to the providers it names, so `style:` on a
    # radar is legal.  It used to be legal and unread: the name was known
    # and the value never looked at.
    dict(name="a provider's setting written on a widget, and wrong",
         config=config(a=google(), b=put('widgets', 'radar1',
                                         'base-provider', 'googlemaps'),
                       c=put('widgets', 'radar1', 'style', 'nonsense')),
         wants=['widgets.radar1.style', 'not one of the allowed values'],
         forbids=['nothing declares']),
    dict(name="the same setting written on the provider, as before",
         config=config(a=google(), b=put('providers', 'googlemaps',
                                         'style', 'nonsense')),
         wants=['providers.googlemaps.style', 'not one of the allowed'],
         forbids=[]),
    dict(name="a provider's setting written on a widget, and right",
         config=config(a=google(), b=put('widgets', 'radar1',
                                         'base-provider', 'googlemaps'),
                       c=put('widgets', 'radar1', 'style', 'terrain')),
         wants=[], forbids=['style']),

    # two providers on one widget, each declaring style: and meaning
    # something different by it.  The config names which reads it, so a
    # value either one takes is legal
    dict(name='two providers declare it, and one takes the value',
         config=config(a=google(),
                       b=put('widgets', 'radar1', 'overlay-provider',
                             'googlemaps'),
                       c=put('widgets', 'radar1', 'style',
                             'mapbox/satellite-streets-v10')),
         wants=[], forbids=['style']),
    dict(name='two providers declare it, and neither takes the value',
         config=config(a=google(),
                       b=put('widgets', 'radar1', 'overlay-provider',
                             'googlemaps'),
                       c=put('widgets', 'radar1', 'style', 5)),
         wants=['widgets.radar1.style', 'suits nothing that declares it',
                'PiClock3.GoogleMaps', 'PiClock3.Mapbox'],
         forbids=[], once='suits nothing'),

    # a kind block reaches whatever a widget happens to name, so every
    # installed basemap is a candidate and one of them is enough
    dict(name='a kind-settings value only one of the kind takes',
         config=config(a=google(),
                       b=put('kind-settings', 'basemap',
                             {'style': 'terrain'})),
         wants=[], forbids=['kind-settings.basemap.style']),
    # a settings block belongs to no one plugin, so the spec that came
    # from the kind has no name to blame and the sentence has to end
    # without a list rather than sorting a None into one
    dict(name='a kind-settings value none of the kind takes',
         config=config(a=google(),
                       b=put('kind-settings', 'basemap', {'style': 5})),
         wants=['kind-settings.basemap.style', 'suits nothing that declares'],
         forbids=[]),

    # a spec is unreadable without the types the schema that wrote it
    # invented, and those are the provider's rather than the widget's
    dict(name="a passed setting typed by the provider's own type",
         needs='TwinTyped',
         config=config(a=put('providers', 'twin',
                             {'plugin': 'plugins._selftest'}),
                       b=put('widgets', 'radar1', 'base-provider', 'twin'),
                       c=put('widgets', 'radar1', 'style', 'satin')),
         wants=['widgets.radar1.style', 'matte, gloss'], forbids=[]),
    dict(name="the same, with a value that type allows",
         needs='TwinTyped',
         config=config(a=put('providers', 'twin',
                             {'plugin': 'plugins._selftest'}),
                       b=put('widgets', 'radar1', 'base-provider', 'twin'),
                       c=put('widgets', 'radar1', 'style', 'gloss')),
         wants=[], forbids=['style']),

    dict(name='a misspelling is still nobody\'s setting',
         config=config(a=put('widgets', 'radar1', 'stlye', 'terrain')),
         wants=['nothing declares'], forbids=[]),
    # --------------------------- what a repository brought with it
    dict(name='a layout a plugin brought along',
         needs='BundledLayout',
         config=config(a=put('pages', 'clock-page', 'layout', 'tall'),
                       b=put('widgets', 'clock', 'region', 'clock'),
                       c=drop('widgets', 'radar1'),
                       d=drop('widgets', 'current-conditions')),
         wants=[], forbids=['no layout', 'folders hold']),
    dict(name='two of them holding the same name',
         needs=('BundledLayout', 'RivalLayout'),
         config=config(a=put('pages', 'clock-page', 'layout', 'tall'),
                       b=put('widgets', 'clock', 'region', 'clock'),
                       c=drop('widgets', 'radar1'),
                       d=drop('widgets', 'current-conditions')),
         wants=['layouts.tall', '2 folders hold a layout',
                'plugins/_selftest/layouts/tall.yaml is used'],
         forbids=['no layout'], once='folders hold a layout'),
    # the rule the whole ordering exists for
    dict(name='a brought layout cannot take a shipped name',
         needs='ShadowingLayout',
         config=config(),
         wants=['layouts.classic', 'PiClock3/layouts/classic.yaml is used'],
         forbids=['no layout']),

    dict(name='a widget naming a provider that does not resolve',
         config=config(a=put('providers', 'ghost',
                             {'plugin': 'PiClock3.NoSuch'}),
                       b=put('widgets', 'radar1', 'base-provider', 'ghost'),
                       c=put('widgets', 'radar1', 'style', 'nonsense')),
         wants=['no plugin'], forbids=['nothing declares']),
]


# a layout is geometry and nothing else, so one is short enough to carry
# here whole
LAYOUT = ('name: %s\ndescription: brought along by something else\n'
          'regions:\n  clock: {left: 0, top: 0, width: 1, height: 1}\n')

# a case needing a plugin the repo does not ship gets one made under
# plugins/, which is git-ignored, and taken away again afterwards
FIXTURES = {
    'Twin': {'config.yaml': 'kind: basemap\nstyle: streets\n',
             'schema.yaml': 'description: >\n  A widget wearing a'
                            " provider's kind.\n\nsettings:\n"
                            '  style: {is: string}\n'},
    # the same plugin with a default its schema forgot
    'TwinExtra': {'config.yaml': 'kind: basemap\nstyle: streets\nextra: 3\n',
                  'schema.yaml': 'description: >\n  A schema that forgot'
                                 ' one.\n\nsettings:\n'
                                 '  style: {is: string}\n'},
    # somebody else's, cloned a level down
    'Nested': {'config.yaml': 'kind: basemap\nstyle: a\n',
               'schema.yaml': 'description: >\n  Nested.\n\n'
                              'provides: [map]\n\nsettings:\n'
                              '  style: {is: string}\n'},
    # one with no schema at all
    'NoSchema': {'config.yaml': 'kind: basemap\nstyle: streets\n'},
    # one whose schema is there and will not read, and one that is empty.
    # A third-party plugin should not be able to end the run
    'BadSchema': {'config.yaml': 'kind: basemap\nstyle: streets\n',
                  'schema.yaml': 'description: >\n  Bad.\n\nsettings:\n'
                                 '\tstyle: {is: string}\n'},
    'EmptySchema': {'config.yaml': 'kind: basemap\nstyle: streets\n',
                    'schema.yaml': ''},
    # a provider whose setting is typed by a name only its own schema
    # invents - which whoever passes that setting has to read it with
    'TwinTyped': {'config.yaml': 'kind: basemap\nstyle: matte\n',
                  'schema.yaml': 'description: >\n  Invents a type.\n\n'
                                 'provides: [map]\n\ntypes:\n'
                                 '  finish:\n    is: scalar\n'
                                 '    one-of: [matte, gloss]\n\n'
                                 'settings:\n'
                                 '  style: {is: finish}\n'},
    # a repository that brought a layout along with it, and two more that
    # brought one of the same name - which is what makes the collision
    # warning worth having
    'BundledLayout': {os.path.join('layouts', 'tall.yaml'): LAYOUT % 'Tall',
                      'config.yaml': 'kind: basemap\nstyle: a\n',
                      'schema.yaml': 'description: >\n  Brought a layout.\n\n'
                                     'provides: [map]\n\nsettings:\n'
                                     '  style: {is: string}\n'},
    'RivalLayout': {os.path.join('layouts', 'tall.yaml'): LAYOUT % 'Also Tall',
                    'theme.yaml': 'name: Selftest\ndescription: a theme\n'},
    # and one calling its layout by a name the project already ships
    'ShadowingLayout': {os.path.join('layouts', 'classic.yaml'):
                        LAYOUT % 'Not The Real Classic',
                        'layout.yaml': LAYOUT % 'Selftest'},
    # and one inventing a name core already uses
    'TwinCore': {'config.yaml': 'kind: basemap\nstyle: streets\n',
                 'schema.yaml': 'description: >\n  Redefines a core'
                                ' type.\n\nprovides: [map]\n\ntypes:\n'
                                '  color:\n    is: scalar\n'
                                '    one-of: [red, blue]\n\nsettings:\n'
                                '  style: {is: string}\n'},
}


# where a fixture is written, under the git-ignored plugins/.  The leading
# underscore is the whole safety of it: these folders are deleted after a
# run, and one named Twin could be somebody's own installed plugin.
TWIN = os.path.join('plugins', '_selftest')
WHERE = {'Nested': os.path.join('plugins', '_selftest_vendor', 'Thing'),
         'BundledLayout': os.path.join('plugins', '_selftest'),
         'RivalLayout': os.path.join('themes', '_selftest'),
         'ShadowingLayout': os.path.join('layouts', '_selftest')}


class fixture():
    """what the repo does not ship, made on disk and taken away again.

    Written to _selftest under plugins/ unless WHERE says otherwise, so a
    case can pick a variant without the config having to know which.  A
    case wanting two at once - which is what a name in two folders needs -
    names them both.
    """

    def __init__(self, names):
        if isinstance(names, str):
            names = (names,)
        self.names = tuple(names or ())
        self.folders = [WHERE.get(n, TWIN) for n in self.names]

    def __enter__(self):
        for name, folder in zip(self.names, self.folders):
            if os.path.exists(folder):
                # never delete what this did not make
                raise SystemExit('%s is in the way - remove it and run again'
                                 % folder)
            for leaf, text in FIXTURES[name].items():
                path = os.path.join(folder, leaf)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(text)

    def __exit__(self, *exc):
        for folder in self.folders:
            shutil.rmtree(folder, ignore_errors=True)
            # a fixture a level down leaves the folder it sat in behind
            parent = os.path.dirname(folder)
            if parent not in ('plugins', 'themes', 'layouts', '') \
                    and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)


def findings(cfg):
    """each finding as "severity where: message", so a case can ask for a
    severity as easily as for a wording"""
    check = Check(cfg)
    check.run()
    return ['%s %s: %s' % (severity, where, message)
            for severity, where, message in check.found]


# A file that will not parse never reaches Check at all, so these go
# through the reader itself.  Each is (name, text, what it has to say).
READING = [
    ('a tab where spaces belong',
     'pages:\n\tclock-page: {order: 0}\n',
     ['line 2', 'a tab, and yaml indents with spaces']),
    ('indenting that does not line up',
     'pages:\n  a: {order: 0}\n   b: {order: 1}\n',
     ['line 3', 'the indenting does not line up']),
    ('a quote that is never closed',
     "pages:\n  a: {theme: 'circuit}\n",
     ['a quote is opened and never closed']),
    ('a key written twice',
     'location: {latitude: 45}\nwidgets: {}\nlocation: {latitude: 51}\n',
     ['line 3', 'location is written twice, on lines 1 and 3']),
    ('a key written twice inside a block',
     'widgets:\n  clock: {region: a}\n  clock: {region: b}\n',
     ['clock is written twice, on lines 2 and 3']),
    ('an empty file',
     '',
     ['is empty']),
    ('a file of nothing but comments',
     '# just a note\n',
     ['is empty']),
    # the offending line goes under the message, which is the half that
    # makes it readable rather than merely correct
    ('the line itself, with a caret under it',
     'pages:\n\tclock-page: {order: 0}\n',
     ['clock-page', '^']),
    # yaml is happy with these and so are we
    ('a key ending in -- is not the same key', 'a: 1\na--: 2\n', []),
    ('an anchor reused is not a duplicate',
     'x: &a {p: 1}\ny: *a\nz: *a\n', []),
]


def reads():
    """each reading case as the sentence it produced, or '' for none"""
    import tempfile
    from PiClock3.Config import ConfigError, readYaml
    out = []
    for name, text, wants in READING:
        handle, path = tempfile.mkstemp(suffix='.yaml', text=True)
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            fh.write(text)
        try:
            readYaml(path)
            said = ''
        except ConfigError as e:
            said = '%s: %s' % (e.where, e.message)
        finally:
            os.unlink(path)
        out.append((name, wants, said.replace(path, '<file>')))
    return out


def agreements():
    """the three things that walk a part's folders, against each other.

    A layout the clock loads and --check has never heard of is the worst
    thing either of them can say, and it is what three copies of the same
    folder list would eventually produce.  So the copies were made one -
    and this is what says they stayed one.
    """
    import glob
    from PiClock3.ResolvedConfig import (loadPart, noSuchPart, partPaths,
                                         partRoots)
    out = []
    for kind in ('layouts', 'themes'):
        known = Check({}).named(kind)

        missed = sorted(n for n in known if loadPart(kind, n)[0] is None)
        out.append(('every %s --check knows of, the clock loads' % kind[:-1],
                    missed, 'these are named and do not load: %s' % missed))

        # and the other way, which is the one that bites: a name --check
        # has never heard of is a config it calls wrong and the clock runs
        walked = set()
        for root in partRoots(kind):
            for entry in glob.glob(os.path.join(root, '*')):
                walked.add(os.path.splitext(os.path.basename(entry))[0])
        real = {n for n in walked
                if any(os.path.isfile(p) for p, _ in partPaths(kind, n))}
        unknown = sorted(real - known)
        out.append(('every %s under a searched folder, --check knows of'
                    % kind[:-1], unknown,
                    'these load and are not named: %s' % unknown))

        sentence = noSuchPart(kind, 'nosuch')
        absent = [r.replace(os.sep, '/') for r in partRoots(kind)
                  if r.replace(os.sep, '/') + '/' not in sentence]
        out.append(('the "no %s named" sentence names every folder searched'
                    % kind[:-1], absent,
                    'searched and not named: %s' % absent))
    return out


def main():
    failed = fixed = 0
    for name, bad, complaint in agreements():
        if bad:
            failed += 1
            print('  FAIL  %s\n          %s' % (name, complaint))
        else:
            print('  ok    %s' % name)

    for name, wants, said in reads():
        bad = [w for w in wants if w not in said]
        if not wants and said:
            bad = ['said %r and should have read cleanly' % said]
        if bad:
            failed += 1
            print('  FAIL  %s' % name)
            print('          missing %s in %r' % (bad, said))
        else:
            print('  ok    %s' % name)

    for case in CASES:
        with fixture(case.get('needs')):
            found = findings(case['config'])
        bad = []
        for want in case['wants']:
            if not any(want in f for f in found):
                bad.append('did not say %r' % want)
        for forbid in case['forbids']:
            hit = [f for f in found if forbid in f]
            if hit:
                bad.append('said %r: %s' % (forbid, '; '.join(hit)))
        if case.get('once'):
            hit = [f for f in found if case['once'] in f]
            if len(hit) != 1:
                bad.append('said %r %d times, wanted once'
                           % (case['once'], len(hit)))
        if case.get('xfail'):
            if bad:
                print('  xfail %-52s %s' % (case['name'], bad[0]))
            else:
                print('  FIXED %-52s (drop the xfail)' % case['name'])
                fixed += 1
            continue
        if bad:
            failed += 1
            print('  FAIL  %s' % case['name'])
            for line in bad:
                print('          %s' % line)
            for line in found:
                print('          found: %s' % line)
        else:
            print('  ok    %s' % case['name'])

    print('\n  %d cases, %d failed, %d expected failures now fixed'
          % (len(CASES) + len(READING) + len(agreements()), failed, fixed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
