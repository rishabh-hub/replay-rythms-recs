def extract_player_and_game_data(replay_data, target_player_id):
    """
    Extracts relevant data for a target player from the replay JSON.

    Args:
        replay_data (dict): The full replay JSON data.
        target_player_id (str): The ID of the player to analyze.

    Returns:
        dict: A dictionary containing 'player_stats', 'player_team_stats',
              'opponent_team_stats', and 'game_duration', or None if player not found.
    """
    game_duration = replay_data.get("duration")
    if game_duration is None:
        print("Error: Game duration not found in replay data.")
        return None

    player_stats = None
    player_team_stats = None
    opponent_team_stats = None

    for team_color, team_data in replay_data.get("teams", {}).items():
        for player in team_data.get("players", []):
            if player.get("id") == target_player_id:
                player_stats = player
                player_team_stats = team_data
                # Determine opponent team
                if team_color == "blue":
                    opponent_team_stats = replay_data.get("teams", {}).get("orange", {})
                else:
                    opponent_team_stats = replay_data.get("teams", {}).get("blue", {})
                break
        if player_stats:
            break

    if not player_stats:
        print(f"Error: Player with ID '{target_player_id}' not found.")
        return None
    if not player_team_stats:
        print(f"Error: Team data for player '{target_player_id}' not found.") # Should not happen if player is found
        return None
    if not opponent_team_stats:
        print(f"Error: Opponent team data not found.") # Should not happen if player is found and teams exist
        return None


    return {
        "player_stats": player_stats,
        "player_team_stats": player_team_stats,
        "opponent_team_stats": opponent_team_stats,
        "game_duration": game_duration,
        "game_overtime": replay_data.get("overtime", False) # Added for potential future use or context
    }

# Example Usage (assuming replay_data_sample is populated with your full sample):
# target_player_id = "ce45140fcd644755b01660aa2dc6977b" # ZwyxerS
# extracted_data = extract_player_and_game_data(replay_data_sample, target_player_id)
# if extracted_data:
#     print(f"Data for player {extracted_data['player_stats']['name']}:")
#     print(f"  Game Duration: {extracted_data['game_duration']}")
#     print(f"  Player Goals: {extracted_data['player_stats']['goals']}")
#     print(f"  Player Team Goals: {extracted_data['player_team_stats']['goals']}")
#     print(f"  Opponent Team Goals: {extracted_data['opponent_team_stats']['goals']}")