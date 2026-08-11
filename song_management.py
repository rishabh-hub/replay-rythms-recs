import json
import os

SONG_DATABASE_FILE = "songs.json"
ENRICHED_DATABASE_FILE = "enriched_songs.json"

USE_AGENTIC = os.getenv("USE_AGENTIC", "false").lower() == "true"


def load_song_database(agentic=None):
    """
    Loads the song database from the JSON file.
    When agentic mode is active, loads enriched_songs.json and uses
    llm_moods/llm_themes for matching instead of the original fields.

    Args:
        agentic: Override for USE_AGENTIC flag. If None, uses env var.

    Returns a list of song dictionaries, or an empty list if an error occurs.
    """
    use_agentic = agentic if agentic is not None else USE_AGENTIC

    if use_agentic:
        db_file = ENRICHED_DATABASE_FILE
    else:
        db_file = SONG_DATABASE_FILE

    try:
        with open(db_file, "r", encoding="utf-8") as f:
            songs = json.load(f)
        if not isinstance(songs, list):
            print(f"Error: Song database '{db_file}' should be a list of songs.")
            return []

        # When agentic, promote llm_moods/llm_themes to moods/themes for matching
        if use_agentic:
            for song in songs:
                if "llm_moods" in song:
                    song["moods"] = song["llm_moods"]
                if "llm_themes" in song:
                    song["themes"] = song["llm_themes"]
                if "llm_energy" in song:
                    song["energy"] = song["llm_energy"]

        print(f"Successfully loaded {len(songs)} songs from '{db_file}'.")
        return songs
    except FileNotFoundError:
        if use_agentic:
            print(
                f"Warning: '{db_file}' not found. Falling back to '{SONG_DATABASE_FILE}'."
            )
            return load_song_database(agentic=False)
        print(f"Error: Song database file '{db_file}' not found.")
        return []
    except json.JSONDecodeError:
        print(
            f"Error: Could not decode JSON from '{db_file}'. Check for syntax errors."
        )
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading songs: {e}")
        return []


if __name__ == "__main__":
    song_db = load_song_database()
    if song_db:
        print(f"\nFirst song in DB: {song_db[0]['title']} by {song_db[0]['artist']}")
