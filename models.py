"""
============================================================
CMO.AI — Shared Data Models
============================================================
These Pydantic models define the exact shape of data that
flows between agents through MongoDB.
============================================================
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ─────────────────────────────────────────────
# INPUT: What branding agent saves to MongoDB
# ─────────────────────────────────────────────

class BrandProfile(BaseModel):
    """
    Written by: Branding Agent
    Read by: Marketing Strategy Agent

    This is the full brand identity document stored in MongoDB
    under the 'brand_profiles' collection.
    """

    # MongoDB document ID (user session or user_id)
    user_id: str = Field(..., description="Unique user identifier")

    # Core Brand Info
    brand_name: str = Field(..., description="Name of the brand")
    industry: str = Field(..., description="Industry the brand operates in")
    product_or_service: str = Field(..., description="What the brand sells")

    # Audience
    target_audience: str = Field(..., description="Who the brand is targeting")
    audience_age_range: Optional[str] = Field(None, description="e.g. 18-25, 25-40")
    audience_location: Optional[str] = Field(None, description="Country or city")

    # Brand Identity
    brand_mission: Optional[str] = Field(None, description="Brand's mission statement")
    brand_values: Optional[List[str]] = Field(default=[], description="Core brand values")
    brand_tone: Optional[str] = Field(None, description="e.g. professional, playful, bold")
    brand_colors: Optional[List[str]] = Field(default=[], description="Hex color codes")
    brand_slogan: Optional[str] = Field(None, description="Brand tagline if any")

    # Business Goals
    marketing_goal: Optional[str] = Field(None, description="e.g. Brand Awareness, Sales, Lead Gen")
    budget: Optional[float] = Field(None, description="Marketing budget in USD")
    preferred_platforms: Optional[List[str]] = Field(default=[], description="e.g. Instagram, TikTok")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="active", description="active | archived")


# ─────────────────────────────────────────────
# OUTPUT: What marketing agent saves to MongoDB
# ─────────────────────────────────────────────

class WeeklySchedule(BaseModel):
    """One week of content schedule"""
    week_number: int
    platform: str
    content_type: str        # post / reel / story / email / ad
    topic: str
    posting_day: str         # Monday, Tuesday, etc.
    posting_time: str        # e.g. 7:00 PM


class CampaignPhase(BaseModel):
    """One phase of the marketing campaign"""
    phase_number: int
    phase_name: str          # e.g. Awareness, Engagement, Conversion
    duration_weeks: int
    objective: str
    key_activities: List[str]
    budget_allocation: float  # percentage of total budget
    kpis: List[str]


class FinancialProjection(BaseModel):
    """Realistic financial model based on budget"""
    total_budget: float
    estimated_reach: int
    estimated_clicks: int
    estimated_conversions: int
    estimated_revenue: float
    cost_per_click: float
    cost_per_acquisition: float
    roas: float              # Return on Ad Spend
    assumptions: List[str]  # Transparent assumptions made


class MarketingStrategy(BaseModel):
    """
    Written by: Marketing Strategy Agent
    Read by: Content Agent, Image Agent, Video Agent

    Stored in MongoDB under 'marketing_strategies' collection.
    """

    # Links back to brand
    user_id: str
    brand_name: str

    # Strategy Core
    positioning_statement: str
    unique_value_proposition: str
    competitive_advantage: str

    # Audience Analysis
    audience_analysis: str
    audience_pain_points: List[str]
    audience_desires: List[str]

    # Campaign
    campaign_name: str
    campaign_goal: str
    campaign_duration_weeks: int
    campaign_phases: List[CampaignPhase]

    # Content Plan
    content_pillars: List[str]   # 3-5 content themes
    content_formats: List[str]   # Reels, carousels, blogs, etc.
    weekly_schedule: List[WeeklySchedule]

    # Budget
    platform_budget_breakdown: dict  # {"Instagram": 400, "TikTok": 200}
    financial_projection: FinancialProjection

    # For Content Agent — specific instructions
    content_guidelines: str      # Tone, style, dos and don'ts
    hashtag_strategy: List[str]  # Top hashtags to use
    cta_examples: List[str]      # Call-to-action phrases

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    strategy_version: int = Field(default=1)
