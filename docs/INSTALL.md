# Installing PiClock3

From a fresh Raspberry Pi to a clock that starts itself at boot.  The steps
are the same on every release it runs on.

## What you need

- **A Raspberry Pi** and **Raspberry Pi OS with desktop**.  Tested on:

  | | Bullseye | Bookworm | Trixie |
  |---|---|---|---|
  | Pi 4, 64-bit | yes | yes | yes |
  | Pi 4, 32-bit | yes | yes | yes |
  | Pi Zero W, 32-bit | yes | yes | yes |

  The Zero takes a few minutes to start the clock.  Python 3.9, which
  Bullseye ships, is the oldest that works.
- **A screen**, and **a network connection** - the weather, the radar and the
  maps all come from the internet.

## Prepare the Pi

1. Write Raspberry Pi OS **with desktop** to the card with Raspberry Pi
   Imager, and in its settings give the user, the Wi-Fi, ssh, and the time
   zone and keyboard for where the clock is.  The clock takes its language
   from the Pi's - see [WRITING-A-LANGUAGE.md](WRITING-A-LANGUAGE.md).
2. Boot it.  The clock needs the desktop running to draw on, so set the Pi
   to start the desktop and log in automatically:

   ```
   sudo raspi-config nonint do_boot_behaviour B4
   ```

   B4 is raspi-config's "Desktop Autologin" choice.  Or run
   `sudo raspi-config` and pick it from the menu.

## Install

Log in as that user - on the Pi's own screen or over ssh - **not** as root.
From your home directory:

```
git clone https://github.com/n0bel/PiClock3.git
cd PiClock3
sudo apt update
sudo apt install python3-pyqt5 python3-yaml
export PIP_BREAK_SYSTEM_PACKAGES=1
python3 -m pip install -r requirements.txt
cp examples/default.yaml Config.yaml
cp examples/ApiKeys.yaml ApiKeys.yaml
```

Everything after `cd PiClock3` runs in that folder.

- **PyQt5 comes from apt.**  Installing it with pip builds Qt from source,
  which takes hours on a Pi and usually runs out of memory first.
- **`PIP_BREAK_SYSTEM_PACKAGES=1`** is for Bookworm and Trixie, whose pip
  refuses to install outside a venv with `error:
  externally-managed-environment`.  Without `sudo`, pip installs into
  `~/.local` and touches nothing apt owns.  Bullseye's pip ignores the
  setting.
- **Those packages belong to the user who ran pip.**  Start the clock as the
  same user, or it stops with `ModuleNotFoundError` for packages that are
  plainly installed.

## Keys and your location

`Config.yaml` is the clock; `ApiKeys.yaml` holds its keys.  Both are yours,
and git ignores them.

The radar needs no key, but the map under it does: the example's maps come
from Mapbox.  Put a key in `ApiKeys.yaml`:

- Mapbox - https://account.mapbox.com - goes in `mbapi`
- or Google Static Maps - https://console.cloud.google.com - goes in
  `googleapi`.  Then, on each radar in `Config.yaml`, change
  `base-provider: mapbox` to `base-provider: googlemaps` and the `style:`
  to `hybrid`.

For no key at all, start from `examples/openfreemap.yaml` instead.

Then set your own place in `Config.yaml` - `latitude:`, `longitude:`, and
the nearest airfield for `METAR:`.  The example sits at 45, -93 with KMSP.

Ask the clock what it thinks of the config:

```
python3 PyQtPiClock3.py --check
```

It says what is wrong - an unfilled key, a misspelled setting - and exits.
It needs no screen, so it works over ssh.
[WRITING-A-CONFIG.md](WRITING-A-CONFIG.md) covers everything a config can say.

## First run

**From a terminal on the Pi's desktop:**

```
python3 PyQtPiClock3.py
```

Over ssh it fails with `could not connect to display`, since an ssh session
has no screen.  To start it on the Pi's screen from ssh:

```
DISPLAY=:0 python3 PyQtPiClock3.py
```

F4 quits.  Space turns the page.

**On a Pi Zero**, the first start after installing is slow: Python compiles
the tree as it imports it, which can time out the first web requests and
leave the forecast empty.  Start it again.

## Start at boot

```
mkdir -p ~/.config/autostart
cp PiClock3.desktop ~/.config/autostart/
```

When the desktop starts, it runs `startup.sh`, which shows **Starting
PiClock3 in 45 seconds** with **Now** and **Cancel**, then starts the clock.
Cancel leaves you at the desktop to work on the Pi.  If the time has not been
set from the network when the countdown ends, it waits for that too, up to a
minute, so the clock never starts on the wrong day.

`PiClock3.desktop` expects the clone at `~/PiClock3`.  If it is elsewhere,
change the path on its `Exec=` line.  For a different countdown, add the
number of seconds after `startup.sh` there.

To stop starting at boot, delete `~/.config/autostart/PiClock3.desktop`.

On a Pi Zero, the clock takes about a minute and a half to appear after the
countdown.

## Keep the screen on

```
sudo raspi-config nonint do_blanking 1
```

Or **Display Options, Screen Blanking, No** in `sudo raspi-config`.  Reboot
for it to take.

The clock hides the mouse pointer itself while it is full screen.

## Updating

```
cd ~/PiClock3
git pull
python3 -m pip install -r requirements.txt
```

The last line matters only when `requirements.txt` changed, and does nothing
otherwise.  `Config.yaml` and `ApiKeys.yaml` are untouched by a pull.

## When it does not work

| what you see | what it is |
|---|---|
| `could not connect to display` | started over ssh - see [First run](#first-run) |
| `ModuleNotFoundError` | the requirements are not installed for this user - rerun the pip line as them |
| an empty desktop after boot | the clock stopped at startup - the reason is in `~/.xsession-errors` and `PyQtPiClock3.log` |
| day and month names in English | the language's locale is not installed - `sudo dpkg-reconfigure locales` |
| a list of problems instead of a clock | the config - `python3 PyQtPiClock3.py --check` says what to fix |

`PyQtPiClock3.log`, in the PiClock3 folder, is the first thing to attach to
a bug report: https://github.com/n0bel/PiClock3/issues
