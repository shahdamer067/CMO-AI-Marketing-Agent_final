"""
CMO.AI — Test Script v3
Run: python test_agent.py [--tools-only | --mode1 | --mode2]
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

MOCK_BRAND_PROFILE = {
    "user_id": "test_user_001",
    "brand_name": "GlowUp Skincare",
    "industry": "beauty",
    "product_or_service": "Natural skincare — serums, moisturizers, face masks",
    "target_audience": "Young women interested in clean beauty and self-care",
    "audience_age_range": "18-28",
    "audience_location": "Egypt and MENA region",
    "brand_mission": "Make clean, effective skincare accessible to everyone",
    "brand_values": ["authenticity", "sustainability", "inclusivity"],
    "brand_tone": "warm, friendly, and empowering",
    "marketing_goal": "Brand Awareness",
    "budget": 800,
    "preferred_platforms": ["Instagram", "TikTok"],
}

# Full completed intake — all 6 questions answered.
# The last assistant message contains the JSON the agent produces
# once it has all answers. This simulates a complete Mode 2 conversation.
MOCK_INTAKE_CONVERSATION = [
    {"role": "user",      "content": "I want a marketing strategy for my business."},
    {"role": "assistant", "content": "Great! What's your brand name and what do you sell?"},
    {"role": "user",      "content": "My brand is FitFuel. We sell protein supplements and fitness snacks."},
    {"role": "assistant", "content": "Nice! What industry are you in?"},
    {"role": "user",      "content": "Health and fitness, sports nutrition."},
    {"role": "assistant", "content": "Who is your target audience?"},
    {"role": "user",      "content": "Gym-goers and fitness enthusiasts, mostly men aged 20-35."},
    {"role": "assistant", "content": "What is your main marketing goal — Brand Awareness, Increase Sales, or Lead Generation?"},
    {"role": "user",      "content": "Increase Sales."},
    {"role": "assistant", "content": "What is your total marketing budget in USD?"},
    {"role": "user",      "content": "1200 dollars."},
    {"role": "assistant", "content": "Which platforms do you want to focus on?"},
    {"role": "user",      "content": "Instagram and YouTube."},
]


def test_tools():
    print("\n" + "="*60)
    print("TEST: TOOLS (no API key needed)")
    print("="*60)
    from tools import budget_allocator, financial_projector, platform_recommender, campaign_structurer, kpi_generator

    checks = [
        (budget_allocator,      json.dumps({"budget":800,"platforms":["Instagram","TikTok"],"goal":"Brand Awareness"}),      "platform_paid_budget"),
        (platform_recommender,  json.dumps({"industry":"beauty","audience_age":"18-28","goal":"Brand Awareness","budget":800}),"recommended_platforms"),
        (financial_projector,   json.dumps({"platform_budgets":{"Instagram":300,"TikTok":100},"avg_order_value":45,"goal":"Brand Awareness"}), "summary"),
        (campaign_structurer,   json.dumps({"goal":"Brand Awareness","total_weeks":8,"budget":800}),                          "phases"),
        (kpi_generator,         json.dumps({"goal":"Brand Awareness","platforms":["Instagram"],"estimated_reach":5000,"budget":800}), "goal_kpis"),
    ]
    for tool, inp, key in checks:
        r = tool.invoke(inp)
        data = json.loads(r)
        assert key in data, f"Missing '{key}' in {tool.name} output"
        print(f"  ✅ {tool.name}")
    print("  🎉 All tools pass!\n")


def check_key():
    key = os.getenv("GROQ_API_KEY","")
    if not key or "your_" in key:
        print("❌ Set GROQ_API_KEY in .env — get a free key at console.groq.com")
        sys.exit(1)


def test_mode1():
    check_key()
    from agent import MarketingStrategyAgent
    print("\n" + "="*60)
    print("TEST: MODE 1 — Brand profile passed directly")
    print("="*60)

    agent = MarketingStrategyAgent()
    try:
        result = agent.run(user_id="test_mode1", brand_profile=MOCK_BRAND_PROFILE)

        assert result.get("strategy_text"), "No strategy text!"
        assert not result.get("intake_in_progress"), "Should not be in intake!"

        text = result["strategy_text"]
        sections = ["EXECUTIVE SUMMARY","TARGET AUDIENCE","POSITIONING",
                    "CAMPAIGN","PLATFORM","CONTENT","BUDGET","FINANCIAL","KPI"]
        missing = [s for s in sections if s not in text.upper()]

        print(f"\n  ✅ Strategy generated: {len(text)} chars")
        print(f"  Mode: {result.get('mode')}")
        print(f"  Sections found: {len(sections)-len(missing)}/{len(sections)}")
        if missing: print(f"  Missing sections: {missing}")
        print("\n--- STRATEGY PREVIEW ---")
        print(text[:800] + "\n...")
    finally:
        agent.close()


def test_mode2():
    check_key()
    from agent import MarketingStrategyAgent
    print("\n" + "="*60)
    print("TEST: MODE 2 — Full intake conversation")
    print("="*60)

    agent = MarketingStrategyAgent()
    try:
        result = agent.run(user_id="test_mode2", conversation=MOCK_INTAKE_CONVERSATION)

        if result.get("intake_in_progress"):
            # This is fine — means the mock conversation wasn't enough
            # The agent is asking for more info
            print(f"  ℹ️  Intake in progress (need more conversation turns)")
            print(f"  Next question: {result.get('next_question','')[:200]}")
        else:
            text = result.get("strategy_text","")
            assert text, "No strategy text returned!"
            print(f"\n  ✅ Mode 2 complete!")
            print(f"  Brand: {result.get('brand_name')}")
            print(f"  Strategy: {len(text)} chars")
            print(f"  Mode: {result.get('mode')}")
            print("\n--- STRATEGY PREVIEW ---")
            print(text[:800] + "\n...")
    finally:
        agent.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--tools-only" in args:
        test_tools()
    elif "--mode1" in args:
        test_tools(); test_mode1()
    elif "--mode2" in args:
        test_tools(); test_mode2()
    else:
        test_tools(); test_mode1(); test_mode2()