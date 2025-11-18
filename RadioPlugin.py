# RadioPlugin v3.0.2
# -------------------
# Major update for Covas:NEXT compatibility
# - Refactored to use new PluginBase and PluginHelper APIs
# - Converted RadioChangedEvent to PluginEvent
# - Implemented new event registration system
# - Improved thread management and error handling
# - Enhanced track change detection for SomaFM stations
# - Added more robust volume control
# Updated to use new event system
# - Removed custom RadioChangedEvent class
# - Using PluginEvent from lib.PluginHelper
# - Simplified event handling

import vlc
import threading
import time
from . import somafm_track_retriever as somaretriever
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Callable
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper, PluginEvent
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
    "SomaFM Defcon": {
        "url": "https://ice.somafm.com/defcon",
        "description": "Dark ambient and industrial music for intense situations."
    },
    "SomaFM Lush": {
        "url": "https://ice.somafm.com/lush",
        "description": "Ambient and ethereal soundscapes for serene journeys."
    },
    "SomaFM Synphaera": {
        "url": "https://ice.somafm.com/synphaera",
        "description": "Cinematic and ambient music for epic space adventures."
    },
    "GalNET Radio": {
        "url": "http://listen.radionomy.com/galnet",
        "description": "Sci-fi themed station with ambient, rock, and classical music, plus GalNet news."
    }
}

PLUGIN_LOG_LEVEL = "ERROR"
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

    def on_chat_start(self, helper: PluginHelper):
        """Initialize plugin when chat starts."""
        # Register actions
        self.register_actions(helper)
        
        # Register the radio_changed event
        helper.register_event(
            name="radio_changed",
            should_reply_check=lambda event: self._should_reply_to_radio_event(event),
            prompt_generator=lambda event: self._generate_radio_prompt(event)
        )
        
        p_log("INFO", "RadioPlugin initialized successfully")
    # -----------------------------------------------------------------
    # SomaFM track retrieval
    # -----------------------------------------------------------------
    def is_somafm_station(self, station_name: str) -> bool:
        """Check if a station name refers to a SomaFM station."""
        somafm_identifiers = ["somafm", "soma.fm"]
        somafm_station_names = [
            "deepspaceone", "deep space one", 
            "groovesalad", "groove salad", 
            "spacestation", "space station", 
            "secretagent", "secret agent", 
            "defcon", "lush", "synphaera"
        ]
    
        station_name_lower = station_name.lower()
    
        # Check if it's explicitly marked as SomaFM in the name
        for identifier in somafm_identifiers:
            if identifier in station_name_lower:
                return True
    
        # Check if it's one of the known SomaFM stations
        for somafm_name in somafm_station_names:
            if somafm_name in station_name_lower:
                return True
    
        # Check if it's in our RADIO_STATIONS dictionary and has a SomaFM URL
        if station_name in RADIO_STATIONS:
            url = RADIO_STATIONS[station_name].get("url", "")
            if "somafm.com" in url or "ice.somafm.com" in url:
                return True
    
            return False
    # -----------------------------------------------------------------
    # Event handling
    # -----------------------------------------------------------------
    def _should_reply_to_radio_event(self, event: PluginEvent) -> bool:
        """Decide whether Covas should reply to a radio track change."""
        try:
            content = event.plugin_event_content
            title = content[0]
            station = content[1]
            command_triggered = content[2] if len (content) > 2 else False
            if len(event.plugin_event_content) > 2:
                command_triggered = event.plugin_event_content[2]
        except (ValueError, TypeError):
            p_log("ERROR", f"Invalid plugin_event_content format: {event.plugin_event_content}")
            return False
        # Skip empty or invalid titles
        if not title or "unknown" in title.lower() or len(title.strip()) <3 :
            p_log("DEBUG", f"Ignoring empty or invalid title")
            return False
        
        normalized_title = title.strip().lower()
        last_title_norm = (self._last_replied_title or "").strip().lower()
        last_station = getattr(self, "_last_replied_station", None)
        current_time = time.time()
        # Initialize repeat counter if doesn't exists
        if not hasattr(self, "_title_repeat_count"):
            self._title_repeat_count ={}
        
        # Create a unque key for the title+station combo
        track_key = f"{normalized_title}|{station}"

        # If same station and same title recently, skip
        if normalized_title == last_title_norm and station == last_station:
            if current_time - self._last_reply_time < 45:  # 45s cooldown for same song
                p_log("DEBUG", f"Duplicate '{title}' on same station ignored (within 45s).")
                return False
            else:
                p_log("DEBUG", f"Same title on same station but cooldown passed, checking trigger.")
        # If cooldown passed but not triggered by a command with counter > 0, ignore
        if not command_triggered:
            #Counter +1
            self._title_repeat_count[track_key] = self._title_repeat_count.get(track_key, 0) + 1
            if self._title_repeat_count[track_key] > 1:
                p_log("DEBUG", f"Same title repeated {self._title_repeat_count[track_key]} times, ignoring")
                return False
            else:
                p_log("DEBUG", f"First repeat of '{title}' after cooldown, allowing reply.")
        else:
            #New title or new station, reset counter
            self._title_repeat_count[track_key] = 0

        # Update memory
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
            return "IMPORTANT: React to this radio track change. The track information could not be retrieved."
        dj_style = self.settings.get('dj_response_style', DEFAULT_DJ_STYLE)
        return f"IMPORTANT: React to this radio track change. New track: '{title}' on station '{station}'. {dj_style}"

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
            default_volume = self.settings.get('default_volume', DEFAULT_VOLUME)
            self.player.audio_set_volume(default_volume)

            self.current_station = station_name
            self.playing = True
            self.stop_monitor = False
            # We had started the radio
            self.command_triggered = True

            # Create and start a new monitor thread
            self.track_monitor_thread = threading.Thread(target=self._monitor_track_changes, args=(helper,))
            self.track_monitor_thread.daemon = True  # Make thread daemon so it exits when main thread exits
            self.track_monitor_thread.start()
        
            p_log("INFO", f"Started playing {station_name} at volume {default_volume}")
            return f"Playing {station_name} at volume {default_volume}"
        except Exception as e:
            p_log("ERROR", f"Failed to start radio: {e}")
            return f"Error starting radio: {e}"

    def _stop_radio(self):
        try:
            # Set flag to stop monitoring thread
            self.stop_monitor = True
        
            # Stop player if it exists
            if self.player:
                self.player.stop()
                self.player = None
            
            self.playing = False
            self.current_station = None
            self.command_triggered = False
        
            # Wait for thread to terminate with timeout
            if self.track_monitor_thread and self.track_monitor_thread.is_alive():
                self.track_monitor_thread.join(timeout=2)
                # Force reference cleanup even if thread didn't terminate properly
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

            actual = self.player.audio_get_volume()
            p_log("INFO", f"Volume set to {actual} (requested {volume})")
            return f"Volume set to {actual}"

        except Exception as e:
            p_log("ERROR", f"Error setting volume: {e}")
            return f"Error setting volume: {e}"

    # -----------------------------------------------------------------
    # Track monitoring
    # -----------------------------------------------------------------
    def _monitor_track_changes(self, helper: PluginHelper):
        """Monitor VLC metadata and trigger an event when the track actually changes."""
        last_title = ""
        last_event_time = 0
        last_check_time = 0
        check_interval = 5
        # Define check intervals
        default_check_interval = 5  # 5 seconds for regular stations
        somafm_check_interval = 20  # Longer interval for SomaFM stations

        command_triggered = getattr(self, "command_triggered", False)
        is_somafm = self.is_somafm_station(self.current_station)
        check_interval = somafm_check_interval if is_somafm else default_check_interval

        p_log("INFO", f"Track monitor started for {self.current_station}.C heck interval: {check_interval}s")
    
        while not self.stop_monitor:
            try:
                if not self.player or self.stop_monitor:
                    time.sleep(1)  # Check more frequently if we should stop
                    continue
                current_time = time.time()
                if current_time - last_check_time < check_interval:
                    time.sleep(1)
                    continue
                last_check_time = current_time

                # Get track info based on station type
                display_title = ""
    
                # Check if this is a SomaFM station
                is_somafm = any(name in self.current_station.lower() for name in ["somafm", "soma.fm", "deepspaceone", "groovesalad", "spacestation", "secretagent"])
    
                if is_somafm:
                    # Use the specialized SomaFM track retriever
                    p_log("DEBUG", f"Using SomaFM track retriever for {self.current_station}")
                    display_title = somaretriever.get_somafm_track_info(self.current_station)
                else:
                    # Use VLC metadata for non-SomaFM stations
                    media = self.player.get_media()
                    if not media:
                        time.sleep(1)
                        continue

                    title = media.get_meta(vlc.Meta.Title)
                    now_playing = media.get_meta(vlc.Meta.NowPlaying)
                    display_title = now_playing or title or ""
    
                normalized_title = display_title.strip().lower()

                if not normalized_title:
                    p_log("DEBUG", f"No title found for {self.current_station}, will check again later")
                    # Check stop flag more frequently
                    for _ in range(5):
                        if self.stop_monitor:
                            break
                        time.sleep(1)
                    continue

                if normalized_title != last_title and (current_time - last_event_time > 5) or command_triggered:
                    p_log("DEBUG", f"New track detected: '{display_title}' (previous: '{last_title}')")
                    last_title = normalized_title
                    last_event_time = current_time
            
                   # Only create event if we're still playing the same station
                    if not self.stop_monitor:
                        try:
                            event = PluginEvent(
                                kind="plugin",
                                plugin_event_name="radio_changed",
                                plugin_event_content=[display_title, self.current_station, command_triggered]
                            )                    
                            p_log("INFO", f"Track changed -> {display_title} (command triggered: {command_triggered})")
                            helper.dispatch_event(event)
                            p_log("DEBUG", "Event dispatched successfully")
                            command_triggered = False
                        except Exception as e:
                            p_log("ERROR", f"Error creating or dispatching event: {e}")
                 # Adaptive sleep based on station type
                sleep_time = 5 if is_somafm else 1
                time.sleep(sleep_time)
            except Exception as e:
                p_log("ERROR", f"Track monitor error: {e}")
                time.sleep(5)
    
        p_log("INFO", f"Track monitor stopped for {self.current_station}.")