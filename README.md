# RadioPlugin for Covas:NEXT – Release 2.0.0

## 📦 Overview

**RadioPlugin** is an extension for **Covas:NEXT** that allows you to listen to and control webradio stations directly from the assistant interface.  
It supports voice commands to play, stop, and switch stations, and announces track changes when metadata is available.

---

## 🚀 What's New in Version 2.0.0

- **NowPlaying Support**: Prefers the `NowPlaying` metadata to display the currently playing track.
- **Smart Fallback**: If metadata is unavailable, displays `StationName - Unknown track`.
- **Title Normalization**: Prevents duplicates caused by spacing or formatting inconsistencies.
- **Improved AI Context**:
  - `status_generator` now includes a natural phrase:  
    _“Now playing: {track} on {station}”_
- **Integrated Station Descriptions**: Each station includes a short description for better context.
- **New Stations Added**:
  - SomaFM Groove Salad
  - GalNET Radio
- **Volume Command**: Set volume (0–100) via the `set_volume` action.

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
- `What’s playing right now?`

---

## 🔧 Features

- **Play/Stop/Change Station** via actions and voice commands.
- **Track Monitoring**: Announces the currently playing track (`NowPlaying` or fallback).
- **Status Reporting**: Displays full context (station, track, description).
- **Volume Control**: Set volume (0–100).

---

## 📥 Installation

1. Copy the plugin folder into `plugins/` of **Covas:NEXT**.
2. Ensure `python_vlc` and `vlc.py` are present in `deps/` or installed globally.
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
