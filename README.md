# 🧠 AI Coding Practice Browser Agent

An AI agent that automates the *repetitive* parts of coding practice — reading the
problem, drafting a solution, pasting it into the editor, running tests, and
debugging failures — while leaving **review and submission entirely to you**.

> The agent never clicks Submit. It reads, writes, and runs — you decide when it's ready.

---

## Architecture

```
┌─────────────┐      CDP (remote debugging port)      ┌──────────────────┐
│   Chrome    │◄──────────────────────────────────────►│ Playwright layer │
│ (your tab)  │                                         └────────┬─────────┘
└─────────────┘                                                  │
                                                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          LangGraph Orchestration                          │
│                                                                            │
│  ProblemReader → Planner → Generator → Formatter → BrowserEditor          │
│         (stop — awaiting user click "Run Tests")                          │
│                                                                            │
│  TestRunner → ErrorAnalyzer ─┬─► success ──────────► SessionMemory        │
│       ▲                       ├─► retry → Retry → Formatter → BrowserEditor
│       │                       └─► max_retries ─────► SessionMemory        │
│       └───────────────────────────────────(loop, user-triggered)          │
└──────────────────────────────────────────────────────────────────────────┘
         │                                                    │
         ▼                                                    ▼
   FastAPI (backend/main.py)                          SQLite (memory/db.py)
         │
         ▼
   Streamlit Dashboard (frontend/streamlit_app.py)
```

### The 10 agents

| # | Agent | Responsibility |
|---|-------|-----------------|
| 1 | Problem Reader | Reads the active tab, extracts title/description/examples/constraints/starter code |
| 2 | Planner | Determines data structures, algorithm strategy, complexity, edge cases |
| 3 | Code Generator | Writes a solution matching the exact function signature |
| 4 | Code Formatter | Strips markdown/prose, ensures pure executable code |
| 5 | Browser Editor | Clears and replaces the Monaco editor contents |
| 6 | Test Runner | Clicks **Run** (never Submit), waits for completion |
| 7 | Error Analyzer | Classifies compiler/runtime/WA/TLE/MLE errors into structured JSON |
| 8 | Retry | Builds a minimal-fix prompt from problem + prior code + error, loops |
| 9 | Session Memory | Persists problems, attempts, errors, and final solutions to SQLite |
| 10 | Dashboard | Summarizes run state for the Streamlit UI |

LLM calls are routed through **LiteLLM**, restricted to **free-tier Groq and
OpenRouter models only** (enforced in code — no OpenAI/Anthropic/Gemini keys
are ever read).

---

## Setup

### 1. Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Chrome
- A free [Groq API key](https://console.groq.com) and/or [OpenRouter API key](https://openrouter.ai)

### 2. Install dependencies

```bash
uv venv

# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

uv pip install -e ".[dev]"
playwright install chromium
```

### 3. Configure environment

```bash
cp .env.example .env
# edit .env and add your GROQ_API_KEY / OPENROUTER_API_KEY
```

### 4. Launch Chrome with remote debugging enabled

The agent attaches to a Chrome instance **you already have open** — it never
launches its own browser profile for solving problems.

```bash
# macOS
open -a "Google Chrome" --args --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222
```

Open your coding problem (e.g. a LeetCode problem page) in that Chrome window.

### 5. Run the backend

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### 6. Run the dashboard

```bash
uv run streamlit run frontend/streamlit_app.py
```

Open `http://localhost:8501`.

---

## Usage

1. Open a coding problem in the Chrome tab (remote-debugging Chrome instance).
2. In the dashboard, choose a language and click **"Read & Solve Problem"**.
   The agent reads the problem, plans, generates code, formats it, and pastes
   it into the editor. It then stops.
3. Review the pasted code if you like, then click **"Run Tests"** in the
   dashboard (this clicks the page's own Run button — not Submit).
4. If tests fail, the agent reads the error, classifies it, and automatically
   generates and pastes a fix. Click **"Run Tests"** again to retry.
5. On success, the dashboard shows a big success banner. **You** review the
   solution and click Submit in the browser yourself.

---

## uv Commands Reference

```bash
uv pip install -e ".[dev]"     # install project + dev deps
uv run pytest                  # run test suite
uv run ruff check .            # lint
uv run uvicorn backend.main:app --reload   # run API
uv run streamlit run frontend/streamlit_app.py  # run dashboard
```

---

## Docker

```bash
cd docker
docker compose up --build
```

> Because the agent attaches to Chrome on your **host machine** via CDP,
> the backend container uses `network_mode: host` (Linux). On Docker
> Desktop (Mac/Windows), point `CHROME_REMOTE_DEBUG_PORT` at
> `host.docker.internal` in `.env` instead.

---

## Testing

```bash
uv run pytest -v
```

Includes unit tests for the DOM parser, code formatter, error analyzer, and
retry-routing logic, using mocked AI responses and mocked browser state (no
live Chrome or API keys required to run the suite).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No open tabs found` | Make sure Chrome was launched with `--remote-debugging-port=9222` and the problem page is open |
| `ElementNotFoundError` for editor/run button | The site's DOM changed — update `backend/config/selectors.py` with new selectors |
| `All configured free-tier LLM providers failed` | Check `GROQ_API_KEY`/`OPENROUTER_API_KEY` in `.env` and your rate limits |
| Retry loop stuck at max retries | Increase `MAX_RETRY_COUNT` in `.env`, or review the problem manually — some problems need a fundamentally different approach the agent isn't converging on |
| Paste doesn't clear old code | The Monaco selector may not be focusing correctly; verify `monaco_editor` selectors in `selectors.py` |

---

## Project layout

```
backend/
  agents/        # the 10 LangGraph agent nodes
  browser/       # Playwright manager + DOM parser
  schemas/       # Pydantic models (single source of truth for all agent I/O)
  memory/        # SQLite models + repository
  services/      # LiteLLM wrapper
  utils/         # rich logging
  langgraph/     # graph wiring (solve graph + test/retry graph)
  config/        # settings.py, selectors.py
  main.py        # FastAPI app
frontend/
  streamlit_app.py
database/        # SQLite file + Chroma persistence dir (gitignored)
tests/           # pytest suite
docker/          # Dockerfiles + compose
```

---

## Design notes / guardrails

- **Two distinct modes, two different guarantees.** The interactive dashboard
  flow (`solve_graph` / `test_and_retry_graph`) never calls `click_submit()`
  and always stops for manual review after pasting/running — this is the
  original practice/debugging workflow. **Batch Mode** (`autonomous_solve_graph`)
  is opt-in and fully autonomous: it solves, tests, retries, submits, and
  advances to the next problem with no pause. Only one batch can run at a
  time, since they share a single browser tab.
- **No paid LLM providers.** `llm_service.py` validates that only
  `groq/` and `openrouter/` prefixed models are used; anything else raises.
- **No hardcoded selectors in agent code** — all live in `config/selectors.py`
  with ordered fallback lists per site profile.

---

## License

MIT — see [LICENSE](LICENSE).
