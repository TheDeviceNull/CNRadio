import vlc
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from openai.types.chat import ChatCompletionMessageParam
from lib.PluginBase import PluginBase
from lib.PluginHelper import PluginHelper, PluginManifest
from lib.Event import Event, ProjectedEvent
from lib.EventManager import Projection
from lib.Logger import log
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, SelectOption, TextAreaSetting, TextSetting, SelectSetting, NumericalSetting, ToggleSetting, ParagraphSetting

# Pre-installed radio stations with descriptions
RADIO_STATIONS = {
    "Radio Sidewinder": {
        "url": "https://radiosidewinder.out.airtime.pro:8000/radiosidewinder_b",
        "description": "Fan-made station for Elite Dangerous with ambient and techno music, in-game news and ads."
    },
    "Hutton Orbital Radio": {
        "url": "https://quincy.torontocast.com:2775/stream",
        "description": "Community radio for Elite Dangerous with pop, rock, and humorous segments."
    },
    "SomaFM Deep Space One": {
        "url": "http://ice1.somafm.com/deepspaceone-128-mp3",
        "description": "Experimental ambient and electronic soundscapes for deep space exploration."
    },
    "SomaFM Groove Salad": {
        "url": "http://ice1.somafm.com/groovesalad-256-mp3",
        "description": "Downtempo and chillout music mix, ideal for relaxation and creativity."
    },
    "SomaFM Space Station": {
        "url": "http1://ice1.somafm.com/spacestation-128-mp3",
        "description": "Futuristic electronic music blend, perfect for space travel vibes."
    },
    "SomaFM Secret Agent": {
        "url": "http://ice1.somafm.com/secretagent-128-mp3",
        "description": "Spy-themed lounge and downtempo music for covert operations."
    },
    "GalNET Radio": {
        "url": "http://listen.radionomy.com/galnet",
        "description": "Sci-fi themed station with ambient, rock, and classical music, plus GalNet news."
    }
}

PLUGIN_LOG_LEVEL = "INFO"
_LEVELS = {"DEBUG": 10, "INFO": 20, "ERROR": 40}
DEFAULT_VOLUME = 55
DEFAULT_DJ_STYLE = "Speak like a DJ or make a witty comment"

def p_log(level: str, *args):
    """Custom logger for RadioPlugin with prefix."""
    try:
        lvl = _LEVELS.get(level.upper(), 999)
        threshold = _LEVELS.get(PLUGIN_LOG_LEVEL.upper(), 999)
        if lvl >= threshold:
            log(level, "[RadioPlugin]", *args)
    except Exception as e:
        log("ERROR", "[RadioPlugin] Logging failure:", e)

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
    """Projection to maintain current radio state."""
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
    """Main Radio Plugin class."""
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, event_classes=[RadioChangedEvent])
        self.current_station = None
        self.player = None
        self.playing = False
        self.track_monitor_thread = None
        self.stop_monitor = False
        
        # Define the plugin settings
        self.settings_config: PluginSettings | None = PluginSettings(
            key="RadioPlugin",
            label="Radio Plugin",
            icon="radio",  # Uses Material Icons
            grids=[
                SettingsGrid(
                    key="general",
                    label="General",
                    fields=[
                        ParagraphSetting(
                            key="radio_plugin_description",
                            label="About Radio Plugin",
                            type="paragraph",
                            readonly=True,
                            placeholder=None,
                            content="The Radio Plugin allows you to listen to internet radio stations while chatting with the assistant. "
                                   "You can play, stop, change stations, and adjust volume using simple commands. "
                                   "The assistant will act as a DJ and comment on track changes."
                        ),
                        ParagraphSetting(
                            key="available_stations",
                            label="Available Radio Stations",
                            type="paragraph",
                            readonly=True,
                            placeholder=None,
                            content=self._generate_stations_html()
                        ),
                        NumericalSetting(
                            key="default_volume",
                            label="Default Volume",
                            type="number",
                            readonly=False,
                            placeholder=None,
                            default_value=DEFAULT_VOLUME,
                            min_value=0,
                            max_value=100,
                            step=1
                        ),
                        TextAreaSetting(
                            key="dj_response_style",
                            label="DJ Response Style",
                            type="textarea",
                            readonly=False,
                            placeholder="Enter instructions for how the assistant should respond to track changes",
                            default_value=DEFAULT_DJ_STYLE,
                            rows=3
                        )
                    ]
                )
            ]
        )

    def _generate_stations_html(self) -> str:
        """Generate HTML content for available stations."""
        html = "<p>The following radio stations are available:</p><ul>"
        for name, info in RADIO_STATIONS.items():
            html += f"<li><strong>{name}</strong>: {info['description']}</li>"
        html += "</ul>"
        return html

    def on_plugin_helper_ready(self, helper: PluginHelper):
        """Called when PluginHelper is ready."""
        self.register_should_reply_handlers(helper)
        self.register_prompt_handlers(helper)

    def register_actions(self, helper: PluginHelper):
        """Register plugin actions."""
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
        helper.register_action("stop_radio", "Stop the radio", {}, lambda args, states: self._stop_radio(), "global")
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
        """Register status generator for context."""
        helper.register_status_generator(
            lambda states: [
                (
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
                )
            ]
        )

    def register_should_reply_handlers(self, helper: PluginHelper):
        """Register handler to decide if Covas should reply."""
        helper.register_should_reply_handler(lambda event, projected_states: self.radio_should_reply_handler(helper, event, projected_states))

    def radio_should_reply_handler(self, helper: PluginHelper, event: Event, projected_states: dict[str, dict]) -> bool | None:
        if isinstance(event, RadioChangedEvent):
            p_log("DEBUG", f"RADIOPLUGIN: radio_should_reply_handler: True for event {event}")
            return True
        return None

    def register_prompt_handlers(self, helper: PluginHelper):
        """Register prompt handler for new events."""
        helper.register_prompt_event_handler(lambda event: self.new_radio_event_prompt_handler(event, helper))

    def new_radio_event_prompt_handler(self, event: Event, helper: PluginHelper) -> list[ChatCompletionMessageParam]:
        """Generate prompt for LLM when track changes."""
        if isinstance(event, RadioChangedEvent):
            # Get the custom DJ response style from settings or use default
            dj_style = helper.get_plugin_setting('RadioPlugin', 'general', 'dj_response_style') or DEFAULT_DJ_STYLE
            
            p_log("DEBUG", f"RADIOPLUGIN: new_radio_event_prompt_handler: Prompt for event {event}")
            return [{
                "role": "user",
                "content": f"IMPORTANT: Ignore previous context. React to this radio track change as if it's the first time. New track: '{event.title}' on station '{event.station}'. {dj_style}"
            }]
        return []

    def on_chat_stop(self, helper: PluginHelper):
        if self.playing:
            p_log("INFO", "Covas:NEXT stopped. Stopping radio playback.")
            self._stop_radio()

    def _start_radio(self, url, station_name, helper: PluginHelper):
        self._stop_radio()
        if not url:
            p_log("ERROR", f"URL for station {station_name} not found.")
            return f"URL for station {station_name} not found."
        try:
            self.player = vlc.MediaPlayer(url)
            self.player.play()
            
            # Set the default volume from settings
            default_volume = helper.get_plugin_setting('RadioPlugin', 'general', 'default_volume') or DEFAULT_VOLUME
            self.player.audio_set_volume(default_volume)
            
            self.current_station = station_name
            self.playing = True
            self.stop_monitor = False
            self.track_monitor_thread = threading.Thread(target=self._monitor_track_changes, args=(helper,))
            self.track_monitor_thread.start()
            p_log("INFO", f"Started playing {station_name} at volume {default_volume}")
            return f"Playing {station_name} at volume {default_volume}"
        except Exception as e:
            p_log("ERROR", f"Failed to start radio: {e}")
            return f"Error starting radio: {e}"

    def _stop_radio(self):
        try:
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
        except Exception as e:
            p_log("ERROR", f"Error stopping radio: {e}")
            return f"Error stopping radio: {e}"

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
                    p_log("DEBUG", f"RADIOPLUGIN: Sending RadioChangedEvent: {event}")
                    helper.put_incoming_event(event)
                    p_log("DEBUG", f"Track changed: {display_title}")
            except Exception as e:
                p_log("ERROR", f"Track monitor error: {e}")
            time.sleep(10)

    def _set_volume(self, volume: int):
        try:
            if self.player:
                self.player.audio_set_volume(volume)
                p_log("INFO", f"RADIOPLUGIN: Volume set to {volume}")
                return f"Volume set to {volume}"
            else:
                p_log("ERROR", "RADIOPLUGIN: No active player to set volume.")
                return "No active player to set volume."
        except Exception as e:
            p_log("ERROR", f"RADIOPLUGIN: Error setting volume: {e}")
            return f"Error setting volume: {e}"