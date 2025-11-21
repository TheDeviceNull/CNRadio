import requests
import urllib3
import re

# Disable warnings for unverified requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Direct firewall friendly stream URL
DIRECT_STREAM_URL = "https://quincy.torontocast.com/hutton"

def get_hutton_track_info():
    """
    Gets the currently playing track on Hutton Orbital Radio.
    Returns just the stream title.
    """
    try:
        # Create a session to handle cookies and redirects
        session = requests.Session()
        
        # Set headers to simulate a browser and request ICY metadata
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Icy-MetaData": "1"  # Request ICY metadata
        }
        
        # Make the request
        response = session.get(DIRECT_STREAM_URL, headers=headers, stream=True, verify=False, timeout=10)
        
        if response.status_code != 200:
            return "Unavailable"
            
        # If we have icy-metaint, we can extract metadata
        if "icy-metaint" in response.headers:
            icy_metaint = int(response.headers["icy-metaint"])
            
            # Read data until metadata
            data = response.raw.read(icy_metaint)
            
            # Read metadata length byte
            meta_length_byte = response.raw.read(1)
            if not meta_length_byte:
                return "Unavailable"
                
            meta_length = ord(meta_length_byte) * 16
            
            # Read metadata
            if meta_length > 0:
                metadata_bytes = response.raw.read(meta_length)
                metadata = metadata_bytes.decode("utf-8", errors="ignore").strip('\0')
                
                # Extract track title
                match = re.search(r"StreamTitle='([^']*)';", metadata)
                if match:
                    return match.group(1)
        
        return "Unavailable"
        
    except Exception:
        return "Unavailable"

if __name__ == "__main__":
    print("Now Playing:", get_hutton_track_info())