# CMO.AI — Marketing Strategy Agent
## Documentation for the Team

---

## 📁 File Structure

```
cmo_ai/
├── .env.example              ← Copy to .env and fill your keys
├── requirements.txt          ← All dependencies
└── marketing_agent/
    ├── models.py             ← Shared data models (BrandProfile, MarketingStrategy)
    ├── database.py           ← MongoDB read/write layer
    ├── tools.py              ← 5 deterministic calculation tools
    ├── agent.py              ← The real LangGraph ReAct agent
    ├── api.py                ← FastAPI endpoints (for frontend team)
    └── test_agent.py         ← Test without needing MongoDB
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env: add your GROQ_API_KEY and MONGODB_URI

# 3. Test the agent (no MongoDB needed)
cd marketing_agent
python test_agent.py

# 4. Run the API server
python api.py
# → API available at http://localhost:8001
```

---

## 🔑 Getting a Free Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free)
3. Create an API key
4. Paste it in your `.env` file

**Why Groq?** Free tier, fast inference, supports LLaMA 3.3 70B which has strong reasoning for structured tasks.

---

## 🧠 How the Agent Works (Real Agent, Not a Chain)

This is a **LangGraph ReAct agent** — the LLM decides what to do, not you.

```
[START]
   ↓
agent_node (LLM reasons: "I need to check platforms first")
   ↓
calls platform_recommender tool
   ↓
tool_node runs the tool, returns real data
   ↓
agent_node (LLM reasons: "Now I need budget split")
   ↓
calls budget_allocator tool
   ↓
... continues until all 5 tools are called ...
   ↓
agent_node (LLM writes the full strategy using tool outputs)
   ↓
[END] → saves to MongoDB
```

**Key difference from your original code:**
- Old: You manually ran tools and stuffed results into a prompt → one LLM call
- New: LLM autonomously decides to call tools, sees results, reasons, calls more tools

---

## 🔗 How This Connects to Other Agents (MongoDB Flow)

```
Branding Agent
    ↓ writes BrandProfile to MongoDB (brand_profiles collection)
    
Marketing Strategy Agent   ← YOU ARE HERE
    ↓ reads BrandProfile
    ↓ runs ReAct loop with 5 tools
    ↓ writes MarketingStrategy to MongoDB (marketing_strategies collection)
    
Content Agent
    ↓ reads MarketingStrategy (strategy_text + content_guidelines)
    ↓ generates posts, emails, captions
    
Image Agent
    ↓ reads MarketingStrategy (brand colors, campaign theme)
    ↓ generates visuals
    
Video Agent
    ↓ reads MarketingStrategy (campaign phases, platform strategy)
    ↓ generates video content
```

---

## 📡 API Endpoints

### POST `/strategy/generate`
Triggers the agent for a user.

```json
// Request
{
  "user_id": "abc123"
}

// Response
{
  "success": true,
  "user_id": "abc123",
  "brand_name": "GlowUp Skincare",
  "strategy_text": "### 🎯 EXECUTIVE SUMMARY\n...",
  "generated_at": "2025-10-15T14:30:00"
}
```

### GET `/strategy/{user_id}`
Fetches existing strategy (called by content agent).

```json
// Response
{
  "success": true,
  "strategy_text": "...",
  "brand_name": "GlowUp Skincare"
}
```

### GET `/health`
```json
{"status": "ok", "agent": "marketing-strategy", "version": "1.0.0"}
```

---

## 🛠️ The 5 Tools (What Each Does)

| Tool | Input | Output | Why Real, Not LLM |
|------|-------|--------|-------------------|
| `platform_recommender` | industry, age, goal, budget | Ranked platforms + fit scores | Uses industry benchmark data |
| `budget_allocator` | budget, platforms, goal | Per-platform + category split | Rule-based calculation |
| `financial_projector` | platform budgets, AOV | Clicks, conversions, ROAS | Uses 2024 CPC/CVR benchmarks |
| `campaign_structurer` | goal, weeks, budget | Phased timeline + activities | Template-based structuring |
| `kpi_generator` | goal, platforms, reach | Specific measurable KPIs | Formula-based targets |

---

## 🗄️ MongoDB Collections

### `brand_profiles` (written by branding agent)
```json
{
  "user_id": "abc123",
  "brand_name": "GlowUp Skincare",
  "industry": "beauty",
  "target_audience": "Young women 18-28",
  "budget": 800,
  "preferred_platforms": ["Instagram", "TikTok"],
  "marketing_goal": "Brand Awareness",
  ...
}
```

### `marketing_strategies` (written by this agent)
```json
{
  "user_id": "abc123",
  "brand_name": "GlowUp Skincare",
  "strategy_text": "### 🎯 EXECUTIVE SUMMARY\n...",
  "brand_profile_snapshot": {...},
  "generated_at": "2025-10-15T14:30:00",
  "model_used": "llama-3.3-70b-versatile"
}
```

---

## ⚠️ Important Notes for Team

1. **Never change `user_id` format** — all agents use it to link documents
2. **Content agent reads `strategy_text`** — make sure it's always a string
3. **`brand_profile_snapshot`** is saved with the strategy so content agent knows what brand data was used
4. **Test with `test_agent.py --tools-only`** first to verify tools work before running the full agent
5. **The agent saves automatically** — no need to call a separate save endpoint

---

## 🐛 Troubleshooting

**"No brand profile found"**
→ Branding agent hasn't saved to MongoDB yet. Use `test_agent.py` to bypass this.

**"GROQ_API_KEY not set"**
→ Copy `.env.example` to `.env` and add your key.

**"recursion limit exceeded"**
→ The LLM got stuck in a tool loop. Increase `recursion_limit` in `agent.py` line with `graph.stream()`.

**MongoDB connection error**
→ Check your `MONGODB_URI` in `.env`. Make sure your IP is whitelisted in MongoDB Atlas.
