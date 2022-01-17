# PiClock3
A Fancy Clock built around a monitor and a Raspberry Pi and python3 + pyqt5

![PiClock Picture](https://raw.githubusercontent.com/n0bel/PiClock/master/Pictures/20150307_222711.jpg)

This project started out as a way to waste a Saturday afternoon.
I had a Raspberry Pi and an extra monitor and had just taken down an analog
clock from my livingroom wall. I was contemplating getting a radio sync'ed
analog clock to replace it, so I didn't have to worry about it being accurate.

But instead the PiClock was born.

The early days and evolution of it are chronicled on my
blog http://n0bel.net/v1/index.php/projects/raspberry-pi-clock

PiClock3 is a complete rewrite of PiClock (https://github.com/n0bel/PiClock).
It is based on python3 and PyQt5.   It is also much more modular and less monolithic.

At this point, this is a rough preview of the direction being taken for PiClock3.
For something useful that works use the original PiClock (https://github.com/n0bel/PiClock)
It is still being updated.

On-going updates to this will be https://github.com/n0bel/PiClock/issues/230 

I'll be commiting many partially complete commits here as an easy means to
distribute code my PiClocks for testing.

No detailed instructions have been created.  Basic information follows.

PiOS as of 2021-10-30 (bullseye)
```
sudo apt install python3-pyqt5
sudo apt install python3-yaml
sudo pip3 install pyyaml-include
sudo pip3 install astral
sudo pip3 install tzlocal
sudo pip3 install compassheadinglib
sudo pip3 install metar
git clone https://github.com/n0bel/PiClock3.git
cd PiClock3
cp Config-Example.yaml Config.yaml
cp ApiKeys-Example.yaml ApiKeys.yaml
python3 PyQtPiClock3.py
```

### Currently Completed Plugins
* Clock (Analog, Digital plugins)
* Sunrise/sunset/moonphase (Astral plugin)
* Date at the top (Date plugin)
* Current conditions (METAR plugin only)

### Work In progress (my local commits too buggy to release)
* Radar Plugin (via RainViewer)
* Google Maps Plugin (for radar background)
* Mapbox Maps Plugin (for radar background)

### Remaining To DO
* Forecast Plugins
  * Open Weather Map
  * DarkSky
  * Climacell
  * Open-Meteo
* Current Condions Plugin
  * Open Weather Map
  * Dark Sky
  * ClimaCell
  * Open-Meteo


I'll welcome any contributions.


