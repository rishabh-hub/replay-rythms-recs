def calculate_game_intensity(player_stats, game_duration):
    """
    Calculates the Game Intensity score.
    Formula: (total_distance / duration) + (supersonic_speed_percent * 2)
    """
    if game_duration == 0: # Avoid division by zero
        return 0

    total_distance = player_stats.get("movement", {}).get("total_distance", 0)
    supersonic_percent = player_stats.get("movement", {}).get("time_supersonic_speed_percent", 0)

    # Assuming total_distance is in some unit that makes sense when divided by seconds.
    # If total_distance is very large (e.g., cm), you might want to scale it.
    # For Rocket League, distances are often in Unreal Units (uu).
    # Let's assume the raw value is fine for now, or needs scaling later.
    # For example, if total_distance / duration gives a value around 1000-2000
    # and supersonic_percent * 2 gives a value around 0-100, the distance part dominates.
    # You might want to normalize or weight these components differently if one overshadows the other too much.
    # For now, sticking to your formula:
    intensity = (total_distance / game_duration) + (supersonic_percent * 2)
    return intensity

def calculate_performance_score(player_stats):
    """
    Calculates the Performance Score.
    Formula: (goals * 100) + (saves * 50) + (shooting_percentage)
    """
    goals = player_stats.get("goals", 0)
    saves = player_stats.get("saves", 0)
    shooting_percentage = player_stats.get("shooting_percentage", 0.0)

    performance = (goals * 100) + (saves * 50) + shooting_percentage
    return performance

def calculate_teamwork_factor(player_stats, player_team_stats):
    """
    Calculates the Teamwork Factor.
    Formula: assists / total_team_goals
    """
    assists = player_stats.get("assists", 0)
    total_team_goals = player_team_stats.get("goals", 0)

    if total_team_goals == 0:
        return 0.0  # Or handle as per your preference (e.g., if player has assists but team goals is 0, this is weird)
    
    teamwork = assists / total_team_goals
    return teamwork

def calculate_game_outcome(player_team_stats, opponent_team_stats):
    """
    Determines game outcome (win/loss) and score differential for the player's team.
    """
    player_team_goals = player_team_stats.get("goals", 0)
    opponent_team_goals = opponent_team_stats.get("goals", 0)

    score_differential = player_team_goals - opponent_team_goals # Positive if win, negative if loss

    if score_differential > 0:
        win_status = "win"
    elif score_differential < 0:
        win_status = "loss"
    else:
        win_status = "draw" # Should not happen in Rocket League typical modes unless it's pre-overtime

    # We are interested in the absolute difference for "closeness"
    abs_score_differential = abs(score_differential)
    
    return {
        "win_status": win_status,
        "score_differential": score_differential, # Actual diff
        "abs_score_differential": abs_score_differential # Absolute diff for closeness
    }

# Example of calculating all metrics:
# if extracted_data:
#     intensity = calculate_game_intensity(extracted_data['player_stats'], extracted_data['game_duration'])
#     performance = calculate_performance_score(extracted_data['player_stats'])
#     teamwork = calculate_teamwork_factor(extracted_data['player_stats'], extracted_data['player_team_stats'])
#     outcome = calculate_game_outcome(extracted_data['player_team_stats'], extracted_data['opponent_team_stats'])

#     print(f"  Intensity: {intensity:.2f}")
#     print(f"  Performance: {performance:.2f}")
#     print(f"  Teamwork: {teamwork:.2f}")
#     print(f"  Outcome: {outcome}")