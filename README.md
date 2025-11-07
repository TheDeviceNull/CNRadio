# RadioPlugin for Covas:NEXT – Release 2.1.0

## 📦 Overview

**RadioPlugin** is an extension for **Covas:NEXT** that allows you to listen to and control webradio stations directly from the assistant interface.  
It supports voice commands to play, stop, and switch stations, and announces track changes when metadata is available.

---

## 🚀 What's New in Version 2.1.0

- **Configuration Tab**: New settings interface with plugin description, station list, and user preferences
- **Customizable DJ Responses**: Set how the assistant should react to track changes via settings
- **Default Volume Setting**: Configure your preferred starting volume (default: 55)
- **Enhanced Station Listings**: Stations now display with detailed descriptions in the settings panel
- **Improved Track Metadata Handling**: Better detection and display of currently playing tracks
- **Additional Radio Stations**: Added SomaFM Space Station and SomaFM Secret Agent
- **Volume Applied on Start**: Radio stations now start at your configured default volume

---

## 📡 Supported Stations

### Radio Sidewinder  
🔗 https://radiosidewinder.out.airtime.pro:8000/radiosidewinder_b  
Fan-made station for *Elite Dangerous* with ambient and techno music, in-game news, and ads.

### Hutton Orbital Radio  
🔗 https://quincy.torontocast.com/hutton  
Community radio for *Elite Dangerous* with pop, rock, and humorous segments.

### SomaFM Deep Space One  
🔗 https://ice.somafm.com/deepspaceone  
Experimental ambient and electronic soundscapes for deep space exploration.

### SomaFM Groove Salad  
🔗 https://ice.somafm.com/groovesalad  
Downtempo and chillout music mix, ideal for relaxation and creativity.

### SomaFM Space Station
🔗 https://ice.somafm.com/spacestation  
Futuristic electronic music blend, perfect for space travel vibes.

### SomaFM Secret Agent
🔗 https://ice.somafm.com/secretagent  
Spy-themed lounge and downtempo music for covert operations.

### GalNET Radio  
🔗 http://listen.radionomy.com/galnet  
Sci-fi themed station with ambient, rock, and classical music, plus GalNet news.

---

## 🗣 Voice Commands

The plugin responds to natural commands like:

- `Play radio`  
- `Play Radio Sidewinder`  
- `Stop radio`  
- `Change station to GalNET Radio`  
- `Set volume to 50`  
- `What's playing right now?`

---

## 🔧 Features

- **Play/Stop/Change Station** via actions and voice commands.
- **Track Monitoring**: Announces the currently playing track (`NowPlaying` or fallback).
- **Status Reporting**: Displays full context (station, track, description).
- **Volume Control**: Set volume (0–100).
- **Configuration Panel**: Customize plugin behavior through settings interface.
- **Personalized DJ Style**: Configure how the assistant responds to track changes.

---

## 📥 Installation

1. Copy the plugin folder into `%APPDATA%/com.covas-next.ui/plugins/` directory.
2. Ensure `python_vlc` and `vlc.py` are present in `deps/` or installed globally.

You can install them using command, inside the plugin folder:

`pip install -r requirements.txt --target=./deps --upgrade`

3. Install **VLC media player**.
4. Restart **Covas:NEXT** and enable the plugin from the *Plugins* interface.

---

## ⚙️ Requirements

- `python_vlc >= 3.0.12118`  
- **VLC media player** installed on the system.

---

## ⚠️ VLC Dependency

This plugin requires [VLC media player](https://www.videolan.org/vlc/) to be installed on the system.

Without this, the plugin will fail to load with an error like:

`Failed to load plugin CNRadio: Failed to load dynlib/dll '.\libvlc.dll'. Most likely this dynlib/dll was not found when the application was frozen.`