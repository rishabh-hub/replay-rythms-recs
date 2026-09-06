## Create an app
## check what all needs to be initialised in lifecycle
## create routes : /health ,/ , /recommend , /recomend/test , /webhook/recommend 
## See if there's an app error handler corollary in FastAPI too
## run app on port 8001

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import your existing modules
from constants import FULL_REPLAY_DATA_SAMPLE

USE_AGENTIC = os.getenv("USE_AGENTIC", "false").lower() == "true"

logger = logging.getLogger(__name__)

from recommendation_service import (
    get_song_recommendations,
)

app = FastAPI(
    # Flask 404s on a trailing slash; Starlette would 307-redirect instead.
    redirect_slashes=False,
    # Flask serves no docs routes, so neither should the port.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

class RecModel(BaseModel):
    player_id:str
    replay_data:dict | None=None
    top_n:int=3


class WebhookModel(RecModel):
    # Flask did `data.get("callback_url")` and discarded it, so any JSON type
    # was accepted. Typing this `str` would 422 requests Flask answered 200.
    callback_url: Any = None


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

            if not target_player_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "Missing required parameter: player_id",
                    },
                )

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


@app.get("/recommend/test")
def test_recommendations(
    player_id: str = "ce45140fcd644755b01660aa2dc6977b",
    top_n: int = 3,
):
    """Test endpoint using sample data"""
    try:
        result = get_song_recommendations(FULL_REPLAY_DATA_SAMPLE, player_id, top_n)

        if result.get("success"):
            result["metadata"] = {
                "used_sample_data": True,
                "method": "GET",
                "note": "This is a test endpoint using sample data",
                "processed_at": datetime.utcnow().isoformat(),
            }

        # Flask returns 200 here regardless of result["success"] - preserved.
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error in test_recommendations: {e!s}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error: {e!s}"},
        )


@app.post("/webhook/recommend")
def webhook_recommend(data: WebhookModel):
    """Webhook endpoint for asynchronous processing"""
    try:
        target_player_id = data.player_id
        replay_data = data.replay_data
        top_n = data.top_n

        if not target_player_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Missing required parameter: player_id",
                },
            )

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
                "webhook": True,
            }

        # TODO: If callback_url is provided, send result to that URL
        # This is where you'd implement the actual webhook callback

        return JSONResponse(
            content={
                "success": True,
                "message": "Recommendation processed",
                "result": result,
            }
        )

    except Exception as e:
        logger.error(f"Error in webhook_recommend: {e!s}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Internal server error: {e!s}"},
        )


# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Flask hand-rolled its body checks and returned 400 with this shape.
    # FastAPI validates before the handler runs and would return a 422 with a
    # `detail` body, so restore the original status and shape here.
    return JSONResponse(
        status_code=400,
        content={"success": False, "error": "Request must be JSON"},
    )


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Endpoint not found",
            "available_endpoints": [
                "/",
                "/health",
                "/recommend",
                "/recommend/test",
                "/webhook/recommend",
            ],
        },
    )


@app.exception_handler(500)
async def internal_error(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )
