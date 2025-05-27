# --- Threshold Definitions ---
# These are initial guesses and WILL need tuning based on observed metric ranges!
# For Intensity: Rocket League avg speed is ~1300-1500 uu/s. Supersonic is ~2200 uu/s.
# (total_distance / duration) could be around 1400.
# (supersonic_speed_percent * 2) could be around (e.g. 20% supersonic * 2) = 40.
# So intensity might range from 1000 to 2000+.
INTENSITY_THRESHOLD_HIGH = 1400 # e.g. avg_speed of 1460 + 20% supersonic_time*2
INTENSITY_THRESHOLD_LOW = 1100

# For Performance: 1 goal = 100. 1 save = 50. Max shooting % = 100.
# A good game could be 2 goals (200) + 2 saves (100) + 60% shooting (60) = 360
PERFORMANCE_THRESHOLD_HIGH = 300
PERFORMANCE_THRESHOLD_LOW = 100 # e.g. 1 goal or 2 saves

# For Teamwork: assists / team_goals. Ranges from 0 to 1 (or more if multiple players assist one goal, though typically 1).
# If 3 team goals and player has 1 assist, factor is 0.33. If 2 assists, 0.66.
TEAMWORK_THRESHOLD_HIGH = 0.5 # Player involved in at least half the team's goals via assists
TEAMWORK_THRESHOLD_LOW = 0.2

# For Game Outcome Closeness:
# abs_score_differential is the absolute difference in goals.
# 0 or 1 goal difference is very close. 2 goals is somewhat close. 3+ is not.
SCORE_DIFFERENTIAL_CLOSE = 1 # Game decided by 1 goal or less (e.g. OT)
SCORE_DIFFERENTIAL_MODERATE = 2 # Game decided by 2 goals

# --- Categorization Functions ---
def categorize_intensity(intensity_score):
    if intensity_score >= INTENSITY_THRESHOLD_HIGH:
        return "High"
    elif intensity_score <= INTENSITY_THRESHOLD_LOW:
        return "Low"
    else:
        return "Medium"

def categorize_performance(performance_score):
    if performance_score >= PERFORMANCE_THRESHOLD_HIGH:
        return "High"
    elif performance_score <= PERFORMANCE_THRESHOLD_LOW:
        return "Low"
    else:
        return "Medium"

def categorize_teamwork(teamwork_factor):
    if teamwork_factor >= TEAMWORK_THRESHOLD_HIGH:
        return "High"
    elif teamwork_factor <= TEAMWORK_THRESHOLD_LOW:
        return "Low"
    else:
        return "Medium"

def categorize_game_closeness(abs_score_differential, is_overtime):
    if is_overtime or abs_score_differential <= SCORE_DIFFERENTIAL_CLOSE:
        return "Very Close / Overtime"
    elif abs_score_differential <= SCORE_DIFFERENTIAL_MODERATE:
        return "Moderately Close"
    else:
        return "Not Close"

# Example Usage:
# if extracted_data:
    # ... (calculate metrics as above)
#     intensity_cat = categorize_intensity(intensity)
#     performance_cat = categorize_performance(performance)
#     teamwork_cat = categorize_teamwork(teamwork)
#     closeness_cat = categorize_game_closeness(outcome['abs_score_differential'], extracted_data['game_overtime'])

#     print(f"  Intensity Category: {intensity_cat}")
#     print(f"  Performance Category: {performance_cat}")
#     print(f"  Teamwork Category: {teamwork_cat}")
#     print(f"  Closeness Category: {closeness_cat}")