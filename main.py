## Create an app
## check what all needs to be initialised in lifecycle
## create routes : /health ,/ , /recommend , /recomend/test , /webhook/recommend 
## See if there's an app error handler corollary in FastAPI too
## run app on port 8001

import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import your existing modules
from constants import FULL_REPLAY_DATA_SAMPLE

USE_AGENTIC = os.getenv("USE_AGENTIC", "false").lower() == "true"

logger = logging.getLogger(__name__)

from recommendation_service import (
    get_song_recommendations,
)


app = FastAPI()

class RecModel(BaseModel):
    player_id:str
    replay_data:dict | None=None
    top_n:int=3


@app.get("/")
async def root():
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
                    "replay_data": "... (full replay data object)",
                },
            },
            "GET /recommend/test": "Test endpoint using sample data",
        },
        "sample_player_ids": [
            "ce45140fcd644755b01660aa2dc6977b",  # ZwyxerS
            "2b3e20011e864ad8b2437605bdf543ae",  # MeanCereal3591
            "47377aec381141e680bb1e316e553b92",  # SideSwiper420e
        ],
    }
    return docs

@app.get("/health")
async def health_check():
    """Health check endpoint for FastAPI server running inside Docker/Render"""
    return {"status":"healthy","timestamp":datetime.now(timezone.utc),"service":"song-recommendation-engine"}

@app.post("/recommend")
def recommend_songs(data:RecModel):
    """Main recommendation endpoint"""
    try:
            # Extract parameters
            
            target_player_id = data.player_id
            replay_data = data.replay_data
            top_n = data.top_n
    
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
                    "processed_at": datetime.utcnow().isoformat(),
                }
    
            status_code = 200 if result.get("success") else 400
            return JSONResponse(status_code=status_code, content=result)
    
    except Exception as e:
        logger.error(f"Error in recommend_songs: {e!s}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Internal server error: {e!s}"},
        )

    


