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
        self.wxconfig = self.piclock.config.plugins['weather-common']
        self.wxcommon = piclock.plugins['weather-common']

    def fontCalc(self, size):
        return "%dpx" % (float(size) * self.block.frameRect().height())

    def start(self):

        self.wxicon = QLabel(self.block)
        self.wxicon.setObjectName("wxicon")

        rr = self.block.frameRect()
        w = int(rr.width() * .6)
        h = int(rr.height() * .6)
        x = rr.left() + int((rr.width() - w) / 2)
        y = rr.top() - int(rr.height() * .1)
        self.wxicon.setGeometry(x, y, w, h)
        self.wxicon.setStyleSheet("#wxicon { background-color transparent; }")

        self.wxdesc = QLabel(self.block)
        self.wxdesc.setObjectName('wxdesc')
        self.wxdesc.setStyleSheet("#wxdesc { background-color: transparent; color: " +
                                  self.piclock.expand(self.wxconfig.color) +
                                  "; font-size: " +
                                  self.fontCalc(.1) +
                                  "; " +
                                  # Config.fontattr +
                                  "}")
        self.wxdesc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .4)
        self.wxdesc.setGeometry(x, y, w, h)

        self.temper = QLabel(self.block)
        self.temper.setObjectName('temper')
        self.temper.setStyleSheet("#temper { background-color: transparent; color: " +
                                  self.piclock.expand(self.wxconfig.color) +
                                  "; font-size: " +
                                  self.fontCalc(.2) +
                                  "; " +
                                  # Config.fontattr +
                                  "}")
        self.temper.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .45)
        self.temper.setGeometry(x, y, w, h)

        self.pressure = QLabel(self.block)
        self.pressure.setObjectName('pressure')
        self.pressure.setStyleSheet("#pressure { background-color: transparent; color: " +
                                    self.piclock.expand(self.wxconfig.color) +
                                    "; font-size: " +
                                    self.fontCalc(.1) +
                                    "; " +
                                    # Config.fontattr +
                                    "}")
        self.pressure.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .65)
        self.pressure.setGeometry(x, y, w, h)

        self.humidity = QLabel(self.block)
        self.humidity.setObjectName('humidity')
        self.humidity.setStyleSheet("#humidity { background-color: transparent; color: " +
                                    self.piclock.expand(self.wxconfig.color) +
                                    "; font-size: " +
                                    self.fontCalc(.07) +
                                    "; " +
                                    # Config.fontattr +
                                    "}")
        self.humidity.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .75)
        self.humidity.setGeometry(x, y, w, h)

        self.wind = QLabel(self.block)
        self.wind.setObjectName('wind')
        self.wind.setStyleSheet("#wind { background-color: transparent; color: " +
                                self.piclock.expand(self.wxconfig.color) +
                                "; font-size: " +
                                self.fontCalc(.07) +
                                "; " +
                                # Config.fontattr +
                                "}")
        self.wind.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .82)
        self.wind.setGeometry(x, y, w, h)

        self.feelslike = QLabel(self.block)
        self.feelslike.setObjectName('feelslike')
        self.feelslike.setStyleSheet("#feelslike { background-color: transparent; color: " +
                                     self.piclock.expand(self.wxconfig.color) +
                                     "; font-size: " +
                                     self.fontCalc(.05) +
                                     "; " +
                                     # Config.fontattr +
                                     "}")
        self.feelslike.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .89)
        self.feelslike.setGeometry(x, y, w, h)

        self.wdate = QLabel(self.block)
        self.wdate.setObjectName('wdate')
        self.wdate.setStyleSheet("#wdate { background-color: transparent; color: " +
                                 self.piclock.expand(self.wxconfig.color) +
                                 "; font-size: " +
                                 self.fontCalc(.05) +
                                 "; " +
                                 # Config.fontattr +
                                 "}")
        self.wdate.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        w = rr.width()
        h = int(rr.height() * .6)
        x = rr.left()
        y = rr.top() + int(rr.height() * .95)
        self.wdate.setGeometry(x, y, w, h)

        # self.clockrect = self.block.frameRect()
        # self.w.setGeometry(self.clockrect)
        # self.w.setStyleSheet(
        #    "#w { background-color: transparent; " +
        #    " font-family:sans-serif;" +
        #    " font-weight: light;" +
        #    " background-color: transparent;" +
        #    " font-size: " + self.fontCalc(0.3) +
        #    "}")
        #
        # self.wx

        self.timer = QTimer()
        self.timer.timeout.connect(self.getMetar)
        self.timer.start(int(1000 * self.wxconfig['refresh'] *
                             60 + random.uniform(1000, 10000)))

        self.getMetar()
        logging.info("startup finished %s %s", self.name, self.module)

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
