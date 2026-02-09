"""
Game Narrative Analyst Agent (Phase 2)

Replaces metrics.py + threshold.py + rule_engine.py with a single LLM call
that reads the STORY of a game from stat combinations, producing a rich
narrative instead of mood labels.
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

# Deterministic fallback imports
from metrics import (
    calculate_game_intensity,
    calculate_game_outcome,
    calculate_performance_score,
    calculate_teamwork_factor,
)
from threshold import (
    categorize_game_closeness,
    categorize_intensity,
    categorize_performance,
    categorize_teamwork,
)
from rule_engine import determine_desired_song_attributes

load_dotenv()

SYSTEM_PROMPT = """You are a Rocket League game analyst. You read raw post-game stats and produce a vivid, specific narrative about what happened in the game — from the perspective of ONE target player.

## Rocket League Domain Knowledge

- **Boost starving**: High small-pad pickups + low boost = denying opponent resources = tactical play
- **Ballchasing**: High speed + many touches + low passing = not rotating properly, selfish play
- **Rotation**: Balanced positioning across team = disciplined play
- **Double commit**: When stats show both teammates doing the same thing = disorganized
- **Demo plays**: High demos = physical, aggressive playstyle
- **Aerial mastery**: High aerial goals/touches = mechanical skill, flashy plays
- **Overtime context**: Everything in OT is amplified — saves matter more, goals are clutch
- **Score differential**: 1-0 feels completely different from 7-1
- **Comeback vs blowout**: Being down 0-3 and winning 4-3 is a COMPLETELY different story than leading 4-0 and winning 4-3

## Player Archetypes

Choose the most fitting archetype for the target player based on their stats IN CONTEXT:

- **The Guardian**: High saves, low goals, defensive anchor — the quiet backbone
- **The One-Man Army**: High goals, low assists, solo carry — did it all alone
- **The Conductor**: High assists, orchestrated the offense — made teammates shine
- **The Chaos Agent**: High speed, lots of shots but low accuracy — frenetic, reckless energy
- **The Phoenix**: Part of a comeback — refused to quit, rose from the ashes
- **The Enforcer**: High demos + high speed — physical domination
- **The Streak**: Multiple goals in short time — explosive hot streak
- **The Clutch Artist**: Key contributions in overtime or final moments — ice in their veins
- **The Complete Package**: Balanced goals/assists/saves — versatile, did everything
- **The Troll**: High movement but zero meaningful contributions — along for the ride
- **The Heartbroken Star**: High stats but lost — carried hard but it wasn't enough

## Critical Instructions

1. Read stat COMBINATIONS, not individual stats. "3 goals" means different things depending on:
   - Assists (solo carry vs team player)
   - Game score (close vs blowout)
   - Overtime (clutch vs comfortable)
   - Team contribution share (carried vs contributed)

2. The narrative should be vivid and specific to THIS game. No generic descriptions.

3. The song_search_direction should describe the STORY a song should tell — NOT mood labels like "energetic" or "triumphant". Think: "songs about being the last one standing when everything went wrong" not "sad, reflective songs".

4. Always respond with valid JSON matching the exact schema specified."""

USER_PROMPT_TEMPLATE = """Analyze this Rocket League game for the target player and produce a game narrative.

## Target Player Stats
- Name: {player_name}
- Goals: {player_goals}
- Assists: {player_assists}
- Saves: {player_saves}
- Shooting %: {player_shooting_pct}%
- MVP: {is_mvp}
- Total Distance: {total_distance}
- Supersonic Speed %: {supersonic_pct}%

## Player's Team ({team_name})
- Team Goals: {team_goals}
- Team Saves: {team_saves}
- Team Shots: {team_shots}
- Team Shooting %: {team_shooting_pct}%
- Team Assists: {team_assists}

## Opponent Team
- Opponent Goals: {opp_goals}
- Opponent Saves: {opp_saves}
- Opponent Shots: {opp_shots}

## Game Context
- Duration: {duration} seconds
- Overtime: {overtime} ({overtime_seconds}s of OT)
- Final Score: {team_goals} - {opp_goals} ({win_loss})
- Score Differential: {score_diff}
- Map: {map_name}

Respond with this exact JSON structure:
{{
  "narrative": "1-2 sentence vivid game story from this player's perspective",
  "key_observations": ["3-5 specific insights drawn from stat COMBINATIONS, not individual stats"],
  "player_archetype": "One of the archetypes listed above, with a short dash explanation",
  "emotional_arc": "How the game felt over time for this player",
  "song_search_direction": "2-3 sentence narrative description of what kind of song to find. Describe the STORY the song should tell, not mood labels."
}}"""

REQUIRED_FIELDS = ["narrative", "key_observations", "player_archetype", "emotional_arc", "song_search_direction"]


def analyze_game(extracted_data: dict) -> dict:
    """
    Core Phase 2 function. Sends extracted game data to gpt-4.1-mini
    to produce a rich game narrative instead of deterministic mood labels.

    Returns a dict with: narrative, key_observations, player_archetype,
    emotional_arc, song_search_direction.

    Falls back to deterministic analysis if the LLM call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your"):
        print("Warning: No valid OPENAI_API_KEY found. Using deterministic fallback.")
        return _fallback_analysis(extracted_data)

    player = extracted_data["player_stats"]
    team = extracted_data["player_team_stats"]
    opponent = extracted_data["opponent_team_stats"]

    # Determine win/loss
    team_goals = team.get("goals", 0)
    opp_goals = opponent.get("goals", 0)
    if team_goals > opp_goals:
        win_loss = "WIN"
    elif team_goals < opp_goals:
        win_loss = "LOSS"
    else:
        win_loss = "DRAW"

    # Determine team name/color
    team_name = team.get("name", "Unknown")

    # Build user prompt
    overtime = extracted_data.get("game_overtime", False)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        player_name=player.get("name", "Unknown"),
        player_goals=player.get("goals", 0),
        player_assists=player.get("assists", 0),
        player_saves=player.get("saves", 0),
        player_shooting_pct=player.get("shooting_percentage", 0),
        is_mvp="Yes" if player.get("mvp", False) else "No",
        total_distance=player.get("movement", {}).get("total_distance", 0),
        supersonic_pct=round(player.get("movement", {}).get("time_supersonic_speed_percent", 0), 2),
        team_name=team_name,
        team_goals=team_goals,
        team_saves=team.get("saves", 0),
        team_shots=team.get("shots", 0),
        team_shooting_pct=team.get("shooting_percentage", 0),
        team_assists=team.get("assists", 0),
        opp_goals=opp_goals,
        opp_saves=opponent.get("saves", 0),
        opp_shots=opponent.get("shots", 0),
        duration=extracted_data.get("game_duration", 0),
        overtime="Yes" if overtime else "No",
        overtime_seconds=extracted_data.get("overtime_seconds", 0) if overtime else 0,
        win_loss=win_loss,
        score_diff=team_goals - opp_goals,
        map_name=extracted_data.get("map_name", "Unknown"),
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        analysis = json.loads(content)

        # Validate all required fields exist
        for field in REQUIRED_FIELDS:
            if field not in analysis:
                print(f"Warning: LLM response missing '{field}'. Using fallback.")
                return _fallback_analysis(extracted_data)

        return analysis

    except Exception as e:
        print(f"Warning: LLM call failed ({e}). Using deterministic fallback.")
        return _fallback_analysis(extracted_data)


def _fallback_analysis(extracted_data: dict) -> dict:
    """
    Deterministic fallback using the old metrics/threshold/rule_engine pipeline.
    Produces a basic analysis when the LLM is unavailable.
    """
    player = extracted_data["player_stats"]
    team = extracted_data["player_team_stats"]
    opponent = extracted_data["opponent_team_stats"]
    duration = extracted_data["game_duration"]
    overtime = extracted_data.get("game_overtime", False)

    # Run old pipeline
    intensity_score = calculate_game_intensity(player, duration)
    performance_score = calculate_performance_score(player)
    teamwork_factor = calculate_teamwork_factor(player, team)
    outcome = calculate_game_outcome(team, opponent)

    intensity_cat = categorize_intensity(intensity_score)
    performance_cat = categorize_performance(performance_score)
    teamwork_cat = categorize_teamwork(teamwork_factor)
    closeness_cat = categorize_game_closeness(outcome["abs_score_differential"], overtime)

    desired = determine_desired_song_attributes(
        intensity_cat, performance_cat, teamwork_cat, outcome, closeness_cat
    )

    # Build a basic narrative from the categories
    player_name = player.get("name", "Unknown")
    win_status = outcome["win_status"]

    narrative = f"{player_name} had a {performance_cat.lower()} performance "
    if win_status == "win":
        narrative += f"in a {closeness_cat.lower()} win."
    elif win_status == "loss":
        narrative += f"in a {closeness_cat.lower()} loss."
    else:
        narrative += "in a draw."

    # Basic archetype from categories
    if performance_cat == "High" and teamwork_cat == "Low":
        archetype = "The One-Man Army"
    elif teamwork_cat == "High":
        archetype = "The Conductor"
    elif player.get("saves", 0) > player.get("goals", 0):
        archetype = "The Guardian"
    elif performance_cat == "Low" and win_status == "loss":
        archetype = "The Troll"
    else:
        archetype = "The Complete Package"

    return {
        "narrative": narrative,
        "key_observations": [
            f"Performance: {performance_cat} ({round(performance_score, 1)} pts)",
            f"Intensity: {intensity_cat}",
            f"Teamwork: {teamwork_cat}",
            f"Game closeness: {closeness_cat}",
        ],
        "player_archetype": archetype,
        "emotional_arc": f"A {intensity_cat.lower()}-intensity {win_status}",
        "song_search_direction": f"Songs matching {desired['energy']} energy, {', '.join(desired['moods'])} mood.",
        "_fallback": True,
        "_desired_profile": desired,
    }


def analyst_output_to_song_profile(analysis: dict) -> dict:
    """
    Bridge function: converts the Game Analyst's narrative output into the
    {bpm, energy, moods, themes} format that song_matcher.py expects.

    This is TEMPORARY for Phase 2. Phase 3+ will use the narrative directly
    via the Music Curator agent.
    """
    # If fallback was used, the old desired_profile is already computed
    if analysis.get("_fallback") and analysis.get("_desired_profile"):
        return analysis["_desired_profile"]

    # --- Energy ---
    energy = _infer_energy(analysis)

    # --- BPM range from energy ---
    if energy == "High":
        bpm = "High (140-180)"
    elif energy == "Medium":
        bpm = "Medium (110-140)"
    else:
        bpm = "Low (80-110)"

    # --- Moods from key_observations + emotional_arc ---
    moods = _extract_moods(analysis)

    # --- Themes from narrative + player_archetype ---
    themes = _extract_themes(analysis)

    return {
        "bpm": bpm,
        "energy": energy,
        "moods": moods,
        "themes": themes,
    }


# ── Bridge helpers ──────────────────────────────────────────────────

# Mood vocabulary from the existing song database
MOOD_KEYWORDS = {
    "Triumphant": ["triumph", "victorious", "champion", "conquer", "glory", "crowned"],
    "Energetic": ["energy", "intense", "explosive", "fire", "adrenaline", "relentless", "frenetic"],
    "Uplifting": ["uplift", "inspiring", "hope", "rise", "soar", "overcome"],
    "Tense": ["tense", "pressure", "nerve", "edge", "wire", "nail-biting"],
    "Dramatic": ["dramatic", "epic", "climax", "stakes", "cinematic"],
    "Clutch": ["clutch", "last-second", "final moment", "overtime", "buzzer", "ice in"],
    "Heartbreak": ["heartbreak", "heartbroken", "devastat", "so close", "agoniz", "cruel"],
    "Reflective": ["reflect", "quiet", "subdued", "contemplat", "thoughtful", "passenger"],
    "Focused": ["focused", "precise", "calculated", "methodical", "disciplin"],
    "Suspenseful": ["suspense", "uncertain", "back and forth", "seesaw"],
    "Melancholic": ["melanchol", "sad", "sorrow", "lost", "empty"],
    "Confident": ["confident", "swagger", "dominant", "command", "control"],
    "Defiant": ["defiant", "refuse", "never give up", "comeback", "wouldn't quit", "phoenix"],
    "Chaotic": ["chaos", "chaotic", "wild", "reckless", "frantic", "mayhem"],
    "Nostalgic": ["nostalgic", "memory", "remember", "looking back"],
}

THEME_KEYWORDS = {
    "Victory": ["win", "won", "victory", "champion", "triumph", "conquer"],
    "Defeat": ["loss", "lost", "defeat", "fell short", "wasn't enough"],
    "Comeback": ["comeback", "came back", "down and rose", "phoenix", "refused to quit"],
    "Solo Carry": ["solo", "alone", "carried", "one-man", "single-handed", "by themselves"],
    "Teamwork": ["team", "together", "assist", "passing", "collaborat", "conductor", "orchestrat"],
    "Resilience": ["resilience", "resilient", "endure", "survive", "fought", "grind"],
    "Celebration": ["celebrat", "party", "joy", "euphori"],
    "Redemption": ["redemption", "redeem", "atone", "make up for"],
    "Dominance": ["dominat", "destroy", "blowout", "crushed", "unstoppable"],
    "Underdog": ["underdog", "unexpected", "surprise", "against the odds"],
    "Collaborative": ["collaborat", "together", "crew", "unit", "squad"],
}


def _infer_energy(analysis: dict) -> str:
    """Infer energy level from archetype and emotional arc."""
    archetype = analysis.get("player_archetype", "").lower()
    arc = analysis.get("emotional_arc", "").lower()
    narrative = analysis.get("narrative", "").lower()
    direction = analysis.get("song_search_direction", "").lower()

    all_text = f"{archetype} {arc} {narrative} {direction}"

    high_signals = ["intense", "explosive", "relentless", "chaos", "frenetic", "adrenaline",
                    "army", "enforcer", "streak", "fire", "domina", "carry", "unstoppable"]
    low_signals = ["quiet", "reflective", "subdued", "passenger", "troll", "empty",
                   "contemplat", "melanchol", "gentle", "soft"]

    high_count = sum(1 for s in high_signals if s in all_text)
    low_count = sum(1 for s in low_signals if s in all_text)

    if high_count > low_count:
        return "High"
    elif low_count > high_count:
        return "Low"
    return "Medium"


def _extract_moods(analysis: dict) -> list:
    """Extract mood labels by matching keywords against observations and emotional arc."""
    text = " ".join([
        analysis.get("emotional_arc", ""),
        " ".join(analysis.get("key_observations", [])),
        analysis.get("narrative", ""),
        analysis.get("song_search_direction", ""),
    ]).lower()

    matched = []
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(mood)

    # Always return at least one mood
    if not matched:
        matched = ["Energetic"]

    return matched


def _extract_themes(analysis: dict) -> list:
    """Extract theme labels by matching keywords against narrative and archetype."""
    text = " ".join([
        analysis.get("narrative", ""),
        analysis.get("player_archetype", ""),
        " ".join(analysis.get("key_observations", [])),
        analysis.get("song_search_direction", ""),
    ]).lower()

    matched = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(theme)

    if not matched:
        matched = ["Victory"] if "win" in text or "won" in text else ["Resilience"]

    return matched
