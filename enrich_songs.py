"""
Song Enrichment Pipeline — Phase 1 of Agentic Recs
Enriches songs.json with:
  1. Last.fm crowd-sourced tags (what real people tag songs as)
  2. LLM-generated profiles (human-perceived moods, themes, vibes, game-moment associations)

Usage:
  python enrich_songs.py                    # Run full enrichment
  python enrich_songs.py --lastfm-only      # Only Last.fm tags
  python enrich_songs.py --llm-only         # Only LLM profiling
  python enrich_songs.py --dry-run          # Preview without writing

Requires in .env:
  LASTFM_API_KEY=...
  OPENAI_API_KEY=sk-...
"""

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

SONGS_INPUT = "songs.json"
SONGS_OUTPUT = "enriched_songs.json"
LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"
LASTFM_RATE_LIMIT = 0.25  # seconds between requests (safe for ~4 req/s)
LLM_RATE_LIMIT = 0.3  # seconds between OpenAI calls
LLM_MODEL = "gpt-4.1-mini"


# ─── Last.fm Enrichment ─────────────────────────────────────────────────────


def fetch_lastfm_tags(
    artist: str, track: str, api_key: str, limit: int = 15
) -> list[dict]:
    """Fetch crowd-sourced tags from Last.fm's track.getTopTags endpoint."""
    try:
        resp = requests.get(
            LASTFM_BASE_URL,
            params={
                "method": "track.getTopTags",
                "artist": artist,
                "track": track,
                "api_key": api_key,
                "format": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if "toptags" not in data or "tag" not in data["toptags"]:
            # Try without "ft." / "feat." in artist name (common mismatch)
            clean_artist = (
                artist.split(" ft.")[0].split(" feat.")[0].split(" &")[0].strip()
            )
            if clean_artist != artist:
                return fetch_lastfm_tags(clean_artist, track, api_key, limit)
            return []

        tags = data["toptags"]["tag"]
        if isinstance(tags, dict):  # Single tag comes as dict, not list
            tags = [tags]

        return [
            {"name": tag["name"].lower().strip(), "count": int(tag["count"])}
            for tag in tags[:limit]
            if int(tag["count"]) > 0
        ]
    except requests.RequestException as e:
        print(f"    Last.fm API error: {e}")
        return []
    except (KeyError, ValueError, TypeError) as e:
        print(f"    Last.fm parse error: {e}")
        return []


def enrich_with_lastfm(songs: list[dict], api_key: str) -> list[dict]:
    """Add Last.fm crowd-sourced tags to each song."""
    print("\n═══ Last.fm Crowd-Sourced Tags ═══\n")
    total = len(songs)
    success = 0

    for i, song in enumerate(songs):
        title = song["title"]
        artist = song["artist"]
        print(f"  [{i + 1}/{total}] {title} — {artist}", end="")

        if song.get("lastfm_tags"):
            print(" (already enriched, skipping)")
            success += 1
            continue

        tags = fetch_lastfm_tags(artist, title, api_key)
        song["lastfm_tags"] = tags

        if tags:
            tag_names = [t["name"] for t in tags[:5]]
            print(f"  → {', '.join(tag_names)}")
            success += 1
        else:
            print("  → no tags found")

        time.sleep(LASTFM_RATE_LIMIT)

    print(f"\n  Last.fm: {success}/{total} songs enriched\n")
    return songs


# ─── LLM Enrichment ─────────────────────────────────────────────────────────

LLM_PROMPT = """You are a music expert who deeply understands how people perceive and feel about songs. You know what listeners on Reddit, forums, and social media say about popular music.

For the song "{title}" by {artist}, provide a detailed profile based on HUMAN PERCEPTION — not audio analysis. Think about:
- What mood does this song put people in?
- What real-life moments or scenarios does it soundtrack?
- What would a Rocket League player feel if this played during their replay?

Return a JSON object with these fields:

{{
  "energy": "High" or "Medium" or "Low",
  "moods": ["list of 3-6 mood words from the vocabulary below"],
  "themes": ["list of 2-4 theme words from the vocabulary below"],
  "vibe_description": "One vivid sentence describing how this song FEELS to listeners",
  "game_moments": ["list of 2-4 Rocket League game moments this song would perfectly soundtrack"]
}}

MOOD VOCABULARY (pick the most fitting ones):
Energetic, Triumphant, Reflective, Tense, Uplifting, Dramatic, Focused, Heartbreak, Clutch, Suspenseful, Defiant, Aggressive, Melancholy, Euphoric, Nostalgic, Dreamy, Anthemic, Dark, Confident, Playful, Intense, Brooding, Bittersweet, Serene, Rebellious, Empowering, Gritty, Hypnotic, Wistful, Exhilarant

THEME VOCABULARY (pick the most fitting ones):
Victory, Celebration, Comeback, Underdog, Domination, Resilience, Rivalry, Journey, Teamwork, Solo Carry, Heartbreak Loss, Close Game, Blowout Win, Overtime Thriller, Defensive Stand, Aerial Mastery, Speed Rush, Last Second Save, Redemption, Glory

GAME MOMENTS examples (be specific to Rocket League):
"Scoring a double-tap aerial goal", "Winning a 1v3 clutch", "Nail-biting overtime sudden death",
"Dominating the opponent 7-0", "Making a game-saving save in the last second",
"Smooth passing play with teammates", "Coming back from 0-3 down", "Freestyle dribble goal"

Be specific to THIS song. Don't be generic."""


def profile_song_with_llm(title: str, artist: str, client: OpenAI) -> dict | None:
    """Generate a human-perceived song profile using OpenAI."""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type": "json_object"},
            max_tokens=400,
            messages=[
                {"role": "system", "content": "You output valid JSON only."},
                {
                    "role": "user",
                    "content": LLM_PROMPT.format(title=title, artist=artist),
                },
            ],
        )
        result = json.loads(response.choices[0].message.content)

        # Validate expected fields
        required = {"energy", "moods", "themes", "vibe_description", "game_moments"}
        if not required.issubset(result.keys()):
            missing = required - result.keys()
            print(f"    LLM missing fields: {missing}")
            return None

        return result
    except Exception as e:
        print(f"    LLM error: {e}")
        return None


def enrich_with_llm(songs: list[dict], api_key: str) -> list[dict]:
    """Add LLM-generated profiles to each song."""
    print("\n═══ LLM Profiling (OpenAI) ═══\n")
    client = OpenAI(api_key=api_key)
    total = len(songs)
    success = 0

    for i, song in enumerate(songs):
        title = song["title"]
        artist = song["artist"]
        print(f"  [{i + 1}/{total}] {title} — {artist}", end="")

        if song.get("llm_moods"):
            print(" (already enriched, skipping)")
            success += 1
            continue

        profile = profile_song_with_llm(title, artist, client)

        if profile:
            song["llm_energy"] = profile["energy"]
            song["llm_moods"] = profile["moods"]
            song["llm_themes"] = profile["themes"]
            song["llm_vibe"] = profile["vibe_description"]
            song["llm_game_moments"] = profile["game_moments"]
            print(f"  → {profile['energy']} | {', '.join(profile['moods'][:4])}")
            success += 1
        else:
            print("  → FAILED")

        time.sleep(LLM_RATE_LIMIT)

        # Save progress every 10 songs (crash safety)
        if (i + 1) % 10 == 0:
            save_songs(songs, SONGS_OUTPUT)
            print(f"  [checkpoint saved at {i + 1}/{total}]")

    print(f"\n  LLM: {success}/{total} songs profiled\n")
    return songs


# ─── Utilities ───────────────────────────────────────────────────────────────


def load_songs(path: str) -> list[dict]:
    """Load songs from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_songs(songs: list[dict], path: str):
    """Save songs to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=2, ensure_ascii=False)


def print_summary(songs: list[dict]):
    """Print enrichment summary stats."""
    print("\n═══ Enrichment Summary ═══\n")
    total = len(songs)
    has_lastfm = sum(1 for s in songs if s.get("lastfm_tags"))
    has_llm = sum(1 for s in songs if s.get("llm_moods"))

    print(f"  Total songs:        {total}")
    print(f"  Last.fm enriched:   {has_lastfm}/{total}")
    print(f"  LLM profiled:       {has_llm}/{total}")

    # Show energy distribution from LLM
    energies = {}
    for s in songs:
        e = s.get("llm_energy", "not profiled")
        energies[e] = energies.get(e, 0) + 1
    print("\n  LLM Energy distribution:")
    for e, count in sorted(energies.items()):
        print(f"    {e}: {count}")

    # Show most common LLM moods
    mood_counts = {}
    for s in songs:
        for m in s.get("llm_moods", []):
            mood_counts[m] = mood_counts.get(m, 0) + 1
    if mood_counts:
        print("\n  Top 10 LLM moods:")
        for mood, count in sorted(mood_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {mood}: {count}")

    # Show most common LLM themes
    theme_counts = {}
    for s in songs:
        for t in s.get("llm_themes", []):
            theme_counts[t] = theme_counts.get(t, 0) + 1
    if theme_counts:
        print("\n  Top 10 LLM themes:")
        for theme, count in sorted(theme_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {theme}: {count}")

    print()


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Enrich songs.json with Last.fm tags and LLM profiles"
    )
    parser.add_argument(
        "--lastfm-only", action="store_true", help="Only run Last.fm enrichment"
    )
    parser.add_argument(
        "--llm-only", action="store_true", help="Only run LLM enrichment"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Load and summarize without enriching"
    )
    parser.add_argument(
        "--input", default=SONGS_INPUT, help=f"Input file (default: {SONGS_INPUT})"
    )
    parser.add_argument(
        "--output", default=SONGS_OUTPUT, help=f"Output file (default: {SONGS_OUTPUT})"
    )
    args = parser.parse_args()

    # Load songs — prefer enriched file if it exists (for re-runs)
    if os.path.exists(args.output) and args.input != args.output:
        print(f"Found existing {args.output}, loading it (for incremental enrichment)")
        songs = load_songs(args.output)
    else:
        songs = load_songs(args.input)

    print(f"Loaded {len(songs)} songs")

    if args.dry_run:
        print_summary(songs)
        return

    run_lastfm = not args.llm_only
    run_llm = not args.lastfm_only

    # Last.fm enrichment
    if run_lastfm:
        lastfm_key = os.getenv("LASTFM_API_KEY")
        if not lastfm_key:
            print(
                "WARNING: LASTFM_API_KEY not set in .env — skipping Last.fm enrichment"
            )
            print("  Get a free key at: https://www.last.fm/api/account/create")
        else:
            songs = enrich_with_lastfm(songs, lastfm_key)
            save_songs(songs, args.output)

    # LLM enrichment
    if run_llm:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            print("ERROR: OPENAI_API_KEY not set in .env — cannot run LLM enrichment")
            sys.exit(1)
        songs = enrich_with_llm(songs, openai_key)
        save_songs(songs, args.output)

    print_summary(songs)
    print(f"Enriched data saved to {args.output}")


if __name__ == "__main__":
    main()
