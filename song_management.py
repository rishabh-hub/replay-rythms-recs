import json

SONG_DATABASE_FILE = "songs.json"

def load_song_database():
    """
    Loads the song database from the JSON file.
    Returns a list of song dictionaries, or an empty list if an error occurs.
    """
    try:
        with open(SONG_DATABASE_FILE, 'r', encoding='utf-8') as f:
            songs = json.load(f)
        # Basic validation: check if it's a list
        if not isinstance(songs, list):
            print(f"Error: Song database '{SONG_DATABASE_FILE}' should be a list of songs.")
            return []
        # Optional: further validation for each song entry can be added here
        # For example, check for required keys like 'title', 'artist', 'bpm', etc.
        print(f"Successfully loaded {len(songs)} songs from '{SONG_DATABASE_FILE}'.")
        return songs
    except FileNotFoundError:
        print(f"Error: Song database file '{SONG_DATABASE_FILE}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{SONG_DATABASE_FILE}'. Check for syntax errors.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading songs: {e}")
        return []

# Example of how you might use this (not part of the main app flow yet):
if __name__ == "__main__":
    song_db = load_song_database()
    if song_db:
        print(f"\nFirst song in DB: {song_db[0]['title']} by {song_db[0]['artist']}")