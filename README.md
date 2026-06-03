# M&A Target Evaluation — Multi-Agent System

Apex Capital Partners ($2.5B AUM) multi-agent AI system for evaluating fintech M&A targets. Uses DeepSeek LLM-powered specialist agents with fan-out parallelism, architectural evaluation, and a Board-ready dashboard.

## Architecture

```
orchestrator
 ├── scout            → Screens 10 fintech targets against investment criteria
 ├── financial_analyst → Scores revenue growth, margins, valuation, cash runway
 ├── risk_analyst      → Assesses regulatory, tech, market, execution risk
 ├── strategy_analyst  → Evaluates portfolio fit, synergies, integration complexity
 └── report_writer    → Produces 1-page Board investment memo
```

**Strategies**: fan-out parallelism (analysts run in parallel per company), evaluator-optimizer feedback loop, file-based agent memory.

## Prerequisites

```bash
pip install openai
```

Set your DeepSeek API key in `.env`:

```
DEEPSEEK_API_KEY=sk-your-key-here
```

The system reads the key **only** from `.env` — environment variables are ignored.

## How to Run

### Phase 1 — Single-Agent Baseline
Deterministic benchmark (no LLM). One monolithic agent does everything.

```bash
python single_agent\baseline.py
python test_phase1.py          # validates the baseline
```

### Phase 2 — Multi-Agent Orchestrator
Real LLM-powered agents. Orchestrator fans out financial/risk/strategy analysts per company.

```bash
python multi_agent\orchestrator.py
```

### Phase 3 — Fan-Out Optimizer
Benchmarks sequential vs parallel execution. Measures speedup.

```bash
python multi_agent\fanout.py
```

### Phase 4 — Evaluator Agent
Meta-evaluates the entire architecture. Scores 1-10 on design, prompts, output quality, scalability.

```bash
python evaluator\evaluator.py
```

### Phase 5 — Improvement Loop
Evaluator feedback → LLM rewrites weak prompts → promotes to active → re-score → before/after delta.

```bash
python evaluator\improvement_loop.py
```

Note: Evaluator score is subjective (LLM judging LLM prompts). Real validation needs A/B testing of actual agent outputs. Original prompts backed up as `prompt_v1.md` — rename to restore.

### Phase 6 — Board Dashboard
Two modes available:

**Static HTML** (self-contained, no server):
```bash
python dashboard\generate_dashboard.py
start dashboard\index.html
```

**Interactive Server** (Flask, buttons trigger pipeline phases):
```bash
python dashboard\server.py
# Open http://localhost:5000
```

### Phase 7 — Log Analyzer
Parses all JSON logs across phases. Produces timing stats, score distributions, evaluator progression, improvement deltas, and cross-phase comparison.

```bash
python log_analyzer.py
```

Output: `logs/analysis_report.json` + printed summary.

### Phase 8 — Final Write-up
What broke, what you'd change, production-readiness verdict.

_TODO_

## Project Structure

```
Assignment 8/
  data/
    companies.json          # 10 simulated fintech targets
    apex_portfolio.json     # Apex Capital investment criteria + current portfolio
  single_agent/
    baseline.py             # Phase 1: monolithic benchmark
  test_phase1.py            # Phase 1 validation suite
  multi_agent/
    llm_client.py           # Shared DeepSeek client (reads .env only)
    orchestrator.py         # Phase 2: orchestrator + fan-out
    fanout.py              # Phase 3: sequential vs parallel benchmark
    agents/
      scout/prompt.md
      financial_analyst/prompt.md
      risk_analyst/prompt.md
      strategy_analyst/prompt.md
      report_writer/prompt.md
      */memory/             # Agent output storage (gitignored)
  evaluator/
    prompt.md               # Phase 4: evaluator agent prompt
    evaluator.py            # Phase 4: evaluator runner
    improvement_loop.py     # Phase 5: feedback → rewrite → promote → re-score
    scores.json             # Evaluation scores per iteration (gitignored)
  logs/                     # Execution logs (gitignored)
  dashboard/
    generate_dashboard.py   # Static HTML generator
    server.py              # Interactive Flask dashboard server
    index.html             # Generated static dashboard (gitignored)
```

## Logs

All runs produce timestamped JSON logs in `logs/`. Agents store intermediate outputs in their `memory/` folders.

## Benchmarks

| Phase | Strategy | Time |
|-------|----------|------|
| 1 | Single-agent (deterministic) | <1s |
| 2 | Multi-agent (LLM, fan-out analysis) | depends on API latency |
| 3 | Sequential vs Fan-out comparison | see `logs/run_3_fanout_benchmark.json` |
