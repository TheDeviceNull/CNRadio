# RadioPlugin v2.2.0
# -------------------
# Stable release for Covas:NEXT
# - SomaFM station support with accurate track retrieval via JSON API

import vlc
import threading
import time
from . import somafm_track_retriever as somaretriever
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from openai.types.chat import ChatCompletionMessageParam
from lib.PluginBase import PluginBase
from lib.PluginHelper import PluginHelper, PluginManifest
from lib.Event import Event, ProjectedEvent
from lib.EventManager import Projection
from lib.Logger import log
from lib.PluginSettingDefinitions import (
    PluginSettings, SettingsGrid, SelectOption, TextAreaSetting, TextSetting,
    SelectSetting, NumericalSetting, ToggleSetting, ParagraphSetting
)

# ---------------------------------------------------------------------
# Pre-installed radio stations
# ---------------------------------------------------------------------
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
        "url": "https://ice.somafm.com/deepspaceone",
        "description": "Experimental ambient and electronic soundscapes for deep space exploration."
    },
    "SomaFM Groove Salad": {
        "url": "https://ice.somafm.com/groovesalad",
        "description": "Downtempo and chillout mix, perfect for relaxing flight time."
    },
    "SomaFM Space Station": {
        "url": "https://ice.somafm.com/spacestation",
        "description": "Futuristic electronica, ambient, and experimental tunes."
    },
    "SomaFM Secret Agent": {
        "url": "https://ice.somafm.com/secretagent",
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

# ---------------------------------------------------------------------
# Helper logger
# ---------------------------------------------------------------------
def p_log(level: str, *args):
    """Custom logger for RadioPlugin with prefix."""
    try:
        lvl = _LEVELS.get(level.upper(), 999)
        threshold = _LEVELS.get(PLUGIN_LOG_LEVEL.upper(), 999)
        if lvl >= threshold:
            log(level, "[RadioPlugin]", *args)
    except Exception as e:
        log("ERROR", "[RadioPlugin] Logging failure:", e)

# ---------------------------------------------------------------------
# Event and Projection
# ---------------------------------------------------------------------
@dataclass
class RadioChangedEvent(Event):
    """Event triggered when VLC metadata changes track."""
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
    """Projection maintaining the current radio state."""
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

# ---------------------------------------------------------------------
# Main plugin class
# ---------------------------------------------------------------------
class RadioPlugin(PluginBase):
    """Main Radio Plugin for Covas:NEXT."""
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, event_classes=[RadioChangedEvent])
        self.current_station = None
        self.player = None
        self.playing = False
        self.track_monitor_thread = None
        self.stop_monitor = False
        self._last_replied_title = None
        self._last_reply_time = 0

        self.settings_config: PluginSettings | None = PluginSettings(
            key="RadioPlugin",
            label="Radio Plugin",
            icon="radio",
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
                            content="The Radio Plugin lets you listen to internet radio stations while chatting with Covas:NEXT. "
                                    "It plays, stops, switches stations, and adjusts volume. Covas comments on track changes like a DJ."
                        ),
                        ParagraphSetting(
                            key="available_stations",
                            label="Available Stations",
                            type="paragraph",
                            readonly=True,
                            content=self._generate_stations_html()
                        ),
                        NumericalSetting(
                            key="default_volume",
                            label="Default Volume",
                            type="number",
                            default_value=DEFAULT_VOLUME,
                            min_value=0,
                            max_value=100,
                            step=1
                        ),
                        TextAreaSetting(
                            key="dj_response_style",
                            label="DJ Response Style",
                            type="textarea",
                            default_value=DEFAULT_DJ_STYLE,
                            rows=3
                        )
                    ]
                )
            ]
        )

    # -----------------------------------------------------------------
    # Plugin setup
    # -----------------------------------------------------------------
    def _generate_stations_html(self) -> str:
        html = "<p>The following radio stations are available:</p><ul>"
        for name, info in RADIO_STATIONS.items():
            html += f"<li><strong>{name}</strong>: {info['description']}</li>"
        html += "</ul>"
        return html

    def on_plugin_helper_ready(self, helper: PluginHelper):
        self.register_should_reply_handlers(helper)
        self.register_prompt_handlers(helper)

    # -----------------------------------------------------------------
    # Action registration
    # -----------------------------------------------------------------
    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            "play_radio", "Play a webradio station",
            {"type": "object", "properties": {"station": {"type": "string", "enum": list(RADIO_STATIONS.keys())}}, "required": ["station"]},
            lambda args, states: self._start_radio(RADIO_STATIONS.get(args["station"], {}).get("url"), args["station"], helper),
            "global"
        )
        helper.register_action("stop_radio", "Stop the radio", {}, lambda args, states: self._stop_radio(), "global")
        helper.register_action(
            "change_radio", "Change to another station",
            {"type": "object", "properties": {"station": {"type": "string", "enum": list(RADIO_STATIONS.keys())}}, "required": ["station"]},
            lambda args, states: self._start_radio(RADIO_STATIONS.get(args["station"], {}).get("url"), args["station"], helper),
            "global"
        )
        helper.register_action(
            "set_volume", "Set the radio volume",
            {"type": "object", "properties": {"volume": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["volume"]},
            lambda args, states: self._set_volume(args["volume"]),
            "global"
        )

    # -----------------------------------------------------------------
    # Reply and prompt logic
    # -----------------------------------------------------------------
    def register_should_reply_handlers(self, helper: PluginHelper):
        helper.register_should_reply_handler(lambda event, projected_states: self.radio_should_reply_handler(helper, event, projected_states))

    def radio_should_reply_handler(self, helper: PluginHelper, event: Event, projected_states: dict[str, dict]) -> bool | None:
        """Decide whether Covas should reply to a radio track change."""
        if not isinstance(event, RadioChangedEvent):
            return None

        # Skip empty or invalid titles
        if not event.title or "unknown" in event.title.lower() or len(event.title.strip()) < 3:
            p_log("DEBUG", f"RADIOPLUGIN: Ignoring empty or invalid title '{event.title}'")
            return False

        normalized_title = event.title.strip().lower()
        last_title_norm = (self._last_replied_title or "").strip().lower()
        last_station = getattr(self, "_last_replied_station", None)
        current_time = time.time()

        # If same station and same title recently, skip
        if normalized_title == last_title_norm and event.station == last_station:
            if current_time - self._last_reply_time < 45:  # 45s cooldown for same song
                p_log("DEBUG", f"RADIOPLUGIN: Duplicate '{event.title}' on same station ignored (within 45s).")
                return False
            else:
                log("DEBUG", f"RADIOPLUGIN: Same title on same station but cooldown passed, allowing reply.")

        # Update memory
        self._last_replied_title = event.title
        self._last_replied_station = event.station
        self._last_reply_time = current_time

        p_log("DEBUG", f"RADIOPLUGIN: Will reply to '{event.title}' on {event.station}")
        return True

    def register_prompt_handlers(self, helper: PluginHelper):
        helper.register_prompt_event_handler(lambda event: self.new_radio_event_prompt_handler(event, helper))

    def new_radio_event_prompt_handler(self, event: Event, helper: PluginHelper) -> list[ChatCompletionMessageParam]:
        if isinstance(event, RadioChangedEvent):
            dj_style = helper.get_plugin_setting('RadioPlugin', 'general', 'dj_response_style') or DEFAULT_DJ_STYLE
            return [{
                "role": "user",
                "content": f"IMPORTANT: React to this radio track change. "
                           f"New track: '{event.title}' on station '{event.station}'. {dj_style}"
            }]
        return []

    # -----------------------------------------------------------------
    # Player control
    # -----------------------------------------------------------------
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

    def _set_volume(self, volume: int):
        """Set the playback volume safely, even during stream startup."""
        try:
            if not self.player:
                p_log("ERROR", "RADIOPLUGIN: No active player to set volume.")
                return "No active player to set volume."

            volume = max(0, min(100, int(volume)))
            result = self.player.audio_set_volume(volume)

            if result == -1:
                time.sleep(0.5)
                result = self.player.audio_set_volume(volume)

            if result == -1:
                p_log("ERROR", "RADIOPLUGIN: VLC refused volume change (player not ready).")
                return "Unable to set volume right now."

            actual = self.player.audio_get_volume()
            p_log("INFO", f"RADIOPLUGIN: Volume set to {actual} (requested {volume})")
            return f"Volume set to {actual}"

        except Exception as e:
            p_log("ERROR", f"RADIOPLUGIN: Error setting volume: {e}")
            return f"Error setting volume: {e}"

    # -----------------------------------------------------------------
    # Track monitoring (debounced)
    # -----------------------------------------------------------------
    def _monitor_track_changes(self, helper: PluginHelper):
        """Monitor VLC metadata and trigger an event when the track actually changes."""
        last_title = ""
        last_event_time = 0

        p_log("INFO", "Track monitor started.")
        while not self.stop_monitor:
            try:
                if not self.player:
                    time.sleep(2)
                    continue

                # Get track info based on station type
                display_title = ""
            
                # Check if this is a SomaFM station
                is_somafm = any(name in self.current_station.lower() for name in ["somafm", "soma.fm", "deepspaceone", "groovesalad", "spacestation", "secretagent"])
            
                if is_somafm:
                    # Use the specialized SomaFM track retriever
                    p_log("DEBUG", f"Using SomaFM track retriever for {self.current_station}")
                    display_title = somaretriever.get_somafm_track_info(self.current_station)
            
                # If we couldn't get info from SomaFM API or it's not a SomaFM station,
                # fall back to VLC metadata
                if not display_title:
                    media = self.player.get_media()
                    if not media:
                        time.sleep(2)
                        continue

                    title = media.get_meta(vlc.Meta.Title)
                    now_playing = media.get_meta(vlc.Meta.NowPlaying)
                    display_title = now_playing or title or ""
            
                normalized_title = display_title.strip().lower()

                if not normalized_title:
                    time.sleep(5)
                    continue

                current_time = time.time()
                if normalized_title != last_title and (current_time - last_event_time > 5):
                    last_title = normalized_title
                    last_event_time = current_time
                    event = RadioChangedEvent(station=self.current_station, title=display_title)
                    p_log("INFO", f"Track changed -> {display_title}")
                    helper.put_incoming_event(event)

                time.sleep(10)

            except Exception as e:
                p_log("ERROR", f"Track monitor error: {e}")
                time.sleep(10)