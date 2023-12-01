# PiClock3
A Fancy Clock built around a monitor and a Raspberry Pi and Python3 + PyQt5

![PiClock Picture](https://raw.githubusercontent.com/n0bel/PiClock/master/Pictures/20150307_222711.jpg)

This project started out as a way to waste a Saturday afternoon.
I had a Raspberry Pi and an extra monitor and had just taken down an analog
clock from my living room wall. I was contemplating getting a radio synced
analog clock to replace it, so I didn't have to worry about it being accurate.

But instead the PiClock was born.

The early days and evolution of it are chronicled on my
blog http://n0bel.net/v1/index.php/projects/raspberry-pi-clock

PiClock3 is a complete rewrite of PiClock (https://github.com/n0bel/PiClock).
It is based on Python3 and PyQt5.  It is also much more modular and less monolithic.

At this point, this is a rough preview of the direction being taken for PiClock3.
For something useful that works, use this fork of PiClock (https://github.com/SerBrynden/PiClock)
It is still being updated.

Ongoing updates to this will be https://github.com/n0bel/PiClock/issues/230 

I'll be committing many partially complete commits here as an easy means to
distribute code my PiClocks for testing.

No detailed instructions have been created.  Basic information follows.

1. On GitHub.com, navigate to the main page of the repository: [PiClock3](../)
2. Above the list of files, click the **< > Code** button.
3. Copy the HTTPS URL for the repository. It'll look something like this:
https://github.com/USERNAME/PiClock3.git
4. Log into your Pi, (either on the screen or via ssh) (NOT as root).
You'll be in the home directory of the user pi (/home/pi) by default,
and this is where you want to be.
5. Download PiClock3 using the `git clone` command followed by the 
HTTPS URL for the repository, for example:

```
git clone https://github.com/USERNAME/PiClock3.git
```
PiOS as of 2021-10-30 (bullseye)
```
cd PiClock3
sudo apt update
sudo apt install python3-pyqt5
sudo apt install python3-yaml
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
cp Config-Example.yaml Config.yaml
cp ApiKeys-Example.yaml ApiKeys.yaml
python3 PyQtPiClock3.py
```

### Currently Completed Plugins
* Clock (Analog, Digital plugins)
* Sunrise/sunset/moon phase (Astral plugin)
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
* Current Conditions Plugin
  * Open Weather Map
  * Dark Sky
  * ClimaCell
  * Open-Meteo


I'll welcome any contributions.


