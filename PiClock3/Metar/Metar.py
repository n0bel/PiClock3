import datetime
import logging
import random

import tzlocal
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QLabel
from metar import Metar as MetarModule

from ..Plugin import Plugin

logger = logging.getLogger(__name__)


class TimeZoneUTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class Metar(Plugin):
    metar_cond = [
        ('CLR', '', '', 'Clear', 'clear-day', 0),
        ('NSC', '', '', 'Clear', 'clear-day', 0),
        ('SKC', '', '', 'Clear', 'clear-day', 0),
        ('FEW', '', '', 'Few Clouds', 'partly-cloudy-day', 1),
        ('NCD', '', '', 'Clear', 'clear-day', 0),
        ('SCT', '', '', 'Scattered Clouds', 'partly-cloudy-day', 2),
        ('BKN', '', '', 'Mostly Cloudy', 'partly-cloudy-day', 3),
        ('OVC', '', '', 'Cloudy', 'cloudy', 4),

        ('///', '', '', '', 'cloudy', 0),
        ('UP', '', '', '', 'cloudy', 0),
        ('VV', '', '', '', 'cloudy', 0),
        ('//', '', '', '', 'cloudy', 0),

        ('DZ', '', '', 'Drizzle', 'rain', 10),

        ('RA', 'FZ', '+', 'Heavy Freezing Rain', 'sleet', 11),
        ('RA', 'FZ', '-', 'Light Freezing Rain', 'sleet', 11),
        ('RA', 'SH', '+', 'Heavy Rain Showers', 'sleet', 11),
        ('RA', 'SH', '-', 'Light Rain Showers', 'rain', 11),
        ('RA', 'BL', '+', 'Heavy Blowing Rain', 'rain', 11),
        ('RA', 'BL', '-', 'Light Blowing Rain', 'rain', 11),
        ('RA', 'FZ', '', 'Freezing Rain', 'sleet', 11),
        ('RA', 'SH', '', 'Rain Showers', 'rain', 11),
        ('RA', 'BL', '', 'Blowing Rain', 'rain', 11),
        ('RA', '', '+', 'Heavy Rain', 'rain', 11),
        ('RA', '', '-', 'Light Rain', 'rain', 11),
        ('RA', '', '', 'Rain', 'rain', 11),

        ('SN', 'FZ', '+', 'Heavy Freezing Snow', 'snow', 12),
        ('SN', 'FZ', '-', 'Light Freezing Snow', 'snow', 12),
        ('SN', 'SH', '+', 'Heavy Snow Showers', 'snow', 12),
        ('SN', 'SH', '-', 'Light Snow Showers', 'snow', 12),
        ('SN', 'BL', '+', 'Heavy Blowing Snow', 'snow', 12),
        ('SN', 'BL', '-', 'Light Blowing Snow', 'snow', 12),
        ('SN', 'FZ', '', 'Freezing Snow', 'snow', 12),
        ('SN', 'SH', '', 'Snow Showers', 'snow', 12),
        ('SN', 'BL', '', 'Blowing Snow', 'snow', 12),
        ('SN', '', '+', 'Heavy Snow', 'snow', 12),
        ('SN', '', '-', 'Light Snow', 'snow', 12),
        ('SN', '', '', 'Rain', 'snow', 12),

        ('SG', 'BL', '', 'Blowing Snow', 'snow', 12),
        ('SG', '', '', 'Snow', 'snow', 12),
        ('GS', 'BL', '', 'Blowing Snow Pellets', 'snow', 12),
        ('GS', '', '', 'Snow Pellets', 'snow', 12),

        ('IC', '', '', 'Ice Crystals', 'snow', 13),
        ('PL', '', '', 'Ice Pellets', 'snow', 13),

        ('GR', '', '+', 'Heavy Hail', 'thunderstorm', 14),
        ('GR', '', '', 'Hail', 'thunderstorm', 14),
    ]

    def __init__(self, piclock, name, config):
        super().__init__(piclock, name, config)
        self.metarreply = None
        self.timer = None
        self.wdate = None
        self.feelslike = None
        self.wind = None
        self.humidity = None
        self.pressure = None
        self.temper = None
        self.wxdesc = None
        self.wxicon = None
        # the merged config lives on the instance now, not in the config
        # section, which holds only what the entry itself said
        self.wxcommon = piclock.plugins['weather-common']
        self.wxconfig = self.wxcommon.config

    def part(self, name, align=True):
        """one labelled part of this region, placed by the plugin's layout.

        The geometry keys are the ones a page layout uses, resolved against
        this region rather than a page, so nothing about where these sit or
        how big they are is written in the code.
        """
        spec = self.config['layout'][name]
        rr = self.region.frameRect()
        label = QLabel(self.region)
        label.setObjectName(name)
        style = 'background-color: transparent;'
        if 'font-size' in spec:
            props = self.piclock.scaleFont({'font-size': spec['font-size']},
                                           rr.height())
            style += ' color: %s; font-size: %s;' % (
                self.piclock.expand(self.wxconfig.color), props['font-size'])
        label.setStyleSheet('#%s { %s }' % (name, style))
        if align:
            label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        label.setGeometry(self.piclock._regionRect(rr.width(), rr.height(),
                                                   spec))
        return label

    def start(self):

        self.wxicon = self.part('wxicon', align=False)
        self.wxdesc = self.part('wxdesc')
        self.temper = self.part('temper')
        self.pressure = self.part('pressure')
        self.humidity = self.part('humidity')
        self.wind = self.part('wind')
        self.feelslike = self.part('feelslike')
        self.wdate = self.part('wdate')

        self.timer = QTimer()
        self.timer.timeout.connect(self.getMetar)
        self.timer.start(int(1000 * self.wxconfig['refresh'] *
                             60 + random.uniform(1000, 10000)))

        self.getMetar()
        logging.info("startup finished %s %s", self.name, self.plugin)

    def pageChange(self):
        return

    def getMetar(self):
        logging.info("getMetar")
        metarurl = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/" + \
                   self.config.METAR + ".TXT"
        logging.info("metar url %s", metarurl)
        r = QUrl(metarurl)
        r = QNetworkRequest(r)
        self.metarreply = self.piclock.net.get(r)
        self.metarreply.finished.connect(self.gotMetar)

    def gotMetar(self):
        logging.info("gotMetar")
        wxstr = str(self.metarreply.readAll(), 'utf-8')
        for wxline in wxstr.splitlines():
            if wxline.startswith(self.config.METAR):
                wxstr = wxline
        logging.info('wxmetar: %s', wxstr)
        f = MetarModule.Metar(wxstr, strict=False)
        logging.info("metardata %s", f)
        dt = f.time.replace(
            tzinfo=TimeZoneUTC()).astimezone(
            tzlocal.get_localzone())

        daytime = True

        pri = -1
        weather = ''
        icon = ''
        logging.info(repr(f.sky))
        for s in f.sky:
            for c in self.metar_cond:
                if s[0] == c[0]:
                    if c[5] > pri:
                        pri = c[5]
                        weather = c[3]
                        icon = c[4]
        for w in f.weather:
            for c in self.metar_cond:
                if w[2] == c[0]:
                    if c[1] > '':
                        if w[1] == c[1]:
                            if c[2] > '':
                                if w[0][0:1] == c[2]:
                                    if c[5] > pri:
                                        pri = c[5]
                                        weather = c[3]
                                        icon = c[4]
                    else:
                        if c[2] > '':
                            if w[0][0:1] == c[2]:
                                if c[5] > pri:
                                    pri = c[5]
                                    weather = c[3]
                                    icon = c[4]
                        else:
                            if c[5] > pri:
                                pri = c[5]
                                weather = c[3]
                                icon = c[4]

        p = QtGui.QPixmap(self.wxcommon.icon(icon))
        self.wxicon.setPixmap(p.scaled(
            self.wxicon.width(), self.wxicon.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        self.wxdesc.setText(weather)
        self.temper.setText(
            self.wxcommon.units(
                'temperature',
                'C',
                f.temp.value('C')))
        if f.press:
            self.pressure.setText(self.piclock.language('pressure') + ' ' +
                                  self.wxcommon.units('pressure', 'mb', f.press.value('MB')))
        self.humidity.setText(self.piclock.language('humidity') + ' ' +
                              self.wxcommon.humidity(f.temp.value('C'), f.dewpt.value('C')))
        ws = self.piclock.language('wind')
        if f.wind_dir:
            ws += ' ' + self.wxcommon.units('direction', 'deg', f.wind_dir.value())
        ws += ' ' + self.wxcommon.units('speed', 'kph', f.wind_speed.value('KMH'))
        if f.wind_gust:
            ws += (' ' + self.piclock.language('gusting') + ' ' +
                   self.wxcommon.units('speed', 'kph', f.wind_speed.value('KMH')))
        self.wind.setText(ws)
        self.feelslike.setText(self.piclock.language('feels_like') + ' ' +
                               self.wxcommon.feelsLike(f.temp.value('C'),
                                                       f.dewpt.value('C'), f.wind_speed.value('KMH')))
        self.wdate.setText("{0:%H:%M} {1}".format(dt, self.config.METAR))
