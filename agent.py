"""
============================================================
CMO.AI — Marketing Strategy Agent v3.1 (Bug Fixes)
============================================================
FIXES vs v3:

  BUG 1 FIXED — Mode 1 was going to intake even when
    brand_profile was passed directly to run().
    Root cause: check_profile_node always queried MongoDB
    and overwrote the mode, even when brand_profile was
    already provided.
    Fix: when brand_profile is passed to run(), the graph
    starts at strategy_step directly, skipping check_profile
    and intake entirely.

  BUG 2 FIXED — Groq 400 error: "missing properties: input_json"
    Root cause: call_tool_step used LLM tool-calling to invoke
    tools. The LLM passed individual fields (industry, budget...)
    instead of the single input_json string the tools expect.
    Groq validates tool schemas strictly and rejected it.
    Fix: tools are now called DIRECTLY with json.dumps() inputs.
    No LLM needed for tool execution — we already know the inputs.

MODE 1: profile in MongoDB → strategy_step → tools → write
MODE 2: no profile → intake questions → strategy_step → tools → write
============================================================
"""

import os, json, re
from typing import TypedDict, Annotated, List, Optional
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

from tools import (
    budget_allocator,
    financial_projector,
    platform_recommender,
    campaign_structurer,
    kpi_generator,
)
from database import MarketingDB

load_dotenv()

TOOLS_LIST = [
    budget_allocator,
    financial_projector,
    platform_recommender,
    campaign_structurer,
    kpi_generator,
]

# ─────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:        Annotated[List, add_messages]
    brand_profile:   Optional[dict]
    user_id:         str
    mode:            str          # "db" | "intake"
    intake_complete: bool
    tool_results:    dict         # {"platform": {...}, "budget": {...}, ...}
    tools_done:      List[str]    # which tools have been called so far


# ─────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────

INTAKE_SYSTEM_PROMPT = """
You are the Marketing Strategy Agent for CMO.AI.

The user wants a marketing strategy but has no saved brand profile.
Collect 6 pieces of information through friendly conversation.

Ask ONE question at a time. Be warm, not like a form.
After each answer, briefly acknowledge it, then ask the next question.

Questions to ask (in order):
1. Brand name and what they sell
2. Industry
3. Target audience (age, interests, location if mentioned)
4. Main marketing goal: Brand Awareness, Increase Sales, or Lead Generation
5. Total marketing budget in USD (ask for a specific number if vague)
6. Which platforms: Instagram, TikTok, YouTube, Facebook, LinkedIn

When you have ALL 6 answers, output ONLY this JSON with no other text:
{"intake_complete":true,"brand_name":"...","product_or_service":"...","industry":"...","target_audience":"...","audience_age_range":"...","marketing_goal":"...","budget":0,"preferred_platforms":[]}
"""

STRATEGY_WRITE_PROMPT = """
You are a senior CMO. Write a COMPLETE, professional marketing strategy.
Every number must come from the tool data below — do not invent figures.

BRAND:
Name: {brand_name}
Industry: {industry}
Product/Service: {product_or_service}
Target Audience: {target_audience} (age {audience_age_range})
Location: {audience_location}
Brand Tone: {brand_tone}
Brand Mission: {brand_mission}
Goal: {marketing_goal}
Total Budget: ${budget}

PLATFORM ANALYSIS (from platform_recommender tool):
{platform_data}

BUDGET BREAKDOWN (from budget_allocator tool):
{budget_data}

FINANCIAL PROJECTIONS (from financial_projector tool):
{financial_data}

CAMPAIGN PHASES (from campaign_structurer tool):
{campaign_data}

KPIs (from kpi_generator tool):
{kpi_data}

Write every section in full. Reference specific numbers from the tool data above.
Paid budget: ${paid_budget} | Content budget: ${content_budget} | Influencer: ${influencer_budget}
Total clicks: {total_clicks} | Conversions: {total_conversions} | Revenue: ${total_revenue} | ROAS: {roas}x

### 🎯 EXECUTIVE SUMMARY
### 👥 TARGET AUDIENCE ANALYSIS
### 💡 POSITIONING & DIFFERENTIATION
### 📅 CAMPAIGN STRUCTURE
### 📱 PLATFORM STRATEGY
### 📝 CONTENT PILLARS & WEEKLY SCHEDULE
### 💰 BUDGET BREAKDOWN
### 📊 FINANCIAL PROJECTIONS
### 🎯 KPIs & SUCCESS METRICS
### ✍️ CONTENT GUIDELINES (for content agent — tone, style, dos and don'ts)
### 🏷️ HASHTAG STRATEGY (15-20 specific hashtags)
### 📣 CALL-TO-ACTION EXAMPLES (6-8 specific CTAs)
"""


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def make_llm(temperature=0.3, max_tokens=4000):
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv("GROQ_API_KEY")
    )


def extract_json(text: str) -> Optional[dict]:
    """
    Robust JSON extraction from LLM output.
    Handles: raw JSON, ```json blocks, JSON embedded in text.
    """
    if not text:
        return None
    # Try 1: whole string is JSON
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    # Try 2: ```json ... ``` block
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    # Try 3: first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


# ─────────────────────────────────────────────────────────
# NODES
# ─────────────────────────────────────────────────────────

def check_profile_node(state: AgentState, db: MarketingDB) -> dict:
    """Query MongoDB — sets mode to 'db' or 'intake'."""
    profile = db.get_brand_profile(state["user_id"])
    if profile:
        print(f"[Agent] Mode 1 (DB): found profile for '{profile.get('brand_name')}'")
        return {"brand_profile": profile, "mode": "db",
                "intake_complete": True, "tool_results": {}, "tools_done": []}
    else:
        print(f"[Agent] Mode 2 (Intake): no profile found, starting intake")
        return {"brand_profile": None, "mode": "intake",
                "intake_complete": False, "tool_results": {}, "tools_done": []}


def intake_node(state: AgentState, llm) -> dict:
    """Conversational intake — asks questions until all 6 answered."""
    msgs = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in msgs):
        msgs = [SystemMessage(content=INTAKE_SYSTEM_PROMPT)] + msgs

    response = llm.invoke(msgs)
    content = response.content if hasattr(response, "content") else ""

    if "intake_complete" in content:
        data = extract_json(content)
        if data and data.get("intake_complete"):
            profile = {
                "user_id":             state["user_id"],
                "brand_name":          data.get("brand_name", "Unknown"),
                "product_or_service":  data.get("product_or_service", ""),
                "industry":            data.get("industry", ""),
                "target_audience":     data.get("target_audience", ""),
                "audience_age_range":  data.get("audience_age_range", "25-35"),
                "audience_location":   data.get("audience_location", "Global"),
                "brand_tone":          data.get("brand_tone", "professional"),
                "brand_mission":       data.get("brand_mission", ""),
                "brand_values":        data.get("brand_values", []),
                "marketing_goal":      data.get("marketing_goal", "Brand Awareness"),
                "budget":              float(data.get("budget", 1000)),
                "preferred_platforms": data.get("preferred_platforms", ["Instagram"]),
                "source":              "direct_intake",
                "created_at":          datetime.utcnow().isoformat()
            }
            print(f"[Agent] Intake complete → '{profile['brand_name']}'")
            return {"messages": [response], "brand_profile": profile,
                    "intake_complete": True, "mode": "intake"}

    return {"messages": [response], "intake_complete": False, "mode": "intake"}


def call_tool_step(state: AgentState, tool_name: str) -> dict:
    """
    Calls ONE tool DIRECTLY using json.dumps() inputs.

    WHY DIRECT (not LLM tool-calling):
    The tools expect a single 'input_json' string parameter.
    When the LLM called them via tool-binding, it passed individual
    fields instead, causing Groq 400 errors. Since we already know
    exactly what inputs each tool needs, we call them directly —
    faster, cheaper, and always correct.
    """
    bp = state["brand_profile"]
    tr = state.get("tool_results", {})
    platforms = bp.get("preferred_platforms", ["Instagram"]) or ["Instagram"]

    result_data = {}

    if tool_name == "platform":
        inp = json.dumps({
            "industry":     bp.get("industry", "general"),
            "audience_age": bp.get("audience_age_range", "25-35"),
            "goal":         bp.get("marketing_goal", "Brand Awareness"),
            "budget":       bp.get("budget", 1000)
        })
        result_data = extract_json(platform_recommender.invoke(inp)) or {}

    elif tool_name == "budget":
        confirmed = tr.get("platform", {}).get("recommended_platforms", platforms)
        inp = json.dumps({
            "budget":    bp.get("budget", 1000),
            "platforms": confirmed,
            "goal":      bp.get("marketing_goal", "Brand Awareness")
        })
        result_data = extract_json(budget_allocator.invoke(inp)) or {}

    elif tool_name == "financial":
        paid_budgets = tr.get("budget", {}).get(
            "platform_paid_budget",
            {p: round(bp.get("budget", 1000) / len(platforms), 2) for p in platforms}
        )
        inp = json.dumps({
            "platform_budgets": paid_budgets,
            "avg_order_value":  50,
            "goal":             bp.get("marketing_goal", "Brand Awareness")
        })
        result_data = extract_json(financial_projector.invoke(inp)) or {}

    elif tool_name == "campaign":
        inp = json.dumps({
            "goal":        bp.get("marketing_goal", "Brand Awareness"),
            "total_weeks": 8,
            "budget":      bp.get("budget", 1000)
        })
        result_data = extract_json(campaign_structurer.invoke(inp)) or {}

    elif tool_name == "kpi":
        financial_summary = tr.get("financial", {}).get("summary", {})
        reach = financial_summary.get("total_estimated_clicks", 5000)
        confirmed = tr.get("platform", {}).get("recommended_platforms", platforms)
        inp = json.dumps({
            "goal":            bp.get("marketing_goal", "Brand Awareness"),
            "platforms":       confirmed,
            "estimated_reach": reach,
            "budget":          bp.get("budget", 1000)
        })
        result_data = extract_json(kpi_generator.invoke(inp)) or {}

    print(f"[Agent] Tool '{tool_name}' ✓  keys: {list(result_data.keys())[:5]}")

    return {
        "tool_results": {**tr, tool_name: result_data},
        "tools_done":   state.get("tools_done", []) + [tool_name]
    }


def write_strategy_node(state: AgentState, llm) -> dict:
    """Writes the full strategy using all 5 tool results."""
    bp = state["brand_profile"]
    tr = state.get("tool_results", {})

    budget_data    = tr.get("budget", {})
    financial_data = tr.get("financial", {}).get("summary", {})
    cat_split      = budget_data.get("category_split", {})

    prompt = STRATEGY_WRITE_PROMPT.format(
        brand_name        = bp.get("brand_name", ""),
        industry          = bp.get("industry", ""),
        product_or_service= bp.get("product_or_service", ""),
        target_audience   = bp.get("target_audience", ""),
        audience_age_range= bp.get("audience_age_range", ""),
        audience_location = bp.get("audience_location", "Global"),
        brand_tone        = bp.get("brand_tone", "professional"),
        brand_mission     = bp.get("brand_mission", ""),
        marketing_goal    = bp.get("marketing_goal", "Brand Awareness"),
        budget            = bp.get("budget", 1000),
        platform_data     = json.dumps(tr.get("platform", {}),  indent=2),
        budget_data       = json.dumps(budget_data,              indent=2),
        financial_data    = json.dumps(financial_data,           indent=2),
        campaign_data     = json.dumps(tr.get("campaign", {}),   indent=2),
        kpi_data          = json.dumps(tr.get("kpi", {}),        indent=2),
        paid_budget       = cat_split.get("paid_ads", ""),
        content_budget    = cat_split.get("content_creation", ""),
        influencer_budget = cat_split.get("influencer_marketing", ""),
        total_clicks      = financial_data.get("total_estimated_clicks", ""),
        total_conversions = financial_data.get("total_estimated_conversions", ""),
        total_revenue     = financial_data.get("total_estimated_revenue", ""),
        roas              = financial_data.get("overall_roas", ""),
    )

    print("[Agent] Writing strategy from tool data...")
    response = llm.invoke([
        SystemMessage(content="You are a senior CMO. Write a detailed professional marketing strategy. Use ALL numbers provided. Never invent figures."),
        HumanMessage(content=prompt)
    ])
    return {"messages": [response]}


# ─────────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────────

TOOL_SEQUENCE = ["platform", "budget", "financial", "campaign", "kpi"]


def route_after_check(state: AgentState) -> str:
    return "strategy_step" if state["mode"] == "db" else "intake"


def route_after_intake(state: AgentState) -> str:
    return "strategy_step" if state.get("intake_complete") else "intake"


def route_strategy_step(state: AgentState) -> str:
    """Route to the next uncalled tool, or write_strategy if all done."""
    done = state.get("tools_done", [])
    for tool in TOOL_SEQUENCE:
        if tool not in done:
            return tool
    return "write_strategy"


# ─────────────────────────────────────────────────────────
# AGENT CLASS
# ─────────────────────────────────────────────────────────

class MarketingStrategyAgent:
    """
    Marketing Strategy Agent — Mode 1 (DB) + Mode 2 (Intake).

    Usage:
        agent = MarketingStrategyAgent()

        # Mode 1 — brand profile in MongoDB:
        result = agent.run(user_id="abc123")

        # Mode 2 — direct user (pass conversation history):
        result = agent.run(user_id="abc123", conversation=[...])

        # Testing — bypass DB and intake completely:
        result = agent.run(user_id="test", brand_profile={...})
    """

    def __init__(self):
        self.db           = MarketingDB()
        self.intake_llm   = make_llm(temperature=0.5, max_tokens=800)
        self.strategy_llm = make_llm(temperature=0.4, max_tokens=8000)
        self.graph        = self._build_graph()
        print("[Agent] Marketing Strategy Agent v3.1 initialized.")

    def _build_graph(self):
        graph = StateGraph(AgentState)

        db           = self.db
        intake_llm   = self.intake_llm
        strategy_llm = self.strategy_llm

        # start node: decides whether to check MongoDB or skip straight to strategy
        # This is the real fix for Bug 1 — check_profile is only called when needed
        def start_node(state: AgentState) -> dict:
            # Pure passthrough — just lets route_from_start decide where to go
            # Returns empty dict so LangGraph state is not modified
            return {}

        def route_from_start(state: AgentState) -> str:
            if state.get("brand_profile") is not None:
                # Already have a profile — go straight to tools
                return "strategy_step"
            # No profile — check MongoDB first
            return "check_profile"

        graph.add_node("start",          start_node)
        graph.add_node("check_profile",  lambda s: check_profile_node(s, db))
        graph.add_node("intake",         lambda s: intake_node(s, intake_llm))
        graph.add_node("strategy_step",  lambda s: s)   # passthrough dispatcher

        # One node per tool — calls tool directly, no LLM involved
        for tn in TOOL_SEQUENCE:
            graph.add_node(f"tool_{tn}", lambda s, t=tn: call_tool_step(s, t))

        graph.add_node("write_strategy", lambda s: write_strategy_node(s, strategy_llm))

        graph.set_entry_point("start")

        graph.add_conditional_edges("start", route_from_start, {
            "strategy_step": "strategy_step",
            "check_profile": "check_profile"
        })

        graph.add_conditional_edges("check_profile", route_after_check, {
            "strategy_step": "strategy_step",
            "intake":        "intake"
        })
        graph.add_conditional_edges("intake", route_after_intake, {
            "strategy_step": "strategy_step",
            "intake":        "intake"
        })
        graph.add_conditional_edges("strategy_step", route_strategy_step, {
            **{t: f"tool_{t}" for t in TOOL_SEQUENCE},
            "write_strategy": "write_strategy"
        })
        for tn in TOOL_SEQUENCE:
            graph.add_edge(f"tool_{tn}", "strategy_step")

        graph.add_edge("write_strategy", END)

        return graph.compile()

    def run(self, user_id: str, conversation: list = None, brand_profile: dict = None) -> dict:
        """
        Run the agent.

        BUG 1 FIX: when brand_profile is provided, we inject it directly
        into the state with mode='db' and intake_complete=True, so
        check_profile_node never runs and can never overwrite the mode.
        """
        print(f"\n[Agent] run() → user: {user_id}")

        # Build initial messages for intake (Mode 2)
        initial_messages = []
        if conversation:
            for m in conversation:
                cls = HumanMessage if m["role"] == "user" else AIMessage
                initial_messages.append(cls(content=m["content"]))
        if not initial_messages and brand_profile is None:
            initial_messages = [HumanMessage(content="I want a marketing strategy for my business.")]

        if brand_profile is not None:
            # ── TESTING / MODE 1 BYPASS ──────────────────────────────────
            # Skip check_profile and intake entirely.
            # Inject profile + set mode='db' + intake_complete=True so
            # the graph goes straight to strategy_step on first conditional.
            print(f"[Agent] Brand profile provided directly → skipping DB check")
            start_mode         = "db"
            start_intake_done  = True
        else:
            start_mode         = "unknown"
            start_intake_done  = False

        state: AgentState = {
            "messages":        initial_messages,
            "brand_profile":   brand_profile,   # None for real Mode 2 runs
            "user_id":         user_id,
            "mode":            start_mode,
            "intake_complete": start_intake_done,
            "tool_results":    {},
            "tools_done":      [],
        }

        print("[Agent] Running graph...")
        final_state = {}
        step = 0

        for chunk in self.graph.stream(state, {"recursion_limit": 40}):
            step += 1
            node = list(chunk.keys())[0]
            print(f"[Agent] Step {step}: {node}")
            node_output = chunk.get(node) or {}
            final_state.update(node_output)

        # Intake still in progress?
        if final_state.get("mode") == "intake" and not final_state.get("intake_complete"):
            msgs = final_state.get("messages", [])
            last_ai = next(
                (m.content for m in reversed(msgs) if isinstance(m, AIMessage)),
                "Tell me about your business!"
            )
            return {"strategy_text": None, "intake_in_progress": True,
                    "next_question": last_ai, "saved": False,
                    "brand_name": None, "mode": "intake"}

        # Extract strategy text from messages
        msgs = final_state.get("messages", [])
        strategy_text = ""
        for m in reversed(msgs):
            if hasattr(m, "content") and isinstance(m.content, str) and len(m.content) > 300:
                strategy_text = m.content
                break

        # Save to MongoDB
        bp        = final_state.get("brand_profile") or brand_profile or {}
        brand_name= bp.get("brand_name", "Unknown")
        mode      = final_state.get("mode", start_mode)

        doc = {
            "user_id":               user_id,
            "brand_name":            brand_name,
            "strategy_text":         strategy_text,
            "brand_profile_snapshot":bp,
            "tool_results":          final_state.get("tool_results", {}),
            "generated_at":          datetime.utcnow().isoformat(),
            "agent_version":         "3.1",
            "model_used":            "llama-3.3-70b-versatile",
            "mode":                  mode
        }
        saved = self.db.save_marketing_strategy(user_id, doc)

        # Mode 2: also persist the brand profile for next visit
        if mode == "intake" and bp:
            self.db.save_brand_profile(user_id, bp)
            print("[Agent] Mode 2: brand profile saved to MongoDB for future visits")

        print(f"[Agent] Done! {len(strategy_text)} chars | mode={mode} | saved={saved}")
        return {
            "strategy_text":     strategy_text,
            "intake_in_progress":False,
            "next_question":     None,
            "saved":             saved,
            "brand_name":        brand_name,
            "mode":              mode,
            "generated_at":      doc["generated_at"]
        }

    def close(self):
        self.db.close()