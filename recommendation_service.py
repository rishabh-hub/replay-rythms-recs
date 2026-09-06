"""
Framework-agnostic recommendation logic.

Imported by the FastAPI app (main.py). Kept separate from the web layer so the
recommendation pipeline stays framework-agnostic - this is what allowed the
Flask and FastAPI apps to be diffed against identical logic during the
migration.
"""

import logging
import os

from extract_data import extract_player_and_game_data
from game_analyst import analyst_output_to_song_profile, analyze_game
from metrics import (
    calculate_game_intensity,
    calculate_game_outcome,
    calculate_performance_score,
    calculate_teamwork_factor,
)
from rule_engine import determine_desired_song_attributes
from song_management import load_song_database
from song_matcher import find_matching_songs
from threshold import (
    categorize_game_closeness,
    categorize_intensity,
    categorize_performance,
    categorize_teamwork,
)

USE_AGENTIC = os.getenv("USE_AGENTIC", "false").lower() == "true"

logger = logging.getLogger(__name__)


def get_song_recommendation_profile(replay_data, target_player_id):
    """
    Main function to process a replay for a player and get desired song attributes.
    """
    try:
        # 1. Extract data
        extracted_info = extract_player_and_game_data(replay_data, target_player_id)
        if not extracted_info:
            return None

        player_stats = extracted_info.get("player_stats")
        player_team_stats = extracted_info.get("player_team_stats")
        opponent_team_stats = extracted_info.get("opponent_team_stats")
        game_duration = extracted_info.get("game_duration")
        game_overtime = extracted_info.get("game_overtime")

        # 2. Calculate Metrics
        intensity_score = calculate_game_intensity(player_stats, game_duration)
        performance_score = calculate_performance_score(player_stats)
        teamwork_factor = calculate_teamwork_factor(player_stats, player_team_stats)
        game_outcome_details = calculate_game_outcome(
            player_team_stats, opponent_team_stats
        )

        # 3. Categorize Metrics
        intensity_cat = categorize_intensity(intensity_score)
        performance_cat = categorize_performance(performance_score)
        teamwork_cat = categorize_teamwork(teamwork_factor)
        closeness_cat = categorize_game_closeness(
            game_outcome_details.get("abs_score_differential"), game_overtime
        )

        # 4. Determine Desired Song Attributes using Rule Engine
        desired_attributes = determine_desired_song_attributes(
            intensity_cat,
            performance_cat,
            teamwork_cat,
            game_outcome_details,
            closeness_cat,
        )

        return {
            "player_name": player_stats.get("name"),
            "metrics": {
                "intensity_score": round(intensity_score, 2),
                "performance_score": round(performance_score, 2),
                "teamwork_factor": round(teamwork_factor, 2),
                "game_outcome": game_outcome_details,
            },
            "categories": {
                "intensity": intensity_cat,
                "performance": performance_cat,
                "teamwork": teamwork_cat,
                "closeness": closeness_cat,
            },
            "desired_song_profile": desired_attributes,
        }
    except TypeError as e:
        logger.error(f"Error in get_song_recommendation_profile: {e!s}")
        return None


def get_agentic_recommendation_profile(replay_data, target_player_id):
    """
    Agentic pipeline: uses the Game Narrative Analyst LLM to read the story
    of the game, then bridges the output to the old matcher format.
    """
    extracted_info = extract_player_and_game_data(replay_data, target_player_id)
    if not extracted_info:
        return None

    game_reading = analyze_game(extracted_info)
    desired_song_profile = analyst_output_to_song_profile(game_reading)

    return {
        "player_name": extracted_info["player_stats"].get("name"),
        "game_reading": game_reading,
        "desired_song_profile": desired_song_profile,
    }


def get_song_recommendations(replay_data, target_player_id, top_n=3):
    """
    Get song recommendations for a player based on replay data.
    Returns both the profile and recommendations.
    Uses agentic LLM pipeline when USE_AGENTIC is true.
    """
    try:
        if USE_AGENTIC:
            profile_info = get_agentic_recommendation_profile(
                replay_data, target_player_id
            )
        else:
            profile_info = get_song_recommendation_profile(
                replay_data, target_player_id
            )

        if not profile_info:
            return {
                "success": False,
                "error": f"Could not generate recommendation profile for player {target_player_id}.",
            }

        # Load song database (enriched when agentic)
        song_db = load_song_database(agentic=USE_AGENTIC)
        if not song_db:
            return {"success": False, "error": "Failed to load song database."}

        # Find matching songs
        desired_attributes_for_matching = profile_info["desired_song_profile"]
        recommended_songs = find_matching_songs(
            song_db, desired_attributes_for_matching, top_n=top_n
        )

        result = {
            "success": True,
            "profile": profile_info,
            "recommendations": recommended_songs or [],
            "player_id": target_player_id,
        }

        # Include game_reading in output when agentic
        if USE_AGENTIC and "game_reading" in profile_info:
            result["game_reading"] = profile_info["game_reading"]

        return result

    except Exception as e:
        logger.error(f"Error in get_song_recommendations: {e!s}")
        return {"success": False, "error": f"Error processing recommendation: {e!s}"}
