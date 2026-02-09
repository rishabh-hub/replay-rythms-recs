# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Replay Rhythms Recs is a song recommendation engine for Rocket League replays. It analyzes gameplay metrics (intensity, performance, teamwork, game closeness) and maps them to song attributes (BPM, energy, moods, themes) to recommend contextually appropriate music.

## Commands

### Run locally
```bash
python app.py                    # Flask dev server on port 8000
gunicorn --bind 0.0.0.0:8000 app:app  # Production server
```

### CLI testing
```bash
python recommend.py <player_id> --top_n 3
# Example: python recommend.py ce45140fcd644755b01660aa2dc6977b
```

### Docker
```bash
docker build -t song-recs .
docker run -p 8000:8000 song-recs
```

### Spotify URL fixer (requires .env with SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)
```bash
python spotify_url_fixer.py      # Converts search URLs to track URLs in songs.json
```

## Architecture

### Data Flow Pipeline
```
Replay JSON → extract_data.py → metrics.py → threshold.py → rule_engine.py → song_matcher.py → Recommendations
```

1. **extract_data.py**: Parses Rocket League replay JSON to extract player stats, team stats, opponent stats
2. **metrics.py**: Calculates four core metrics:
   - `calculate_game_intensity()`: Movement distance + supersonic speed %
   - `calculate_performance_score()`: Goals×100 + saves×50 + shooting%
   - `calculate_teamwork_factor()`: Assists / team goals
   - `calculate_game_outcome()`: Win/loss status and score differential
3. **threshold.py**: Categorizes raw metrics into High/Medium/Low buckets
4. **rule_engine.py**: Maps categories to desired song attributes (BPM range, energy, moods, themes)
5. **song_matcher.py**: Scores songs against desired profile using weighted matching:
   - BPM match: +50 points
   - Energy match: +30 points
   - Mood matches: +15 per match
   - Theme matches: +10 per match

### API Endpoints (app.py)
- `GET /` - API documentation
- `GET /health` - Health check
- `POST /recommend` - Main endpoint (requires `player_id`, optional `replay_data`, `top_n`)
- `GET /recommend/test?player_id=ID` - Test with sample data
- `POST /webhook/recommend` - Webhook variant with callback_url support

### Key Files
- **songs.json**: Song database with BPM, energy, moods, themes, Spotify URLs
- **recommend.py**: Vercel serverless handler + CLI interface
- **app.py**: Flask server for Docker/Render deployment

## Song Database Schema

```json
{
  "song_id": 1,
  "title": "Song Name",
  "artist": "Artist Name",
  "bpm": 120,
  "energy": "High|Medium|Low",
  "moods": ["Energetic", "Uplifting"],
  "themes": ["Victory", "Celebration"],
  "source_url": "https://open.spotify.com/track/...",
  "track_id": "spotify_track_id"
}
```

## Threshold Tuning

Constants in threshold.py control metric categorization:
- `INTENSITY_THRESHOLD_HIGH/LOW`: 1400/1100 (based on Rocket League movement speeds)
- `PERFORMANCE_THRESHOLD_HIGH/LOW`: 300/100
- `TEAMWORK_THRESHOLD_HIGH/LOW`: 0.5/0.2
- `SCORE_DIFFERENTIAL_CLOSE/MODERATE`: 1/2 goals
