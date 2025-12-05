# RadioPlugin for Covas:NEXT

## 📦 Overview

**RadioPlugin** is an extension for **Covas:NEXT** that lets you listen to and control internet radio stations directly from the assistant interface. It supports voice commands to play, stop, and switch stations, and announces track changes when metadata is available.

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
Downtempo and chillout mix, ideal for relaxation and creativity.

### SomaFM Space Station  
🔗 https://ice.somafm.com/spacestation  
Futuristic electronica, ambient, and experimental tunes.

### SomaFM Secret Agent  
🔗 https://ice.somafm.com/secretagent  
Spy-themed lounge and downtempo music for covert operations.

### GalNET Radio  
🔗 http://listen.radionomy.com/galnet  
Sci-fi themed station with ambient, rock, and classical music, plus GalNet news.

### BigFM  
🔗 https://streams.bigfm.de/bigfm-deutschland-128-mp3  
Popular German hits and chart-toppers for energetic flights.

### Radio Capital  
🔗 https://playerservices.streamtheworld.com/api/livestream-redirect/CAPITAL.mp3  
Italian hits and contemporary music for lively journeys.

### Radio DeeJay  
🔗 https://streamcdnm15-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiodeejay/radiodeejay/master_ma.m3u8  
Italian talk-show station with a mix of pop, dance, and rock music.

### Radio DeeJay Linetti  
🔗 https://streamcdnm3-4c4b867c89244861ac216426883d1ad0.msvdn.net/webradio/deejaywfmlinus/live.m3u8  
Italian station featuring DJ Linus preferred songs from '80 to today.

---

## 🗣 Voice Commands

Examples:
- `Play radio`
- `Play Radio Sidewinder`
- `Stop radio`
- `Change station to BigFM`
- `Set volume to 50`
- `What's playing right now?`

---

## 🔧 Features

- **Play/Stop/Change Station** via actions and voice commands.
- **Lazy/Active Track Monitoring**: Starts in lazy mode (long intervals), switches to active mode when titles repeat.
- **Track Announcements**: Announces current track with duplicate suppression and Unicode normalization.
- **Playback State Persistence**: Uses `RadioPlaybackProjection` to remember station/title across sessions.
- **New Action**: `radio_status` to retrieve current playback info.
- **Volume Control**: Set volume (0–100).
- **Configuration Panel**: Customize plugin behavior.
- **Personalized DJ Style**: Configure how the assistant responds to track changes.

---

## 📥 Installation

1. Copy the plugin folder into `%APPDATA%/com.covas-next.ui/plugins/`.
2. Ensure `python_vlc` and `vlc.py` are present in `deps/` or installed globally.
3. Install dependencies:
   ```
   pip install -r requirements.txt --target=./deps --upgrade
   ```
4. Install **VLC media player**.
5. Restart **Covas:NEXT** and enable the plugin.

---

## ⚙️ Requirements

- `python_vlc >= 3.0.12118`
- **VLC media player** installed on the system.

---

## ⚠️ Migration Notes

- Include `deejay_track_retriever.py` in the plugin folder for DeeJay stations.
- Requires Covas:NEXT build with **Projection** support.
- No breaking changes for existing settings.

---

## 📚 Release Notes

See [CNRadio v3.3.1 Release Notes](https://github.com/TheDeviceNull/CNRadio/releases/tag/v.3.3.1).
