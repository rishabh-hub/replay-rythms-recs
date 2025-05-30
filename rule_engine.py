# def determine_desired_song_attributes(
#     intensity_category, 
#     performance_category, 
#     teamwork_category, 
#     game_outcome_details, # This is the dict from calculate_game_outcome()
#     closeness_category
#     ):
#     """
#     Applies predefined rules to map game metrics to desired song attributes.
#     """
#     desired_attributes = {
#         "bpm": None,        # e.g., "High", "Medium", "Low" or a range [140, 180]
#         "energy": None,     # e.g., "High", "Medium", "Low"
#         "mood": set(),      # Can collect multiple moods, e.g., {"Tense", "Dramatic"}
#         "theme": set()      # Can collect multiple themes, e.g., {"Victory", "Energetic"}
#     }

#     # Rule 1: Intensity -> BPM
#     if intensity_category == "High":
#         desired_attributes["bpm"] = "High (140-180)" # Or store as a range: [140, 180]
#     elif intensity_category == "Medium":
#         desired_attributes["bpm"] = "Medium (110-140)" # Or store as a range: [110, 140]
#     else: # Low
#         desired_attributes["bpm"] = "Low (80-110)" # Or store as a range: [80, 110]

#     # Rule 2: Performance -> Energetic/Victory
#     # Let's make this dependent on winning for "Victory"
#     if performance_category == "High":
#         desired_attributes["energy"] = "High"
#         if game_outcome_details["win_status"] == "win":
#             desired_attributes["theme"].add("Victory")
#             desired_attributes["mood"].add("Triumphant") # More specific than just "Energetic"
#         else:
#             desired_attributes["mood"].add("Energetic") # High performance but loss/draw -> still energetic
#     elif performance_category == "Medium":
#         desired_attributes["energy"] = "Medium"
#         desired_attributes["mood"].add("Focused")
#     else: # Low performance
#         desired_attributes["energy"] = "Low"
#         if game_outcome_details["win_status"] == "loss":
#              desired_attributes["mood"].add("Reflective") # Low performance and loss
#         else:
#              desired_attributes["mood"].add("Neutral")


#     # Rule 3: Teamwork -> Collaborative/group songs
#     if teamwork_category == "High":
#         desired_attributes["theme"].add("Collaborative")
#         desired_attributes["mood"].add("Uplifting") # Often associated with teamwork
#         # If energy is not set yet, or is low, high teamwork might boost it
#         if desired_attributes["energy"] is None or desired_attributes["energy"] == "Low":
#             desired_attributes["energy"] = "Medium"


#     # Rule 4: Close games -> Tense/dramatic music
#     if closeness_category == "Very Close / Overtime":
#         desired_attributes["mood"].add("Tense")
#         desired_attributes["mood"].add("Dramatic")
#         if game_outcome_details["win_status"] == "win":
#             desired_attributes["mood"].add("Clutch") # Specific mood for close wins
#         elif game_outcome_details["win_status"] == "loss":
#             desired_attributes["mood"].add("Heartbreak") # Specific mood for close losses
#     elif closeness_category == "Moderately Close":
#         desired_attributes["mood"].add("Suspenseful")

#     # Fallback for energy if not set by performance
#     if desired_attributes["energy"] is None:
#         if intensity_category == "High":
#             desired_attributes["energy"] = "High"
#         elif intensity_category == "Medium":
#             desired_attributes["energy"] = "Medium"
#         else:
#             desired_attributes["energy"] = "Low"
            
#     # Convert sets to lists for easier JSON serialization later if needed
#     desired_attributes["mood"] = list(desired_attributes["mood"]) if desired_attributes["mood"] else None
#     desired_attributes["theme"] = list(desired_attributes["theme"]) if desired_attributes["theme"] else None
    
#     return desired_attributes

# Example Usage:
# if extracted_data:
    # ... (calculate metrics and categories as above)
#     song_attrs = determine_desired_song_attributes(
#         intensity_cat,
#         performance_cat,
#         teamwork_cat,
#         outcome, # The full outcome dictionary
#         closeness_cat
#     )
#     print(f"Desired Song Attributes: {song_attrs}")


def determine_desired_song_attributes(
    intensity_category,
    performance_category,
    teamwork_category,
    game_outcome_details,
    closeness_category
):
    """
    Maps gameplay metrics to a desired song profile, using keys that match your songs.json.
    """
    desired = {
        "bpm": None,          # e.g. "High (140-180)"
        "energy": None,       # "High", "Medium", "Low"
        "moods": [],          # list of desired song moods
        "themes": []          # list of desired song themes
    }

    # 1. Intensity → BPM range
    if intensity_category == "High":
        desired["bpm"] = "High (140-180)"
    elif intensity_category == "Medium":
        desired["bpm"] = "Medium (110-140)"
    else:
        desired["bpm"] = "Low (80-110)"

    # 2. Performance → Energy + Victory/Triumph
    if performance_category == "High":
        desired["energy"] = "High"
        if game_outcome_details.get("win_status") == "win":
            desired["themes"].append("Victory")
            desired["moods"].append("Triumphant")
        else:
            desired["moods"].append("Energetic")
    elif performance_category == "Medium":
        desired["energy"] = "Medium"
        desired["moods"].append("Focused")
    else:
        desired["energy"] = "Low"
        if game_outcome_details.get("win_status") == "loss":
            desired["moods"].append("Reflective")
        else:
            desired["moods"].append("Neutral")

    # 3. Teamwork → Collaborative + Uplifting
    if teamwork_category == "High":
        desired["themes"].append("Collaborative")
        desired["moods"].append("Uplifting")
        if desired["energy"] in (None, "Low"):
            desired["energy"] = "Medium"

    # 4. Closeness → Tense/Drama/Clutch/Heartbreak
    if closeness_category == "Very Close / Overtime":
        desired["moods"].extend(["Tense", "Dramatic"])
        if game_outcome_details.get("win_status") == "win":
            desired["moods"].append("Clutch")
        elif game_outcome_details.get("win_status") == "loss":
            desired["moods"].append("Heartbreak")
    elif closeness_category == "Moderately Close":
        desired["moods"].append("Suspenseful")

    # 5. Fallback for energy
    if desired["energy"] is None:
        if intensity_category == "High":
            desired["energy"] = "High"
        elif intensity_category == "Medium":
            desired["energy"] = "Medium"
        else:
            desired["energy"] = "Low"

    # dedupe
    desired["moods"] = list(dict.fromkeys(desired["moods"]))
    desired["themes"] = list(dict.fromkeys(desired["themes"]))

    return desired