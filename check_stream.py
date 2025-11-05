import vlc
import time

# Stream URL to monitor
# stream_url = "http://ice1.somafm.com/secretagent-128-mp3"
stream_url = "http://ice1.somafm.com/secretagent-128-mp3"
# Create VLC media player
player = vlc.MediaPlayer(stream_url)
player.play()

# Wait for playback to start
time.sleep(5)

# Get media object
media = player.get_media()

# Initialize last known title
last_title = ""

print("Monitoring stream metadata...")

try:
    while True:
        # Parse metadata from network
        media.parse_with_options(vlc.MediaParseFlag.network, timeout=5)

        # Try multiple metadata fields
        now_playing = media.get_meta(vlc.Meta.NowPlaying)
        title = media.get_meta(vlc.Meta.Title)
        artist = media.get_meta(vlc.Meta.Artist)
        description = media.get_meta(vlc.Meta.Description)

        # Determine current track info
        current_info = now_playing or title or artist or description or "Unknown track"
        current_info = current_info.strip()

        # Print only if changed
        if current_info and current_info.lower() != last_title.lower():
            print(f"Now Playing: {current_info}")
            last_title = current_info

        # Wait before checking again
        time.sleep(10)

except KeyboardInterrupt:
    print("Stopped monitoring.")
    player.stop()

