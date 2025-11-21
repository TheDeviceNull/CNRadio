import vlc
import time
import requests
import json
from bs4 import BeautifulSoup

# Stream URL to monitor
stream_url = "https://ice.somafm.com/defcon"
# SomaFM song info endpoint (using HTTP instead of HTTPS)
song_info_url = "http://somafm.com/songs/defcon.json"

# Create VLC media player
player = vlc.MediaPlayer(stream_url)
player.play()

# Wait for playback to start
time.sleep(5)

# Get media object
media = player.get_media()

# Initialize last known title
last_title = ""

def get_stream_metadata():
    """Try to get metadata directly from the stream"""
    # Parse metadata from network
    media.parse_with_options(vlc.MediaParseFlag.network, timeout=5)

    # Try multiple metadata fields
    now_playing = media.get_meta(vlc.Meta.NowPlaying)
    title = media.get_meta(vlc.Meta.Title)
    artist = media.get_meta(vlc.Meta.Artist)
    description = media.get_meta(vlc.Meta.Description)

    # Determine current track info
    current_info = now_playing or title or artist or description
    
    # Filter out cases where we just get the stream name
    if current_info and current_info.strip().lower() != "deepspaceone":
        return current_info.strip()
    return None

def get_somafm_song_info():
    """Get track information from the SomaFM songs JSON endpoint"""
    try:
        response = requests.get(song_info_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # SomaFM typically returns an array of songs with the most recent first
            if data and isinstance(data, list) and len(data) > 0:
                song = data[0]  # Get the most recent song
                
                # Extract artist and title
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
                
    except Exception as e:
        print(f"Error fetching SomaFM song data: {e}")
    
    return None

def get_alternative_song_info():
    """Try alternative SomaFM endpoints for song information"""
    try:
        # Try the "recently played" endpoint
        alt_url = "http://somafm.com/recent/deepspaceone.json"
        response = requests.get(alt_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                song = data[0]
                return f"{song.get('artist', '')} - {song.get('title', '')}"
    except Exception:
        pass
    
    try:
        # Try the channel info endpoint which sometimes includes current track
        channel_url = "http://somafm.com/channels.json"
        response = requests.get(channel_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            channels = data.get('channels', [])
            for channel in channels:
                if channel.get('id') == 'deepspaceone':
                    return channel.get('lastPlaying', '')
    except Exception:
        pass
    
    return None

def scrape_somafm_website():
    """Scrape the SomaFM website directly for song information"""
    try:
        # Try the main website for the channel
        url = "http://somafm.com/deepspaceone/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the song information
            song_div = soup.select_one('#nowplaying')
            if song_div:
                return song_div.get_text(strip=True)
            
            # Try alternative selectors
            song_div = soup.select_one('.playing')
            if song_div:
                return song_div.get_text(strip=True)
    except Exception as e:
        print(f"Error scraping website: {e}")
    
    return None

print("Monitoring stream metadata...")

try:
    while True:
        # Strategy 1: Try SomaFM JSON endpoint (most reliable)
        current_info = get_somafm_song_info()
        source = "JSON API"
        
        # Strategy 2: Try alternative SomaFM endpoints
        if not current_info:
            alt_info = get_alternative_song_info()
            if alt_info:
                current_info = alt_info
                source = "alternative API"
        
        # Strategy 3: Try to get metadata directly from the stream
        if not current_info:
            stream_info = get_stream_metadata()
            if stream_info:
                current_info = stream_info
                source = "stream"
        
        # Strategy 4: Scrape the website directly
        if not current_info:
            web_info = scrape_somafm_website()
            if web_info:
                current_info = web_info
                source = "website"
            
        # If we have info from any source and it's different from last time
        if current_info and current_info.lower() != last_title.lower():
            print(f"Now Playing: {current_info} (source: {source})")
            last_title = current_info
        elif not current_info and not last_title:
            print("Unable to retrieve track information")

        # Wait before checking again
        time.sleep(10)

except KeyboardInterrupt:
    print("Stopped monitoring.")
    player.stop()