# RadioPlugin v.2.0.1 
# Added Stop_Radio on Chat Stop, improved track monitoring, new Radio Station, and settings config.
# A plugin for Covas:NEXT to stream space-themed radio stations.
# Developed by The Device Null
# Requires python-vlc: pip install python-vlc
import vlc
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from lib.PluginBase import PluginBase
from lib.PluginHelper import PluginHelper, PluginManifest
from lib.Event import Event, ProjectedEvent
from lib.EventManager import Projection
from lib.Logger import log
from lib.PluginSettingDefinitions import (
    PluginSettings, SettingsGrid, ParagraphSetting, TextSetting, TextAreaSetting
)
# Pre-installed radio stations with descriptions
RADIO_STATIONS = {
    "Radio Sidewinder": {
        "url": "https://radiosidewinder.out.airtime.pro:8000/radiosidewinder_b",
        "description": "Fan-made station for Elite Dangerous with ambient and techno music, in-game news and ads."
    },
    "Hutton Orbital Radio": {
        "url": "https://quincy.torontocast.com/hutton",
        "description": "Community radio for Elite Dangerous with pop, rock, and humorous segments."
    },
    "SomaFM Deep Space One": {
        "url": "https://ice.somafm.com/deepspaceone",
        "description": "Experimental ambient and electronic soundscapes for deep space exploration."
    },
    "SomaFM Groove Salad": {
        "url": "https://ice.somafm.com/groovesalad",
        "description": "Downtempo and chillout music mix, ideal for relaxation and creativity."
    },
    "SomaFM Space Station": {
        "url": "https://ice.somafm.com/spacestation",
        "description": "Futuristic electronic music blend, perfect for space travel vibes."
    },
    "GalNET Radio": {
        "url": "http://listen.radionomy.com/galnet",
        "description": "Sci-fi themed station with ambient, rock, and classical music, plus GalNet news."
    }
}

PLUGIN_LOG_LEVEL = "INFO"
_LEVELS = {"DEBUG": 10, "INFO": 20, "ERROR": 40}

def p_log(level: str, *args):
    try:
        lvl = _LEVELS.get(level.upper(), 999)
        threshold = _LEVELS.get(PLUGIN_LOG_LEVEL.upper(), 999)
        if lvl >= threshold:
            log(level, *args)
    except Exception:
        pass

@dataclass
class RadioChangedEvent(Event):
    station: str
    title: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['tool'] = 'tool'
    text: list[str] = field(default_factory=list)
    processed_at: float = 0.0
    memorized_at: str = None
    responded_at: str = None

    def __post_init__(self):
        self.text = [f"Radio changed to {self.station}: {self.title}"]

    def __str__(self) -> str:
        return self.text[0]

class CurrentRadioState(Projection[dict[str, Any]]):
    def get_default_state(self) -> dict[str, Any]:
        return {"station": "", "title": "", "playing": False}

    def process(self, event: Event) -> list[ProjectedEvent]:
        projected = []
        if isinstance(event, RadioChangedEvent):
            self.state["station"] = event.station
            self.state["title"] = event.title
            self.state["playing"] = True
            projected.append(ProjectedEvent({
                "event": "RadioChanged",
                "station": event.station,
                "title": event.title
            }))
        return projected

class RadioPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, event_classes=[RadioChangedEvent])
        self.current_station = None
        self.player = None
        self.playing = False
        self.track_monitor_thread = None
        self.stop_monitor = False
        self.settings_config = {
            "key": "radio_plugin_settings",
            "label": "Radio Plugin Configuration",
            "icon": "radio",
            "grids": [
                {
                    "key": "description_grid",
                    "label": "Plugin Description",
                    "fields": [
                        {
                            "key": "plugin_description",
                            "label": "About This Plugin",
                            "type": "paragraph",
                            "readonly": True,
                            "placeholder": None,
                            "content": "This plugin allows you to stream various space-themed radio stations."
                        }
                    ]
                },
                {
                    "key": "preinstalled_stations",
                    "label": "Pre-installed Stations",
                    "fields": [
                        {
                            "key": "station_list",
                            "label": "Available Stations",
                            "type": "textarea",
                            "readonly": True,
                            "placeholder": None,
                            "default_value": "\n".join([f"{name}: {info['url']}" for name, info in RADIO_STATIONS.items()]),
                            "rows": 10,
                            "cols": 60
                        }
                    ]
                }
            ]
        }

    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            "play_radio",
            "Play a webradio station",
            {
                "type": "object",
                "properties": {
                    "station": {"type": "string", "enum": list(RADIO_STATIONS.keys())}
                },
                "required": ["station"]
            },
            lambda args, states: self._start_radio(RADIO_STATIONS.get(args["station"], {}).get("url"), args["station"], helper),
            "global"
        )
        helper.register_action(
            "stop_radio",
            "Stop the radio",
            {},
            lambda args, states: self._stop_radio(),
            "global"
        )
        helper.register_action(
            "change_radio",
            "Change to another radio station",
            {
                "type": "object",
                "properties": {
                    "station": {"type": "string", "enum": list(RADIO_STATIONS.keys())}
                },
                "required": ["station"]
            },
            lambda args, states: self._start_radio(RADIO_STATIONS.get(args["station"], {}).get("url"), args["station"], helper),
            "global"
        )
        helper.register_action(
            "set_volume",
            "Set the volume of the radio",
            {
                "type": "object",
                "properties": {
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["volume"]
            },
            lambda args, states: self._set_volume(args["volume"]),
            "global"
        )

    def register_projections(self, helper: PluginHelper):
        helper.register_projection(CurrentRadioState())

    def register_status_generators(self, helper: PluginHelper):
        helper.register_status_generator(
            lambda states: [(
                "Radio Status",
                {
                    "available_stations": list(RADIO_STATIONS.keys()),
                    "station_descriptions": {name: RADIO_STATIONS[name]["description"] for name in RADIO_STATIONS},
                    "current_station": states.get("CurrentRadioState", {}).get("station", ""),
                    "current_track": states.get("CurrentRadioState", {}).get("title", ""),
                    "is_playing": states.get("CurrentRadioState", {}).get("playing", False),
                    "description": f"Now playing: {states.get('CurrentRadioState', {}).get('title', 'Unknown')} on {states.get('CurrentRadioState', {}).get('station', 'Unknown')}",
                    "available_actions": {
                        "play_radio": "Play a station",
                        "change_radio": "Change to another station (provide station name)",
                        "stop_radio": "Stop the radio",
                        "set_volume": "Set the volume (0–100)"
                    },
                    "hint": "To change station, use change_radio with parameter station."
                }
            )]
        )

    def on_chat_stop(self, helper: PluginHelper):
        if self.playing:
            p_log("INFO", "Covas:NEXT stopped. Stopping radio playback.")
            self._stop_radio()

    def _start_radio(self, url, station_name, helper: PluginHelper):
        self._stop_radio()
        if not url:
            return f"URL for station {station_name} not found."
        self.player = vlc.MediaPlayer(url)
        self.player.play()
        self.current_station = station_name
        self.playing = True
        self.stop_monitor = False
        self.track_monitor_thread = threading.Thread(target=self._monitor_track_changes, args=(helper,))
        self.track_monitor_thread.start()
        p_log("INFO", f"Started playing {station_name}")
        return f"Playing {station_name}"

    def _stop_radio(self):
        if self.player:
            self.player.stop()
            self.player = None
        self.playing = False
        self.current_station = None
        self.stop_monitor = True
        if self.track_monitor_thread:
            self.track_monitor_thread.join(timeout=1)
            self.track_monitor_thread = None
        p_log("INFO", "Stopped radio")
        return "Radio stopped."

    def _monitor_track_changes(self, helper: PluginHelper):
        last_title = ""
        while not self.stop_monitor:
            try:
                media = self.player.get_media()
                media.parse_with_options(vlc.MediaParseFlag.network, timeout=5)

                title = media.get_meta(vlc.Meta.Title)
                now_playing = media.get_meta(vlc.Meta.NowPlaying)

                p_log("DEBUG", f"Metadata check: Title={title}, NowPlaying={now_playing}")

                display_title = now_playing or title or f"{self.current_station} - Unknown track"
                normalized_title = display_title.strip().lower()

                if normalized_title and normalized_title != last_title:
                    last_title = normalized_title
                    event = RadioChangedEvent(station=self.current_station, title=display_title)
                    helper.put_incoming_event(event)
                    p_log("INFO", f"Track changed: {display_title}")
            except Exception as e:
                p_log("ERROR", f"Track monitor error: {e}")
            time.sleep(10)

    def _set_volume(self, volume: int):
        if self.player:
            self.player.audio_set_volume(volume)
            p_log("INFO", f"Volume set to {volume}")
            return f"Volume set to {volume}"
        else:
            return "No active player to set volume."
    def on_chat_stop(self, helper: PluginHelper):
        if self.playing:
            p_log("INFO", "Covas:NEXT stopped. Stopping radio playback.")
            self._stop_radio()
