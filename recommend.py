from http.server import BaseHTTPRequestHandler
import json
import sys
import os

# Add the current directory to Python path to import other modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your existing modules (keeping everything the same)
from extract_data import extract_player_and_game_data
from metrics import calculate_game_intensity, calculate_game_outcome, calculate_performance_score, calculate_teamwork_factor
from rule_engine import determine_desired_song_attributes
from threshold import (
    categorize_game_closeness, 
    categorize_intensity, 
    categorize_performance, 
    categorize_teamwork,
)
from song_management import load_song_database
from song_matcher import find_matching_songs

# Your existing sample data (keeping it for backward compatibility)
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

# Your existing function (keeping it exactly the same)
def get_song_recommendation_profile(replay_data, target_player_id):
    """
    Main function to process a replay for a player and get desired song attributes.
    """
    # 1. Extract data
    extracted_info = extract_player_and_game_data(replay_data, target_player_id)
    if not extracted_info:
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

# New function to get song recommendations (extracted from your main())
def get_song_recommendations(replay_data, target_player_id, top_n=3):
    """
    Get song recommendations for a player based on replay data.
    Returns both the profile and recommendations.
    """
    try:
        # Get the profile
        profile_info = get_song_recommendation_profile(replay_data, target_player_id)
        
        if not profile_info:
            return {
                "success": False,
                "error": f"Could not generate recommendation profile for player {target_player_id}."
            }
        
        # Load song database
        song_db = load_song_database()
        if not song_db:
            return {
                "success": False,
                "error": "Failed to load song database."
            }
        
        # Find matching songs
        desired_attributes_for_matching = profile_info["desired_song_profile"]
        recommended_songs = find_matching_songs(song_db, desired_attributes_for_matching, top_n=top_n)
        
        return {
            "success": True,
            "profile": profile_info,
            "recommendations": recommended_songs or [],
            "player_id": target_player_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing recommendation: {str(e)}"
        }

# Vercel serverless function handler
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "No request body provided")
                return
                
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters from request
            target_player_id = request_data.get('player_id')
            replay_data = request_data.get('replay_data')
            top_n = request_data.get('top_n', 3)
            
            # Validate required parameters
            if not target_player_id:
                self._send_error(400, "Missing required parameter: player_id")
                return
            
            # Use provided replay data or fall back to sample data
            if not replay_data:
                replay_data = FULL_REPLAY_DATA_SAMPLE
                # Add a note that sample data was used
                using_sample = True
            else:
                using_sample = False
            
            # Get recommendations
            result = get_song_recommendations(replay_data, target_player_id, top_n)
            
            # Add metadata
            if result.get("success"):
                result["metadata"] = {
                    "used_sample_data": using_sample,
                    "timestamp": replay_data.get("date"),
                    "request_id": f"{target_player_id}_{top_n}"
                }
            
            self._send_json_response(result)
            
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON in request body")
        except Exception as e:
            self._send_error(500, f"Internal server error: {str(e)}")
    
    def do_GET(self):
        # Handle GET requests - useful for testing
        # Can use query parameters for basic testing
        from urllib.parse import urlparse, parse_qs
        
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            player_id = query_params.get('player_id', [None])[0]
            top_n = int(query_params.get('top_n', [3])[0])
            
            if not player_id:
                # Return API documentation
                docs = {
                    "message": "Song Recommendation API",
                    "endpoints": {
                        "POST /": {
                            "description": "Get song recommendations based on replay data",
                            "required_params": ["player_id"],
                            "optional_params": ["replay_data", "top_n"],
                            "example": {
                                "player_id": "ce45140fcd644755b01660aa2dc6977b",
                                "top_n": 3,
                                "replay_data": "... (full replay data object)"
                            }
                        },
                        "GET /?player_id=ID&top_n=N": {
                            "description": "Test endpoint using sample data"
                        }
                    },
                    "sample_player_ids": [
                        "ce45140fcd644755b01660aa2dc6977b",  # ZwyxerS
                        "2b3e20011e864ad8b2437605bdf543ae",  # MeanCereal3591
                        "47377aec381141e680bb1e316e553b92"   # SideSwiper420e
                    ]
                }
                self._send_json_response(docs)
                return
            
            # Use sample data for GET requests
            result = get_song_recommendations(FULL_REPLAY_DATA_SAMPLE, player_id, top_n)
            result["metadata"] = {
                "used_sample_data": True,
                "method": "GET",
                "note": "This is a test endpoint using sample data"
            }
            
            self._send_json_response(result)
            
        except Exception as e:
            self._send_error(500, f"Error: {str(e)}")
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _send_json_response(self, data, status_code=200):
        """Helper method to send JSON responses"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def _send_error(self, status_code, message):
        """Helper method to send error responses"""
        error_response = {
            "success": False,
            "error": message,
            "status_code": status_code
        }
        self._send_json_response(error_response, status_code)


# Keep your original main() function for command-line usage
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Get song recommendation profile based on game replay stats.")
    parser.add_argument("player_id", help="The ID of the player to analyze.")
    parser.add_argument("--replay_id", help="The ID of the replay (currently uses hardcoded sample data).", default="sample_replay")
    parser.add_argument("--top_n", type=int, default=3, help="Number of top song recommendations to show.")

    args = parser.parse_args()

    target_player_id = args.player_id
    replay_data_to_use = FULL_REPLAY_DATA_SAMPLE 
    
    print(f"Analyzing replay for player ID: {target_player_id} (using sample replay data)\n")

    profile_info = get_song_recommendation_profile(replay_data_to_use, target_player_id)

    if not profile_info:
      print(f"Could not generate recommendation profile for player {target_player_id}.")
      return
    
    print("--- Desired Song Profile ---")
    desired_attributes_for_matching = profile_info["desired_song_profile"]
    print(json.dumps(profile_info, indent=2))
    print("\n")

    song_db = load_song_database()
    if not song_db:
        print("Failed to load song database. Cannot provide recommendations.")
        return
    
    print(f"--- Top {args.top_n} Song Recommendations ---")
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