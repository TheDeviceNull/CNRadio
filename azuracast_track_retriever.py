"""
AzuraCast Track Retriever Module
--------------------------------
Retriever for radio stations hosted on AzuraCast (e.g. Distant Radio, Pulsar FM, DR Hotline).
Fetches current playing track metadata via AzuraCast REST API with caching.
"""

import requests
import time
from typing import Dict, Tuple, Optional

# Endpoint URL for AzuraCast nowplaying API
AZURACAST_NOWPLAYING_URL = "https://radio.distantworlds3.space/api/nowplaying"

# Caches
_track_cache: Dict[str, Tuple[str, float]] = {}
_api_response_cache: Optional[Tuple[list, float]] = None

# Expiration times in seconds
_TRACK_CACHE_EXPIRY = 15  # 15 seconds per station
_API_CACHE_EXPIRY = 10    # 10 seconds for global API call


def get_azuracast_track_info(url_or_station_name: str) -> str:
    """
    Get track info for an AzuraCast station given its stream URL or station name/shortcode.
    
    Args:
        url_or_station_name: Stream URL (e.g. "https://radio.distantworlds3.space/listen/distant_radio/distantradio.mp3")
                             or shortcode (e.g. "distant_radio").
                             
    Returns:
        String formatted as "Artist - Title" or empty string if unavailable.
    """
    shortcode = _extract_shortcode(url_or_station_name)
    if not shortcode:
        return ""

    # Check station-specific cache
    current_time = time.time()
    if shortcode in _track_cache:
        cached_info, timestamp = _track_cache[shortcode]
        if current_time - timestamp < _TRACK_CACHE_EXPIRY:
            return cached_info

    # Fetch data from API
    nowplaying_data = _fetch_nowplaying_data()
    if not nowplaying_data:
        return ""

    # Look for matching station in API response
    track_info = ""
    for entry in nowplaying_data:
        station = entry.get("station", {})
        if station.get("shortcode") == shortcode or station.get("name", "").lower() == shortcode.lower():
            song = entry.get("now_playing", {}).get("song", {})
            title = song.get("title", "").strip()
            artist = song.get("artist", "").strip()
            
            if artist and title:
                track_info = f"{artist} - {title}"
            elif title:
                track_info = title
            elif artist:
                track_info = artist
            break

    # Cache result
    _track_cache[shortcode] = (track_info, current_time)
    return track_info


def _extract_shortcode(input_str: str) -> str:
    """Extract shortcode from stream URL or return normalized string."""
    if not input_str:
        return ""

    # If full URL like https://radio.distantworlds3.space/listen/distant_radio/distantradio.mp3
    if "/listen/" in input_str:
        parts = input_str.split("/listen/")
        if len(parts) > 1:
            shortcode = parts[1].split("/")[0]
            return shortcode

    # If station display name or already shortcode
    clean = input_str.lower().replace(" ", "")
    if "distantradio" in clean or "distant_radio" in clean:
        return "distant_radio"
    if "pulsarfm" in clean or "pulsar" in clean:
        return "pulsarfm"
    if "hotline" in clean:
        return "hotline"

    return input_str.strip()


def _fetch_nowplaying_data() -> Optional[list]:
    """Fetch all stations' nowplaying data from AzuraCast API with caching and SSL verify fallback."""
    global _api_response_cache

    current_time = time.time()
    if _api_response_cache:
        data, timestamp = _api_response_cache
        if current_time - timestamp < _API_CACHE_EXPIRY:
            return data

    try:
        # Try normal SSL verification first
        response = requests.get(AZURACAST_NOWPLAYING_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            _api_response_cache = (data, current_time)
            return data
    except requests.exceptions.SSLError:
        # SSL certificate verify error fallback
        try:
            response = requests.get(AZURACAST_NOWPLAYING_URL, verify=False, timeout=5)
            if response.status_code == 200:
                data = response.json()
                _api_response_cache = (data, current_time)
                return data
        except Exception:
            pass
    except Exception:
        pass

    return None
