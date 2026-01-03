# Radio Plugin v4.0.2
# Release Notes:
# -------------------
# Added new radio stations: Enigmatic Station 1, Seven Rays, Ambient Radio UK, Echoes of BlueMars
# Centralized station URL retrieval in get_retriever_for_station method
# RadioPlugin v4.0.1
# Release Notes:
# -------------------  
# Volume Persistence Improvement
# - The plugin now remembers the last set volume level across station changes and restarts.
# - Corrected volume retrieval timing to ensure accurate volume setting.
# -------------------
# RadioPlugin v4.0.0
# Covas:NEXT Internet Radio Plugin with DJ-style track announcements
# - Added new radio stations: Distant Radio 33.05, Pulsar FM, DR Hotline
# - Added new track retriever for generic MP3 streams, when metadata is not readable directly from VLC
# - Removed dj_radio_response_style setting to adhere to what Rude told me: don't mess with event dispatching. The plugin just dispatches events, Covas decides how to respond.
#   If users wants DJ style, they can set it in Covas Character Prompt.
# - Added enable_announcements action to toggle announcements on/off via actions
# Pydantic BaseModel for action parameters
# Refactored action methods to use Pydantic models
# Commented out radio_status action to streamline code
# -------------------
# Release 3.3.3 - Dec 2025
# Removed unused radio_status action to streamline code
# Fixed minor bug in stop_radio action definition type object with empty parameters
# -------------------

import vlc
import threading
import time
import unicodedata
from . import somafm_track_retriever as somaretriever
from . import hutton_orbital_track_retriever as huttonretriever
from . import deejay_track_retriever as deejayretriever
from . import mp3_stream_track_retriever as mp3streamretriever
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Callable, Optional
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper, PluginEvent
from lib.Event import Event
from lib.Logger import log
from lib.PluginSettingDefinitions import (
    PluginSettings, SettingsGrid, SelectOption, TextAreaSetting, TextSetting,
    SelectSetting, NumericalSetting, ToggleSetting, ParagraphSetting
)
from pydantic.main import BaseModel

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
PLUGIN_LOG_LEVEL = "INFO"
_LEVELS = {"DEBUG": 10, "INFO": 20, "ERROR": 40}
DEFAULT_VOLUME = 55
ENABLED = True


# Monitoring intervals
LAZY_INTERVAL_STANDARD = 90  # seconds for lazy mode (standard stations)
LAZY_INTERVAL_SPECIAL = 100  # seconds for lazy mode (SomaFM/Hutton)
ACTIVE_INTERVAL_STANDARD = 15  # seconds for active mode (standard stations)
ACTIVE_INTERVAL_SPECIAL = 20 # seconds for active mode (SomaFM/Hutton)
COMMAND_RESPONSE_DELAY = 10  # seconds to wait after command before announcing
MIN_EVENT_INTERVAL = 5  # minimum seconds between track announcements
GRACE_PERIOD = 1.5  # seconds for projection update grace period
MIN_TITLE_LENGTH = 3  # minimum length for valid titles

# ---------------------------------------------------------------------
# Pydantic models for action parameters
# ---------------------------------------------------------------------

class PlayRadioParameters(BaseModel):
    station: str

class ChangeRadioParameters(BaseModel):
    station: str

class SetVolumeParameters(BaseModel):
    volume: int

class StopRadioParameters(BaseModel):
    pass

class EnableAnnouncementsParameters(BaseModel):
    enable: bool
# ---------------------------------------------------------------------
# Pre-installed radio stations
# ---------------------------------------------------------------------
RADIO_STATIONS = {
    "Radio Sidewinder": {
        "url": "https://radiosidewinder.out.airtime.pro:8000/radiosidewinder_b",
        "description": "Fan-made station for Elite Dangerous with ambient and techno music, in-game news and ads.",
        "type": "standard"
    },
    "Hutton Orbital Radio": {
        "url": "https://quincy.torontocast.com/hutton",
        "description": "Community radio for Elite Dangerous with pop, rock, and humorous segments.",
        "type": "Icy"
    },
    "SomaFM Deep Space One": {
        "url": "https://ice.somafm.com/deepspaceone",
        "description": "Experimental ambient and electronic soundscapes for deep space exploration.",
        "type": "Soma"
    },
    "SomaFM Groove Salad": {
        "url": "https://ice.somafm.com/groovesalad",
        "description": "Downtempo and chillout mix, perfect for relaxing flight time.",
        "type": "Soma"
    },
    "SomaFM Space Station": {
        "url": "https://ice.somafm.com/spacestation",
        "description": "Futuristic electronica, ambient, and experimental tunes.",
        "type": "Soma"
    },
    "SomaFM Secret Agent": {
        "url": "https://ice.somafm.com/secretagent",
        "description": "Spy-themed lounge and downtempo music for covert operations.",
        "type": "Soma"
    },
    "SomaFM Defcon": {
        "url": "https://ice.somafm.com/defcon",
        "description": "Dark ambient and industrial music for intense situations.",
        "type": "Soma"
    },
    "SomaFM Lush": {
        "url": "https://ice.somafm.com/lush",
        "description": "Ambient and ethereal soundscapes for serene journeys.",
        "type": "Soma"
    },
    "SomaFM Synphaera": {
        "url": "https://ice.somafm.com/synphaera",
        "description": "Cinematic and ambient music for epic space adventures.",
        "type": "Soma"
    },
    "GalNET Radio": {
        "url": "http://listen.radionomy.com/galnet",
        "description": "Sci-fi themed station with ambient, rock, and classical music, plus GalNet news.",
        "type": "standard"
    },
    "BigFM": {
        "url": "https://streams.bigfm.de/bigfm-deutschland-128-mp3",
        "description": "Popular German hits and chart-toppers for energetic flights.",
        "type": "standard"
    },
    "Radio Capital": {
        "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/CAPITAL.mp3",
        "description": "Italian hits and contemporary music for lively journeys.",
        "type": "standard"
    },
    "Radio DeeJay": {   
        "url": "https://streamcdnm15-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiodeejay/radiodeejay/master_ma.m3u8",
        "description": "Italian talk-show station with a mix of pop, dance, and rock music.",
        "type": "DeeJay"
    },
    "Radio DeeJay Linetti": {
        "url": "https://streamcdnm3-4c4b867c89244861ac216426883d1ad0.msvdn.net/webradio/deejaywfmlinus/live.m3u8",
        "description": "Italian station featuring DJ Linus preferred songs from '80 to today.",
        "type": "DeeJay"
    },
    "Kohina Radio": {
        "url": "https://player.kohina.com/icecast/stream.opus",
        "description": "Hand picked chip tunes from classic computers and consoles. SID, Amiga, Atari ST, Arcade, PC, and more!",
        "type": "standard"
    },
    "Radio CVGM": {
        "url": "http://radio.cvgm.net:8000/cvgm128",
        "description": "Video game music station featuring soundtracks from classic and modern games, demo scene and computer music.",
        "type": "standard"
    },
    "Nectarine Demoscene Radio": {
        "url": "http://necta.burn.net:8000/nectarine",
        "description": "Demoscene music station playing tracks from the demoscene community.",
        "type": "standard"
    },
    "Radio Ericade": {
        "url": "http://legacy.ericade.net:8000/stream/1/",
        "description": "Computer and demoscene music.",
        "type": "standard"
    },
    "Distant Radio 33.05": {
        "url": "https://radio.distantworlds3.space/listen/distant_radio/distantradio.mp3",
        "description": "Interstellar soundwaves through space!\nTunes so good even the vacuum can't stop the beat.",
        "type": "Icy"
    },
    "Pulsar FM": {
        "url": "https://radio.distantworlds3.space/listen/pulsarfm/pulsarfm.mp3",
        "description": "Why are we here? Why are you here?\nClassic trance, trance classics pulsing across the galaxy",
        "type": "Icy"
    },
    "DR Hotline": {
        "url": "https://radio.distantworlds3.space/listen/hotline/hotline.mp3",
        "description": "For the blacklight dwellers.\nEverything is Synthetic",
        "type": "Icy"
    },
    "Enigmatic Station 1": {
        "url": "https://myradio24.org/8226",
        "description": "Ambient and downtempo music for mysterious space journeys.",
        "type": "Icy"
    },
    "Seven Rays": {
        "url": "http://7rays.stream.laut.fm/7rays",
        "description": "Chillout and ambient tunes for relaxing space travel.",
        "type": "standard"
    },
    "Ambient Radio UK": {
        "url": "http://uk2.internet-radio.com:31491/",
        "description": "Ambient music station for serene space exploration.",
        "type": "standard"
    },
    "Echoes of BlueMars": {
        "url": "http://streams.echoesofbluemars.org/bluemars.m3u",
        "description": "Ambient and experimental music for deep space exploration.",
        "type": "standard"
    }
}
TRACK_RETRIEVERS = {
    "Soma": somaretriever.get_somafm_track_info,
    "Icy": mp3streamretriever.get_track_info,
    "DeeJay": deejayretriever.get_deejay_track_info,
    "standard": lambda url: None  # Standard stations rely on VLC metadata
}
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
# Track monitoring state class
# ---------------------------------------------------------------------
@dataclass
class MonitorState:
    """Encapsulates the state of the track monitor."""
    current_station: Optional[str] = None
    last_title: str = ""
    last_normalized_title: str = ""
    last_event_time: float = 0
    last_check_time: float = 0
    command_triggered: bool = False
    
    # Lazy/active monitoring state
    is_lazy_mode: bool = True
    checks_without_change: int = 0
    prev_check_title: Optional[str] = None
    
    # Intervals based on station type
    lazy_interval: int = LAZY_INTERVAL_STANDARD
    active_interval: int = ACTIVE_INTERVAL_STANDARD
    
    # Title repeat tracking
    title_repeat_count: dict = field(default_factory=dict)
    
    @property
    def current_interval(self) -> int:
        """Get the current check interval based on monitoring mode."""
        return self.lazy_interval if self.is_lazy_mode else self.active_interval
    
    def update_intervals_for_station(self, station_name: str) -> None:
        """Update intervals based on station type."""
        is_special = RadioPlugin.is_special_station(station_name)
        self.lazy_interval = LAZY_INTERVAL_SPECIAL if is_special else LAZY_INTERVAL_STANDARD
        self.active_interval = ACTIVE_INTERVAL_SPECIAL if is_special else ACTIVE_INTERVAL_STANDARD
        p_log("DEBUG", f"Updated intervals for {station_name}: lazy={self.lazy_interval}s, active={self.active_interval}s")
    
    def reset_for_station_change(self, new_station: str) -> None:
        """Reset monitoring state when station changes."""
        self.current_station = new_station
        self.last_title = ""
        self.last_normalized_title = ""
        self.last_event_time = 0
        self.last_check_time = 0
        self.is_lazy_mode = True
        self.checks_without_change = 0
        self.prev_check_title = None
        self.update_intervals_for_station(new_station)
        p_log("INFO", f"Monitor state reset for station change to {new_station}")
# ---------------------------------------------------------------------
# Main plugin class
# ---------------------------------------------------------------------
class RadioPlugin(PluginBase):
    """Main Radio Plugin for Covas:NEXT."""
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self.current_station = None
        self.player = None
        self.playing = False
        self.track_monitor_thread = None
        self.monitor_state = MonitorState()
        self.stop_monitor = threading.Event()
        self._last_replied_title = None
        self._last_replied_station = None
        self._last_reply_time = 0
        self.helper = None
        self._title_repeat_count = {}
        
        # In-memory state to replace projection
        self._radio_state = {
            "current_station": None,
            "current_title": None,
            "last_updated": 0.0,
            "command_triggered": False
        }
        p_log("DEBUG", f"_radio_state initialized: {self._radio_state}")
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
                        NumericalSetting(
                            key="default_volume",
                            label="Default Volume",
                            type="number",
                            default_value=DEFAULT_VOLUME,
                            min_value=0,
                            max_value=100,
                            step=1
                        ),
                        ToggleSetting(
                            key="enable_radio_plugin",
                            label="Enable Radio Plugin Announcements",
                            type="toggle",
                            default_value=ENABLED
                        ),
                        ParagraphSetting(
                            key="available_stations",
                            label="Available Stations",
                            type="paragraph",
                            readonly=True,
                            content=self._generate_stations_html()
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

    def on_chat_start(self, helper: PluginHelper):
        """Initialize plugin when chat starts."""
        # Register actions
        self.helper = helper
        self.register_actions(helper)
        
        p_log("DEBUG", "Reply check function registered successfully")
        # Register the radio_changed event
        helper.register_event(
            name="radio_changed",
            should_reply_check=lambda event: self._should_reply_to_radio_event(event),
            prompt_generator=lambda event: self._generate_radio_prompt(event)
        )
        
        p_log("INFO", "RadioPlugin initialized successfully")

    # -----------------------------------------------------------------
    # Station type detection
    # -----------------------------------------------------------------
    @staticmethod
    @staticmethod
    def is_special_station(station_name: str) -> bool:
        """Check if a station requires special handling."""
        special_types = {"Soma", "Icy", "DeeJay"}
        station = RADIO_STATIONS.get(station_name)
        if not station:
            return False
        return station.get("type") in special_types

    
    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize a track title for consistent comparison."""
        if not title:
            return ""
        try:
            return unicodedata.normalize('NFKC', title.strip()).casefold()
        except Exception:
            return title.strip().lower()
    # -----------------------------------------------------------------
    # Event handling
    # -----------------------------------------------------------------
    def _should_reply_to_radio_event(self, event: PluginEvent) -> bool:
        """Decide whether Covas should reply to a radio track change."""
        try:
            content = event.plugin_event_content
            title = content[0]
            station = content[1]
            command_triggered = content[2] if len(content) > 2 else False
            event_time = content[3] if len(content) > 3 else time.time()
        except (ValueError, TypeError):
            p_log("ERROR", f"Invalid plugin_event_content format: {event.plugin_event_content}")
            return False
        # Skip if plugin announcements are disabled
        if not self.settings.get('enable_radio_plugin', ENABLED):
            p_log("DEBUG", "Radio plugin announcements are disabled in settings.")
            return False
        # Skip empty or invalid titles
        if not title or "unknown" in title.lower() or len(title.strip()) < MIN_TITLE_LENGTH:
            p_log("DEBUG", "Ignoring empty or invalid title")
            return False
    
        normalized_title = self.normalize_title(title)
        last_title_norm = self.normalize_title(self._last_replied_title or "")
        last_station = self._last_replied_station
        current_time = time.time()
    
        # Create a unique key for the title+station combo
        track_key = f"{normalized_title}|{station}"
    
        # Always allow command-triggered events
        if command_triggered:
            p_log("DEBUG", f"Command triggered event, allowing reply for '{title}' on {station}")
        
            # Update memory for future comparisons
            self._last_replied_title = title
            self._last_replied_station = station
            self._last_reply_time = current_time
        
            # Reset counter for command-triggered events
            self._title_repeat_count[track_key] = 0
        
            return True
    
        # If same station and same title as last replied, suppress automatic announcements
        if normalized_title == last_title_norm and station == last_station:
            p_log("DEBUG", f"Same title on same station and unchanged; suppressing announcement.")
            return False
    
        # For new titles or different stations, manage repeat counters
        # Increment counter
        self._title_repeat_count[track_key] = self._title_repeat_count.get(track_key, 0) + 1
        if self._title_repeat_count[track_key] > 1:
            p_log("DEBUG", f"Same title repeated {self._title_repeat_count[track_key]} times, ignoring")
            return False
        else:
            p_log("DEBUG", f"First occurrence of '{title}' after cooldown, allowing reply.")
    
        # Update memory for future comparisons
        self._last_replied_title = title
        self._last_replied_station = station
        self._last_reply_time = current_time
    
        p_log("DEBUG", f"Will reply to '{title}' on {station}")
        return True
    
    def _generate_radio_prompt(self, event: PluginEvent) -> str:
        """Generate prompt for radio track change events."""
        try:
            content = event.plugin_event_content
            if isinstance(content, list) and len(content) >= 2:
                title = content[0]
                station = content[1]
            else:
                raise ValueError(f"Expected list with at least 2 elements, got: {content}")
        except (ValueError, TypeError) as e:
            p_log("ERROR", f"Invalid plugin_event_content format in prompt generator: {event.plugin_event_content}")
            return "React to this radio track change. The track information could not be retrieved."
        
        prompt = f"React to this radio track change. New track: '{title}' on station '{station}'."
        p_log("DEBUG", f"Generated radio prompt: {prompt}")
        return prompt
    # -----------------------------------------------------------------
    # Action registration
    # -----------------------------------------------------------------
    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            name="play_radio",
            description=f"Play a webradio station, available stations: {', '.join(RADIO_STATIONS.keys())}",
            parameters=PlayRadioParameters,
            method=self.play_radio_action,
            action_type="global"
        )
        helper.register_action(
            name="stop_radio",
            description="Stop the radio",
            parameters=StopRadioParameters,
            method=self.stop_radio_action,
            action_type="global"
        )
        helper.register_action(
            name="change_radio",
            description="Change to another station",
            parameters=ChangeRadioParameters,
            method=self.change_radio_action,
            action_type="global"
        )
        helper.register_action(
            name="set_volume",
            description="Set the radio volume",
            parameters=SetVolumeParameters,
            method=self.set_volume_action,
            action_type="global"
        )
        helper.register_action(
            name="enable_announcements",
            description="Enable or disable radio announcements",
            parameters=EnableAnnouncementsParameters,
            method=self.enable_announcements_action,
            action_type="global"
        )
    # -----------------------------------------------------------------
    # Define track retriever based on station type
    # -----------------------------------------------------------------
    def get_retriever_for_station(self, station_name: str):
        station = RADIO_STATIONS.get(station_name)
        if not station:
            return None

        station_type = station.get("type", "standard")
        return TRACK_RETRIEVERS.get(station_type)
    # -----------------------------------------------------------------
    # Action methods
    # -----------------------------------------------------------------
    def play_radio_action(self, model: PlayRadioParameters, context: dict) -> str:
        station_name = model.station
        station_info = RADIO_STATIONS.get(station_name)
        if not station_info:
            return f"Station {station_name} not found."
        url = station_info['url']
        return self._start_radio(url, station_name, self.helper)
    def change_radio_action(self, model: ChangeRadioParameters, context: dict) -> str:
        station_name = model.station
        station_info = RADIO_STATIONS.get(station_name)
        if not station_info:
            return f"Station {station_name} not found."
        url = station_info['url']
        return self._start_radio(url, station_name, self.helper)
    def set_volume_action(self, model: SetVolumeParameters, context: dict) -> str:
        volume = model.volume
        return self._set_volume(volume)
    def stop_radio_action(self, model: StopRadioParameters, context: dict) -> str:
        return self._stop_radio()
    def enable_announcements_action(self, model: EnableAnnouncementsParameters, context: dict) -> str:
        enable = model.enable
        self.settings['enable_radio_plugin'] = enable
        status = "enabled" if enable else "disabled"
        #Start or stop the monitor thread based on new setting
        if enable and self.playing and (not self.track_monitor_thread or not self.track_monitor_thread.is_alive()):
            self.stop_monitor.clear()  # Reset the stop event
            self.track_monitor_thread = threading.Thread(
                target=self._monitor_track_changes, 
                args=(self.helper,),
                daemon=True  # Make thread daemon so it exits when main thread exits
            )
            self.track_monitor_thread.start()
            p_log("INFO", "Radio plugin announcements enabled; starting track monitor.")
        elif not enable:
            self.stop_monitor.set()  # Signal the monitor thread to stop
            p_log("INFO", "Radio plugin announcements disabled; stopping track monitor.")
        p_log("INFO", f"Radio plugin announcements have been {status} via action.")
        return f"Radio plugin announcements have been {status}."
    # -----------------------------------------------------------------
    # Player control
    # -----------------------------------------------------------------
    def on_chat_stop(self, helper: PluginHelper):
        if self.playing:
            p_log("INFO", "Covas:NEXT stopped. Stopping radio playback.")
            self._stop_radio()

    def _start_radio(self, url, station_name, helper: PluginHelper):
        # Ensure proper cleanup of previous radio session
        self._stop_radio()

        if not url:
            p_log("ERROR", f"URL for station {station_name} not found.")
            return f"URL for station {station_name} not found."
    
        try:
            # Wait a moment to ensure previous thread is fully terminated
            time.sleep(0.5)
    
            self.player = vlc.MediaPlayer(url)
            self.player.play()
#            default_volume = self.settings.get('default_volume', DEFAULT_VOLUME)
#            self.player.audio_set_volume(default_volume)
            # Set volume to default if self.volume is not set
            volume = getattr(self, 'volume', self.settings.get('default_volume', DEFAULT_VOLUME))
            self.player.audio_set_volume(volume)
            self.current_station = station_name
            self.playing = True
            self.stop_monitor.clear()  # Reset the stop event
            # Reset title repeat count for new station
            self._title_repeat_count = {}
            # Ensure command_triggered is set to True for both new plays and station changes
            self.monitor_state.command_triggered = True
            self.monitor_state.reset_for_station_change(station_name)
            self._radio_state = {
                    "current_station": station_name,
                    "current_title": None,
                    "last_updated": 0.0,
                    "command_triggered": True
                }
            # Create and start a new monitor thread if not already running
            if not self.enable_announcements_action or not self.settings.get('enable_radio_plugin', ENABLED):
                p_log("INFO", "Radio plugin announcements are disabled; not starting track monitor.")
            else:
                if not self.track_monitor_thread or not self.track_monitor_thread.is_alive():
                    self.track_monitor_thread = threading.Thread(
                        target=self._monitor_track_changes, 
                        args=(helper,),
                        daemon=True  # Make thread daemon so it exits when main thread exits
                    )
                    self.track_monitor_thread.start()
    
            p_log("INFO", f"Started playing {station_name} at volume {volume}")
            return f"Playing {station_name}."
        except Exception as e:
            p_log("ERROR", f"Failed to start radio: {e}")
            return f"Error starting radio: {e}"
    def _stop_radio(self):
        try:
            # Set flag to stop monitoring thread
            self.stop_monitor.set()
        
            # Stop player if it exists
            if self.player:
                self.player.stop()
                self.player = None
            
            self.playing = False
            self.current_station = None
            self.monitor_state.command_triggered = False
            
            # Clear in-memory state
            self._radio_state ={
                "current_station": None,
                "current_title": None,
                "last_updated": 0.0,
                "command_triggered": False
            }
            # Reset title repeat count
            self._title_repeat_count = {}
            # Wait for thread to terminate with timeout
            if self.track_monitor_thread and self.track_monitor_thread.is_alive():
                self.track_monitor_thread.join(timeout=2)
            
            p_log("INFO", "Stopped radio")
            return "Radio stopped."
        except Exception as e:
            p_log("ERROR", f"Error stopping radio: {e}")
            return f"Error stopping radio: {e}"

    def _set_volume(self, volume: int):
        """Set the playback volume safely, even during stream startup."""
        try:
            if not self.player:
                p_log("ERROR", "No active player to set volume.")
                return "No active player to set volume."

            volume = max(0, min(100, int(volume)))
            result = self.player.audio_set_volume(volume)

            if result == -1:
                time.sleep(0.5)
                result = self.player.audio_set_volume(volume)

            if result == -1:
                p_log("ERROR", "VLC refused volume change (player not ready).")
                return "Unable to set volume right now."
            # Wait a moment to ensure volume is applied
            time.sleep(0.2)
            actual = self.player.audio_get_volume()
            
            # Store volume in instance for future use
            self.volume = actual
            p_log("INFO", f"Volume set to {actual} (requested {volume})")
            return f"Volume set to {actual}"

        except Exception as e:
            p_log("ERROR", f"Error setting volume: {e}")
            return f"Error setting volume: {e}"
    # -----------------------------------------------------------------
    # Track monitoring
    # -----------------------------------------------------------------
    def _monitor_track_changes(self, helper: PluginHelper):
        """Monitor VLC metadata and trigger an event when the track changes."""
        state = self.monitor_state
    
        # If a command just triggered the play or change, wait before the monitor starts announcing tracks
        if state.command_triggered:
            p_log("DEBUG", f"Delaying initial check by {COMMAND_RESPONSE_DELAY} seconds to allow AI response to command")
            for _ in range(COMMAND_RESPONSE_DELAY):
                if self.stop_monitor.is_set():
                    return
                time.sleep(1)
#            state.command_triggered = False # Moved to after first announcement to ensure it's honored
    
        # Initialize state for the current station
        state.reset_for_station_change(self.current_station)
    
        p_log("INFO", f"Track monitor started for {state.current_station}. Lazy mode active with interval {state.lazy_interval}s")
         
        # Main monitoring loop
        while not self.stop_monitor.is_set():
            try:
                if not self.player or self.stop_monitor.is_set():
                    time.sleep(1)  # Check more frequently if we should stop
                    continue
                
                current_time = time.time()
                # Get current check interval based on monitoring mode
                check_interval = state.current_interval
                
                # Skip if not enough time has passed since last check
                if current_time - state.last_check_time < check_interval:
                    time.sleep(1)
                    continue
                
                state.last_check_time = current_time
                
                # Check if station changed
                if self.current_station != state.current_station:
                    p_log("INFO", f"Station changed from {state.current_station} -> {self.current_station}, resetting monitor state")
                    state.reset_for_station_change(self.current_station)
                
                # Get track info based on station type
                display_title = self._get_track_info(state.current_station)
                
                if not display_title:
                    time.sleep(1)
                    continue
                
                # Normalize title for comparison
                normalized_title = self.normalize_title(display_title)
                
                # Process the track based on monitoring mode
                self._process_track_update(helper, state, display_title, normalized_title)
                
                # Sleep for the appropriate interval
                time.sleep(check_interval)
                
            except Exception as e:
                p_log("ERROR", f"Track monitor error: {e}")
                time.sleep(5)
        
        p_log("INFO", f"Track monitor stopped for {state.current_station}.")
        
    def _get_track_info(self, station_name: str) -> str:
        """Get the current track info based on station type with fallback to VLC metadata."""
        if not station_name:
            return ""

        station = RADIO_STATIONS.get(station_name)
        if not station:
            return ""

        station_type = station.get("type", "standard")
        url = station.get("url", "")

        # 1) Recupera il retriever dalla mappa
        retriever = TRACK_RETRIEVERS.get(station_type)
        title = None

        # 2) Se esiste un retriever, provalo
        if retriever:
            try:
                p_log("DEBUG", f"Using {station_type} retriever for {station_name}")
                title = retriever(url)
            except Exception as e:
                p_log("ERROR", f"Retriever for {station_name} failed: {e}")
                title = None

        # 3) Fallback VLC se:
        #    - retriever = None (standard)
        #    - retriever ha fallito
        #    - retriever ha restituito None o stringa vuota
        if not title:
            try:
                if not self.player:
                    return ""

                media = self.player.get_media()
                if not media:
                    return ""

                title = media.get_meta(vlc.Meta.NowPlaying) or media.get_meta(vlc.Meta.Title)
                return title or ""
            except Exception as e:
                p_log("ERROR", f"Error getting VLC metadata: {e}")
                return ""
        return title

    
    def _process_track_update(self, helper: PluginHelper, state: MonitorState, display_title: str, normalized_title: str):
        """Process a track update based on the current monitoring mode."""
        current_time = time.time()
        command_triggered = state.command_triggered
    
        # In lazy mode: check if title changed from previous check
        if state.is_lazy_mode:
            # First check in lazy mode - store the title and always announce
            if state.prev_check_title is None:
                state.prev_check_title = normalized_title
                p_log("DEBUG", f"First lazy check: stored baseline '{normalized_title}'")
            
                # Always announce the track on first check (like in original code)
                self._announce_track(helper, display_title, state.current_station, command_triggered)
                state.command_triggered = False
                state.last_title = normalized_title
                state.last_event_time = current_time
                return
            
            # Compare with previous check
            if normalized_title != state.prev_check_title:
                # Title changed - announce and reset counter
                p_log("DEBUG", f"Title changed in lazy mode: '{state.prev_check_title}' -> '{normalized_title}'")
                self._announce_track(helper, display_title, state.current_station, command_triggered)
                state.prev_check_title = normalized_title
                state.last_title = normalized_title
                state.last_event_time = current_time
                state.checks_without_change = 0
                state.command_triggered = False
            else:
                # Title unchanged - increment counter
                state.checks_without_change += 1
                p_log("DEBUG", f"Title unchanged in lazy mode ({state.checks_without_change} checks)")
                
                # After two unchanged checks, switch to active mode
                if state.checks_without_change >= 2:
                    state.is_lazy_mode = False
                    p_log("DEBUG", f"Switching to active mode (interval: {state.active_interval}s)")
        
        # In active mode: check if title changed from last announced title
        else:
            # If title changed from last announced, announce and switch back to lazy mode
            if normalized_title != state.last_title or command_triggered:
                p_log("DEBUG", f"Title changed in active mode: '{state.last_title}' -> '{normalized_title}'")
                self._announce_track(helper, display_title, state.current_station, command_triggered)
                state.last_title = normalized_title
                state.last_event_time = current_time
                state.command_triggered = False
                
                # Switch back to lazy mode
                state.is_lazy_mode = True
                state.checks_without_change = 0
                state.prev_check_title = normalized_title
                p_log("DEBUG", f"Switching back to lazy mode (interval: {state.lazy_interval}s)")
    
    def _announce_track(self, helper: PluginHelper, title: str, station: str, command_triggered: bool):
        """Announce a track change by dispatching an event."""
        try:
            if not title or len(title.strip()) < MIN_TITLE_LENGTH:
                p_log("DEBUG", f"Not announcing invalid title: '{title}'")
                return
            
            p_log("INFO", f"Announcing track: '{title}' on {station} (command triggered: {command_triggered})")
        
            # Create and dispatch the event
            event = PluginEvent(
                kind="plugin",
                plugin_event_name="radio_changed",
                plugin_event_content=[title, station, command_triggered, time.time()]
            )
        
            # Clear the state to ensure the event is processed
            self._radio_state = {
                "current_station": None,
                "current_title": None,
                "last_updated": 0.0,
                "command_triggered": False
            }
        
            # Dispatch the event
            helper.dispatch_event(event)
        
            # Wait a short time to ensure event processing starts
            time.sleep(0.5)
        
            # Now update the state
            self._radio_state.update({
                "current_station": station,
                "current_title": title,
                "last_updated": time.time(),
                "command_triggered": command_triggered
            })
        
            p_log("DEBUG", f"Event dispatched successfully. Updated _radio_state: {self._radio_state}")
        except Exception as e:
            p_log("ERROR", f"Error announcing track: {e}")