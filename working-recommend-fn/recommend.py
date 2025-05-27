# full_replay_data_sample and target_player_id_example = "ce45140fcd644755b01660aa2dc6977b" (ZwyxerS)
import json
import argparse # Import argparse

# Assuming these files are in the same directory or your Python path is set up
from extract_data import extract_player_and_game_data
from metrics import calculate_game_intensity, calculate_game_outcome, calculate_performance_score, calculate_teamwork_factor
from rule_engine import determine_desired_song_attributes
from threshold import (
    categorize_game_closeness, 
    categorize_intensity, 
    categorize_performance, 
    categorize_teamwork,
    # Make sure your threshold constants are also accessible if needed directly
    # or are used within these categorization functions.
    # For now, the functions encapsulate their use.
)
# Import new modules
from song_management import load_song_database
from song_matcher import find_matching_songs

# This is the sample data. In a real app, you'd fetch this based on replay_id
# For this example, we'll keep using it.
FULL_REPLAY_DATA_SAMPLE = {
  "date": "2024-11-15T19:43:35+05:30",
  "teams": {
    "blue": {
      "name": "Blue", "goals": 4, "saves": 1, "score": 1077, "shots": 6, "assists": 3,
      "players": [
        {"id": "2b3e20011e864ad8b2437605bdf543ae", "name": "MeanCereal3591", "goals": 3, "saves": 1, "assists": 1, "shooting_percentage": 60, "movement": {"total_distance": 541590, "time_supersonic_speed_percent": 3.842779}},
        {"id": "47377aec381141e680bb1e316e553b92", "name": "SideSwiper420e", "goals": 1, "saves": 0, "assists": 2, "shooting_percentage": 100, "movement": {"total_distance": 580470, "time_supersonic_speed_percent": 11.889804}},
        {"id": "cee92d16ea7a43b28d8d46fce2feee73", "name": "SohumV10", "goals": 0, "saves": 0, "assists": 0, "shooting_percentage": 0, "movement": {"total_distance": 498272, "time_supersonic_speed_percent": 4.390057}}
      ], "shooting_percentage": 66.666664
    },
    "orange": {
      "name": "Orange", "goals": 5, "saves": 2, "score": 1120, "shots": 8, "assists": 0,
      "players": [
        {"id": "ce45140fcd644755b01660aa2dc6977b", "mvp": True, "name": "ZwyxerS", "goals": 2, "saves": 1, "assists": 0, "shooting_percentage": 50, "movement": {"total_distance": 539619, "time_supersonic_speed_percent": 6.2792473}},
        {"id": "a22ada86f31a4c7594ba204b4450969d", "name": "cheems_die", "goals": 2, "saves": 0, "assists": 0, "shooting_percentage": 66.666664, "movement": {"total_distance": 593960, "time_supersonic_speed_percent": 10.0871315}},
        {"id": "60034da98a4c48eea051416df7845c71", "name": "scardrip04", "goals": 1, "saves": 1, "assists": 0, "shooting_percentage": 100, "movement": {"total_distance": 614834, "time_supersonic_speed_percent": 12.574303}}
      ], "shooting_percentage": 62.5
    }
  },
  "title": "2024-11-15.19.43 ZwyxerS Ranked Standard Win", "season": 16, "duration": 451,
  "map_name": "Urban Central", "overtime": True, "playlist": "Ranked Standard", "overtime_seconds": 59
}

def get_song_recommendation_profile(replay_data, target_player_id):
    """
    Main function to process a replay for a player and get desired song attributes.
    """
    # 1. Extract data
    extracted_info = extract_player_and_game_data(replay_data, target_player_id)
    if not extracted_info:
        # Error message already printed by extract_player_and_game_data
        return None 

    player_stats = extracted_info["player_stats"]
    player_team_stats = extracted_info["player_team_stats"]
    opponent_team_stats = extracted_info["opponent_team_stats"]
    game_duration = extracted_info["game_duration"]
    game_overtime = extracted_info["game_overtime"]

    # 2. Calculate Metrics
    intensity_score = calculate_game_intensity(player_stats, game_duration)
    performance_score = calculate_performance_score(player_stats)
    teamwork_factor = calculate_teamwork_factor(player_stats, player_team_stats)
    game_outcome_details = calculate_game_outcome(player_team_stats, opponent_team_stats)

    # 3. Categorize Metrics
    intensity_cat = categorize_intensity(intensity_score)
    performance_cat = categorize_performance(performance_score)
    teamwork_cat = categorize_teamwork(teamwork_factor)
    closeness_cat = categorize_game_closeness(game_outcome_details['abs_score_differential'], game_overtime)
    
    # 4. Determine Desired Song Attributes using Rule Engine
    desired_attributes = determine_desired_song_attributes(
        intensity_cat,
        performance_cat,
        teamwork_cat,
        game_outcome_details,
        closeness_cat
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
        "desired_song_profile": desired_attributes
    }

def main():
    parser = argparse.ArgumentParser(description="Get song recommendation profile based on game replay stats.")
    parser.add_argument("player_id", help="The ID of the player to analyze.")
    # Optional: If you want to simulate fetching replay data by ID in the future
    parser.add_argument("--replay_id", help="The ID of the replay (currently uses hardcoded sample data).", default="sample_replay")
    parser.add_argument("--top_n", type=int, default=3, help="Number of top song recommendations to show.")


    args = parser.parse_args()

    target_player_id = args.player_id
    # In a real scenario, you would use args.replay_id to fetch data from Supabase
    # For now, we use the hardcoded FULL_REPLAY_DATA_SAMPLE
    replay_data_to_use = FULL_REPLAY_DATA_SAMPLE 
    
    print(f"Analyzing replay for player ID: {target_player_id} (using sample replay data)\n")

    profile_info = get_song_recommendation_profile(replay_data_to_use, target_player_id)

    if not profile_info:
      print(f"Could not generate recommendation profile for player {target_player_id}.")
      return
    
    print("--- Desired Song Profile ---")
    # The key 'desired_song_attributes' now holds what we need for matching
    desired_attributes_for_matching = profile_info["desired_song_profile"]
    # Print the whole profile_info for debugging context
    print(json.dumps(profile_info, indent=2))
    print("\n")

     # --- Load Song Database ---
    song_db = load_song_database()
    if not song_db:
        print("Failed to load song database. Cannot provide recommendations.")
        return
    
    # --- Find Matching Songs ---
    print(f"--- Top {args.top_n} Song Recommendations ---")
    # Pass the actual desired attributes dict to the matcher
    recommended_songs = find_matching_songs(song_db, desired_attributes_for_matching, top_n=args.top_n)

    if recommended_songs:
        for i, song in enumerate(recommended_songs):
            print(f"{i+1}. \"{song['title']}\" by {song['artist']}")
            print(f"   Score: {song['match_score']}")
            print(f"   BPM: {song['bpm']}, Energy: {song['energy']}")
            print(f"   Moods: {', '.join(song.get('moods', []))}")
            print(f"   Themes: {', '.join(song.get('themes', []))}")
            print(f"   Matched on: {', '.join(song.get('matched_criteria_details', []))}")
            if song.get('source_url'):
                print(f"   Listen: {song['source_url']}")
            print("-" * 10)
    else:
        print("No suitable songs found in the database for the generated profile.")
        print("Consider expanding your song database or adjusting matching criteria/rules.")

if __name__ == "__main__":
    main()