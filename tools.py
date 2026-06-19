"""
============================================================
CMO.AI — Marketing Agent Tools
============================================================
These are the REAL tools the LangChain agent can call.
Each tool does deterministic calculations — no LLM guessing
for numbers. The LLM uses these results to reason and write
the strategy narrative.

Tools:
  1. budget_allocator      → splits budget per platform
  2. financial_projector   → realistic ROI estimates
  3. platform_recommender  → best platforms per audience
  4. campaign_structurer   → builds campaign phase timeline
  5. competitor_analyzer   → positioning opportunities
  6. kpi_generator         → goal-specific KPIs
============================================================
"""

import json
from langchain.tools import tool


# ─────────────────────────────────────────────────────────
# Platform-specific benchmarks (industry averages 2024)
# Source: WordStream, HubSpot, Statista averages
# ─────────────────────────────────────────────────────────

PLATFORM_BENCHMARKS = {
    "Instagram": {"cpc": 0.70, "ctr": 0.022, "cvr": 0.032, "best_for": ["fashion", "beauty", "food", "lifestyle", "fitness"]},
    "TikTok":    {"cpc": 0.50, "ctr": 0.030, "cvr": 0.025, "best_for": ["entertainment", "fashion", "gaming", "youth", "trends"]},
    "Facebook":  {"cpc": 0.97, "ctr": 0.019, "cvr": 0.040, "best_for": ["local business", "real estate", "finance", "b2c"]},
    "LinkedIn":  {"cpc": 5.26, "ctr": 0.008, "cvr": 0.060, "best_for": ["b2b", "saas", "recruitment", "professional services"]},
    "YouTube":   {"cpc": 0.49, "ctr": 0.012, "cvr": 0.028, "best_for": ["education", "tech", "tutorials", "brand storytelling"]},
    "Twitter":   {"cpc": 0.38, "ctr": 0.015, "cvr": 0.020, "best_for": ["tech", "news", "community", "startups"]},
    "Pinterest": {"cpc": 1.50, "ctr": 0.018, "cvr": 0.035, "best_for": ["home decor", "diy", "weddings", "food", "fashion"]},
}

GOAL_BUDGET_SPLIT = {
    "Brand Awareness":  {"paid_ads": 0.50, "content": 0.30, "influencer": 0.20},
    "Increase Sales":   {"paid_ads": 0.65, "content": 0.20, "influencer": 0.15},
    "Lead Generation":  {"paid_ads": 0.60, "content": 0.30, "influencer": 0.10},
}


# ─────────────────────────────────────────────────────────
# TOOL 1: Budget Allocator
# ─────────────────────────────────────────────────────────

@tool
def budget_allocator(input_json: str) -> str:
    """
    Splits a marketing budget across platforms and categories.
    Call this FIRST to understand budget distribution.

    Input JSON fields:
        budget (float): Total marketing budget in USD
        platforms (list): Selected platforms e.g. ["Instagram", "TikTok"]
        goal (str): "Brand Awareness" | "Increase Sales" | "Lead Generation"

    Returns a JSON string with per-platform and per-category breakdown.
    """
    try:
        data = json.loads(input_json)
        budget = float(data["budget"])
        platforms = data["platforms"]
        goal = data.get("goal", "Brand Awareness")

        # Get split ratios for the goal
        splits = GOAL_BUDGET_SPLIT.get(goal, GOAL_BUDGET_SPLIT["Brand Awareness"])

        paid_budget = budget * splits["paid_ads"]
        content_budget = budget * splits["content"]
        influencer_budget = budget * splits["influencer"]

        # Distribute paid budget across platforms (weighted by CTR)
        total_ctr = sum(PLATFORM_BENCHMARKS.get(p, {}).get("ctr", 0.02) for p in platforms)
        platform_breakdown = {}

        for platform in platforms:
            bench = PLATFORM_BENCHMARKS.get(platform, {"ctr": 0.02})
            weight = bench["ctr"] / total_ctr if total_ctr > 0 else 1 / len(platforms)
            platform_breakdown[platform] = round(paid_budget * weight, 2)

        result = {
            "total_budget": budget,
            "goal": goal,
            "category_split": {
                "paid_ads": round(paid_budget, 2),
                "content_creation": round(content_budget, 2),
                "influencer_marketing": round(influencer_budget, 2)
            },
            "platform_paid_budget": platform_breakdown,
            "recommendation": f"For '{goal}', {int(splits['paid_ads']*100)}% goes to paid ads distributed across your platforms."
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 2: Financial Projector
# ─────────────────────────────────────────────────────────

@tool
def financial_projector(input_json: str) -> str:
    """
    Projects realistic financial outcomes: clicks, conversions, revenue, ROAS.
    Uses real industry benchmark data per platform — NOT guesses.
    Call this after budget_allocator to get ROI estimates.

    Input JSON fields:
        platform_budgets (dict): {"Instagram": 300, "TikTok": 200}
        avg_order_value (float): Average revenue per sale in USD
        goal (str): "Brand Awareness" | "Increase Sales" | "Lead Generation"

    Returns realistic projections with transparent assumptions.
    """
    try:
        data = json.loads(input_json)
        platform_budgets = data["platform_budgets"]
        aov = float(data.get("avg_order_value", 50))
        goal = data.get("goal", "Increase Sales")

        total_clicks = 0
        total_conversions = 0
        total_budget = 0
        platform_projections = {}

        for platform, budget in platform_budgets.items():
            bench = PLATFORM_BENCHMARKS.get(platform, {"cpc": 0.70, "ctr": 0.02, "cvr": 0.03})
            clicks = int(float(budget) / bench["cpc"])
            conversions = int(clicks * bench["cvr"])
            revenue = round(conversions * aov, 2)

            platform_projections[platform] = {
                "budget": float(budget),
                "cpc": bench["cpc"],
                "clicks": clicks,
                "cvr_rate": f"{bench['cvr']*100:.1f}%",
                "conversions": conversions,
                "revenue": revenue,
                "roas": round(revenue / float(budget), 2) if float(budget) > 0 else 0
            }

            total_clicks += clicks
            total_conversions += conversions
            total_budget += float(budget)

        total_revenue = total_conversions * aov
        overall_roas = round(total_revenue / total_budget, 2) if total_budget > 0 else 0
        cpa = round(total_budget / total_conversions, 2) if total_conversions > 0 else 0

        result = {
            "summary": {
                "total_paid_budget": round(total_budget, 2),
                "total_estimated_clicks": total_clicks,
                "total_estimated_conversions": total_conversions,
                "total_estimated_revenue": round(total_revenue, 2),
                "overall_roas": overall_roas,
                "cost_per_acquisition": cpa,
                "avg_order_value_used": aov
            },
            "per_platform": platform_projections,
            "assumptions": [
                "CPC and CVR based on 2024 industry averages (WordStream/HubSpot)",
                "Conversions = clicks × platform CVR benchmark",
                f"Revenue = conversions × ${aov} avg order value",
                "Actual results vary by creative quality, targeting, and seasonality",
                "Organic reach not included — paid only"
            ]
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 3: Platform Recommender
# ─────────────────────────────────────────────────────────

@tool
def platform_recommender(input_json: str) -> str:
    """
    Recommends the best social media platforms based on audience and industry.
    Call this to validate or improve platform selection.

    Input JSON fields:
        industry (str): e.g. "fashion", "tech", "food"
        audience_age (str): e.g. "18-25", "25-40", "35-55"
        goal (str): "Brand Awareness" | "Increase Sales" | "Lead Generation"
        budget (float): Total budget to flag if LinkedIn is too expensive

    Returns recommended platforms ranked by fit score with reasoning.
    """
    try:
        data = json.loads(input_json)
        industry = data.get("industry", "").lower()
        age = data.get("audience_age", "25-35")
        goal = data.get("goal", "Brand Awareness")
        budget = float(data.get("budget", 500))

        scores = {}

        for platform, bench in PLATFORM_BENCHMARKS.items():
            score = 0

            # Industry fit
            if any(kw in industry for kw in bench["best_for"]):
                score += 3

            # Age fit
            age_scores = {
                "Instagram": ["18-25", "25-35"],
                "TikTok": ["13-18", "18-25"],
                "Facebook": ["25-40", "35-55", "40-60"],
                "LinkedIn": ["25-40", "30-50"],
                "YouTube": ["18-25", "25-40", "25-35"],
                "Twitter": ["18-25", "25-35"],
                "Pinterest": ["25-40", "30-45"],
            }
            if any(a in age for a in age_scores.get(platform, [])):
                score += 2

            # Goal fit
            if goal == "Lead Generation" and platform == "LinkedIn":
                score += 2
            if goal == "Brand Awareness" and platform in ["TikTok", "Instagram", "YouTube"]:
                score += 2
            if goal == "Increase Sales" and platform in ["Instagram", "Facebook", "Pinterest"]:
                score += 2

            # Budget fit (skip LinkedIn if budget < $500 for paid)
            if platform == "LinkedIn" and budget < 500:
                score -= 2

            scores[platform] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = [p for p, s in ranked[:3]]

        result = {
            "recommended_platforms": top_3,
            "all_scores": {p: s for p, s in ranked},
            "reasoning": {
                p: f"Score {s}/7 — {'Strong fit' if s >= 5 else 'Good fit' if s >= 3 else 'Weak fit'} for your industry and audience"
                for p, s in ranked[:4]
            },
            "warning": "LinkedIn has high CPC ($5.26 avg). Only use if B2B or budget > $500." if budget < 500 and "LinkedIn" in top_3 else None
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 4: Campaign Structurer
# ─────────────────────────────────────────────────────────

@tool
def campaign_structurer(input_json: str) -> str:
    """
    Builds a structured multi-phase campaign timeline.
    Always call this to give the campaign a professional structure.

    Input JSON fields:
        goal (str): "Brand Awareness" | "Increase Sales" | "Lead Generation"
        total_weeks (int): Campaign duration in weeks (e.g. 8, 12)
        budget (float): Total campaign budget

    Returns a phased campaign plan with objectives, activities, and KPIs.
    """
    try:
        data = json.loads(input_json)
        goal = data.get("goal", "Brand Awareness")
        total_weeks = int(data.get("total_weeks", 8))
        budget = float(data.get("budget", 1000))

        # Phase templates per goal
        phase_templates = {
            "Brand Awareness": [
                {"name": "Launch & Buzz", "pct_weeks": 0.25, "pct_budget": 0.30,
                 "objective": "Introduce the brand to the target audience",
                 "activities": ["Brand reveal post", "Teaser reels", "Influencer seeding", "Hashtag campaign launch"],
                 "kpis": ["Impressions", "Reach", "Follower growth rate", "Share of voice"]},
                {"name": "Content Blitz", "pct_weeks": 0.50, "pct_budget": 0.50,
                 "objective": "Build consistent brand presence and community",
                 "activities": ["Daily educational posts", "Behind-the-scenes stories", "UGC campaigns", "Collaborations"],
                 "kpis": ["Engagement rate", "Profile visits", "Story views", "Brand mentions"]},
                {"name": "Amplification", "pct_weeks": 0.25, "pct_budget": 0.20,
                 "objective": "Scale reach with paid promotion of top content",
                 "activities": ["Boost top-performing posts", "Retargeting warm audiences", "PR outreach"],
                 "kpis": ["Cost per 1000 impressions (CPM)", "Branded search volume", "Net Promoter Score"]},
            ],
            "Increase Sales": [
                {"name": "Warm-Up", "pct_weeks": 0.20, "pct_budget": 0.20,
                 "objective": "Build trust and product awareness before selling",
                 "activities": ["Product showcase posts", "Customer testimonials", "Demo videos", "Value content"],
                 "kpis": ["Reach", "Engagement", "Website traffic", "Email signups"]},
                {"name": "Conversion Push", "pct_weeks": 0.50, "pct_budget": 0.55,
                 "objective": "Drive direct purchases through targeted ads and offers",
                 "activities": ["Retargeting ads", "Limited-time offers", "Cart abandonment emails", "Sales landing page"],
                 "kpis": ["Conversion rate", "Cost per acquisition (CPA)", "Revenue", "ROAS"]},
                {"name": "Retention & Upsell", "pct_weeks": 0.30, "pct_budget": 0.25,
                 "objective": "Turn buyers into loyal repeat customers",
                 "activities": ["Post-purchase email sequence", "Loyalty rewards", "Upsell campaigns", "Review requests"],
                 "kpis": ["Repeat purchase rate", "Customer lifetime value (LTV)", "Review count", "Referral rate"]},
            ],
            "Lead Generation": [
                {"name": "Attract", "pct_weeks": 0.30, "pct_budget": 0.25,
                 "objective": "Drive traffic to lead capture assets",
                 "activities": ["Educational content", "Free resource promotion", "SEO blog posts", "Social ads to landing page"],
                 "kpis": ["Traffic", "CTR", "Landing page visits", "Cost per click"]},
                {"name": "Convert", "pct_weeks": 0.45, "pct_budget": 0.55,
                 "objective": "Capture leads through forms, downloads, and demos",
                 "activities": ["Lead magnet ads", "Webinar promotion", "Free trial offers", "Email opt-in campaigns"],
                 "kpis": ["Lead conversion rate", "Cost per lead (CPL)", "Form submissions", "Email list growth"]},
                {"name": "Nurture", "pct_weeks": 0.25, "pct_budget": 0.20,
                 "objective": "Move leads down the funnel toward purchase",
                 "activities": ["Email drip campaigns", "Retargeting ads", "Case study content", "Demo follow-ups"],
                 "kpis": ["Email open rate", "Click-through rate", "SQLs generated", "Pipeline value"]},
            ]
        }

        phases_raw = phase_templates.get(goal, phase_templates["Brand Awareness"])
        phases = []
        for i, p in enumerate(phases_raw):
            weeks = max(1, round(total_weeks * p["pct_weeks"]))
            phases.append({
                "phase_number": i + 1,
                "phase_name": p["name"],
                "duration_weeks": weeks,
                "budget_allocated": round(budget * p["pct_budget"], 2),
                "objective": p["objective"],
                "key_activities": p["activities"],
                "kpis": p["kpis"]
            })

        result = {
            "goal": goal,
            "total_duration_weeks": total_weeks,
            "total_budget": budget,
            "phases": phases,
            "note": "Adjust phase budgets based on early performance data."
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────
# TOOL 5: KPI Generator
# ─────────────────────────────────────────────────────────

@tool
def kpi_generator(input_json: str) -> str:
    """
    Generates specific, measurable KPIs based on goal, budget, and platform.
    Call this last to finalize success metrics for the strategy.

    Input JSON fields:
        goal (str): "Brand Awareness" | "Increase Sales" | "Lead Generation"
        platforms (list): e.g. ["Instagram", "TikTok"]
        estimated_reach (int): From financial projector output
        budget (float): Total budget

    Returns a KPI dashboard with targets and tracking methods.
    """
    try:
        data = json.loads(input_json)
        goal = data.get("goal", "Brand Awareness")
        platforms = data.get("platforms", ["Instagram"])
        reach = int(data.get("estimated_reach", 10000))
        budget = float(data.get("budget", 1000))

        base_kpis = {
            "Brand Awareness": [
                {"kpi": "Total Impressions", "target": f"{reach * 5:,}", "how_to_track": "Platform analytics dashboard"},
                {"kpi": "Follower Growth Rate", "target": "10-15% per month", "how_to_track": "Weekly follower count log"},
                {"kpi": "Engagement Rate", "target": "3-6% per post", "how_to_track": "(Likes+Comments+Shares)/Reach"},
                {"kpi": "Brand Mention Volume", "target": f"{int(budget/10)} mentions/month", "how_to_track": "Google Alerts / Brand24"},
                {"kpi": "Share of Voice", "target": "Increase by 20%", "how_to_track": "Social listening tools"},
            ],
            "Increase Sales": [
                {"kpi": "Return on Ad Spend (ROAS)", "target": "3x minimum", "how_to_track": "Platform conversion tracking"},
                {"kpi": "Cost Per Acquisition (CPA)", "target": f"< ${budget/max(1,int(budget/50)):.0f}", "how_to_track": "Ad account → conversions"},
                {"kpi": "Conversion Rate", "target": "2-4%", "how_to_track": "Google Analytics / Shopify"},
                {"kpi": "Monthly Revenue from Ads", "target": f"${budget * 3:.0f}+ (3x ROAS)", "how_to_track": "Revenue dashboard"},
                {"kpi": "Cart Abandonment Rate", "target": "< 70%", "how_to_track": "E-commerce analytics"},
            ],
            "Lead Generation": [
                {"kpi": "Cost Per Lead (CPL)", "target": f"< ${budget/max(1,int(budget/20)):.0f}", "how_to_track": "Ad account → lead form metrics"},
                {"kpi": "Lead Conversion Rate", "target": "5-10%", "how_to_track": "Landing page analytics"},
                {"kpi": "Monthly Leads Generated", "target": f"{int(budget/25)}+ leads", "how_to_track": "CRM / email list"},
                {"kpi": "Email Open Rate", "target": "> 25%", "how_to_track": "Mailchimp / email platform"},
                {"kpi": "SQLs (Sales Qualified Leads)", "target": f"{int(budget/100)}+ per month", "how_to_track": "CRM pipeline"},
            ]
        }

        platform_kpis = []
        for platform in platforms:
            if platform == "Instagram":
                platform_kpis.append({"platform": "Instagram", "kpi": "Story Views", "target": f"{int(reach*0.1):,}+ per story"})
                platform_kpis.append({"platform": "Instagram", "kpi": "Reel Plays", "target": f"{int(reach*0.3):,}+ per reel"})
            elif platform == "TikTok":
                platform_kpis.append({"platform": "TikTok", "kpi": "Video Completion Rate", "target": "> 40%"})
                platform_kpis.append({"platform": "TikTok", "kpi": "For You Page Reach", "target": f"{int(reach*0.5):,}+"})
            elif platform == "LinkedIn":
                platform_kpis.append({"platform": "LinkedIn", "kpi": "Post Impressions", "target": f"{int(reach*0.2):,}+"})
                platform_kpis.append({"platform": "LinkedIn", "kpi": "Connection Request Rate", "target": "> 15%"})

        result = {
            "goal_kpis": base_kpis.get(goal, base_kpis["Brand Awareness"]),
            "platform_specific_kpis": platform_kpis,
            "review_cadence": "Review KPIs weekly. Adjust budget toward top-performing platforms after week 2.",
            "tools_recommended": ["Meta Ads Manager", "Google Analytics 4", "Later.com (scheduling)", "Notion (tracking dashboard)"]
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})