# Final Write-Up: M&A Multi-Agent System

## What We Built

A multi-agent LLM system for Apex Capital Partners to evaluate fintech M&A targets. The system uses DeepSeek-powered specialist agents (scout, financial analyst, risk analyst, strategy analyst, report writer) coordinated by an orchestrator with fan-out parallelism. It includes an evaluator agent that scores the architecture 1-10, an improvement loop that rewrites weak prompts based on evaluator feedback, an interactive Board dashboard, and comprehensive logging.

**The business problem**: A mid-market PE firm needs to screen and evaluate 10 acquisition targets faster and more systematically than manual analyst work. The system ingests target data, screens against criteria, produces scored rankings with risk flags, and generates a Board-ready investment memo.

## Architecture Decision Log

| Decision | Rationale |
|----------|-----------|
| 5 specialist agents vs 1 monolithic | Clean separation of concerns; each prompt is focused and testable |
| File-based memory per agent | No database needed; audit trail preserved; simple to inspect |
| Fan-out via ThreadPoolExecutor | I/O-bound (API calls), so threads work well; 6 workers = good throughput |
| DeepSeek via OpenAI-compatible SDK | Cost-effective; JSON mode enforces structured outputs |
| `.env` only, no system env vars | Security requirement from stakeholder; manual parser avoids dependency |
| Evaluator-optimizer loop | Attempts to close feedback loop on prompt quality |

## What Worked

1. **Fan-out delivers real speedup.** Sequential analysis took 80s; fan-out took 19s. That's 4.15x faster with 6 workers — real parallelism on I/O-bound LLM calls. This is the clearest win of the entire project.

2. **Agent decomposition is logical.** Scout screens, then three analysts evaluate different dimensions (financial, risk, strategy), then a writer synthesizes. Each agent has a clear contract (JSON output schema). The separation makes debugging easy — if risk scores look wrong, you check the risk analyst prompt, not a monolith.

3. **Memory folders work.** Each agent writes its intermediate results to `memory/{company_id}.json`. You can literally open the folder and see what the financial analyst thought about PayFlow Solutions. This is invaluable for debugging and audit.

4. **The evaluator gives honest feedback.** It correctly identified that the improvement loop can't fix code-level issues (like missing retry logic), and that prompt rewriting alone has limits. Score started at 7.8/10 and ended at 8.7/10 after 6 iterations.

5. **The dashboard is functional.** The Flask server actually works — click a button, it runs the orchestrator, evaluator, or improvement loop. KPI cards update. Risk heatmap renders. The expandable company rows show detail. It's not "AI slop" — it's a real operational dashboard.

## What Broke

1. **The improvement loop is circular.** The evaluator (an LLM) judges the prompts (also LLM outputs) and suggests improvements. Another LLM rewrites the prompts. The evaluator re-evaluates and — surprise — gives a higher score. Is the prompt actually better, or is the evaluator just agreeing with itself? There's no ground truth. The score went from 7.8 to 8.7, but we can't prove the prompts improved. The "loop" is a well-intentioned demo with a fundamental epistemology problem.

2. **The evaluator keeps suggesting the same improvements.** Iterations 1-6 all flagged: (a) add retry logic to the API client, (b) harden the scout prompt, (c) standardize composite scoring. The first is a code change the loop can't make. The second and third keep getting rewritten but never truly resolve. The loop doesn't converge — it cycles.

3. **`prompt_v1.md` collision.** On the second loop run, the backup file already existed and `os.rename` crashed. Fixed by checking existence first, but it highlights that the loop wasn't designed for multiple iterations from the start.

4. **JSON-only mode blocked text responses.** The LLM client forced `response_format={"type": "json_object"}` for every call. When the improvement loop needed to rewrite a prompt (which is plain markdown text), the API rejected non-JSON responses. Fixed by adding an `expect_json` parameter, but this was a design oversight.

5. **Dashboard showed all zeros initially.** The report format from the LLM used `ranked_targets` but the dashboard JS read `ranked_companies`. Field name mismatch. Fixed by enriching the orchestrator's `save_report` to include computed scores alongside the LLM narrative.

6. **Notebook `exec()` failed on `__file__`.** The validation test used `__file__` which doesn't exist in Jupyter's `exec()` context. Fixed by adding a fallback to `os.getcwd()`.

7. **Windows encoding broke Unicode arrows.** `→` crashed on cp1252 terminal. Replaced with `->`.

## What I'd Change

1. **Ground the evaluator in real metrics.** Instead of an LLM judging LLMs, evaluate against: (a) agreement between analyst scores on the same company, (b) whether risk flags match the raw data, (c) latency and cost per run. Quantitative, not subjective.

2. **Make the improvement loop code-aware.** Some improvements (retry logic, rate limiting, error handling) require code changes. The loop should be able to suggest code patches, not just prompt rewrites. Or at minimum, route code-level feedback to a human-readable issue log.

3. **Add A/B testing for prompts.** Before promoting a rewritten prompt, run both versions against the same input and compare outputs. If the evaluator scores the new output higher, promote it. Without A/B, you're blind.

4. **Use async I/O instead of threads.** `asyncio` + `aiohttp` would scale better than `ThreadPoolExecutor` for 100+ API calls. Threads work fine for 18 concurrent calls but create overhead for larger fan-outs.

5. **Persist the dashboard state.** Currently each page refresh re-reads from disk. Store results in a lightweight DB (SQLite) so the dashboard has history, filtering, and comparison views.

6. **Better error propagation.** If one analyst fails, the orchestrator currently logs "analyst_error" and skips that company. It should retry, fall back to a deterministic heuristic, or at minimum flag it prominently in the Board memo.

## Did I Get Completely Confused?

Yes, twice:

1. **Phase 3 scope confusion.** Originally built evaluator and dashboard for Phase 3 when the plan called it "Fan-Out Optimizer." Had to reset, delete files, and rebuild correctly. Lesson: the phase plan is the contract. Don't skip ahead.

2. **The improvement loop's philosophical problem.** Spent time building prompt rewriting infrastructure before realizing: if an LLM evaluates an LLM's prompt, and another LLM rewrites it, and the same evaluating LLM re-scores it — what are we actually measuring? The architecture is sound but the measurement is circular. This is the kind of confusion that only becomes clear after you build it.

## Would I Put This Into Enterprise Production?

**No — but parts of it, yes.**

### What could go to production:
- **The agent decomposition pattern** (orchestrator + specialists) is solid. With real analysts writing the prompts and a domain expert calibrating the scoring, this is how many financial services AI systems work.
- **The fan-out parallelism** is production-grade. Add async I/O, rate limiting, and exponential backoff, and it scales.
- **The file-based memory and logging** is good for audit trails. In production you'd swap it for a proper database, but the pattern is right.

### What can't go to production:
- **No error handling for API failures.** If DeepSeek is down or rate-limited, the entire pipeline silently fails. Production systems need retry with backoff, circuit breakers, and fallbacks.
- **No security.** The `.env` file approach is fine for a prototype but a production system needs secrets management (Vault, AWS Secrets Manager). There's also no authentication on the dashboard server — anyone on the network can trigger expensive LLM calls.
- **No data validation.** The orchestrator trusts the LLM output format blindly. If the scout returns a malformed JSON or missing fields, it crashes. Production needs schema validation at every agent boundary.
- **The evaluator-optimizer loop is a demo, not a process.** Real improvement loops need: A/B testing, ground truth benchmarks, human review checkpoints, and versioned prompt artifacts. An LLM judging LLMs is not governance.
- **No cost tracking.** Each run costs money (DeepSeek API calls). The system doesn't track token usage or cost per evaluation. A Board would want to know: "what did this analysis cost us?"

### Bottom line:
This is a strong prototype that demonstrates the architectural patterns correctly. The agent decomposition, fan-out strategy, and dashboard would carry over to production. But you'd need 2-3 more sprints of hardening (error handling, security, validation, cost tracking) before putting real money behind its recommendations. The core insight — that specialist LLM agents with parallel execution can meaningfully accelerate analyst workflows — is valid and valuable.

## Key Metrics Summary

| Metric | Value |
|--------|-------|
| Targets evaluated | 10 |
| Passed screening (multi-agent) | 6 |
| Fan-out speedup | 4.15x (75.9% reduction) |
| Architecture score (initial) | 7.8/10 |
| Architecture score (after improvement) | 8.7/10 |
| Improvement loop delta | +0.9 |
| Improvement loop iterations | 6 |
| Production readiness | ALMOST (per evaluator) |
| Single-agent baseline time | <1s (deterministic, no LLM) |
| Multi-agent run time | ~39s (LLM-powered) |
