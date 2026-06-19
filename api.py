"""
============================================================
CMO.AI — Marketing Strategy Agent API (FastAPI)
============================================================
Exposes the marketing agent as REST endpoints.
The frontend team calls these endpoints.

Endpoints:
  POST /strategy/generate     → Run the agent for a user
  GET  /strategy/{user_id}    → Fetch existing strategy
  GET  /health                → Health check

How to run:
    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8001

Then call:
    POST http://localhost:8001/strategy/generate
    Body: {"user_id": "abc123"}
============================================================
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from agent import MarketingStrategyAgent
from database import MarketingDB

app = FastAPI(
    title="CMO.AI — Marketing Strategy Agent",
    description="Generates complete marketing strategies from brand profiles",
    version="1.0.0"
)

# Allow frontend (Next.js on Vercel) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: set to your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────

class GenerateRequest(BaseModel):
    user_id: str
    brand_profile: Optional[dict] = None  # Optional override (for testing)


class GenerateResponse(BaseModel):
    success: bool
    user_id: str
    brand_name: Optional[str]
    strategy_text: Optional[str]
    generated_at: Optional[str]
    error: Optional[str] = None


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Simple health check — call this to verify API is running."""
    return {"status": "ok", "agent": "marketing-strategy", "version": "1.0.0"}


@app.post("/strategy/generate", response_model=GenerateResponse)
async def generate_strategy(request: GenerateRequest):
    """
    Main endpoint — triggers the marketing strategy agent.
    
    The agent will:
    1. Load brand profile from MongoDB (using user_id)
    2. Run ReAct loop with 5 marketing tools
    3. Generate full strategy
    4. Save back to MongoDB
    5. Return strategy text

    Expected call from frontend:
        POST /strategy/generate
        {"user_id": "user_abc123"}
    """
    agent = MarketingStrategyAgent()

    try:
        result = agent.run(
            user_id=request.user_id,
            brand_profile=request.brand_profile  # None = fetch from MongoDB
        )

        if "error" in result and result.get("strategy_text") is None:
            raise HTTPException(status_code=404, detail=result["error"])

        return GenerateResponse(
            success=True,
            user_id=request.user_id,
            brand_name=result.get("brand_name"),
            strategy_text=result.get("strategy_text"),
            generated_at=result.get("generated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        return GenerateResponse(
            success=False,
            user_id=request.user_id,
            brand_name=None,
            strategy_text=None,
            generated_at=None,
            error=str(e)
        )
    finally:
        agent.close()


@app.get("/strategy/{user_id}", response_model=GenerateResponse)
async def get_strategy(user_id: str):
    """
    Fetches an already-generated strategy from MongoDB.
    Content agent uses this to read the marketing plan.

    Expected call from content agent:
        GET /strategy/user_abc123
    """
    db = MarketingDB()
    try:
        strategy = db.get_marketing_strategy(user_id)
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail=f"No strategy found for user_id: {user_id}"
            )
        return GenerateResponse(
            success=True,
            user_id=user_id,
            brand_name=strategy.get("brand_name"),
            strategy_text=strategy.get("strategy_text"),
            generated_at=strategy.get("generated_at")
        )
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
