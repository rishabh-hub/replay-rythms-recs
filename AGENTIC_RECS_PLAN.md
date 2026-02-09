# Agentic Recommendation System — Plan & Architecture

## Problem Statement

The current recommendation pipeline is **deterministic and bottlenecked**:
- Same stats → same thresholds → same desired profile → same song, every time
- Only 6/71 songs are High energy — MVP players always get Viva La Vida
- "Victory" theme exists on exactly 1 song (Eye of the Tiger), but its BPM misses the range
- Moods/themes were manually assigned and don't reflect what people actually feel about songs
- A static song database means no freshness — the same 71 songs forever

## Core Insights

1. **Human-perceived semantics > audio analysis**: We don't want danceability/acousticness. We want what PEOPLE say about a song's vibe. LLMs trained on millions of reviews/discussions already have this knowledge.

2. **Unique game semantics > mood labels**: Matching "High energy → High energy song" is just a fancier rule engine. The real value is reading the STORY of each game from the stats and finding a song that tells the same story. Two "High performance wins" can have completely different narratives — a solo carry vs. a team orchestration — and deserve completely different songs.

3. **Curated + Dynamic > either alone**: A static curated database provides quality and community input. Dynamic LLM-powered discovery provides variety, freshness, and songs beyond the database. The best system uses both.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│              OFFLINE: Song Database Enrichment                │
│                                                               │
│  songs.json ──→ Last.fm tags ──→ LLM profiling ──→           │
│                  (free API)     (gpt-4.1-mini)               │
│                                      │                        │
│                              enriched_songs.json              │
│           (human-perceived moods, themes, vibes,              │
│            game-moment associations)                          │
│                                                               │
│  Grows over time via:                                         │
│    - User suggestions ("this song fits my replay")            │
│    - Community/friend picks                                   │
│    - Re-running enrichment after adding songs                 │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              RUNTIME: Agentic Pipeline (per request)          │
│                                                               │
│  Replay JSON                                                  │
│      │                                                        │
│      ▼                                                        │
│  extract_data.py (unchanged)                                  │
│      │                                                        │
│      ▼                                                        │
│  ┌────────────────────────────────────────┐                    │
│  │ AGENT 1: Game Narrative Analyst        │                    │
│  │ (gpt-4.1-mini — single LLM call)      │                    │
│  │                                        │                    │
│  │ Raw stats → RICH game reading:         │                    │
│  │  - narrative (the game's story)        │                    │
│  │  - key_observations (specific insights │                    │
│  │    drawn from stat combinations)       │                    │
│  │  - player_archetype (the role they     │                    │
│  │    played in this game)                │                    │
│  │  - emotional_arc (how the game felt)   │                    │
│  │  - song_search_direction (semantic     │                    │
│  │    description of what song to find    │                    │
│  │    — NOT mood labels)                  │                    │
│  │                                        │                    │
│  │ REPLACES: metrics.py + threshold.py    │                    │
│  │           + rule_engine.py             │                    │
│  └──────────────┬─────────────────────────┘                    │
│                 │                                              │
│                 ▼                                              │
│       ┌─────────┴──────────┐                                   │
│       │                    │                                   │
│       ▼                    ▼                                   │
│  ┌──────────────┐   ┌───────────────────┐                      │
│  │ Curated      │   │ Discovery Agent   │                      │
│  │ Matcher      │   │ (gpt-4.1-mini)    │                      │
│  │              │   │                   │                      │
│  │ Scores       │   │ LLM suggests 5-6  │                      │
│  │ enriched DB  │   │ songs based on    │                      │
│  │ against the  │   │ song_search_      │                      │
│  │ game reading │   │ direction         │                      │
│  │              │   │       │           │                      │
│  │ Returns top  │   │       ▼           │                      │
│  │ 3-4 curated  │   │ Spotify Search    │                      │
│  │ candidates   │   │ API verification  │                      │
│  │              │   │ (filter fakes,    │                      │
│  │ (code-based, │   │  get real links)  │                      │
│  │  no LLM)     │   │       │           │                      │
│  │              │   │ Returns 3-4       │                      │
│  │              │   │ verified songs    │                      │
│  └──────┬───────┘   └────────┬──────────┘                      │
│         │                    │                                 │
│         └────────┬───────────┘                                 │
│                  │                                             │
│                  ▼                                             │
│  ┌────────────────────────────────────────┐                    │
│  │ AGENT 3: Music Curator                 │                    │
│  │ (gpt-4.1-mini — final selection)       │                    │
│  │                                        │                    │
│  │ Sees ALL candidates (labeled           │                    │
│  │ [curated] vs [discovered])             │                    │
│  │                                        │                    │
│  │ Picks final 3 recommendations by       │                    │
│  │ matching each song's story to the      │                    │
│  │ UNIQUE game narrative                  │                    │
│  │                                        │                    │
│  │ For each pick, outputs:                │                    │
│  │  - which key_observations drove        │                    │
│  │    the choice                          │                    │
│  │  - WHY this song matches THIS game     │                    │
│  │    (not generic "it's energetic")      │                    │
│  │  - the connection between game story   │                    │
│  │    and song story                      │                    │
│  └──────────────┬─────────────────────────┘                    │
│                 │                                              │
│                 ▼                                              │
│  ┌────────────────────────────────────────┐                    │
│  │ FINAL OUTPUT                           │                    │
│  │                                        │                    │
│  │ {                                      │                    │
│  │   game_reading: {                      │                    │
│  │     narrative: "...",                   │                    │
│  │     key_observations: [...],           │                    │
│  │     player_archetype: "..."            │                    │
│  │   },                                   │                    │
│  │   recommendations: [                   │                    │
│  │     {                                  │                    │
│  │       title, artist, spotify_url,      │                    │
│  │       source: "curated"|"discovered",  │                    │
│  │       match_reasoning: "Your 6 saves   │                    │
│  │         carried this OT win...",       │                    │
│  │       observations_used: [...]         │                    │
│  │     }                                  │                    │
│  │   ]                                    │                    │
│  │ }                                      │                    │
│  └────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

---

## The Key Differentiator: Unique Game Semantics

This is the core of the entire system. The Game Analyst doesn't produce mood labels — it reads the STORY.

### Example: Two "High Performance Wins" → Completely Different Songs

**Game A** — 5 goals, 0 assists, 83% shooting, team won 5-4 in OT, zero boost sharing:
```json
{
  "narrative": "A one-man army. Didn't pass, didn't set up — just took
    over. Pure solo brilliance in a chaotic game that came down to the wire.",
  "key_observations": [
    "5 of 5 team goals — complete solo carry",
    "0 assists despite 83% shooting — chose to finish everything alone",
    "5-4 scoreline — chaos on both ends, no defense just pure offense",
    "Overtime finish — refused to let the game end without winning it"
  ],
  "player_archetype": "The One-Man Army — carried everything on their back",
  "emotional_arc": "Relentless intensity building to an overtime explosion",
  "song_search_direction": "Songs about seizing your one shot, carrying
    everything alone under insane pressure. The lone wolf who won't be
    denied. Raw, intense, personal — not a team celebration anthem."
}
```
→ **"Lose Yourself" by Eminem** — not "We Are The Champions"

**Game B** — 1 goal, 4 assists, team won 6-1, high boost sharing:
```json
{
  "narrative": "The conductor. Orchestrated every play, made teammates
    look brilliant. Total unit domination — passing felt like an art form.",
  "key_observations": [
    "4 assists on 6 goals — involved in 83% of team's offense",
    "Only 1 personal goal — chose to create rather than finish",
    "6-1 blowout — complete team domination from start to finish",
    "High boost sharing — literally fueling teammates' success"
  ],
  "player_archetype": "The Conductor — orchestrates everything,
    makes everyone better",
  "emotional_arc": "Smooth confidence building to total dominance",
  "song_search_direction": "Songs about running things as a crew,
    being in effortless flow, making the whole team shine. Confident
    and smooth, not gritty or desperate."
}
```
→ **"All I Do Is Win" by DJ Khaled** or **"Run This Town" by Jay-Z**

### More Rocket League-Specific Narratives the Agent Should Catch

| Stat Pattern | What It Means | Player Archetype | Song Direction |
|---|---|---|---|
| High saves, 0 goals, close win | Defensive anchor | The Guardian | Quiet strength, protector, unsung hero |
| High boost pickup, 0 contributions, long OT | Goofing around | The Troll | Silly, chaotic, meme energy |
| High speed, low boost, lots of shots but low % | Ballchasing | The Chaos Agent | Frenetic, relentless, reckless energy |
| Balanced goals/assists/saves | Complete player | The Complete Package | Versatile, confident, well-rounded |
| 0-0 at end of regulation, winning goal in OT | Defensive stalemate → sudden hero | The Clutch Artist | Tension → release, patience → explosion |
| Big comeback (down 0-3, won 4-3) | Refused to quit | The Phoenix | Defiance, comeback, never-say-die |
| High demo count + high speed | Physical domination | The Enforcer | Aggressive, intimidating, dominant |
| Hat trick in under 2 mins | Explosive hot streak | The Streak | Explosive energy, unstoppable momentum |

### Rocket League Domain Knowledge for the Game Analyst

The Game Analyst's system prompt must include RL-specific context:

- **Boost starving**: High small pad pickups + low boost = denying opponent resources = tactical play
- **Ballchasing**: High speed + many touches + low passing = not rotating properly
- **Rotation**: Balanced positioning across team = disciplined play
- **Double commit**: When stats show both teammates doing same thing = disorganized
- **Demo plays**: High demos = physical, aggressive playstyle
- **Aerial mastery**: High aerial goals/touches = mechanical skill, flashy plays
- **Overtime context**: Everything in OT is amplified — saves matter more, goals are clutch
- **Score differential**: 1-0 feels completely different from 7-1
- **Comeback vs. blowout**: Being down 0-3 and winning 4-3 is a COMPLETELY different story than leading 4-0 and winning 4-3

---

## Implementation Phases

### Phase 1: Song Database Enrichment ✅ COMPLETE

**Script**: `enrich_songs.py` | **Model**: `gpt-4.1-mini`

- Last.fm crowd-sourced tags: 45/71 songs enriched
- LLM profiling: 71/71 songs profiled
- Output: `enriched_songs.json`
- Energy distribution: High: 37, Medium: 27, Low: 7 (was: High: 6, Medium: 33, Low: 32)
- Victory theme: 33 songs (was: 1 song)

The enriched DB serves as:
- Quality floor (verified songs with rich metadata and working Spotify links)
- Community input channel (users/friends suggest songs → add to DB → re-enrich)
- High-confidence matching source (more data per song than dynamic discovery)

### Phase 2: Game Narrative Analyst Agent

**Goal**: Read the STORY of a game from raw stats, not just categorize into buckets.

**Replaces**: `metrics.py` + `threshold.py` + `rule_engine.py`

**Input**: Raw replay stats from `extract_data.py`

**Output** (structured JSON):
```json
{
  "narrative": "1-2 sentence vivid description of what this game was",
  "key_observations": [
    "Specific insight drawn from stat combinations (3-5 items)",
    "Each one connects raw numbers to a MEANING",
    "e.g. '4 assists on 6 goals — the puppetmaster pulling every string'"
  ],
  "player_archetype": "Short label — The Guardian, The One-Man Army, etc.",
  "emotional_arc": "How the game FELT over time — tension, release, dominance, chaos",
  "song_search_direction": "2-3 sentence semantic description of what kind of
    song to find. Describes the STORY the song should tell, not mood labels.
    This is the primary input for the Discovery Agent."
}
```

**Key design principle**: The `song_search_direction` is a NARRATIVE description, not a list of keywords. "Songs about being the quiet backbone while chaos erupts around you" is infinitely more useful than "energy: High, mood: Triumphant" for finding the RIGHT song.

**Why this produces unique results**: Because the narrative comes from specific stat COMBINATIONS — not individual stats mapped to buckets. The same "3 goals" means different things depending on assists (solo carry vs. team player), game score (close vs. blowout), and overtime (clutch vs. comfortable).

### Phase 3: Song Sourcing (two parallel tracks)

#### Track A: Curated Matcher (code, no LLM)

Scores `enriched_songs.json` against the Game Analyst's output using the enriched `llm_moods`, `llm_themes`, `llm_game_moments`, `llm_vibe` fields.

- Fast, free, deterministic
- Returns top 3-4 candidates with match scores
- Advantages: verified Spotify links, rich metadata, community-curated
- Limitations: fixed pool of songs, can feel repetitive over time

#### Track B: Discovery Agent (1 LLM call + Spotify verification)

Uses `song_search_direction` from the Game Analyst to find songs BEYOND the curated database.

**How it works**:
1. LLM receives the game narrative + `song_search_direction`
2. Prompted to suggest 5-6 REAL songs that match the specific game story
3. Prompted for genre diversity and mix of well-known + lesser-known picks
4. Each suggestion verified via Spotify Search API (catches hallucinations, gets real links)
5. Returns 3-4 verified songs with Spotify URLs

**Mitigations for LLM popularity bias**:
- Prompt explicitly asks for genre diversity (not all pop/rock)
- Asks for at least 1-2 lesser-known/unexpected picks
- Uses `song_search_direction` (specific story) not mood labels (generic)
- Instructs to avoid "obvious" picks and think creatively

**Mitigations for hallucination**:
- Request 5-6 songs, expect 1-2 to fail Spotify verification
- Only return Spotify-verified songs with working URLs
- If too many fail, return fewer rather than fake results

**Limitations**:
- LLM knowledge cutoff (June 2024 for gpt-4.1-mini) — truly new songs won't appear
- Future enhancement: web search or Spotify trending integration for real-time freshness

### Phase 4: Music Curator Agent (final selection + reasoning)

**Goal**: Pick the best 3 songs from all candidates, with transparent reasoning tied to specific game observations.

**Input**:
- Game Analyst output (narrative, key_observations, archetype, song_search_direction)
- Curated candidates (3-4 songs, labeled `[curated]`)
- Discovered candidates (3-4 songs, labeled `[discovered]`)

**Output**:
```json
{
  "game_reading": {
    "narrative": "A defensive masterclass...",
    "key_observations": ["6 saves with 0 goals...", "..."],
    "player_archetype": "The Guardian"
  },
  "recommendations": [
    {
      "rank": 1,
      "title": "Fix You",
      "artist": "Coldplay",
      "spotify_url": "https://open.spotify.com/track/...",
      "source": "curated",
      "match_reasoning": "Your 6 saves carried this 1-0 OT win — you were the
        quiet backbone while chaos erupted around you. 'Fix You' captures that
        same feeling of steady devotion and quiet triumph that only a true
        defender knows.",
      "observations_used": [
        "6 saves with 0 goals — pure defensive dedication",
        "Won 1-0 in overtime — every save mattered"
      ]
    },
    {
      "rank": 2,
      "title": "The Scientist",
      "artist": "Coldplay",
      "spotify_url": "https://open.spotify.com/track/...",
      "source": "discovered",
      "match_reasoning": "The precision of your positioning — low speed but
        always in the right place — mirrors the deliberate, methodical beauty
        of this track. Every note placed with care, like every save you made.",
      "observations_used": [
        "Highest boost usage but lowest speed — reading plays, not chasing",
        "Low speed but constant positioning — the brain, not the legs"
      ]
    }
  ]
}
```

**Key design principle**: Every `match_reasoning` must reference specific `observations_used` from the Game Analyst. No generic "this is an energetic song for your energetic game." The reasoning is the product.

**Mix ratio**: The Curator decides how many curated vs. discovered songs make the final 3. Sometimes curated dominates (when the DB has perfect matches). Sometimes discovered songs are more fitting. No hardcoded ratio.

---

## Phase 5: Integration

- Wire into `app.py` / `recommend.py`
- Update `/recommend` endpoint to call the agentic pipeline
- Response includes `game_reading` + `recommendations` with full reasoning
- Keep old rule-based pipeline as fallback (feature flag `USE_AGENTIC=true`)
- Add `OPENAI_API_KEY`, `LASTFM_API_KEY`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` to env

---

## Data Sources

| Source | What It Provides | Cost | Used In |
|--------|-----------------|------|---------|
| Last.fm `track.getTopTags` | Crowd-sourced mood/genre/vibe tags | Free | Phase 1 enrichment |
| OpenAI `gpt-4.1-mini` | Song profiles, game narratives, song discovery, curation | See below | Phase 1-4 |
| Spotify Search API | Track URL/ID verification for discovered songs | Free | Phase 3 Discovery |
| `enriched_songs.json` | Curated song database with rich metadata | N/A | Phase 3 Curated Matcher |

## Runtime Cost Model

| Component | Cost per request |
|---|---|
| Game Analyst (1 LLM call) | ~$0.003 |
| Curated Matcher (code, no LLM) | $0 |
| Discovery Agent (1 LLM call + 5-6 Spotify searches) | ~$0.004 |
| Music Curator (1 LLM call) | ~$0.004 |
| **Total per recommendation** | **~$0.01-0.015** |

At 100 recs/day = ~$1-1.50/day. At 1000 recs/day = ~$10-15/day.

---

## Framework Decision

**v1: No framework** — Raw OpenAI SDK + agentic tool-use loop.

Reasons:
- Three agents chained together doesn't need CrewAI/LangGraph overhead
- Full control over prompts, tools, and flow
- Easy to debug (print the messages)
- Zero extra dependencies beyond `openai`

**Future (v2+)**: Consider Pydantic AI for type-safe structured outputs, or web search integration for truly fresh song discovery.

---

## Key Design Decisions

1. **Enrichment is offline**: Run `enrich_songs.py` once (or when adding songs). No enrichment cost at runtime.
2. **Three agents, clear responsibilities**: Game Analyst (reads the game), Discovery Agent (finds new songs), Music Curator (picks and explains). Curated Matcher is code, not an agent.
3. **Unique game semantics are the product**: The `song_search_direction` is a narrative, not mood labels. The `match_reasoning` ties song choices to specific game observations. This is what makes recommendations feel personal.
4. **Curated + Dynamic hybrid**: Curated DB = quality floor + community input. Discovery = variety + freshness. Music Curator blends both.
5. **Transparency is mandatory**: Every recommendation must show WHAT the agent noticed about the game and WHY it picked that song. No black-box matching.
6. **Spotify verification for all discovered songs**: No hallucinated songs reach the user. If it's not on Spotify with a real link, it's dropped.
7. **OpenAI `gpt-4.1-mini`**: Best balance of quality/cost for structured output and instruction following. ~$0.01 per full recommendation.

---

## Environment Variables

```env
OPENAI_API_KEY=sk-...
LASTFM_API_KEY=...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

## Dependencies

```
openai>=1.0.0
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## Open Questions / Future Enhancements

- **Real-time freshness**: Integrate web search or Spotify trending charts to discover songs released after the LLM's training cutoff
- **User feedback loop**: Track which recommendations users liked → feed back into curated DB and prompt engineering
- **Player history**: If we've recommended songs for this player before, avoid repeats
- **Multi-player support**: Different players in the same game get different narratives and different songs
- **Playlist generation**: Instead of top 3, generate a full replay soundtrack with intro/climax/outro sections
