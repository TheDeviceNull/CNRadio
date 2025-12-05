"""
Radio Deejay Track Retriever
----------------------------
Retrieves the currently playing track from Radio Deejay's API.
Used by RadioPlugin for Covas:NEXT.
"""

import requests
import time
import urllib3
from typing import Dict, Tuple

# Disable warnings for unverified requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Official "onair" endpoints
DEFAULT_URL = "https://www.deejay.it/api/pub/v2/all/gdwc-audio-player/onair?format=json"
LINETTI_URL = "https://streamcdnm6-4c4b867c89244861ac216426883d1ad0.msvdn.net/webradio/metadata/deejaywfmlinus.json"

# Cache: title and timestamp
_cache: Dict[str, Tuple[str, float]] = {}
_CACHE_EXPIRY = 20  # seconds

# Headers: browser-like UA for compatibility with CDNs/WAF
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36 DeejayTitleRetriever/1.0",
    "Accept": "application/json, text/plain, */*",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

def _map_title(data: dict, is_linetti: bool = False) -> str:
    """
    Extract the Title from the JSON response based on format.
    """
    if is_linetti:
        # Format for Linetti: extract from json.now.artist and json.now.title
        try:
            now_data = data.get("json", {}).get("now", {})
            artist = now_data.get("artist", "")
            title = now_data.get("title", "")
            if artist and title:
                return f"{artist} - {title}".strip()
            return title or ""
        except (KeyError, AttributeError):
            return ""
    else:
        # Original Radio Deejay format
        return (data.get("title") or "").strip()

def get_deejay_track_info(station_name: str = None) -> str:
    """
    Returns the current track title from Radio Deejay.
    In case of error, returns an empty string.
    
    Args:
        station_name: Optional station name to determine which endpoint to use
    """
    # Determine which URL to use based on station name
    is_linetti = station_name and "linetti" in station_name.lower()
    url = LINETTI_URL if is_linetti else DEFAULT_URL
    
    now = time.time()
    cache_key = url  # Use URL as cache key
    
    # Check cache
    if cache_key in _cache:
        cached_value, ts = _cache[cache_key]
        age = now - ts
        if age < _CACHE_EXPIRY:
            return cached_value

    # HTTP request
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=8, verify=False)
    except requests.exceptions.RequestException:
        _cache[cache_key] = ("", now)
        return ""

    if resp.status_code != 200:
        _cache[cache_key] = ("", now)
        return ""

    # Parse JSON
    try:
        data = resp.json()
    except ValueError:
        _cache[cache_key] = ("", now)
        return ""

    # Map title based on format
    title = _map_title(data, is_linetti)
    
    # Update cache (even if empty to debounce/retry)
    _cache[cache_key] = (title, now)
    return title

if __name__ == "__main__":
    print("Radio Deejay Now Playing:", get_deejay_track_info())
    print("Radio Deejay Linetti Now Playing:", get_deejay_track_info("Radio DeeJay Linetti"))