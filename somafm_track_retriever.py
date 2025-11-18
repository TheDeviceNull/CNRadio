"""
SomaFM Track Retriever Module - Optimized Version
------------------------------------------------
Specialized module for retrieving current track information from SomaFM stations
using HTTP requests. This module is designed to be used by the RadioPlugin
when a SomaFM station is selected.

Optimized to reduce API calls and improve efficiency.
"""

import requests
import time
import re
from typing import Dict, Optional, Tuple, Any

# Cache to store track information and reduce API calls
_track_cache: Dict[str, Tuple[str, float]] = {}
# Cache for station IDs to avoid repeated extraction
_station_id_cache: Dict[str, str] = {}
# Cache for channels data to avoid repeated API calls
_channels_cache: Dict[str, Any] = {}
_channels_cache_timestamp: float = 0

# Cache expiration times in seconds
_TRACK_CACHE_EXPIRY = 20
_CHANNELS_CACHE_EXPIRY = 300  # 5 minutes


def get_somafm_track_info(station_name: str) -> str:
    """
    Get the current track information for a SomaFM station.
    
    Args:
        station_name: The name of the SomaFM station (e.g., "deepspaceone", "groovesalad")
        
    Returns:
        A string with the current track information or empty string if unavailable
    """
    # Extract station ID from full name if needed
    station_id = _get_station_id(station_name)
    
    # Check cache first
    if station_id in _track_cache:
        cached_info, timestamp = _track_cache[station_id]
        if time.time() - timestamp < _TRACK_CACHE_EXPIRY:
            return cached_info
    
    # Try to get track information using the most efficient method first
    track_info = _get_from_json_api(station_id)
    
    # If that fails, try the channels API (which is cached)
    if not track_info:
        track_info = _get_from_channels_api(station_id)
    
    # Update cache if we got information
    if track_info:
        _track_cache[station_id] = (track_info, time.time())
    else:
        # If we couldn't get any info, cache an empty string to prevent repeated failed attempts
        _track_cache[station_id] = ("", time.time())
        
    return track_info or ""


def _get_station_id(station_name: str) -> str:
    """
    Get the station ID from the station name, using cache when possible.
    """
    # Check if we've already processed this station name
    if station_name in _station_id_cache:
        return _station_id_cache[station_name]
    
    # Extract the station ID using the extraction method
    station_id = _extract_station_id(station_name)
    _station_id_cache[station_name] = station_id
    return station_id


def _extract_station_id(station_name: str) -> str:
    """Extract the station ID from the full station name."""
    # Handle common SomaFM station names
    if "SomaFM" in station_name:
        # Extract the part after "SomaFM " if present
        match = re.search(r'SomaFM\s+(.+)', station_name, re.IGNORECASE)
        if match:
            name_part = match.group(1).lower()
            # Convert spaces to underscores and remove special characters
            return re.sub(r'[^a-z0-9]', '', name_part.replace(' ', ''))
    
    # For URLs, extract the last part
    if "/" in station_name:
        return station_name.split("/")[-1].lower()
    
    # Default: just lowercase and remove spaces/special chars
    return re.sub(r'[^a-z0-9]', '', station_name.lower().replace(' ', ''))


def _get_from_json_api(station_id: str) -> Optional[str]:
    """Try to get track info from the primary SomaFM JSON API."""
    try:
        url = f"http://somafm.com/songs/{station_id}.json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "songs" in data and len(data["songs"]) > 0:
                song = data["songs"][0]  # Get the most recent song
                artist = song.get('artist', '')
                title = song.get('title', '')
                album = song.get('album', '')
                
                if artist and title:
                    if album:
                        return f"{artist} - {title} [{album}]"
                    else:
                        return f"{artist} - {title}"
                elif title:
                    return title
    except Exception:
        pass
    
    return None


def _get_from_channels_api(station_id: str) -> Optional[str]:
    """
    Try to get track info from the SomaFM channels API.
    Uses a cached version of the channels data when possible.
    """
    global _channels_cache, _channels_cache_timestamp
    
    current_time = time.time()
    
    # Check if we need to refresh the channels cache
    if not _channels_cache or (current_time - _channels_cache_timestamp > _CHANNELS_CACHE_EXPIRY):
        try:
            url = "http://somafm.com/channels.json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                _channels_cache = response.json()
                _channels_cache_timestamp = current_time
        except Exception:
            # If the API call fails, keep using the old cache if available
            if not _channels_cache:
                return None
    
    # Use the cached channels data
    try:
        channels = _channels_cache.get('channels', [])
        for channel in channels:
            if channel.get('id') == station_id:
                last_playing = channel.get('lastPlaying', '')
                if last_playing:
                    return last_playing
    except Exception:
        pass
    
    return None