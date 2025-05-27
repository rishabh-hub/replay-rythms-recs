from flask import Flask, request, jsonify
import json
import os
import sys
from datetime import datetime

# Add the current directory to Python path to import other modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your existing modules
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

app = Flask(__name__)

# Your existing sample data
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
    try:
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
    except Exception as e:
        app.logger.error(f"Error in get_song_recommendation_profile: {str(e)}")
        return None

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
        app.logger.error(f"Error in get_song_recommendations: {str(e)}")
        return {
            "success": False,
            "error": f"Error processing recommendation: {str(e)}"
        }

# Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker/Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "song-recommendation-engine"
    })

@app.route('/', methods=['GET'])
def api_docs():
    """API documentation endpoint"""
    docs = {
        "message": "Song Recommendation API",
        "version": "1.0.0",
        "endpoints": {
            "GET /health": "Health check endpoint",
            "GET /": "API documentation",
            "POST /recommend": {
                "description": "Get song recommendations based on replay data",
                "required_params": ["player_id"],
                "optional_params": ["replay_data", "top_n"],
                "example": {
                    "player_id": "ce45140fcd644755b01660aa2dc6977b",
                    "top_n": 3,
                    "replay_data": "... (full replay data object)"
                }
            },
            "GET /recommend/test": "Test endpoint using sample data"
        },
        "sample_player_ids": [
            "ce45140fcd644755b01660aa2dc6977b",  # ZwyxerS
            "2b3e20011e864ad8b2437605bdf543ae",  # MeanCereal3591
            "47377aec381141e680bb1e316e553b92"   # SideSwiper420e
        ]
    }
    return jsonify(docs)

@app.route('/recommend', methods=['POST'])
def recommend_songs():
    """Main recommendation endpoint"""
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON"
            }), 400
        
        data = request.get_json()
        
        # Extract parameters
        target_player_id = data.get('player_id')
        replay_data = data.get('replay_data')
        top_n = data.get('top_n', 3)
        
        # Validate required parameters
        if not target_player_id:
            return jsonify({
                "success": False,
                "error": "Missing required parameter: player_id"
            }), 400
        
        # Use provided replay data or fall back to sample data
        if not replay_data:
            replay_data = FULL_REPLAY_DATA_SAMPLE
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
                "request_id": f"{target_player_id}_{top_n}",
                "processed_at": datetime.utcnow().isoformat()
            }
        
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
        
    except Exception as e:
        app.logger.error(f"Error in recommend_songs: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/recommend/test', methods=['GET'])
def test_recommendations():
    """Test endpoint using sample data"""
    try:
        # Get query parameters
        player_id = request.args.get('player_id', 'ce45140fcd644755b01660aa2dc6977b')
        top_n = int(request.args.get('top_n', 3))
        
        # Use sample data
        result = get_song_recommendations(FULL_REPLAY_DATA_SAMPLE, player_id, top_n)
        
        if result.get("success"):
            result["metadata"] = {
                "used_sample_data": True,
                "method": "GET",
                "note": "This is a test endpoint using sample data",
                "processed_at": datetime.utcnow().isoformat()
            }
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in test_recommendations: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error: {str(e)}"
        }), 500

@app.route('/webhook/recommend', methods=['POST'])
def webhook_recommend():
    """Webhook endpoint for asynchronous processing"""
    try:
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON"
            }), 400
        
        data = request.get_json()
        
        # Extract parameters
        target_player_id = data.get('player_id')
        replay_data = data.get('replay_data')
        top_n = data.get('top_n', 3)
        callback_url = data.get('callback_url')  # Optional webhook callback
        
        if not target_player_id:
            return jsonify({
                "success": False,
                "error": "Missing required parameter: player_id"
            }), 400
        
        # For now, process synchronously (you can make this async later with Celery/Redis)
        if not replay_data:
            replay_data = FULL_REPLAY_DATA_SAMPLE
            using_sample = True
        else:
            using_sample = False
        
        result = get_song_recommendations(replay_data, target_player_id, top_n)
        
        if result.get("success"):
            result["metadata"] = {
                "used_sample_data": using_sample,
                "timestamp": replay_data.get("date"),
                "request_id": f"{target_player_id}_{top_n}",
                "processed_at": datetime.utcnow().isoformat(),
                "webhook": True
            }
        
        # TODO: If callback_url is provided, send result to that URL
        # This is where you'd implement the actual webhook callback
        
        return jsonify({
            "success": True,
            "message": "Recommendation processed",
            "result": result
        })
        
    except Exception as e:
        app.logger.error(f"Error in webhook_recommend: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "available_endpoints": ["/", "/health", "/recommend", "/recommend/test", "/webhook/recommend"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500

if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), debug=False)